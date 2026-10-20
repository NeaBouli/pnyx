"""
MOD-19: Newsletter Integration (Listmonk + Brevo)
POST /api/v1/newsletter/subscribe  — Public signup
GET  /api/v1/newsletter/lists      — Public list of available lists
GET  /api/v1/newsletter/stats      — Public transparency (Brevo account stats)
POST /api/v1/newsletter/webhook/brevo — Brevo event webhook
"""
import os
import json
import logging
import secrets
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlencode
from rate_limit import limiter
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, EmailStr
import httpx
import redis.asyncio as aioredis

from ip_utils import hashed_rate_subject, rate_limit_key_for_ip, redis_fixed_window_limit
from dependencies import verify_admin_key
from services import newsletter_service
from services.mail_policy import operator_reply_to
from services.newsletter_consent import (
    CONFIRMED_KEY, CONFIRM_ONCE, CONSENT_SCHEMA, confirmation_payload,
    SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY, BREVO_REMOVE_RETRY_KEY,
    LISTMONK_REMOVE_RETRY_KEY, WITHDRAW_CONSENT,
    BREVO_ADD_UNSETTLED_KEY, QUEUE_BREVO_ADD, QUEUE_DELIVERY_REMOVAL,
    LISTMONK_ADD_UNSETTLED_KEY, QUEUE_LISTMONK_ADD,
    delivery_eligible, parse_consent,
)

logger = logging.getLogger(__name__)

class NewsletterRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def sanitized_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid newsletter request") from None

        return sanitized_handler


router = APIRouter(prefix="/api/v1/newsletter", tags=["MOD-19 Newsletter"], route_class=NewsletterRoute)

# ── Config ────────────────────────────────────────────────────────────────────

LISTMONK_URL = os.getenv("LISTMONK_URL", "http://172.18.0.7:9000")
LISTMONK_USER = os.getenv("LISTMONK_ADMIN_USER", "admin")
LISTMONK_PW = os.getenv("LISTMONK_ADMIN_PASSWORD", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
# EKA-09: shared bearer token required on the Brevo event webhook.
BREVO_WEBHOOK_TOKEN = os.getenv("BREVO_WEBHOOK_TOKEN", "")

# List ID mapping (from Listmonk)
LIST_IDS = {
    "citizens": 3,
    "press": 4,
    "parties": 5,
    "public_bodies": 6,
    "ngos": 7,
    "government": 8,
}

VALID_FREQUENCIES = {"weekly", "monthly"}
VALID_LANGUAGES = {"el", "en"}
VALID_TYPES = set(LIST_IDS.keys())

# EKA-04: fixed-window limits on attempted confirmation emails
SUBSCRIBE_IP_LIMIT = 10
SUBSCRIBE_IP_WINDOW_SECONDS = 3600
SUBSCRIBE_EMAIL_LIMIT = 3
SUBSCRIBE_EMAIL_WINDOW_SECONDS = 86400
EMAIL_RATE_NAMESPACE = "newsletter:subscribe:email"


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    subscriber_type: str = "citizens"
    frequency: str = "weekly"
    language: str = "el"
    topic_new_proposals: bool = False
    topic_active_votes: bool = True
    topic_vote_results: bool = True
    topic_system_news: bool = False
    topic_breaking_news: bool = False


class UnsubscribeRequest(BaseModel):
    email: EmailStr


# ── Listmonk API helper ──────────────────────────────────────────────────────

async def _listmonk_request(method: str, path: str, json_data: dict = None) -> dict:
    if not LISTMONK_PW:
        if method in ("POST", "PUT"):
            raise newsletter_service.ContactNotWritten()
        raise HTTPException(status_code=503, detail="Newsletter system not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.request(
            method,
            f"{LISTMONK_URL}{path}",
            json=json_data,
            auth=(LISTMONK_USER, LISTMONK_PW),
        )
        if r.status_code >= 300:
            # EKA-16: status code only — the provider body may echo the subscriber email.
            logger.error("[MOD-19] Listmonk request failed: status=%s", r.status_code)
            if method in ("POST", "PUT") and r.status_code < 500:
                raise newsletter_service.ContactNotWritten()
            raise HTTPException(502, "Newsletter provider request failed")
        return r.json()


async def _remove_listmonk_contact(email: str, *, require_present: bool = False) -> bool:
    # Keep the blocklist query in the body. Listmonk accepts a SQL expression;
    # quotes inside the literal are escaped.
    literal = email.replace("'", "''")
    query = f"lower(subscribers.email) = lower('{literal}')"
    if require_present:
        # A successful bulk blocklist also returns true when nothing matched.
        # Lookup URLs are redacted by the newsletter transport log filter.
        result = await _listmonk_request("GET", "/api/subscribers?" + urlencode({"query": query}))
        if not any(isinstance(contact, dict) and isinstance(contact.get("email"), str)
                   and contact["email"].casefold() == email.casefold()
                   for contact in result.get("data", {}).get("results", [])):
            return False
    result = await _listmonk_request("PUT", "/api/subscribers/query/blocklist", {
        "query": query,
    })
    return result.get("data") is True


async def _retry_withdrawal(store: aioredis.Redis, email: str) -> bool:
    success = True
    for key, unsettled_key, remove in (
        (BREVO_REMOVE_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY, newsletter_service.remove_contact),
        (LISTMONK_REMOVE_RETRY_KEY, LISTMONK_ADD_UNSETTLED_KEY, _remove_listmonk_contact),
    ):
        if not await store.hget(key, email):
            continue
        try:
            unsettled = await store.hget(unsettled_key, email.casefold())
            removed = (await remove(email, require_present=True) if unsettled == "uncertain"
                       else await remove(email))
            # An absent contact is not evidence that an in-flight write settled.
            if removed and unsettled != "pending":
                if unsettled:
                    await store.hdel(unsettled_key, email.casefold())
                await store.hdel(key, email)
            else:
                success = False
        except Exception:
            success = False
    if not success:
        logger.error("[MOD-19] Newsletter withdrawal delivery failed; retry retained")
    return success


async def _remove_ineligible_contact(store: aioredis.Redis, email: str) -> bool:
    await store.eval(
        QUEUE_DELIVERY_REMOVAL, 3, BREVO_ADD_RETRY_KEY, BREVO_REMOVE_RETRY_KEY,
        LISTMONK_REMOVE_RETRY_KEY, email, "1" if LISTMONK_PW else "0",
    )
    return await _retry_withdrawal(store, email)


async def _withdraw_subscription(store: aioredis.Redis, email: str, reason: str) -> bool:
    # Provider events can change casing; preserve stored consent identities while
    # matching the provider's case-insensitive contact identity.
    identities = {email}
    identities.update(field for field in await store.hkeys(CONFIRMED_KEY) if field.casefold() == email.casefold())
    for identity in identities:
        await store.eval(
            WITHDRAW_CONSENT, 5, CONFIRMED_KEY, SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY,
            BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY,
            identity, reason, "1" if LISTMONK_PW else "0", email.casefold(),
        )
    success = True
    for identity in identities:
        if not await _retry_withdrawal(store, identity):
            success = False
    return success


async def _sync_brevo_contact(store: aioredis.Redis, email: str, name: str = "") -> bool:
    """Queue before delivery; a concurrent withdrawal always wins over an add."""
    try:
        if await store.hget(SUPPRESSED_KEY, email.casefold()):
            await _withdraw_subscription(store, email, "suppressed")
            return False
        raw = await store.hget(CONFIRMED_KEY, email)
        data = parse_consent(email, raw)
        if data is None or not delivery_eligible(data, datetime.now(timezone.utc)):
            await _remove_ineligible_contact(store, email)
            return False
        queued = await store.eval(
            QUEUE_BREVO_ADD, 5, CONFIRMED_KEY, SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY,
            BREVO_REMOVE_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY, email, raw, email.casefold(),
        )
        if queued != 1:
            return False
        not_written = False
        try:
            added = await newsletter_service.add_contact(email, name)
        except newsletter_service.ContactSuppressed:
            await store.hdel(BREVO_ADD_UNSETTLED_KEY, email.casefold())
            await _withdraw_subscription(store, email, "provider_suppressed")
            return False
        except (newsletter_service.ContactNotWritten, httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            # No write can still arrive: release serialization and retain retry work.
            not_written = True
            added = False
        except Exception:
            added = False  # Even a timed-out write can have reached the provider.
        if added or not_written:
            await store.hdel(BREVO_ADD_UNSETTLED_KEY, email.casefold())
        else:
            await store.hset(BREVO_ADD_UNSETTLED_KEY, email.casefold(), "uncertain")
        # A withdrawal may have happened while the provider request was in flight.
        if await store.hget(SUPPRESSED_KEY, email.casefold()):
            await _withdraw_subscription(store, email, "suppressed")
            return False
        if added:
            await store.hdel(BREVO_ADD_RETRY_KEY, email)
            return True
    except Exception:
        pass
    logger.error("[MOD-19] Brevo contact sync failed; confirmed consent retained for retry")
    return False


async def _sync_listmonk_contact(store: aioredis.Redis, email: str) -> bool:
    """Retain removal work until even a timed-out creation has been reconciled."""
    try:
        if await store.hget(SUPPRESSED_KEY, email.casefold()):
            await _withdraw_subscription(store, email, "suppressed")
            return False
        raw = await store.hget(CONFIRMED_KEY, email)
        data = parse_consent(email, raw)
        if data is None or not delivery_eligible(data, datetime.now(timezone.utc)):
            await _remove_ineligible_contact(store, email)
            return False
        queued = await store.eval(
            QUEUE_LISTMONK_ADD, 4, CONFIRMED_KEY, SUPPRESSED_KEY,
            LISTMONK_REMOVE_RETRY_KEY, LISTMONK_ADD_UNSETTLED_KEY, email, raw, email.casefold(),
        )
        if queued != 1:
            return False
        try:
            await _listmonk_request("POST", "/api/subscribers", {
                "email": email, "name": data.get("name", ""),
                "status": "enabled", "preconfirm_subscriptions": True,
                "attribs": data.get("topics", {}),
            })
        except (newsletter_service.ContactNotWritten, httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            await store.hdel(LISTMONK_ADD_UNSETTLED_KEY, email.casefold())
            raise
        except Exception:
            await store.hset(LISTMONK_ADD_UNSETTLED_KEY, email.casefold(), "uncertain")
            raise
        else:
            await store.hdel(LISTMONK_ADD_UNSETTLED_KEY, email.casefold())
        finally:
            if await store.hget(SUPPRESSED_KEY, email.casefold()):
                await _withdraw_subscription(store, email, "suppressed")
        return not await store.hget(SUPPRESSED_KEY, email.casefold())
    except Exception:
        logger.error("[MOD-19] Listmonk contact sync failed; reconciliation retained")
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lists")
async def get_lists() -> dict:
    """Public: available newsletter lists."""
    return {
        "lists": [
            {"id": "citizens", "name_el": "Πολίτες", "name_en": "Citizens"},
            {"id": "press", "name_el": "Τύπος", "name_en": "Press"},
            {"id": "parties", "name_el": "Κόμματα", "name_en": "Parties"},
            {"id": "public_bodies", "name_el": "Δημόσιοι Φορείς", "name_en": "Public Bodies"},
            {"id": "ngos", "name_el": "ΜΚΟ / Σύλλογοι", "name_en": "NGOs"},
            {"id": "government", "name_el": "Κυβέρνηση", "name_en": "Government"},
        ]
    }


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, request: Request) -> dict:
    """
    Public: subscribe to newsletter.
    Sends double opt-in email via Brevo. Stores pending token in Redis.
    Subscriber only activated after clicking confirmation link.
    """
    if req.subscriber_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {VALID_TYPES}")
    if req.frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Frequency must be 'weekly' or 'monthly'")
    if req.language not in VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be 'el' or 'en'")

    r = await _get_redis()

    # Check if already confirmed — must not consume rate-limit counters or resend
    existing = await r.hget("newsletter:confirmed", req.email)
    if existing:
        return {"success": True, "message": "Already subscribed."}

    # EKA-04: rate-limit attempted confirmation emails before any token write
    # or provider request. Keys hold only truncated HMAC identifiers.
    normalized_email = req.email.strip().lower()
    bucket_day = date.today()
    email_ref = hashed_rate_subject(
        normalized_email,
        EMAIL_RATE_NAMESPACE,
        today=bucket_day,
    )
    await redis_fixed_window_limit(
        r,
        rate_limit_key_for_ip(
            request,
            "newsletter:subscribe:ip",
            today=bucket_day,
        ),
        SUBSCRIBE_IP_LIMIT,
        SUBSCRIBE_IP_WINDOW_SECONDS,
    )
    await redis_fixed_window_limit(
        r,
        f"ratelimit:{EMAIL_RATE_NAMESPACE}:{bucket_day.isoformat()}:{email_ref}",
        SUBSCRIBE_EMAIL_LIMIT,
        SUBSCRIBE_EMAIL_WINDOW_SECONDS,
    )

    # Generate confirmation token
    token = secrets.token_urlsafe(32)
    sub_data = json.dumps({
        "consent_schema": CONSENT_SCHEMA,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "email": req.email,
        "name": req.name or "",
        "subscriber_type": req.subscriber_type,
        "frequency": req.frequency,
        "language": req.language,
        "topics": {
            "new_proposals": req.topic_new_proposals,
            "active_votes": req.topic_active_votes,
            "vote_results": req.topic_vote_results,
            "system_news": req.topic_system_news,
            "breaking_news": req.topic_breaking_news,
        },
    })

    # Store pending subscription (expires in 24h)
    await r.setex(f"newsletter:pending:{token}", 86400, sub_data)

    # Send confirmation email via Brevo
    confirm_url = f"https://api.ekklesia.gr/api/v1/newsletter/confirm/{token}"

    if req.language == "en":
        subject = "Confirm your subscription — ekklesia Newsletter"
        body = f'<div style="background:#f8fafc;padding:2rem 1rem;font-family:Segoe UI,sans-serif"><div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;border-top:4px solid #2563eb;padding:2rem;text-align:center"><img src="https://ekklesia.gr/pnx.png" width="60"/><h2 style="color:#2563eb">Confirm Subscription</h2><p style="color:#1e293b">Click the button below to confirm your newsletter subscription.</p><a href="{confirm_url}" style="display:inline-block;padding:0.75rem 2rem;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:700;margin:1rem 0">Confirm →</a><p style="color:#94a3b8;font-size:12px">If you did not request this, ignore this email.</p></div></div>'
    else:
        subject = "Επιβεβαίωση εγγραφής — ekklesia Newsletter"
        body = f'<div style="background:#f8fafc;padding:2rem 1rem;font-family:Segoe UI,sans-serif"><div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;border-top:4px solid #2563eb;padding:2rem;text-align:center"><img src="https://ekklesia.gr/pnx.png" width="60"/><h2 style="color:#2563eb">Επιβεβαίωση Εγγραφής</h2><p style="color:#1e293b">Πατήστε το κουμπί για να επιβεβαιώσετε την εγγραφή σας στο newsletter.</p><a href="{confirm_url}" style="display:inline-block;padding:0.75rem 2rem;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:700;margin:1rem 0">Επιβεβαίωση →</a><p style="color:#94a3b8;font-size:12px">Αν δεν ζητήσατε αυτό, αγνοήστε αυτό το email.</p></div></div>'

    if not BREVO_API_KEY:
        raise HTTPException(status_code=503, detail="Email service not configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://api.brevo.com/v3/smtp/email", headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
            }, json={
                "sender": {"name": "ekklesia Newsletter", "email": "newsletter@ekklesia.gr"},
                "to": [{"email": req.email}],
                "replyTo": operator_reply_to(),
                "subject": subject,
                "htmlContent": body,
            })
            if resp.status_code >= 400:
                # EKA-16: status code only — the provider body may echo the subscriber email.
                logger.error(f"[MOD-19] Brevo send failed: {resp.status_code}")
                raise HTTPException(status_code=502, detail="Email send failed")
    except httpx.HTTPError:
        logger.error("[MOD-19] Brevo confirmation email request failed")
        raise HTTPException(status_code=502, detail="Email service error")

    logger.info("[MOD-19] Opt-in email sent ref=emailref:%s", email_ref[:12])
    return {"success": True, "message": "Confirmation email sent. Please check your inbox."}


@router.get("/confirm/{token}")
@limiter.shared_limit("10/minute", scope="newsletter:confirm_subscription")
async def confirm_subscription(token: str, request: Request = None) -> HTMLResponse:
    """Confirm newsletter subscription via token from email link."""
    r = await _get_redis()
    raw = await r.get(f"newsletter:pending:{token}")

    if not raw:
        return HTMLResponse(
            '<div style="text-align:center;padding:3rem;font-family:sans-serif"><h2>Link abgelaufen</h2><p>Bitte registrieren Sie sich erneut auf ekklesia.gr</p></div>',
            status_code=410
        )

    data = json.loads(raw)
    email = data["email"]

    confirmed_at = datetime.now(timezone.utc)
    confirmed_raw = confirmation_payload(data, confirmed_at)
    result = await r.eval(
        CONFIRM_ONCE, 2, f"newsletter:pending:{token}", CONFIRMED_KEY,
        raw, email, confirmed_raw,
    )
    if result == 0:
        return HTMLResponse("Confirmation link expired or already used.", status_code=410)
    if result not in (1, 2):
        raise HTTPException(503, "Confirmation could not be verified")

    if result == 1:
        try:
            # All delivery checks are optional after consent has been saved.
            if await r.hget(SUPPRESSED_KEY, email.casefold()):
                await _withdraw_subscription(r, email, "suppressed")
            elif not delivery_eligible(json.loads(confirmed_raw), confirmed_at):
                await _remove_ineligible_contact(r, email)
            else:
                synced = await _sync_brevo_contact(r, email, data.get("name", ""))
                if LISTMONK_PW and synced:
                    await _sync_listmonk_contact(r, email)
        except Exception:
            logger.error("[MOD-19] Confirmation delivery deferred; consent retained")

    logger.info("[MOD-19] Confirmation processed (new=%s)", result == 1)
    message = (
        "Ευχαριστούμε! Η διεύθυνση email επιβεβαιώθηκε και οι προτιμήσεις σας καταγράφηκαν."
        if result == 1 else
        "Η εγγραφή σας ήταν ήδη επιβεβαιωμένη. Οι προηγούμενες προτιμήσεις σας παραμένουν αμετάβλητες."
    )

    return HTMLResponse(
        '<div style="text-align:center;padding:3rem;font-family:sans-serif">'
        '<img src="https://ekklesia.gr/pnx.png" width="60"/>'
        '<h2 style="color:#2563eb">Εγγραφή Επιβεβαιώθηκε!</h2>'
        f'<p>{message}</p>'
        '<a href="https://ekklesia.gr" style="color:#2563eb">← Επιστροφή στο ekklesia.gr</a>'
        '</div>'
    )


@router.post("/unsubscribe")
async def unsubscribe(
    req: UnsubscribeRequest, _auth: bool = Depends(verify_admin_key),
) -> dict:
    """Operator-recorded withdrawal; public Brevo withdrawals arrive via its webhook."""
    try:
        store = await _get_redis()
        await _withdraw_subscription(store, req.email, "unsubscribed")
    except Exception:
        logger.error("[MOD-19] Newsletter withdrawal persistence failed")
        raise HTTPException(503, "Withdrawal could not be persisted; retry") from None
    return {"success": True, "message": "Unsubscribed."}


# ── Redis for stats caching ───────────────────────────────────────────────────

_nl_redis: aioredis.Redis | None = None

async def _get_redis() -> aioredis.Redis:
    global _nl_redis
    if _nl_redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _nl_redis = aioredis.from_url(url, decode_responses=True)
    return _nl_redis


# ── Stats Endpoint (Brevo + Listmonk) ────────────────────────────────────────

@router.get("/stats")
async def newsletter_stats() -> dict:
    """
    Public transparency endpoint.
    Fetches Brevo account stats + Listmonk subscriber count.
    Cached in Redis for 60 minutes.
    """
    r = await _get_redis()
    cached = await r.get("newsletter:stats_cache")
    if cached:
        return json.loads(cached)

    stats = {
        "plan": "free",
        "emails_sent_month": 0,
        "daily_limit": 300,
        "monthly_limit": 9000,
        "subscribers": 0,
        "open_rate": 0,
        "monthly_cost_eur": 0,
        "status": "ok",
    }

    # Fetch from Brevo API
    if BREVO_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Account info
                acct = await client.get(
                    "https://api.brevo.com/v3/account",
                    headers={"api-key": BREVO_API_KEY},
                )
                if acct.status_code == 200:
                    data = acct.json()
                    plan_list = data.get("plan", [])
                    if plan_list:
                        p = plan_list[0]
                        plan_type = p.get("type", "free")
                        stats["plan"] = plan_type
                        stats["daily_limit"] = p.get("credits", 300)
                        stats["monthly_limit"] = p.get("credits", 300) * 30

                # Email stats this month
                smtp_stats = await client.get(
                    "https://api.brevo.com/v3/smtp/statistics/aggregatedReport",
                    headers={"api-key": BREVO_API_KEY},
                )
                if smtp_stats.status_code == 200:
                    sd = smtp_stats.json()
                    stats["emails_sent_month"] = sd.get("requests", 0)
                    delivered = sd.get("delivered", 0)
                    opened = sd.get("uniqueOpens", 0)
                    if delivered > 0:
                        stats["open_rate"] = round((opened / delivered) * 100, 1)
        except Exception as e:
            logger.error(f"[MOD-19] Brevo API error: {e}")

    # Fetch subscriber count from Redis confirmed + Listmonk
    redis_count = await r.hlen("newsletter:confirmed")
    listmonk_count = 0
    if LISTMONK_PW:
        try:
            result = await _listmonk_request("GET", "/api/subscribers?per_page=1&page=1")
            if "data" in result:
                listmonk_count = result["data"].get("total", 0)
        except Exception:
            pass
    stats["subscribers"] = max(redis_count, listmonk_count)

    # Ampel logic
    usage_pct = (stats["emails_sent_month"] / max(stats["monthly_limit"], 1)) * 100
    if stats["plan"] != "free" or stats["monthly_cost_eur"] > 0:
        stats["status"] = "paid"
    elif usage_pct > 80:
        stats["status"] = "warning"
    else:
        stats["status"] = "ok"

    stats["usage_percent"] = round(usage_pct, 1)

    # Cache for 60 minutes
    await r.setex("newsletter:stats_cache", 3600, json.dumps(stats))

    return stats


# ── Brevo Webhook ─────────────────────────────────────────────────────────────

def _require_brevo_webhook_auth(request: Request) -> None:
    """EKA-09: authenticate the Brevo webhook before any body parsing or Redis I/O.

    Requires ``Authorization: Bearer <BREVO_WEBHOOK_TOKEN>``. Fails closed with
    503 when the server token is not configured, and 401 with a Bearer
    challenge for missing, malformed or wrong credentials. Token material is
    never logged or returned.
    """
    if not BREVO_WEBHOOK_TOKEN:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    authorization = request.headers.get("authorization", "")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        matched = secrets.compare_digest(parts[1], BREVO_WEBHOOK_TOKEN)
    except TypeError:
        # Non-ASCII presented token cannot match; reject without a 500.
        matched = False
    if not matched:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/webhook/brevo")
async def brevo_webhook(request: Request) -> dict:
    """Receive Brevo event webhooks — track sent/opened/bounced."""
    _require_brevo_webhook_auth(request)
    try:
        events = await request.json()
        if not isinstance(events, list):
            events = [events]

        r = await _get_redis()
        # Persist every withdrawal before optional counters/cache work. A batch
        # must not lose later withdrawals because an earlier counter failed.
        for event in events:
            evt = event.get("event", "")
            # Marketing campaigns and transactional mail use different spellings.
            evt = {"unsubscribe": "unsubscribed", "hard_bounce": "hardBounce",
                   "soft_bounce": "softBounce"}.get(evt, evt)
            if evt in ("unsubscribed", "hardBounce", "spam", "complaint") and event.get("email"):
                # Validate without ever returning/logging provider payloads or validation errors.
                email = str(UnsubscribeRequest(email=event["email"]).email)
                await _withdraw_subscription(r, email, evt)

    except Exception:
        logger.error("[MOD-19] Brevo webhook withdrawal persistence failed")
        # Brevo discards 5xx responses; 429 is its retryable HTTP status.
        raise HTTPException(429, "Webhook processing deferred; retry", headers={"Retry-After": "600"}) from None

    try:
        for event in events:
            evt = {"unsubscribe": "unsubscribed", "hard_bounce": "hardBounce",
                   "soft_bounce": "softBounce"}.get(event.get("event", ""), event.get("event", ""))
            if evt in ("sent", "delivered", "opened", "clicked", "unsubscribed", "hardBounce", "softBounce"):
                await r.hincrby("newsletter:events", evt, 1)

        # Invalidate stats cache on activity
        await r.delete("newsletter:stats_cache")

    except Exception:
        logger.error("[MOD-19] Brevo webhook statistics update failed")
    return {"received": True, "events": len(events)}

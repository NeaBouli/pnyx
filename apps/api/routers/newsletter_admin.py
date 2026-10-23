"""
Newsletter Admin — Brevo Campaign Draft/Preview/Send
Admin-only. No subscriber emails returned.
NEA-263: Cross-publish to Telegram after successful send.
"""
import re
import os
import html
import logging
import asyncio
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote

import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr, field_validator

from dependencies import verify_admin_key
from services.mail_policy import OPERATOR_EMAIL
from services.newsletter_lock import newsletter_lock, NewsletterLockUnavailable
from services.telegram_community import _send as tg_send, TOPICS
from services.newsletter_consent import (
    CONFIRMED_KEY, MAX_READINESS_CONTACTS, READ_CONSENT_SNAPSHOT,
    classify_contact, parse_consent, readiness_summary,
    SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY, BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY,
    BREVO_ADD_UNSETTLED_KEY, delivery_eligible, has_doi_evidence,
    TOPICS as NEWSLETTER_TOPICS, UPDATE_PREFERENCES, preference_attributes,
)
from services.newsletter_audience import (
    CampaignPlan, AudienceUnavailable, campaign_plan,
    audit_audience, prepare_audience, authorize_dispatch, log_audience,
)
from services.newsletter_dispatch import temporary_campaign_list
from services import newsletter_service
from routers.newsletter import NewsletterRoute

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/newsletter", tags=["Admin Newsletter"], route_class=NewsletterRoute)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API = "https://api.brevo.com/v3"
SENDER = {"name": "εκκλησία", "email": "newsletter@ekklesia.gr"}
LIST_ID = newsletter_service.LIST_ID
READINESS_TIMEOUT_SECONDS = 25
LIST_SERVICE_READINESS_TIMEOUT_SECONDS = 5.0


class _ContactRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx INFO request logs otherwise expose email identifiers in GET URLs.
        return "https://api.brevo.com/v3/contacts/" not in record.getMessage()


logging.getLogger("httpx").addFilter(_ContactRequestLogFilter())


def _sanitize_html(raw: str) -> str:
    """Minimal sanitization — strip script tags, event handlers, javascript: URLs."""
    raw = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"\bon\w+\s*=\s*[\"'][^\"']*[\"']", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"javascript:", "", raw, flags=re.IGNORECASE)
    return raw


async def _brevo_request(method: str, endpoint: str, data: dict | None = None) -> dict:
    if not BREVO_API_KEY:
        raise HTTPException(503, "Newsletter provider unavailable; retry")
    if method not in {"POST", "GET", "PUT"}:
        raise HTTPException(400, "Unsupported newsletter operation")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(
                method, f"{BREVO_API}/{endpoint}",
                headers={"api-key": BREVO_API_KEY}, json=data,
            )
        if not 200 <= response.status_code < 300:
            if endpoint.endswith("/sendNow") and 400 <= response.status_code < 500:
                raise newsletter_service.CampaignNotSent()
            raise ValueError()
        result = response.json() if response.text else {}
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except newsletter_service.CampaignNotSent:
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        if endpoint.endswith("/sendNow"):
            raise newsletter_service.CampaignNotSent() from None
        raise HTTPException(503, "Newsletter provider unavailable; retry") from None
    except Exception:
        logger.warning("[NEWSLETTER] Provider request unavailable")
        raise HTTPException(503, "Newsletter provider unavailable; retry") from None


# ─── Templates ───────────────────────────────────────────────────────────────

from services.newsletter_service import _HEADER, _FOOTER, _wrap


# ─── Schemas ─────────────────────────────────────────────────────────────────

class DraftRequest(CampaignPlan):
    subject: str = Field(..., min_length=3, max_length=200)
    html_content: str = Field(..., min_length=10)
    name: str = Field(None, max_length=100, description="Campaign name (optional, auto-generated if empty)")


class SendRequest(BaseModel):
    campaign_id: int
    confirm: bool = Field(..., description="Must be true to send")


class PreviewRequest(BaseModel):
    subject: str
    html_content: str


class PreferencesRequest(BaseModel):
    email: EmailStr
    language: Literal["el", "en"]
    frequency: Literal["monthly", "weekly"]
    topics: dict[str, bool]

    @field_validator("topics", mode="before")
    @classmethod
    def validate_topics(cls, value: Any) -> dict[str, bool]:
        if (not isinstance(value, dict) or set(value) != NEWSLETTER_TOPICS
                or any(type(enabled) is not bool for enabled in value.values())):
            raise ValueError("Invalid newsletter preferences")
        return value


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/audience")
async def newsletter_audience(req: CampaignPlan, _auth: bool = Depends(verify_admin_key)) -> dict[str, str | int]:
    """Read-only audience estimate for a plan; no provider or Redis writes."""
    from routers.newsletter import _get_redis
    try:
        store = await _get_redis()
        audience = await audit_audience(store, req)
        log_audience("ready", audience.counts)
        return {"reason": "ready", **audience.counts}
    except AudienceUnavailable as exc:
        log_audience(exc.reason, exc.counts)
        raise HTTPException(503, exc.detail) from None
    except Exception:
        error = AudienceUnavailable()
        log_audience(error.reason, error.counts)
        raise HTTPException(503, error.detail) from None


@router.put("/preferences")
async def newsletter_preferences(req: PreferencesRequest, _auth: bool = Depends(verify_admin_key)) -> dict[str, int]:
    """Operator update of existing DOI consent; suppression and evidence are preserved."""
    from routers.newsletter import _get_redis, _sync_brevo_contact, _remove_ineligible_contact
    try:
        store = await _get_redis()
        async with newsletter_lock(store):
            aliases = [email for email in await store.hkeys(CONFIRMED_KEY) if email.casefold() == req.email.casefold()]
            if len(aliases) != 1:
                return {"updated": 0, "synced": 0, "failed": 1}
            email = aliases[0]
            raw = await store.hget(CONFIRMED_KEY, email)
            data = parse_consent(email, raw)
            if data is None or not has_doi_evidence(data, datetime.now(timezone.utc)) or data.get("consent_state"):
                return {"updated": 0, "synced": 0, "failed": 1}
            data.update(language=req.language, frequency=req.frequency, topics=req.topics)
            updated = await store.eval(UPDATE_PREFERENCES, 3, CONFIRMED_KEY, SUPPRESSED_KEY,
                                       BREVO_ADD_RETRY_KEY, email, email.casefold(), raw, json.dumps(data))
            if updated != 1:
                return {"updated": 0, "synced": 0, "failed": 1}
            synced = (await _sync_brevo_contact(store, email, data.get("name", ""))
                      if any(req.topics.values()) else await _remove_ineligible_contact(store, email))
            return {"updated": 1, "synced": int(synced), "failed": int(not synced)}
    except Exception:
        raise HTTPException(503, "Newsletter preferences unavailable; retry") from None


@router.post("/reconfirm")
async def newsletter_reconfirm(
    dry_run: bool = True, resend: bool = False, _auth: bool = Depends(verify_admin_key),
) -> dict[str, int]:
    from routers.newsletter import reconfirm_legacy
    try:
        return await reconfirm_legacy(dry_run=dry_run, resend=resend)
    except Exception:
        logger.error("[NEWSLETTER] Reconfirmation unavailable; retry retained")
        raise HTTPException(503, "Newsletter reconfirmation unavailable; retry") from None


@router.post("/reconfirm/expire")
async def newsletter_reconfirm_expire(
    dry_run: bool = True, _auth: bool = Depends(verify_admin_key),
) -> dict[str, int]:
    from routers.newsletter import expire_reconfirmations
    try:
        return await expire_reconfirmations(dry_run=dry_run)
    except Exception:
        logger.error("[NEWSLETTER] Reconfirmation expiry unavailable; retry retained")
        raise HTTPException(503, "Newsletter reconfirmation unavailable; retry") from None


@router.post("/backfill")
async def newsletter_backfill(dry_run: bool = True, _auth: bool = Depends(verify_admin_key)) -> dict:
    """Reconcile confirmed consent only. Default to provider reads and aggregate counts."""
    from routers.newsletter import (
        _get_redis, _retry_withdrawal, _sync_brevo_contact,
        _remove_ineligible_contact, _withdraw_subscription,
    )

    counts = {"to_add": 0, "already_present": 0, "held": 0, "failed": 0}
    try:
        store = await _get_redis()
        withdrawals = set()
        if not dry_run:
            withdrawals.update(await store.hkeys(BREVO_REMOVE_RETRY_KEY))
            withdrawals.update(await store.hkeys(LISTMONK_REMOVE_RETRY_KEY))
        confirmed = await store.hgetall(CONFIRMED_KEY)
        if not dry_run:
            for email in withdrawals:
                if not await _retry_withdrawal(store, email):
                    counts["failed"] += 1
    except Exception:
        logger.error("[NEWSLETTER] Backfill store unavailable")
        raise HTTPException(503, "Newsletter store unavailable; retry") from None

    for email, raw in confirmed.items():
        try:
            async with (nullcontext() if dry_run else newsletter_lock(store)):
                data = parse_consent(email, raw)
                if await store.hget(SUPPRESSED_KEY, email.casefold()):
                    if not dry_run:
                        await _withdraw_subscription(store, email, "suppressed")
                    counts["failed"] += 1
                    continue
                if data is None or not delivery_eligible(data, datetime.now(timezone.utc)):
                    counts["failed" if data is None else "held"] += 1
                    if not dry_run and not await _remove_ineligible_contact(store, email):
                        counts["failed"] += 1
                    continue
                status = await newsletter_service.contact_status(email, attributes=preference_attributes(data))
                # Recheck even an existing member against withdrawal during the GET.
                if await store.hget(CONFIRMED_KEY, email) != raw or await store.hget(SUPPRESSED_KEY, email.casefold()):
                    counts["failed"] += 1
                    continue
                if status == "suppressed":
                    if not dry_run:
                        await _withdraw_subscription(store, email, "provider_suppressed")
                    counts["failed"] += 1
                elif status == "already_present":
                    counts["already_present"] += 1
                    if not dry_run:
                        await store.hdel(BREVO_ADD_RETRY_KEY, email)
                        if await store.hget(BREVO_ADD_UNSETTLED_KEY, email.casefold()) == "uncertain":
                            await store.hdel(BREVO_ADD_UNSETTLED_KEY, email.casefold())
                elif status in {"to_add", "to_update"}:
                    # Recheck after the provider read: never enroll a withdrawn snapshot.
                    if await store.hget(CONFIRMED_KEY, email) != raw or await store.hget(SUPPRESSED_KEY, email.casefold()):
                        counts["failed"] += 1
                    elif dry_run or await _sync_brevo_contact(store, email, data.get("name", "")):
                        counts["to_add"] += 1
                    else:
                        counts["failed"] += 1
                else:
                    counts["failed"] += 1
        except Exception:
            logger.error("[NEWSLETTER] Backfill contact failed")
            counts["failed"] += 1
    return counts


@router.get("/readiness")
async def newsletter_readiness(
    _auth: bool = Depends(verify_admin_key), check_list_service: bool = False,
) -> dict[str, Any]:
    """Bounded local-confirmation audit: Redis reads and provider GETs only.

    Not a full provider inventory or an execution manifest. Never returns email
    addresses, tokens, raw provider errors or data belonging to list-only users.
    """
    from routers.newsletter import _get_redis

    store = await _get_redis()
    snapshot = await store.eval_ro(READ_CONSENT_SNAPSHOT, 1, CONFIRMED_KEY, MAX_READINESS_CONTACTS)
    count = int(snapshot[0])
    connection = {"list_service": await _listmonk_connection_health()} if check_list_service else {}
    if count > MAX_READINESS_CONTACTS:
        return {**readiness_summary([], count, False), **connection}
    now = datetime.now(timezone.utc)
    semaphore = asyncio.Semaphore(5)

    async def inspect(client: httpx.AsyncClient, email: str, raw: str) -> tuple[str, list[str]]:
        status, contact = None, None
        if BREVO_API_KEY and parse_consent(email, raw) is not None:
            async with semaphore:
                try:
                    response = await client.get(
                        f"{BREVO_API}/contacts/{quote(email, safe='')}",
                        headers={"api-key": BREVO_API_KEY},
                    )
                    status = response.status_code
                    if status == 200:
                        contact = response.json()
                except (httpx.HTTPError, ValueError):
                    pass  # Unknown provider state is a HOLD; never retry a write.
        return classify_contact(email, raw, status, contact, LIST_ID, now)

    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                decisions = await asyncio.gather(*[
                    inspect(client, snapshot[i], snapshot[i + 1]) for i in range(1, len(snapshot), 2)
                ])
    except TimeoutError:
        raise HTTPException(504, "Readiness check timed out; no contacts changed") from None
    return {**readiness_summary(decisions, count, True), **connection}


async def _listmonk_connection_health() -> dict[str, int]:
    """Optional bounded provider GET; never return contact data or raw errors."""
    from routers.newsletter import LISTMONK_PW, _listmonk_request

    counts = {"configured": int(bool(LISTMONK_PW)), "reachable": 0, "failed": 0}
    if not LISTMONK_PW:
        return counts
    try:
        async with asyncio.timeout(LIST_SERVICE_READINESS_TIMEOUT_SECONDS):
            result = await _listmonk_request("GET", "/api/subscribers?per_page=1&page=1")
            total = result["data"]["total"]
            if type(total) is not int or total < 0:
                raise ValueError("Invalid newsletter provider count")
        counts["reachable"] = 1
    except Exception:
        counts["failed"] = 1
    return counts


@router.get("/stats")
async def newsletter_admin_stats(_auth: bool = Depends(verify_admin_key)):
    """Campaign stats from Brevo — no subscriber emails."""
    if not BREVO_API_KEY:
        raise HTTPException(503, "BREVO_API_KEY nicht konfiguriert")

    campaigns = await _brevo_request("GET", "emailCampaigns?limit=10&offset=0&sort=desc")
    campaign_list = campaigns.get("campaigns", [])

    return {
        "list_id": LIST_ID,
        "total_campaigns": campaigns.get("count", 0),
        "recent_campaigns": [{
            "id": c["id"],
            "name": c.get("name", ""),
            "subject": c.get("subject", ""),
            "status": c.get("status", ""),
            "sent_date": c.get("sentDate"),
            "stats": c.get("statistics", {}).get("globalStats", {}),
        } for c in campaign_list[:10]],
    }


@router.post("/preview")
async def newsletter_preview(req: PreviewRequest, _auth: bool = Depends(verify_admin_key)):
    """Render preview with ekklesia template — no send."""
    sanitized = _sanitize_html(req.html_content)
    wrapped = _wrap(sanitized)
    return {
        "subject": req.subject,
        "html_preview": wrapped,
        "sanitized": sanitized != req.html_content,
    }


@router.post("/draft")
async def newsletter_create_draft(req: DraftRequest, _auth: bool = Depends(verify_admin_key)):
    """Create Brevo campaign draft — does NOT send."""
    sanitized = _sanitize_html(req.html_content)
    wrapped = _wrap(sanitized)

    from datetime import datetime, timezone
    name = req.name or f"ekklesia — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    result = await _brevo_request("POST", "emailCampaigns", {
        "name": name,
        "subject": req.subject,
        "sender": SENDER,
        "replyTo": OPERATOR_EMAIL,
        "type": "classic",
        "tag": req.tag,
        "htmlContent": wrapped,
    })

    campaign_id = result.get("id")
    logger.info("[NEWSLETTER] Draft created")

    return {
        "campaign_id": campaign_id,
        "name": name,
        "subject": req.subject,
        "status": "draft",
        "list_id": LIST_ID,
        "note": "Verwenden Sie POST /send mit confirm=true um zu senden.",
    }


@router.post("/send")
async def newsletter_send(req: SendRequest, _auth: bool = Depends(verify_admin_key)) -> dict[str, str | int]:
    """Send a drafted campaign — requires confirm=true. Cross-publishes to Telegram (non-blocking)."""
    if not req.confirm:
        raise HTTPException(400, "Confirmation required: confirm=true")

    from services.newsletter_claims import DispatchClaim

    audience = None
    claim = None
    try:
        async with newsletter_lock() as lease:
            # The provider campaign ID is the stable identity of this send request.
            claim = await DispatchClaim.acquire(lease, f"admin:{req.campaign_id}", req.campaign_id)
            if not claim.acquired:
                return {"reason": "already_sent" if claim.state == "sent" else f"dispatch_{claim.state}",
                        "sent": 0, "uncertain": int(claim.state == "uncertain")}
            async with claim.attempt():
                campaign = await _brevo_request("GET", f"emailCampaigns/{req.campaign_id}")
                if campaign.get("status") == "sent":
                    await claim.write("sent")
                    return {"reason": "already_sent", "sent": 0}
                plan = campaign_plan(campaign.get("tag"))
                audience = await prepare_audience(lease.store, plan)
                if not audience.selected:
                    await claim.write("failed")
                    log_audience("ready", audience.counts)
                    return {"reason": "ready", **audience.counts, "sent": 0}
                async with temporary_campaign_list(lease, audience) as target:
                    # Fully replace any historical shared list or segment recipients.
                    await _brevo_request("PUT", f"emailCampaigns/{req.campaign_id}", {"recipients": target.recipients})
                    await target.verify_campaign(req.campaign_id)
                    audience = await authorize_dispatch(lease, plan, audience, target)
                    await claim.send(
                        lambda: _brevo_request("POST", f"emailCampaigns/{req.campaign_id}/sendNow", {}),
                        audience.counts, "audience_unavailable",
                    )
    except AudienceUnavailable as exc:
        log_audience(exc.reason, exc.counts)
        raise HTTPException(503, exc.detail) from None
    except Exception as exc:
        error = AudienceUnavailable("lock_unavailable" if isinstance(exc, NewsletterLockUnavailable) else "audience_unavailable",
                                    audience.counts if audience else None)
        log_audience(error.reason, error.counts)
        raise HTTPException(503, error.detail) from None
    logger.info("[NEWSLETTER] Campaign sent")

    # NEA-263: Cross-publish to Telegram (non-blocking)
    tg_sent = False
    try:
        safe_subject = html.escape(campaign.get("subject") or "Newsletter ekklesia.gr")
        tg_msg = (
            f"<b>📧 Νέο Newsletter</b>\n\n"
            f"{safe_subject}\n\n"
            f"👉 <a href=\"https://ekklesia.gr\">ekklesia.gr</a>"
        )
        tg_sent = await tg_send(tg_msg, group_thread_id=TOPICS["platform"])
        if tg_sent:
            logger.info("[NEWSLETTER] Telegram cross-publish OK")
        else:
            logger.warning("[NEWSLETTER] Telegram cross-publish failed")
    except Exception:
        logger.warning("[NEWSLETTER] Telegram cross-publish unavailable")

    log_audience("sent", audience.counts)
    return {"reason": "sent", **audience.counts, "sent": audience.counts["selected"], "telegram_sent": int(tg_sent)}


@router.get("/dispatch-status")
async def newsletter_dispatch_status(_auth: bool = Depends(verify_admin_key)) -> dict[str, int]:
    from routers.newsletter import _get_redis
    from services.newsletter_claims import dispatch_status

    try:
        return await dispatch_status(await _get_redis())
    except Exception:
        raise HTTPException(503, "Newsletter dispatch status unavailable; retry") from None

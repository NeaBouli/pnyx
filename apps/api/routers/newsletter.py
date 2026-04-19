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
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
import httpx
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/newsletter", tags=["MOD-19 Newsletter"])

# ── Config ────────────────────────────────────────────────────────────────────

LISTMONK_URL = os.getenv("LISTMONK_URL", "http://172.18.0.7:9000")
LISTMONK_USER = os.getenv("LISTMONK_ADMIN_USER", "admin")
LISTMONK_PW = os.getenv("LISTMONK_ADMIN_PASSWORD", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

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


# ── Listmonk API helper ──────────────────────────────────────────────────────

async def _listmonk_request(method: str, path: str, json_data: dict = None) -> dict:
    if not LISTMONK_PW:
        raise HTTPException(status_code=503, detail="Newsletter system not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.request(
            method,
            f"{LISTMONK_URL}{path}",
            json=json_data,
            auth=(LISTMONK_USER, LISTMONK_PW),
        )
        if r.status_code >= 400:
            logger.error(f"[MOD-19] Listmonk {method} {path}: {r.status_code} {r.text[:200]}")
        return r.json()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lists")
async def get_lists():
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
async def subscribe(req: SubscribeRequest):
    """
    Public: subscribe to newsletter.
    Sends double opt-in email via Brevo. Stores pending token in Redis.
    Subscriber only activated after clicking confirmation link.
    """
    import secrets

    if req.subscriber_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {VALID_TYPES}")
    if req.frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Frequency must be 'weekly' or 'monthly'")
    if req.language not in VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be 'el' or 'en'")

    r = await _get_redis()

    # Check if already confirmed
    existing = await r.hget("newsletter:confirmed", req.email)
    if existing:
        return {"success": True, "message": "Already subscribed."}

    # Generate confirmation token
    token = secrets.token_urlsafe(32)
    sub_data = json.dumps({
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
                "subject": subject,
                "htmlContent": body,
            })
            if resp.status_code >= 400:
                logger.error(f"[MOD-19] Brevo send failed: {resp.status_code} {resp.text[:200]}")
                raise HTTPException(status_code=502, detail="Email send failed")
    except httpx.HTTPError as e:
        logger.error(f"[MOD-19] Brevo error: {e}")
        raise HTTPException(status_code=502, detail="Email service error")

    logger.info(f"[MOD-19] Opt-in email sent to {req.email}")
    return {"success": True, "message": "Confirmation email sent. Please check your inbox."}


@router.get("/confirm/{token}")
async def confirm_subscription(token: str):
    """Confirm newsletter subscription via token from email link."""
    from fastapi.responses import HTMLResponse

    r = await _get_redis()
    raw = await r.get(f"newsletter:pending:{token}")

    if not raw:
        return HTMLResponse(
            '<div style="text-align:center;padding:3rem;font-family:sans-serif"><h2>Link abgelaufen</h2><p>Bitte registrieren Sie sich erneut auf ekklesia.gr</p></div>',
            status_code=410
        )

    data = json.loads(raw)
    email = data["email"]

    # Mark as confirmed
    await r.hset("newsletter:confirmed", email, raw)
    await r.delete(f"newsletter:pending:{token}")

    # Also register in Listmonk (if available)
    if LISTMONK_PW:
        try:
            await _listmonk_request("POST", "/api/subscribers", {
                "email": email,
                "name": data.get("name", ""),
                "status": "enabled",
                "preconfirm_subscriptions": True,
                "attribs": data.get("topics", {}),
            })
        except Exception:
            pass  # Listmonk is optional — Redis is primary

    logger.info(f"[MOD-19] Subscription confirmed: {email}")

    return HTMLResponse(
        '<div style="text-align:center;padding:3rem;font-family:sans-serif">'
        '<img src="https://ekklesia.gr/pnx.png" width="60"/>'
        '<h2 style="color:#2563eb">Εγγραφή Επιβεβαιώθηκε!</h2>'
        '<p>Ευχαριστούμε! Θα λαμβάνετε ενημερώσεις από το ekklesia.gr</p>'
        '<a href="https://ekklesia.gr" style="color:#2563eb">← Επιστροφή στο ekklesia.gr</a>'
        '</div>'
    )


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
async def newsletter_stats():
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

@router.post("/webhook/brevo")
async def brevo_webhook(request: Request):
    """Receive Brevo event webhooks — track sent/opened/bounced."""
    try:
        events = await request.json()
        if not isinstance(events, list):
            events = [events]

        r = await _get_redis()
        for event in events:
            evt = event.get("event", "")
            if evt in ("sent", "delivered", "opened", "clicked", "unsubscribed", "hardBounce", "softBounce"):
                await r.hincrby("newsletter:events", evt, 1)

        # Invalidate stats cache on activity
        await r.delete("newsletter:stats_cache")

        return {"received": True, "events": len(events)}
    except Exception as e:
        logger.error(f"[MOD-19] Brevo webhook error: {e}")
        return {"received": False, "error": str(e)}

"""
Newsletter Admin — Brevo Campaign Draft/Preview/Send
Admin-only. No subscriber emails returned.
NEA-263: Cross-publish to Telegram after successful send.
"""
import re
import os
import html
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies import verify_admin_key
from services.telegram_community import _send as tg_send, TOPICS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/newsletter", tags=["Admin Newsletter"])

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API = "https://api.brevo.com/v3"
SENDER = {"name": "εκκλησία", "email": "newsletter@ekklesia.gr"}
LIST_ID = int(os.getenv("BREVO_LIST_ID", "2"))


def _sanitize_html(raw: str) -> str:
    """Minimal sanitization — strip script tags, event handlers, javascript: URLs."""
    raw = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"\bon\w+\s*=\s*[\"'][^\"']*[\"']", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"javascript:", "", raw, flags=re.IGNORECASE)
    return raw


async def _brevo_request(method: str, endpoint: str, data: dict = None) -> dict:
    if not BREVO_API_KEY:
        raise HTTPException(503, "BREVO_API_KEY nicht konfiguriert")
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        if method == "POST":
            r = await client.post(f"{BREVO_API}/{endpoint}",
                                  headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                                  json=data)
        elif method == "GET":
            r = await client.get(f"{BREVO_API}/{endpoint}",
                                 headers={"api-key": BREVO_API_KEY})
        else:
            raise HTTPException(400, f"Unsupported method: {method}")
        if r.status_code >= 400:
            logger.warning("[NEWSLETTER] Brevo %s %s → %d: %s", method, endpoint, r.status_code, r.text[:200])
            raise HTTPException(r.status_code, f"Brevo error: {r.text[:200]}")
        return r.json()


# ─── Templates ───────────────────────────────────────────────────────────────

from services.newsletter_service import _HEADER, _FOOTER, _wrap


# ─── Schemas ─────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    html_content: str = Field(..., min_length=10)
    name: str = Field(None, max_length=100, description="Campaign name (optional, auto-generated if empty)")


class SendRequest(BaseModel):
    campaign_id: int
    confirm: bool = Field(..., description="Must be true to send")


class PreviewRequest(BaseModel):
    subject: str
    html_content: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

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
        "type": "classic",
        "recipients": {"listIds": [LIST_ID]},
        "htmlContent": wrapped,
    })

    campaign_id = result.get("id")
    logger.info("[NEWSLETTER] Draft created: %s — %s", campaign_id, req.subject)

    return {
        "campaign_id": campaign_id,
        "name": name,
        "subject": req.subject,
        "status": "draft",
        "list_id": LIST_ID,
        "note": "Verwenden Sie POST /send mit confirm=true um zu senden.",
    }


@router.post("/send")
async def newsletter_send(req: SendRequest, _auth: bool = Depends(verify_admin_key)):
    """Send a drafted campaign — requires confirm=true. Cross-publishes to Telegram (non-blocking)."""
    if not req.confirm:
        raise HTTPException(400, "Bestätigung erforderlich: confirm=true")

    # Fetch campaign subject from Brevo (source of truth, not frontend)
    subject = "Newsletter ekklesia.gr"
    try:
        campaign = await _brevo_request("GET", f"emailCampaigns/{req.campaign_id}")
        subject = campaign.get("subject") or campaign.get("name") or subject
    except Exception as e:
        logger.warning("[NEWSLETTER] Could not fetch campaign %d details: %s", req.campaign_id, e)

    await _brevo_request("POST", f"emailCampaigns/{req.campaign_id}/sendNow", {})
    logger.info("[NEWSLETTER] Campaign %d sent", req.campaign_id)

    # NEA-263: Cross-publish to Telegram (non-blocking)
    tg_sent = False
    try:
        safe_subject = html.escape(subject)
        tg_msg = (
            f"<b>📧 Νέο Newsletter</b>\n\n"
            f"{safe_subject}\n\n"
            f"👉 <a href=\"https://ekklesia.gr\">ekklesia.gr</a>"
        )
        tg_sent = await tg_send(tg_msg, group_thread_id=TOPICS["platform"])
        if tg_sent:
            logger.info("[NEWSLETTER] Telegram cross-publish OK for campaign %d", req.campaign_id)
        else:
            logger.warning("[NEWSLETTER] Telegram cross-publish failed for campaign %d", req.campaign_id)
    except Exception as e:
        logger.warning("[NEWSLETTER] Telegram error (non-blocking): %s", e)

    return {
        "campaign_id": req.campaign_id,
        "status": "sent",
        "message": "Newsletter wurde gesendet.",
        "telegram_sent": tg_sent,
    }

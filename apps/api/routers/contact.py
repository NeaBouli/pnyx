"""Contact router — NGO contact form endpoint (POST /api/v1/contact/ngo).

Sends notification email via Brevo (SendinBlue) API.
Rate-limited: max 3 requests per IP per hour (Redis, hashed IP bucket).
"""

import os
import logging
import re
from typing import Optional, Tuple

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from ip_utils import ip_reference, rate_limit_key_for_ip, redis_fixed_window_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])

# ---------------------------------------------------------------------------
# Rate limiter — Redis fixed window (max 3 per IP per hour)
# ---------------------------------------------------------------------------
RATE_LIMIT = 3
RATE_WINDOW = 3600  # seconds
_redis_client: Optional[aioredis.Redis] = None


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


async def _check_rate_limit(request: Request) -> None:
    """Raise 429 if the hashed IP bucket exceeded the hourly limit."""
    r = await _get_redis()
    try:
        await redis_fixed_window_limit(
            r,
            rate_limit_key_for_ip(request, "contact:ngo"),
            RATE_LIMIT,
            RATE_WINDOW,
        )
    except HTTPException as exc:
        exc.detail = "Rate limit exceeded — max 3 requests per hour."
        raise exc


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class NgoContactRequest(BaseModel):
    subject: str = ""
    first_name: str
    last_name: str
    email: EmailStr
    phone: str = ""
    org: str = ""
    position: str = ""
    region: str = ""
    message: str = ""
    consent: bool = False

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field must not be blank")
        if len(v) > 200:
            raise ValueError("Field too long (max 200 chars)")
        return v

    @field_validator("message", "subject", "org", "position", "region", "phone")
    @classmethod
    def max_length(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("Field too long (max 2000 chars)")
        return v.strip()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
RECIPIENT = os.getenv("CONTACT_RECIPIENT", "noreply@ekklesia.gr")


@router.post("/ngo")
async def contact_ngo(body: NgoContactRequest, request: Request) -> dict:
    """Handle contact form submission. Sends to admin via Brevo. No confirmation email to sender."""
    await _check_rate_limit(request)
    request_ref = ip_reference(request, "contact")

    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent required")

    brevo_key = os.getenv("BREVO_API_KEY")
    if not brevo_key:
        logger.error("[CONTACT] BREVO_API_KEY not set")
        raise HTTPException(status_code=503, detail="Email service unavailable")

    full_name = f"{body.first_name} {body.last_name}"
    subject = body.subject or f"Επικοινωνία ekklesia.gr — {body.org or full_name}"

    html_body = (
        f"<h2>Επικοινωνία — ekklesia.gr</h2>"
        f"<table style='border-collapse:collapse;font-size:14px'>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Θέμα:</td><td>{_escape(subject)}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Όνομα:</td><td>{_escape(full_name)}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Email:</td><td>{_escape(body.email)}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Τηλέφωνο:</td><td>{_escape(body.phone or '-')}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Φορέας:</td><td>{_escape(body.org or '-')}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Θέση:</td><td>{_escape(body.position or '-')}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:bold'>Περιφέρεια/Δήμος:</td><td>{_escape(body.region or '-')}</td></tr>"
        f"</table>"
        f"<hr style='margin:1rem 0'/>"
        f"<p>{_escape(body.message)}</p>"
        f"<hr style='margin:1rem 0'/>"
        f"<p style='color:#999;font-size:0.8em'>Request ref: {request_ref} | Consent: {body.consent}</p>"
    )

    payload = {
        "sender": {"name": "ekklesia.gr", "email": "noreply@ekklesia.gr"},
        "to": [{"email": RECIPIENT, "name": "Ekklesia Admin"}],
        "replyTo": {"email": body.email, "name": full_name},
        "subject": subject,
        "htmlContent": html_body,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers={
                    "api-key": brevo_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        if resp.status_code >= 400:
            logger.error("[CONTACT] Brevo error %s: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail="Email delivery failed")
    except httpx.HTTPError as e:
        logger.error("[CONTACT] HTTP error: %s", e)
        raise HTTPException(status_code=502, detail="Email service unreachable")

    # NO confirmation email to sender (by design)
    logger.info("[CONTACT] Contact ref=%s — %s (%s)", request_ref, full_name, body.org)
    return {"status": "ok", "message": "Message sent successfully"}


def _escape(s: str) -> str:
    """Basic HTML escaping."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

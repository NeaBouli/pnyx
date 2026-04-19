"""Contact router — NGO contact form endpoint (POST /api/v1/contact/ngo).

Sends notification email via Brevo (SendinBlue) API.
Rate-limited: max 3 requests per IP per hour (in-memory).
"""

import os
import time
import logging
import re
from collections import defaultdict
from typing import Dict, List, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])

# ---------------------------------------------------------------------------
# Rate limiter — simple in-memory dict (max 3 per IP per hour)
# ---------------------------------------------------------------------------
_rate_store: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT = 3
RATE_WINDOW = 3600  # seconds


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if IP exceeded rate limit."""
    now = time.time()
    # Prune old entries
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded — max 3 requests per hour.",
        )
    _rate_store[ip].append(now)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class NgoContactRequest(BaseModel):
    org: str
    name: str
    email: EmailStr
    message: str

    @field_validator("org", "name", "message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field must not be blank")
        if len(v) > 2000:
            raise ValueError("Field too long (max 2000 chars)")
        return v

    @field_validator("org", "name")
    @classmethod
    def max_length_short(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("Field too long (max 200 chars)")
        return v


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
RECIPIENT = "kaspartisan@proton.me"


@router.post("/ngo")
async def contact_ngo(body: NgoContactRequest, request: Request) -> dict:
    """Handle NGO contact form submission.

    Validates fields, rate-limits by IP, and sends notification email
    via Brevo transactional API.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    brevo_key = os.getenv("BREVO_API_KEY")
    if not brevo_key:
        logger.error("[CONTACT] BREVO_API_KEY not set")
        raise HTTPException(status_code=503, detail="Email service unavailable")

    subject = f"NGO Επικοινωνία ekklesia.gr — {body.org}"

    html_body = (
        f"<h2>NGO Επικοινωνία — ekklesia.gr</h2>"
        f"<p><strong>Οργανισμός:</strong> {_escape(body.org)}</p>"
        f"<p><strong>Όνομα:</strong> {_escape(body.name)}</p>"
        f"<p><strong>Email:</strong> {_escape(body.email)}</p>"
        f"<hr/>"
        f"<p>{_escape(body.message)}</p>"
        f"<hr/>"
        f"<p style='color:#999;font-size:0.8em'>IP: {client_ip}</p>"
    )

    payload = {
        "sender": {"name": "ekklesia.gr", "email": "noreply@ekklesia.gr"},
        "to": [{"email": RECIPIENT, "name": "Ekklesia Admin"}],
        "replyTo": {"email": body.email, "name": body.name},
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

    # Send confirmation to sender
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.brevo.com/v3/smtp/email",
                json={
                    "sender": {"name": "ekklesia Newsletter", "email": "newsletter@ekklesia.gr"},
                    "to": [{"email": body.email, "name": body.name}],
                    "subject": "Λάβαμε το μήνυμά σας — εκκλησία",
                    "htmlContent": (
                        '<div style="background:#f8fafc;padding:2rem 1rem;font-family:sans-serif">'
                        '<div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;border-top:4px solid #2563eb;padding:2rem">'
                        f'<p>Αγαπητέ/ή {_escape(body.name)},</p>'
                        '<p>Λάβαμε το μήνυμά σας και θα επικοινωνήσουμε σύντομα.</p>'
                        '<p>Ευχαριστούμε για το ενδιαφέρον σας.</p>'
                        '<p style="color:#64748b">— Vendetta Labs / εκκλησία</p>'
                        '</div></div>'
                    ),
                },
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
            )
    except Exception:
        pass  # Confirmation is best-effort

    logger.info("[CONTACT] NGO contact from %s — org=%s", client_ip, body.org)
    return {"status": "ok", "message": "Message sent successfully"}


def _escape(s: str) -> str:
    """Basic HTML escaping."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

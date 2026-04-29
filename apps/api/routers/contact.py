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
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

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
        f"<p style='color:#999;font-size:0.8em'>IP: {client_ip} | Consent: {body.consent}</p>"
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
    logger.info("[CONTACT] Contact from %s — %s (%s)", client_ip, full_name, body.org)
    return {"status": "ok", "message": "Message sent successfully"}


def _escape(s: str) -> str:
    """Basic HTML escaping."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

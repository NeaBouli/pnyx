"""
DiscourseConnect SSO Bridge for pnyx.ekklesia.gr Forum
GET  /api/v1/sso/discourse/initiate  — Entry point from Discourse
POST /api/v1/sso/discourse/callback  — Callback after user confirms identity
"""
import hmac
import hashlib
import base64
import os
import urllib.parse
import logging

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from database import get_db
from models import IdentityRecord, KeyStatus, Periferia, Dimos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sso", tags=["SSO"])

DISCOURSE_SSO_SECRET = os.getenv("DISCOURSE_SSO_SECRET", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


def _verify_sig(payload: str, sig: str) -> bool:
    if not DISCOURSE_SSO_SECRET:
        return False
    expected = hmac.new(
        DISCOURSE_SSO_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def _build_payload(params: dict) -> tuple[str, str]:
    raw = urllib.parse.urlencode(params)
    encoded = base64.b64encode(raw.encode()).decode()
    sig = hmac.new(
        DISCOURSE_SSO_SECRET.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return encoded, sig


@router.get("/discourse/initiate")
async def discourse_sso_initiate(sso: str = Query(...), sig: str = Query(...)):
    """Discourse redirects here → verify sig → store nonce → redirect to verify page."""
    if not _verify_sig(sso, sig):
        raise HTTPException(403, "Invalid SSO signature")

    decoded = base64.b64decode(sso).decode()
    params = dict(urllib.parse.parse_qsl(decoded))
    nonce = params.get("nonce")
    return_sso_url = params.get("return_sso_url")

    if not nonce or not return_sso_url:
        raise HTTPException(400, "Missing nonce or return_sso_url")

    r = await _redis()
    await r.setex(f"sso:discourse:{nonce}", 300, return_sso_url)

    redirect = (
        f"https://ekklesia.gr/sso-verify.html"
        f"?nonce={urllib.parse.quote(nonce)}"
        f"&return_url={urllib.parse.quote(return_sso_url)}"
    )
    return RedirectResponse(url=redirect, status_code=302)


@router.post("/discourse/callback")
async def discourse_sso_callback(
    nonce: str = Query(...),
    public_key_hex: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Called after user confirms identity → build Discourse payload → redirect."""
    r = await _redis()
    return_sso_url = await r.get(f"sso:discourse:{nonce}")
    if not return_sso_url:
        raise HTTPException(410, "Nonce expired or invalid")

    # Load identity
    result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.public_key_hex == public_key_hex,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(404, "Identity not found or not active")

    # Resolve location names
    dimos_name = ""
    periferia_name = ""
    if identity.dimos_id:
        dimos = await db.get(Dimos, identity.dimos_id)
        if dimos:
            dimos_name = dimos.name_el
    if identity.periferia_id:
        periferia = await db.get(Periferia, identity.periferia_id)
        if periferia:
            periferia_name = periferia.name_el

    # Build Discourse SSO payload
    user_params = {
        "nonce": nonce,
        "external_id": identity.nullifier_hash,
        "username": f"citizen_{identity.nullifier_hash[:8]}",
        "email": f"{identity.nullifier_hash[:16]}@noreply.ekklesia.gr",
        "name": "Επαληθευμένος Πολίτης",
        "add_groups": "verified-citizens",
        "suppress_welcome_message": "true",
    }
    if dimos_name:
        user_params["custom.dimos"] = dimos_name
    if periferia_name:
        user_params["custom.periferia"] = periferia_name

    payload, sig = _build_payload(user_params)
    await r.delete(f"sso:discourse:{nonce}")

    logger.info("SSO login: nullifier=%s... dimos=%s", identity.nullifier_hash[:8], dimos_name)

    redirect = f"{return_sso_url}?sso={urllib.parse.quote(payload)}&sig={sig}"
    return RedirectResponse(url=redirect, status_code=302)


# Fix missing import
from fastapi import Depends

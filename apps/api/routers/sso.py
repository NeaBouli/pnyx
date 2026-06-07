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

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from database import get_db
from models import IdentityRecord, KeyStatus, Periferia, Dimos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sso", tags=["SSO"])

DISCOURSE_SSO_SECRET = os.getenv("DISCOURSE_SSO_SECRET", "")
FORUM_SSO_SALT = os.getenv("FORUM_SSO_SALT", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


def validate_forum_sso_config() -> None:
    """Fail closed in production if Discourse SSO secrets are incomplete."""
    environment = os.getenv("ENVIRONMENT", "production")
    if DISCOURSE_SSO_SECRET and FORUM_SSO_SALT:
        return
    if environment != "production":
        logger.warning("[SSO] Discourse SSO secret/salt incomplete in non-production")
        return
    missing = []
    if not DISCOURSE_SSO_SECRET:
        missing.append("DISCOURSE_SSO_SECRET")
    if not FORUM_SSO_SALT:
        missing.append("FORUM_SSO_SALT")
    raise RuntimeError(f"Discourse SSO startup check failed: missing {', '.join(missing)}")


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


async def _build_discourse_redirect(
    *,
    nonce: str,
    return_sso_url: str,
    identity: IdentityRecord,
    db: AsyncSession,
) -> str:
    """Build the DiscourseConnect return URL for a verified identity."""
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

    # external_id is HMAC, not raw nullifier
    external_id = hmac.new(
        FORUM_SSO_SALT.encode(), identity.nullifier_hash.encode(), hashlib.sha256
    ).hexdigest()[:32]

    user_params = {
        "nonce": nonce,
        "external_id": external_id,
        "username": f"citizen_{external_id[:8]}",
        "email": f"{external_id[:16]}@noreply.ekklesia.gr",
        "name": "Επαληθευμένος Πολίτης",
        "add_groups": "verified-citizens",
        "suppress_welcome_message": "true",
    }
    if dimos_name:
        user_params["custom.dimos"] = dimos_name
    if periferia_name:
        user_params["custom.periferia"] = periferia_name

    payload, sig = _build_payload(user_params)
    return f"{return_sso_url}?sso={urllib.parse.quote(payload)}&sig={sig}"


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
        f"https://ekklesia.gr/el/sso-verify"
        f"?nonce={urllib.parse.quote(nonce)}"
        f"&return_url={urllib.parse.quote(return_sso_url)}"
    )
    return RedirectResponse(url=redirect, status_code=302)


@router.post("/discourse/callback")
async def discourse_sso_callback(
    request: Request,
    nonce: str = Query(None),
    public_key_hex: str = Query(None),
    signature_hex: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Called after user confirms identity → verify Ed25519 signature → build Discourse payload → redirect."""
    from keypair import verify_signature

    # Accept both query params and JSON body
    if not nonce or not public_key_hex or not signature_hex:
        try:
            body = await request.json()
            nonce = nonce or body.get("nonce")
            public_key_hex = public_key_hex or body.get("public_key_hex")
            signature_hex = signature_hex or body.get("signature_hex")
        except Exception:
            pass

    if not nonce or not public_key_hex or not signature_hex:
        raise HTTPException(400, "Missing nonce, public_key_hex, or signature_hex")

    # Verify Ed25519 proof-of-possession
    challenge = f"discourse_sso:{nonce}:{public_key_hex}"
    if not verify_signature(public_key_hex, challenge, signature_hex):
        raise HTTPException(401, "Invalid signature — proof of key possession failed")

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

    redirect = await _build_discourse_redirect(
        nonce=nonce,
        return_sso_url=return_sso_url,
        identity=identity,
        db=db,
    )
    await r.delete(f"sso:discourse:{nonce}")

    logger.info("SSO login completed via browser key: pubkey=%s...", public_key_hex[:8])
    return {"redirect_url": redirect}


class DiscourseQRCompleteRequest(BaseModel):
    nonce: str = Field(..., min_length=8)
    session_id: str = Field(..., min_length=10)


@router.post("/discourse/qr-complete")
async def discourse_sso_qr_complete(
    req: DiscourseQRCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete DiscourseConnect after mobile app authenticated a forum_login QR session."""
    r = await _redis()
    return_sso_url = await r.get(f"sso:discourse:{req.nonce}")
    if not return_sso_url:
        raise HTTPException(410, "Nonce expired or invalid")

    qr_data = await r.hgetall(f"polis_qr:{req.session_id}")
    if not qr_data:
        raise HTTPException(410, "QR session expired or invalid")
    if qr_data.get("status") != "authenticated":
        raise HTTPException(403, "QR session is not authenticated")
    if qr_data.get("purpose") != "forum_login":
        raise HTTPException(400, "QR session purpose is not forum_login")

    nullifier_hash = qr_data.get("nullifier_hash") or ""
    public_key_hex = qr_data.get("public_key_hex") or ""
    if not nullifier_hash or not public_key_hex:
        raise HTTPException(400, "QR session missing identity data")

    result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == nullifier_hash,
            IdentityRecord.public_key_hex == public_key_hex,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(404, "Identity not found or not active")

    redirect = await _build_discourse_redirect(
        nonce=req.nonce,
        return_sso_url=return_sso_url,
        identity=identity,
        db=db,
    )
    await r.delete(f"sso:discourse:{req.nonce}")
    await r.delete(f"polis_qr:{req.session_id}")

    logger.info("SSO login completed via forum QR: session=%s", req.session_id[:8])
    return {"redirect_url": redirect}

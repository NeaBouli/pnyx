"""
POLIS QR-Code Browser Login
Flow: Browser → QR → App scannt → Ed25519 sign → Browser authenticated

GET  /api/v1/polis/qr-session         — Generate session + challenge
GET  /api/v1/polis/qr-session/{id}    — Poll status (pending/authenticated/expired)
POST /api/v1/polis/qr-auth            — App submits signed challenge
"""
import os
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from database import get_db
from models import IdentityRecord, KeyStatus
from keypair import verify_challenge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/polis", tags=["POLIS QR Auth"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
SESSION_TTL = 300  # 5 minutes


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


@router.get("/qr-session")
async def create_qr_session():
    """Generate a new QR login session with challenge."""
    session_id = secrets.token_urlsafe(32)
    challenge = secrets.token_hex(32)

    r = await _redis()
    await r.hset(f"polis_qr:{session_id}", mapping={
        "challenge": challenge,
        "status": "pending",
    })
    await r.expire(f"polis_qr:{session_id}", SESSION_TTL)

    qr_data = f"ekklesia://polis-login?session={session_id}&challenge={challenge}"

    return {
        "session_id": session_id,
        "challenge": challenge,
        "qr_data": qr_data,
        "ttl": SESSION_TTL,
    }


@router.get("/qr-session/{session_id}")
async def poll_qr_session(session_id: str):
    """Poll QR session status. Returns pending/authenticated/expired."""
    r = await _redis()
    data = await r.hgetall(f"polis_qr:{session_id}")

    if not data:
        return {"status": "expired", "session_id": session_id}

    status = data.get("status", "pending")
    result = {"status": status, "session_id": session_id}

    if status == "authenticated":
        result["nullifier_hash"] = data.get("nullifier_hash", "")
        result["public_key_hex"] = data.get("public_key_hex", "")

    return result


class QRAuthRequest(BaseModel):
    session_id: str = Field(..., min_length=10)
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    public_key_hex: str = Field(..., min_length=32)
    signature_hex: str = Field(..., min_length=64)


@router.post("/qr-auth")
async def authenticate_qr(req: QRAuthRequest, db: AsyncSession = Depends(get_db)):
    """App submits signed challenge to authenticate browser session."""
    r = await _redis()
    data = await r.hgetall(f"polis_qr:{req.session_id}")

    if not data:
        raise HTTPException(410, "Session expired")

    if data.get("status") != "pending":
        raise HTTPException(409, "Session already authenticated")

    challenge = data.get("challenge", "")
    if not challenge:
        raise HTTPException(400, "Invalid session")

    # Verify identity exists
    result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Identity not found or revoked")

    # Verify public key matches
    if identity.public_key_hex != req.public_key_hex:
        raise HTTPException(403, "Public key mismatch")

    # Verify Ed25519 signature on challenge
    if not verify_challenge(req.public_key_hex, challenge, req.signature_hex):
        raise HTTPException(401, "Invalid signature")

    # Mark session as authenticated
    await r.hset(f"polis_qr:{req.session_id}", mapping={
        "status": "authenticated",
        "nullifier_hash": req.nullifier_hash,
        "public_key_hex": req.public_key_hex,
    })
    await r.expire(f"polis_qr:{req.session_id}", 60)  # 1 min to pickup

    logger.info("QR auth success: session=%s", req.session_id[:8])

    return {"success": True, "session_id": req.session_id}

"""
POLIS QR-Code Browser Login + Vote Auth
Flow: Browser → QR → App scannt → Ed25519 sign → Browser authenticated

GET  /api/v1/polis/qr-session         — Generate session + challenge
GET  /api/v1/polis/qr-session/{id}    — Poll status (pending/authenticated/expired)
POST /api/v1/polis/qr-auth            — App submits signed challenge

Purpose types:
  - "ticket"      — POLIS ticket create/vote (default)
  - "vote"        — Bill vote from browser (requires bill_id)
  - "forum_login" — Discourse forum login (persistent session)
"""
import os
import secrets
import logging
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from database import get_db
from models import IdentityRecord, KeyStatus


def verify_challenge(public_key_hex: str, challenge: str, signature_hex: str) -> bool:
    """Verify Ed25519 signature on a challenge string."""
    try:
        from nacl.signing import VerifyKey
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        vk.verify(challenge.encode("utf-8"), bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/polis", tags=["POLIS QR Auth"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
SESSION_TTL = 300  # 5 minutes


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


@router.get("/qr-session")
async def create_qr_session(
    purpose: Literal["ticket", "vote", "forum_login"] = Query("ticket"),
    bill_id: Optional[str] = Query(None),
):
    """Generate a new QR login session with challenge.

    Query params:
      - purpose: ticket | vote | forum_login
      - bill_id: required when purpose=vote
    """
    # Validate: vote requires bill_id
    if purpose == "vote" and not bill_id:
        raise HTTPException(400, "bill_id is required when purpose=vote")

    session_id = secrets.token_urlsafe(32)
    challenge = secrets.token_hex(32)

    session_data = {
        "challenge": challenge,
        "status": "pending",
        "purpose": purpose,
    }
    if bill_id:
        session_data["bill_id"] = bill_id

    r = await _redis()
    await r.hset(f"polis_qr:{session_id}", mapping=session_data)
    await r.expire(f"polis_qr:{session_id}", SESSION_TTL)

    # Build deep-link URL
    qr_data = f"ekklesia://polis-login?session={session_id}&challenge={challenge}&purpose={purpose}"
    if bill_id:
        qr_data += f"&bill_id={bill_id}"

    return {
        "session_id": session_id,
        "challenge": challenge,
        "qr_data": qr_data,
        "purpose": purpose,
        "bill_id": bill_id,
        "ttl": SESSION_TTL,
    }


@router.get("/qr-session/{session_id}")
async def poll_qr_session(session_id: str):
    """Poll QR session status. Returns pending/authenticated/expired/used."""
    r = await _redis()
    data = await r.hgetall(f"polis_qr:{session_id}")

    if not data:
        return {"status": "expired", "session_id": session_id}

    status = data.get("status", "pending")
    result = {
        "status": status,
        "session_id": session_id,
        "purpose": data.get("purpose", "ticket"),
        "bill_id": data.get("bill_id") or None,
    }

    if status == "authenticated":
        result["nullifier_hash"] = data.get("nullifier_hash", "")
        result["public_key_hex"] = data.get("public_key_hex", "")

    return result


class QRAuthRequest(BaseModel):
    session_id: str = Field(..., min_length=10)
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    public_key_hex: str = Field(..., min_length=32)
    signature_hex: str = Field(..., min_length=64)
    purpose: Literal["ticket", "vote", "forum_login"] = "ticket"
    bill_id: Optional[str] = None


@router.post("/qr-auth")
async def authenticate_qr(req: QRAuthRequest, db: AsyncSession = Depends(get_db)):
    """App submits signed challenge to authenticate browser session."""
    r = await _redis()
    data = await r.hgetall(f"polis_qr:{req.session_id}")

    if not data:
        raise HTTPException(410, "Session expired")

    if data.get("status") == "authenticated":
        raise HTTPException(409, "Session already used — generate a new QR code")

    if data.get("status") != "pending":
        raise HTTPException(409, "Session not in pending state")

    challenge = data.get("challenge", "")
    if not challenge:
        raise HTTPException(400, "Invalid session")

    # Validate purpose matches session
    session_purpose = data.get("purpose", "ticket")
    if req.purpose != session_purpose:
        raise HTTPException(403, f"Purpose mismatch: session is '{session_purpose}', request is '{req.purpose}'")

    # Validate bill_id for vote sessions
    session_bill_id = data.get("bill_id") or None
    if session_purpose == "vote":
        if not req.bill_id or req.bill_id != session_bill_id:
            raise HTTPException(403, "bill_id mismatch — this QR is bound to a specific bill")

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

    # Mark session as authenticated (one-time use)
    await r.hset(f"polis_qr:{req.session_id}", mapping={
        "status": "authenticated",
        "nullifier_hash": req.nullifier_hash,
        "public_key_hex": req.public_key_hex,
    })
    # Short TTL for browser to pickup, then auto-expire
    await r.expire(f"polis_qr:{req.session_id}", 60)

    logger.info("QR auth success: session=%s purpose=%s bill=%s",
                req.session_id[:8], session_purpose, session_bill_id or "-")

    return {
        "success": True,
        "session_id": req.session_id,
        "purpose": session_purpose,
        "bill_id": session_bill_id,
    }

"""
POLIS QR-Code Browser Login + Vote Auth
Flow: Browser → QR → App scannt → Ed25519 sign → Browser authenticated

GET  /api/v1/polis/qr-session         — Generate session + challenge
GET  /api/v1/polis/qr-session/{id}    — Poll status (pending/authenticated/expired)
POST /api/v1/polis/qr-auth            — App submits signed challenge
POST /api/v1/polis/qr-vote            — Browser submits vote via authenticated session

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
from services.bill_visibility import is_public_bill
from services.vote_scope import ScopeAction, ensure_bill_scope_allowed
from models import (
    IdentityRecord, KeyStatus, CitizenVote, VoteChoice,
    ParliamentBill, BillStatus,
)


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

_AUTHENTICATE_SESSION_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then
  return -1
end
if redis.call('HGET', KEYS[1], 'status') ~= 'pending' then
  return 0
end
redis.call('HSET', KEYS[1],
  'status', 'authenticated',
  'nullifier_hash', ARGV[1],
  'public_key_hex', ARGV[2])
redis.call('EXPIRE', KEYS[1], 60)
return 1
"""

_CLAIM_SESSION_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then
  return -1
end
if redis.call('HGET', KEYS[1], 'status') ~= 'authenticated' then
  return 0
end
redis.call('HSET', KEYS[1], 'status', 'processing')
return 1
"""

_RESTORE_SESSION_LUA = """
if redis.call('HGET', KEYS[1], 'status') == 'processing' then
  redis.call('HSET', KEYS[1], 'status', 'authenticated')
  return 1
end
return 0
"""


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def _authenticate_session_once(
    redis_client,
    session_key: str,
    nullifier_hash: str,
    public_key_hex: str,
) -> None:
    result = int(await redis_client.eval(
        _AUTHENTICATE_SESSION_LUA,
        1,
        session_key,
        nullifier_hash,
        public_key_hex,
    ))
    if result == -1:
        raise HTTPException(410, "Session expired")
    if result != 1:
        raise HTTPException(409, "Session already used — generate a new QR code")


async def _claim_authenticated_session(redis_client, session_key: str) -> None:
    result = int(await redis_client.eval(_CLAIM_SESSION_LUA, 1, session_key))
    if result == -1:
        raise HTTPException(410, "Session expired — scan QR again")
    if result != 1:
        raise HTTPException(409, "Session is already being processed or was used")


async def _restore_authenticated_session(redis_client, session_key: str) -> None:
    await redis_client.eval(_RESTORE_SESSION_LUA, 1, session_key)


async def _mark_session_used(redis_client, session_key: str) -> None:
    try:
        await redis_client.hset(session_key, mapping={"status": "used"})
        await redis_client.hdel(session_key, "nullifier_hash", "public_key_hex")
        await redis_client.expire(session_key, 60)
    except Exception:
        # The vote is already committed. Leaving the session in "processing"
        # is fail-closed and prevents a duplicate retry.
        logger.exception("Could not finalize consumed QR session %s", session_key[-8:])


@router.get("/qr-session")
async def create_qr_session(
    purpose: Literal["ticket", "vote", "consensus", "forum_login"] = Query("ticket"),
    bill_id: Optional[str] = Query(None),
):
    """Generate a new QR login session with challenge.

    Query params:
      - purpose: ticket | vote | consensus | forum_login
      - bill_id: required when purpose=vote or consensus
    """
    # Validate: vote/consensus requires bill_id
    if purpose in ("vote", "consensus") and not bill_id:
        raise HTTPException(400, "bill_id is required when purpose=vote or consensus")

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
    purpose: Literal["ticket", "vote", "consensus", "forum_login"] = "ticket"
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

    # Validate bill_id for vote/consensus sessions
    session_bill_id = data.get("bill_id") or None
    if session_purpose in ("vote", "consensus"):
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

    # Atomically bind the pending session. Concurrent auth requests cannot
    # overwrite the identity selected by the first valid signature.
    await _authenticate_session_once(
        r,
        f"polis_qr:{req.session_id}",
        req.nullifier_hash,
        req.public_key_hex,
    )

    logger.info("QR auth success: session=%s purpose=%s bill=%s",
                req.session_id[:8], session_purpose, session_bill_id or "-")

    return {
        "success": True,
        "session_id": req.session_id,
        "purpose": session_purpose,
        "bill_id": session_bill_id,
    }


# ─── QR Web Vote ─────────────────────────────────────────────────────────────

class QRVoteRequest(BaseModel):
    session_id: str = Field(..., min_length=10)
    bill_id: str = Field(..., min_length=1)
    vote: str = Field(..., pattern="^(YES|NO|ABSTAIN)$")


@router.post("/qr-vote")
async def qr_web_vote(req: QRVoteRequest, db: AsyncSession = Depends(get_db)):
    """Browser submits vote via an authenticated QR session.

    The session must have purpose=vote, status=authenticated, and matching bill_id.
    Identity was already verified during QR auth (Ed25519 challenge signed by mobile app).
    No additional signature required — the session IS the proof of identity.
    """
    r = await _redis()
    data = await r.hgetall(f"polis_qr:{req.session_id}")

    if not data:
        raise HTTPException(410, "Session expired — scan QR again")

    if data.get("status") != "authenticated":
        raise HTTPException(403, "Session not authenticated")

    if data.get("purpose") != "vote":
        raise HTTPException(400, "Session purpose is not 'vote'")

    session_bill = data.get("bill_id") or ""
    if session_bill != req.bill_id:
        raise HTTPException(403, "bill_id mismatch — this session is bound to another bill")

    nullifier_hash = data.get("nullifier_hash", "")
    if not nullifier_hash:
        raise HTTPException(400, "Session missing identity data")

    # Verify identity is still active
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Identity not found or revoked")

    # Check bill is votable
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == req.bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, f"Bill {req.bill_id} not found")

    votable = [BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END]
    if bill.status not in votable:
        raise HTTPException(400, f"Voting closed. Status: {bill.status.value}")

    ensure_bill_scope_allowed(identity, bill)

    vote_choice = VoteChoice(req.vote)

    # Check for existing vote
    from sqlalchemy.exc import IntegrityError
    existing = await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == nullifier_hash,
            CitizenVote.bill_id == req.bill_id,
        )
    )
    existing_vote = existing.scalar_one_or_none()

    if existing_vote and bill.status == BillStatus.ACTIVE:
        raise HTTPException(409, "Already voted. Correction available during 24h window.")

    session_key = f"polis_qr:{req.session_id}"
    await _claim_authenticated_session(r, session_key)
    try:
        if existing_vote:
            from datetime import datetime, timezone
            existing_vote.vote = vote_choice
            existing_vote.signature_hex = f"qr-session:{req.session_id[:16]}"
            existing_vote.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            msg = "Vote corrected via QR session."
        else:
            new_vote = CitizenVote(
                nullifier_hash=nullifier_hash,
                bill_id=req.bill_id,
                vote=vote_choice,
                signature_hex=f"qr-session:{req.session_id[:16]}",
            )
            db.add(new_vote)
            msg = "Vote submitted via QR session."
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await _restore_authenticated_session(r, session_key)
        raise HTTPException(409, "Already voted (race condition)")
    except Exception:
        await db.rollback()
        await _restore_authenticated_session(r, session_key)
        raise

    await _mark_session_used(r, session_key)

    logger.info("QR web vote: bill=%s vote=%s nullifier=%s...",
                req.bill_id, req.vote, nullifier_hash[:8])

    return {"success": True, "message": msg, "bill_id": req.bill_id, "vote": req.vote}


class QRConsensusRequest(BaseModel):
    session_id: str = Field(..., min_length=10)
    bill_id: str = Field(..., min_length=1)
    score: int = Field(..., ge=-5, le=5)


@router.post("/qr-consensus")
async def qr_web_consensus(req: QRConsensusRequest, db: AsyncSession = Depends(get_db)):
    """Browser submits consensus via an authenticated QR session.

    Same pattern as qr-vote: session IS the proof of identity.
    No Ed25519 signature required — identity verified during QR auth.
    """
    from sqlalchemy import text as sql_text

    r = await _redis()
    data = await r.hgetall(f"polis_qr:{req.session_id}")

    if not data:
        raise HTTPException(410, "Η συνεδρία έληξε — σαρώστε ξανά τον κωδικό QR")

    if data.get("status") != "authenticated":
        raise HTTPException(403, "Η συνεδρία δεν έχει πιστοποιηθεί")

    if data.get("purpose") != "consensus":
        raise HTTPException(400, "Η συνεδρία δεν είναι τύπου consensus")

    session_bill = data.get("bill_id") or ""
    if session_bill != req.bill_id:
        raise HTTPException(403, "Αναντιστοιχία bill_id")

    nullifier_hash = data.get("nullifier_hash", "")
    if not nullifier_hash:
        raise HTTPException(400, "Λείπουν στοιχεία ταυτότητας")

    # Verify identity
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Η ταυτότητα δεν βρέθηκε ή έχει ανακληθεί")

    # Check bill is OPEN_END
    bill = (await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == req.bill_id)
    )).scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, "Το νομοσχέδιο δεν βρέθηκε")
    if bill.status != BillStatus.OPEN_END:
        raise HTTPException(400, "Η συναίνεση είναι δυνατή μόνο για OPEN_END")

    ensure_bill_scope_allowed(identity, bill, action=ScopeAction.CONSENSUS)

    session_key = f"polis_qr:{req.session_id}"
    await _claim_authenticated_session(r, session_key)
    try:
        # Upsert consensus vote
        await db.execute(sql_text("""
            INSERT INTO consensus_votes (nullifier_hash, bill_id, score)
            VALUES (:nullifier, :bill_id, :score)
            ON CONFLICT (nullifier_hash, bill_id)
            DO UPDATE SET score = :score, created_at = NOW()
        """), {"nullifier": nullifier_hash, "bill_id": req.bill_id, "score": req.score})

        # Update aggregate
        agg = await db.execute(sql_text("""
            SELECT AVG(score)::float, COUNT(*) FROM consensus_votes WHERE bill_id = :bill_id
        """), {"bill_id": req.bill_id})
        row = agg.fetchone()
        bill.consensus_score = round(row[0], 2) if row[0] is not None else 0.0
        bill.consensus_count = row[1] or 0

        # Record in cplm_history (same as normal consensus)
        weight = req.score / 5.0
        await db.execute(sql_text("""
            INSERT INTO cplm_history (nullifier_hash, economic_score, social_score, trigger_type, trigger_bill_id)
            VALUES (:nh, :econ, :soc, 'consensus', :bill_id)
        """), {"nh": nullifier_hash, "econ": weight * 0.05, "soc": 0.0, "bill_id": req.bill_id})

        await db.commit()
    except Exception:
        await db.rollback()
        await _restore_authenticated_session(r, session_key)
        raise

    await _mark_session_used(r, session_key)

    logger.info("QR consensus: bill=%s score=%d nullifier=%s...",
                req.bill_id, req.score, nullifier_hash[:8])

    return {
        "success": True,
        "bill_id": req.bill_id,
        "your_score": req.score,
        "consensus_score": bill.consensus_score,
        "consensus_count": bill.consensus_count,
    }

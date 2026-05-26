"""
POLIS Tickets — App-internal ticket system with Ed25519 crypto.
DB-backed, no GitHub account required. Privacy by Design.

Identity binding: pk_polis must be registered against a verified identity
via POST /polis/register-key before tickets/votes are accepted.
"""
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from database import get_db
from crypto.polis import (
    PolisTicketPayload,
    PolisVotePayload,
    validate_ticket,
    validate_ticket_vote,
    get_short_handle,
    hash_content,
    PROTO_VERSION,
    TIMESTAMP_WINDOW_MS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/polis", tags=["POLIS Tickets"])


# ─── Request Models ──────────────────────────────────────────────────────────

class RegisterKeyRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=64, max_length=64)
    pk_polis: str = Field(..., min_length=64, max_length=64)
    identity_signature: str = Field(..., min_length=128, max_length=128)
    timestamp_ms: int


class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    content: str = Field(..., min_length=10, max_length=2000)
    category: Literal["bug", "proposal", "vote"]
    pk_polis: str = Field(..., min_length=64, max_length=64)
    ticket_nullifier: str = Field(..., min_length=64, max_length=64)
    signature: str = Field(..., min_length=128, max_length=128)
    timestamp_ms: int
    nullifier_hash: str = Field(..., min_length=64, max_length=64)


class VoteRequest(BaseModel):
    vote: Literal["up", "down"]
    pk_polis: str = Field(..., min_length=64, max_length=64)
    vote_nullifier: str = Field(..., min_length=64, max_length=64)
    signature: str = Field(..., min_length=128, max_length=128)
    timestamp_ms: int
    nullifier_hash: str = Field(..., min_length=64, max_length=64)


# ─── Identity Binding ────────────────────────────────────────────────────────

async def _verify_registered_key(nullifier_hash: str, pk_polis: str, db: AsyncSession) -> None:
    """Verify pk_polis is registered to this nullifier_hash."""
    result = await db.execute(
        text("SELECT pk_polis FROM polis_identity_keys WHERE nullifier_hash = :nh"),
        {"nh": nullifier_hash},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="UNREGISTERED_KEY: Register your POLIS key first via POST /polis/register-key")
    if row[0] != pk_polis:
        raise HTTPException(status_code=403, detail="KEY_MISMATCH: pk_polis does not match registered key for this identity")

    # Update last_used_at
    await db.execute(
        text("UPDATE polis_identity_keys SET last_used_at = now() WHERE nullifier_hash = :nh"),
        {"nh": nullifier_hash},
    )


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


# ─── POST /polis/register-key ────────────────────────────────────────────────

@router.post("/register-key", status_code=201)
async def register_polis_key(
    req: RegisterKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register pk_polis against a verified identity. Signed by identity key."""
    # 1. Look up identity
    result = await db.execute(
        text("SELECT public_key_hex, status FROM identity_records WHERE nullifier_hash = :nh"),
        {"nh": req.nullifier_hash},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="UNVERIFIED_IDENTITY: No verified identity found")
    identity_pk_hex, status = row[0], row[1]
    if status != "ACTIVE":
        raise HTTPException(status_code=403, detail="REVOKED_IDENTITY: Identity is not active")

    # 2. Timestamp freshness
    delta = abs(_now_ms() - req.timestamp_ms)
    if delta > TIMESTAMP_WINDOW_MS:
        raise HTTPException(status_code=400, detail="TIMESTAMP_EXPIRED: Request too old")

    # 3. Verify identity_signature
    message = f"polis-register:{req.pk_polis}:{req.nullifier_hash}:{req.timestamp_ms}".encode("utf-8")
    try:
        vk = VerifyKey(bytes.fromhex(identity_pk_hex))
        vk.verify(message, bytes.fromhex(req.identity_signature))
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="INVALID_SIGNATURE: Identity signature verification failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CRYPTO_ERROR: {type(e).__name__}")

    # 4. Insert or idempotent check
    existing = await db.execute(
        text("SELECT pk_polis FROM polis_identity_keys WHERE nullifier_hash = :nh"),
        {"nh": req.nullifier_hash},
    )
    existing_row = existing.fetchone()

    if existing_row:
        if existing_row[0] == req.pk_polis:
            # Idempotent — same key, update last_used
            await db.execute(
                text("UPDATE polis_identity_keys SET last_used_at = now() WHERE nullifier_hash = :nh"),
                {"nh": req.nullifier_hash},
            )
            await db.commit()
            return {"status": "already_registered", "handle": get_short_handle(req.pk_polis)}
        else:
            raise HTTPException(status_code=409, detail="KEY_CONFLICT: Different pk_polis already registered for this identity")

    # Check reverse: pk_polis already used by different nullifier
    reverse = await db.execute(
        text("SELECT nullifier_hash FROM polis_identity_keys WHERE pk_polis = :pk"),
        {"pk": req.pk_polis},
    )
    if reverse.fetchone():
        raise HTTPException(status_code=409, detail="KEY_CONFLICT: This pk_polis is already registered to a different identity")

    try:
        await db.execute(text("""
            INSERT INTO polis_identity_keys (nullifier_hash, pk_polis, signature, timestamp_ms)
            VALUES (:nh, :pk, :sig, :ts)
        """), {
            "nh": req.nullifier_hash,
            "pk": req.pk_polis,
            "sig": req.identity_signature,
            "ts": req.timestamp_ms,
        })
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="KEY_CONFLICT: Registration conflict")

    logger.info("[POLIS] Key registered: %s → %s", req.nullifier_hash[:8], get_short_handle(req.pk_polis))
    return {"status": "registered", "handle": get_short_handle(req.pk_polis)}


# ─── GET /polis/tickets ──────────────────────────────────────────────────────

@router.get("/tickets")
async def list_tickets(
    category: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List POLIS tickets. Public, no auth required."""
    query = "SELECT id, title, category, pk_polis, status, up_votes, down_votes, created_at FROM polis_tickets"
    conditions = []
    params = {}

    if category:
        conditions.append("category = :category")
        params["category"] = category
    if status:
        conditions.append("status = :status")
        params["status"] = status

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT 100"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "tickets": [
            {
                "id": r[0],
                "title": r[1],
                "category": r[2],
                "handle": get_short_handle(r[3]),
                "status": r[4],
                "up_votes": r[5],
                "down_votes": r[6],
                "created_at": r[7].isoformat() if hasattr(r[7], 'isoformat') else str(r[7]) if r[7] else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ─── POST /polis/tickets ────────────────────────────────────────────────────

@router.post("/tickets", status_code=201)
async def create_ticket(
    req: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a POLIS ticket with Ed25519 signed payload. Requires registered pk_polis."""
    # Verify registered key binding
    await _verify_registered_key(req.nullifier_hash, req.pk_polis, db)

    # Build validation payload — title is required and signed
    if not req.title or not req.title.strip():
        raise HTTPException(status_code=400, detail="INVALID_TITLE: Title is required")

    payload = PolisTicketPayload(
        content=req.content,
        category=req.category,
        pk_polis=req.pk_polis,
        ticket_nullifier=req.ticket_nullifier,
        signature=req.signature,
        timestamp_ms=req.timestamp_ms,
        version=PROTO_VERSION,
        title=req.title,
    )

    # Get existing nullifiers
    result = await db.execute(text("SELECT ticket_nullifier FROM polis_tickets"))
    existing = {r[0] for r in result.fetchall()}

    # Validate (includes signature check with title hash)
    err = validate_ticket(payload, existing)
    if err:
        raise HTTPException(status_code=400, detail=f"{err.code}: {err.message}")

    # Insert
    ticket_id = str(uuid.uuid4())[:12]
    try:
        await db.execute(text("""
            INSERT INTO polis_tickets (id, title, content, category, pk_polis, ticket_nullifier, signature, timestamp_ms)
            VALUES (:id, :title, :content, :category, :pk_polis, :nullifier, :signature, :ts)
        """), {
            "id": ticket_id,
            "title": req.title,
            "content": req.content,
            "category": req.category,
            "pk_polis": req.pk_polis,
            "nullifier": req.ticket_nullifier,
            "signature": req.signature,
            "ts": req.timestamp_ms,
        })
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_TICKET: Ticket already exists")

    logger.info("[POLIS] Ticket created: %s by %s", ticket_id, get_short_handle(req.pk_polis))
    return {"id": ticket_id, "handle": get_short_handle(req.pk_polis), "status": "pending"}


# ─── POST /polis/tickets/{ticket_id}/votes ───────────────────────────────────

@router.post("/tickets/{ticket_id}/votes", status_code=201)
async def vote_ticket(
    ticket_id: str,
    req: VoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Vote on a POLIS ticket with Ed25519 signed payload. Requires registered pk_polis."""
    # Verify registered key binding
    await _verify_registered_key(req.nullifier_hash, req.pk_polis, db)

    # Get ticket
    result = await db.execute(
        text("SELECT id, pk_polis FROM polis_tickets WHERE id = :id"),
        {"id": ticket_id},
    )
    ticket = result.fetchone()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_owner_pk = ticket[1]

    # Build validation payload
    payload = PolisVotePayload(
        ticket_id=ticket_id,
        vote=req.vote,
        pk_polis=req.pk_polis,
        vote_nullifier=req.vote_nullifier,
        signature=req.signature,
        timestamp_ms=req.timestamp_ms,
        version=PROTO_VERSION,
    )

    # Get existing vote nullifiers for this ticket
    result = await db.execute(
        text("SELECT vote_nullifier FROM polis_votes WHERE ticket_id = :tid"),
        {"tid": ticket_id},
    )
    existing = {r[0] for r in result.fetchall()}

    # Validate
    err = validate_ticket_vote(payload, existing, ticket_owner_pk)
    if err:
        raise HTTPException(status_code=400, detail=f"{err.code}: {err.message}")

    # Insert vote
    vote_id = str(uuid.uuid4())[:12]
    try:
        await db.execute(text("""
            INSERT INTO polis_votes (id, ticket_id, vote, pk_polis, vote_nullifier, signature, timestamp_ms)
            VALUES (:id, :tid, :vote, :pk, :nullifier, :sig, :ts)
        """), {
            "id": vote_id,
            "tid": ticket_id,
            "vote": req.vote,
            "pk": req.pk_polis,
            "nullifier": req.vote_nullifier,
            "sig": req.signature,
            "ts": req.timestamp_ms,
        })

        col = "up_votes" if req.vote == "up" else "down_votes"
        await db.execute(
            text(f"UPDATE polis_tickets SET {col} = {col} + 1, updated_at = now() WHERE id = :id"),
            {"id": ticket_id},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_VOTE: Already voted on this ticket")

    logger.info("[POLIS] Vote %s on ticket %s by %s", req.vote, ticket_id, get_short_handle(req.pk_polis))
    return {"vote_id": vote_id, "vote": req.vote}

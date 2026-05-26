"""
POLIS Tickets — App-internal ticket system with Ed25519 crypto.
DB-backed, no GitHub account required. Privacy by Design.
"""
import hashlib
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from crypto.polis import (
    PolisTicketPayload,
    PolisVotePayload,
    validate_ticket,
    validate_ticket_vote,
    get_short_handle,
    hash_content,
    PROTO_VERSION,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/polis", tags=["POLIS Tickets"])


# ─── Request / Response Models ───────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    content: str = Field(..., min_length=10, max_length=2000)
    category: Literal["bug", "proposal", "vote"]
    pk_polis: str = Field(..., min_length=64, max_length=64)
    ticket_nullifier: str = Field(..., min_length=64, max_length=64)
    signature: str = Field(..., min_length=128, max_length=128)
    timestamp_ms: int


class VoteRequest(BaseModel):
    vote: Literal["up", "down"]
    pk_polis: str = Field(..., min_length=64, max_length=64)
    vote_nullifier: str = Field(..., min_length=64, max_length=64)
    signature: str = Field(..., min_length=128, max_length=128)
    timestamp_ms: int


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
                "created_at": r[7].isoformat() if r[7] else None,
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
    """Create a POLIS ticket with Ed25519 signed payload."""
    # Build validation payload
    payload = PolisTicketPayload(
        content=req.content,
        category=req.category,
        pk_polis=req.pk_polis,
        ticket_nullifier=req.ticket_nullifier,
        signature=req.signature,
        timestamp_ms=req.timestamp_ms,
        version=PROTO_VERSION,
    )

    # Get existing nullifiers
    result = await db.execute(text("SELECT ticket_nullifier FROM polis_tickets"))
    existing = {r[0] for r in result.fetchall()}

    # Validate
    err = validate_ticket(payload, existing)
    if err:
        raise HTTPException(status_code=400, detail=f"{err.code}: {err.message}")

    # Insert
    ticket_id = str(uuid.uuid4())[:12]
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

    logger.info("[POLIS] Ticket created: %s by %s", ticket_id, get_short_handle(req.pk_polis))
    return {
        "id": ticket_id,
        "handle": get_short_handle(req.pk_polis),
        "status": "pending",
    }


# ─── POST /polis/tickets/{ticket_id}/votes ───────────────────────────────────

@router.post("/tickets/{ticket_id}/votes", status_code=201)
async def vote_ticket(
    ticket_id: str,
    req: VoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Vote on a POLIS ticket with Ed25519 signed payload."""
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

    # Update vote counts
    col = "up_votes" if req.vote == "up" else "down_votes"
    await db.execute(
        text(f"UPDATE polis_tickets SET {col} = {col} + 1, updated_at = now() WHERE id = :id"),
        {"id": ticket_id},
    )
    await db.commit()

    logger.info("[POLIS] Vote %s on ticket %s by %s", req.vote, ticket_id, get_short_handle(req.pk_polis))
    return {"vote_id": vote_id, "vote": req.vote}

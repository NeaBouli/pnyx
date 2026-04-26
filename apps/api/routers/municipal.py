"""
MOD-16: Municipal Governance Router — Active (325 dimoi operational)
GET /api/v1/periferia              — All 13 regions
GET /api/v1/periferia/{id}/dimos   — Municipalities of a region (325 total)
GET /api/v1/decisions              — Decisions (filter by level, periferia_id, dimos_id, status)
"""
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import (
    Periferia, Dimos, Decision, GovernanceLevel, BillStatus,
    DiavgeiaDecision, DiavgeiaVote, IdentityRecord, KeyStatus, VoteChoice,
)

router = APIRouter(prefix="/api/v1", tags=["MOD-16 Municipal"])


# ─── GET /api/v1/periferia ────────────────────────────────────────────────────

@router.get("/periferia")
async def list_periferies(
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
):
    """List all Periferies (Regions) of Greece."""
    stmt = select(Periferia)
    if is_active is not None:
        stmt = stmt.where(Periferia.is_active == is_active)
    stmt = stmt.order_by(Periferia.name_el)
    result = await db.execute(stmt)
    return [
        {
            "id": r.id,
            "name_el": r.name_el,
            "name_en": r.name_en,
            "code": r.code,
            "is_active": r.is_active,
        }
        for r in result.scalars().all()
    ]


# ─── GET /api/v1/periferia/{id}/dimos ─────────────────────────────────────────

@router.get("/periferia/{periferia_id}/dimos")
async def list_dimos_by_periferia(
    periferia_id: int,
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
):
    """List all Dimos (Municipalities) within a Periferia."""
    periferia = await db.get(Periferia, periferia_id)
    if not periferia:
        raise HTTPException(status_code=404, detail="Periferia not found")

    stmt = select(Dimos).where(Dimos.periferia_id == periferia_id)
    if is_active is not None:
        stmt = stmt.where(Dimos.is_active == is_active)
    stmt = stmt.order_by(Dimos.name_el)
    result = await db.execute(stmt)
    return [
        {
            "id": r.id,
            "name_el": r.name_el,
            "name_en": r.name_en,
            "periferia_id": r.periferia_id,
            "population": r.population,
            "is_active": r.is_active,
        }
        for r in result.scalars().all()
    ]


# ─── GET /api/v1/decisions ────────────────────────────────────────────────────

@router.get("/decisions")
async def list_decisions(
    level: Optional[GovernanceLevel] = Query(None, description="Filter by governance level"),
    periferia_id: Optional[int] = Query(None, description="Filter by Periferia ID"),
    dimos_id: Optional[int] = Query(None, description="Filter by Dimos ID"),
    status: Optional[BillStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    List Decisions (municipal/regional/national) with filters.
    Supports filtering by governance level, periferia, dimos, and status.
    """
    stmt = select(Decision)

    if level is not None:
        stmt = stmt.where(Decision.level == level)
    if periferia_id is not None:
        stmt = stmt.where(Decision.periferia_id == periferia_id)
    if dimos_id is not None:
        stmt = stmt.where(Decision.dimos_id == dimos_id)
    if status is not None:
        stmt = stmt.where(Decision.status == status)

    stmt = stmt.order_by(Decision.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "title_el": r.title_el,
            "title_en": r.title_en,
            "pill_el": r.pill_el,
            "pill_en": r.pill_en,
            "summary_short_el": r.summary_short_el,
            "summary_short_en": r.summary_short_en,
            "level": r.level.value if r.level else None,
            "periferia_id": r.periferia_id,
            "dimos_id": r.dimos_id,
            "community_id": r.community_id,
            "categories": r.categories,
            "authority_votes": r.authority_votes,
            "status": r.status.value if r.status else None,
            "vote_date": r.vote_date.isoformat() if r.vote_date else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ─── Voteable Decisions ──────────────────────────────────────────────────────

@router.get("/municipal/{dimos_id}/voteable")
async def get_voteable_decisions(
    dimos_id: int,
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Diavgeia decisions for a specific Dimos that can be voted on."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(DiavgeiaDecision)
        .where(
            DiavgeiaDecision.dimos_id == dimos_id,
            DiavgeiaDecision.publish_timestamp >= cutoff,
        )
        .order_by(DiavgeiaDecision.publish_timestamp.desc())
        .limit(20)
    )
    decisions = result.scalars().all()

    items = []
    for d in decisions:
        # Get vote counts
        yes_c = await db.scalar(select(func.count()).where(DiavgeiaVote.ada == d.ada, DiavgeiaVote.vote == VoteChoice.YES)) or 0
        no_c = await db.scalar(select(func.count()).where(DiavgeiaVote.ada == d.ada, DiavgeiaVote.vote == VoteChoice.NO)) or 0
        abs_c = await db.scalar(select(func.count()).where(DiavgeiaVote.ada == d.ada, DiavgeiaVote.vote == VoteChoice.ABSTAIN)) or 0
        total = yes_c + no_c + abs_c

        items.append({
            "ada": d.ada,
            "subject": d.subject,
            "organization_label": d.organization_label,
            "dimos_id": d.dimos_id,
            "decision_type_uid": d.decision_type_uid,
            "issue_date": d.publish_timestamp.isoformat() if d.publish_timestamp else None,
            "document_url": d.document_url,
            "governance_level": "MUNICIPAL",
            "votes": {"yes": yes_c, "no": no_c, "abstain": abs_c, "total": total},
        })

    return {"dimos_id": dimos_id, "decisions": items, "count": len(items)}


class DecisionVoteRequest(BaseModel):
    ada: str
    nullifier_hash: str
    vote: str  # YES / NO / ABSTAIN


@router.post("/municipal/vote")
async def vote_on_decision(req: DecisionVoteRequest, db: AsyncSession = Depends(get_db)):
    """Cast a vote on a Diavgeia municipal decision."""
    # 1. Verify identity
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Nicht verifiziert oder Key revoziert.")

    # 2. Check decision exists
    dec_result = await db.execute(
        select(DiavgeiaDecision).where(DiavgeiaDecision.ada == req.ada)
    )
    decision = dec_result.scalar_one_or_none()
    if not decision:
        raise HTTPException(404, f"Decision {req.ada} nicht gefunden.")

    # 3. Vote scope: user must be in same dimos
    if decision.dimos_id and identity.dimos_id != decision.dimos_id:
        raise HTTPException(403, "Αυτή η απόφαση αφορά μόνο κατοίκους αυτού του Δήμου.")

    # 4. Parse vote
    try:
        vote_choice = VoteChoice(req.vote.upper())
    except ValueError:
        raise HTTPException(400, f"Ungültige Stimme: {req.vote}")

    # 5. Check duplicate
    existing = await db.execute(
        select(DiavgeiaVote).where(
            DiavgeiaVote.ada == req.ada,
            DiavgeiaVote.nullifier_hash == req.nullifier_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Έχετε ήδη ψηφίσει για αυτή την απόφαση.")

    # 6. Cast vote
    vote = DiavgeiaVote(ada=req.ada, nullifier_hash=req.nullifier_hash, vote=vote_choice)
    db.add(vote)
    await db.commit()

    return {"success": True, "ada": req.ada, "vote": vote_choice.value}

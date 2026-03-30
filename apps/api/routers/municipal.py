"""
MOD-16: Municipal Governance Router — Stub
GET /api/v1/periferia              — All regions (filterable)
GET /api/v1/periferia/{id}/dimos   — Municipalities of a region
GET /api/v1/decisions              — Decisions (filter by level, periferia_id, dimos_id, status)
@status: STUB — Phase Beta+
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Periferia, Dimos, Decision, GovernanceLevel, BillStatus

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

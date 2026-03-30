"""
MOD-16: Municipal Governance Router
GET /api/v1/periferia              — All regions
GET /api/v1/periferia/{id}/dimos   — Municipalities of region
GET /api/v1/decisions              — All decisions (filter by level/periferia/dimos)
@status: STUB — Phase Beta+
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Periferia, Dimos, Decision, GovernanceLevel

router = APIRouter(prefix="/api/v1", tags=["MOD-16 Municipal"])


@router.get("/periferia")
async def get_periferia(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Periferia).where(Periferia.is_active == True))
    return [{"id": p.id, "name_el": p.name_el, "name_en": p.name_en, "code": p.code}
            for p in result.scalars().all()]


@router.get("/periferia/{periferia_id}/dimos")
async def get_dimos(periferia_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dimos).where(Dimos.periferia_id == periferia_id, Dimos.is_active == True)
    )
    return [{"id": d.id, "name_el": d.name_el, "name_en": d.name_en} for d in result.scalars().all()]


@router.get("/decisions")
async def get_decisions(
    level: str | None = Query(None),
    periferia_id: int | None = Query(None),
    dimos_id: int | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    query = select(Decision).order_by(Decision.created_at.desc()).limit(limit).offset(offset)
    if level:
        query = query.where(Decision.level == GovernanceLevel(level.upper()))
    if periferia_id:
        query = query.where(Decision.periferia_id == periferia_id)
    if dimos_id:
        query = query.where(Decision.dimos_id == dimos_id)
    result = await db.execute(query)
    return [{
        "id": d.id, "title_el": d.title_el, "level": d.level.value,
        "status": d.status.value, "periferia_id": d.periferia_id, "dimos_id": d.dimos_id,
    } for d in result.scalars().all()]

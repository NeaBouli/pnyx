"""
MOD-21: Diavgeia Integration Router
POST /api/v1/admin/diavgeia/scrape  — Manual trigger (admin-only)
GET  /api/v1/municipal/{dimos_id}/decisions  — Diavgeia decisions for a municipality
GET  /api/v1/regions/{periferia_id}/decisions — Diavgeia decisions for a region
"""
import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DiavgeiaDecision, DimosDiavgeiaOrg, Dimos, Periferia

logger = logging.getLogger(__name__)
router = APIRouter(tags=["MOD-21 Diavgeia"])

ADMIN_KEY = os.environ.get("ADMIN_KEY", "dev-admin-key")


def verify_admin(admin_key: str = Query(...)) -> str:
    if admin_key != ADMIN_KEY:
        raise HTTPException(403, "Ungültiger Admin-Key")
    return admin_key


# ─── Schemas ────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    decision_type_uids: Optional[list[str]] = None
    published_after: Optional[datetime] = None
    max_pages: int = 10
    dry_run: bool = False


# ─── POST /api/v1/admin/diavgeia/scrape ─────────────────────────────────────

@router.post("/api/v1/admin/diavgeia/scrape")
async def admin_scrape_diavgeia(
    req: ScrapeRequest,
    _key: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger Diavgeia scrape. Admin-only."""
    from services.diavgeia_scraper import scrape_decisions

    result = await scrape_decisions(
        session=db,
        decision_type_uids=req.decision_type_uids,
        published_after=req.published_after,
        max_pages=req.max_pages,
        dry_run=req.dry_run,
    )
    return result.to_dict()


# ─── GET /api/v1/municipal/{dimos_id}/decisions ─────────────────────────────

@router.get("/api/v1/municipal/{dimos_id}/decisions")
async def list_municipal_decisions(
    dimos_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    decision_type_uid: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List Diavgeia decisions for a municipality."""
    dimos = await db.get(Dimos, dimos_id)
    if not dimos:
        raise HTTPException(404, "Dimos not found")

    stmt = (
        select(DiavgeiaDecision)
        .where(DiavgeiaDecision.dimos_id == dimos_id)
    )
    if decision_type_uid:
        stmt = stmt.where(DiavgeiaDecision.decision_type_uid == decision_type_uid)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(DiavgeiaDecision.publish_timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "dimos_id": dimos_id,
        "dimos_name_el": dimos.name_el,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "ada": r.ada,
                "subject": r.subject,
                "decision_type_uid": r.decision_type_uid,
                "decision_type_label": r.decision_type_label,
                "organization_label": r.organization_label,
                "document_url": r.document_url,
                "publish_timestamp": r.publish_timestamp.isoformat() if r.publish_timestamp else None,
            }
            for r in rows
        ],
    }


# ─── GET /api/v1/regions/{periferia_id}/decisions ───────────────────────────

@router.get("/api/v1/regions/{periferia_id}/decisions")
async def list_regional_decisions(
    periferia_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    decision_type_uid: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List Diavgeia decisions for a region (all municipalities within)."""
    periferia = await db.get(Periferia, periferia_id)
    if not periferia:
        raise HTTPException(404, "Periferia not found")

    stmt = (
        select(DiavgeiaDecision)
        .where(DiavgeiaDecision.periferia_id == periferia_id)
    )
    if decision_type_uid:
        stmt = stmt.where(DiavgeiaDecision.decision_type_uid == decision_type_uid)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(DiavgeiaDecision.publish_timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "periferia_id": periferia_id,
        "periferia_name_el": periferia.name_el,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "ada": r.ada,
                "subject": r.subject,
                "decision_type_uid": r.decision_type_uid,
                "decision_type_label": r.decision_type_label,
                "organization_label": r.organization_label,
                "document_url": r.document_url,
                "publish_timestamp": r.publish_timestamp.isoformat() if r.publish_timestamp else None,
                "dimos_id": r.dimos_id,
            }
            for r in rows
        ],
    }

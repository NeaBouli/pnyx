"""
CPLM — Citizens Political Liquid Mirror
GET /api/v1/cplm/aggregate  — Current societal X/Y position
GET /api/v1/cplm/history    — Historical snapshots
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.cplm import get_cplm_cached, get_cplm_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cplm", tags=["CPLM"])


@router.get("/aggregate")
async def cplm_aggregate(db: AsyncSession = Depends(get_db)):
    """Current aggregate political position of all citizens."""
    return await get_cplm_cached(db)


@router.get("/history")
async def cplm_history_endpoint(days: int = Query(30, ge=1, le=365)):
    """Historical CPLM snapshots."""
    entries = await get_cplm_history(days)
    return {"snapshots": entries, "count": len(entries)}

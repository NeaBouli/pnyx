"""
CPLM — Citizens Political Liquid Mirror
GET /api/v1/cplm/aggregate  — Current societal X/Y position
GET /api/v1/cplm/history    — Historical snapshots

Counts only votes whose results are visible (closed votes, or bills that publish results during the
vote); votes of a running vote with hidden results are not included.
"""
from rate_limit import enforce_route_limit, public_heavy
import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.cplm import get_cplm_cached, get_cplm_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cplm", tags=["CPLM"])


@router.get("/aggregate", dependencies=[Depends(enforce_route_limit)])
@public_heavy
async def cplm_aggregate(db: AsyncSession = Depends(get_db), request: Request = None):
    """Current aggregate political position of all citizens.

    Counts only completed votes and votes whose results are already visible.
    """
    return await get_cplm_cached(db)


@router.get("/history", dependencies=[Depends(enforce_route_limit)])
@public_heavy
async def cplm_history_endpoint(days: int = Query(30, ge=1, le=365), request: Request = None,
                                db: AsyncSession = Depends(get_db)):
    """Historical CPLM snapshots."""
    entries = await get_cplm_history(days, db=db)
    return {"snapshots": entries, "count": len(entries)}

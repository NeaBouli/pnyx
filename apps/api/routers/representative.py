"""
εκπρόσωπος API — Volksvertreter Live-Ergebnisse
Verifizierung via Diavgeia ADA-Nummer.
Zugang nur zu WINDOW_24H / PARLIAMENT_VOTED / OPEN_END Bills.
"""
import os
import secrets
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import ParliamentBill, BillStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rep", tags=["Representative"])

TOKEN_TTL_HOURS = 24
ALLOWED_STATUSES = [BillStatus.WINDOW_24H, BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END]


class VerifyRequest(BaseModel):
    ada_number: str = Field(..., min_length=5, max_length=50)


class AuthRequest(BaseModel):
    ada_number: str = Field(..., min_length=5)
    token: str = Field(..., min_length=10)


async def _verify_ada_diavgeia(ada: str) -> dict | None:
    """Check if ADA exists in Diavgeia and return org info."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://diavgeia.gov.gr/opendata/decisions/{ada}.json")
            if r.status_code == 200:
                d = r.json()
                return {
                    "subject": d.get("subject", ""),
                    "organization": d.get("organizationId", ""),
                    "org_label": d.get("organizationLabel", ""),
                    "type": d.get("decisionTypeId", ""),
                }
    except Exception as e:
        logger.warning("[REP] Diavgeia check failed for %s: %s", ada, e)
    return None


async def _get_rep_token(token: str, db: AsyncSession) -> dict | None:
    """Validate representative token."""
    result = await db.execute(text(
        "SELECT ada_number, role, party, region, org_label, expires_at FROM representative_tokens "
        "WHERE token = :token AND expires_at > NOW()"
    ), {"token": token})
    row = result.fetchone()
    if not row:
        return None
    return {"ada_number": row[0], "role": row[1], "party": row[2],
            "region": row[3], "org_label": row[4], "expires_at": row[5]}


async def verify_rep_token(
    authorization: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency: validate Bearer token for representative."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization[7:]
    rep = await _get_rep_token(token, db)
    if not rep:
        raise HTTPException(401, "Invalid or expired token")
    return rep


@router.post("/verify")
async def verify_representative(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify representative via Diavgeia ADA number. Returns a 24h token."""
    ada_info = await _verify_ada_diavgeia(req.ada_number)
    if not ada_info:
        raise HTTPException(403, "ADA not found in Diavgeia — verification failed")

    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    await db.execute(text("""
        INSERT INTO representative_tokens (ada_number, token, role, org_label, expires_at)
        VALUES (:ada, :token, 'representative', :org_label, :expires)
        ON CONFLICT (ada_number) DO UPDATE SET token = :token, expires_at = :expires, org_label = :org_label
    """), {"ada": req.ada_number, "token": token, "org_label": ada_info.get("org_label", ""),
           "expires": expires.replace(tzinfo=None)})
    await db.commit()

    return {
        "ada_number": req.ada_number,
        "token": token,
        "expires_at": expires.isoformat(),
        "org_label": ada_info.get("org_label", ""),
        "subject": ada_info.get("subject", "")[:100],
    }


@router.post("/auth")
async def auth_representative(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with ADA + token."""
    rep = await _get_rep_token(req.token, db)
    if not rep or rep["ada_number"] != req.ada_number:
        raise HTTPException(401, "Invalid credentials")
    return {"authenticated": True, **rep}


@router.get("/bills")
async def get_rep_bills(
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Bills visible to representatives: WINDOW_24H, PARLIAMENT_VOTED, OPEN_END."""
    result = await db.execute(
        select(ParliamentBill)
        .where(ParliamentBill.status.in_(ALLOWED_STATUSES))
        .order_by(ParliamentBill.parliament_vote_date.desc().nullslast())
        .limit(50)
    )
    bills = result.scalars().all()
    return [{
        "id": b.id, "title_el": b.title_el, "status": b.status.value,
        "governance_level": b.governance_level.value if b.governance_level else "NATIONAL",
        "parliament_vote_date": b.parliament_vote_date.isoformat() if b.parliament_vote_date else None,
        "consensus_score": b.consensus_score, "consensus_count": b.consensus_count or 0,
    } for b in bills]


@router.get("/results/{bill_id}")
async def get_rep_results(
    bill_id: str,
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Detailed results for representatives including hourly timeline."""
    bill = (await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )).scalar_one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill.status not in ALLOWED_STATUSES:
        raise HTTPException(403, "Results not yet available for this bill status")

    # Vote counts
    counts = await db.execute(text("""
        SELECT vote, COUNT(*) FROM citizen_votes WHERE bill_id = :bid GROUP BY vote
    """), {"bid": bill_id})
    vote_map = {r[0]: r[1] for r in counts}
    yes = vote_map.get("YES", 0)
    no = vote_map.get("NO", 0)
    abstain = vote_map.get("ABSTAIN", 0)
    total = yes + no + abstain

    # Hourly timeline (last 48h)
    timeline = await db.execute(text("""
        SELECT date_trunc('hour', created_at) as hour, vote, COUNT(*)
        FROM citizen_votes WHERE bill_id = :bid AND created_at > NOW() - INTERVAL '48 hours'
        GROUP BY hour, vote ORDER BY hour
    """), {"bid": bill_id})
    hourly = {}
    for hour, vote, count in timeline:
        h = hour.isoformat() if hour else "?"
        if h not in hourly:
            hourly[h] = {"hour": h, "yes": 0, "no": 0, "abstain": 0}
        hourly[h][vote.lower()] = count

    return {
        "bill_id": bill_id, "title_el": bill.title_el, "status": bill.status.value,
        "yes": yes, "no": no, "abstain": abstain, "total": total,
        "yes_pct": round(yes / total * 100, 1) if total else 0,
        "no_pct": round(no / total * 100, 1) if total else 0,
        "consensus_score": bill.consensus_score,
        "consensus_count": bill.consensus_count or 0,
        "party_votes": bill.party_votes_parliament,
        "timeline": list(hourly.values()),
    }


@router.get("/divergence/{bill_id}")
async def get_rep_divergence(
    bill_id: str,
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Divergence analysis: citizens vs parliament by governance level."""
    bill = (await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )).scalar_one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found")

    counts = await db.execute(text("""
        SELECT vote, COUNT(*) FROM citizen_votes WHERE bill_id = :bid GROUP BY vote
    """), {"bid": bill_id})
    vote_map = {r[0]: r[1] for r in counts}
    yes = vote_map.get("YES", 0)
    no = vote_map.get("NO", 0)
    total = yes + no
    citizen_yes_pct = round(yes / total * 100, 1) if total else 0

    # Parliament result
    pv = bill.party_votes_parliament or {}
    parl_yes = sum(1 for v in pv.values() if v in ("ΝΑΙ", "YES"))
    parl_no = sum(1 for v in pv.values() if v in ("ΟΧΙ", "NO"))
    parl_total = parl_yes + parl_no
    parl_yes_pct = round(parl_yes / parl_total * 100, 1) if parl_total else 0

    divergence = abs(citizen_yes_pct - parl_yes_pct) if total and parl_total else None

    return {
        "bill_id": bill_id, "title_el": bill.title_el,
        "citizen": {"yes_pct": citizen_yes_pct, "total": total},
        "parliament": {"yes_pct": parl_yes_pct, "total": parl_total, "parties": pv},
        "divergence_pct": divergence,
        "governance_level": bill.governance_level.value if bill.governance_level else "NATIONAL",
    }

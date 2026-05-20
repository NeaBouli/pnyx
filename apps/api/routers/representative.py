"""
εκπρόσωπος API — Volksvertreter Live-Ergebnisse
Verifizierung via Diavgeia ADA-Nummer + Admin Invite-Code.
Zugang nur zu WINDOW_24H / PARLIAMENT_VOTED / OPEN_END Bills.
"""
import os
import secrets
import string
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import verify_admin_key
from models import ParliamentBill, BillStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rep", tags=["Representative"])

TOKEN_TTL_HOURS = 24
INVITE_TTL_HOURS = 48
ALLOWED_STATUSES = [BillStatus.WINDOW_24H, BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END]

VALID_ROLES = ["Βουλευτής", "Περιφερειάρχης", "Δήμαρχος", "Δημοτικός Σύμβουλος"]


def _generate_invite_code() -> str:
    """Generate XXXX-XXXX invite code."""
    chars = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"{part1}-{part2}"


# ─── Schemas ──────────────────────────────────────────────────────────────────


class InviteRequest(BaseModel):
    role: str = Field(..., description="Βουλευτής / Περιφερειάρχης / Δήμαρχος / Δημοτικός Σύμβουλος")
    region: str | None = None
    municipality: str | None = None


class VerifyRequest(BaseModel):
    ada_number: str = Field(..., min_length=5, max_length=50)
    invite_code: str = Field(..., min_length=9, max_length=9, description="Format: XXXX-XXXX")


class AuthRequest(BaseModel):
    ada_number: str = Field(..., min_length=5)
    token: str = Field(..., min_length=10)


def _verify_admin(key: bool = Depends(verify_admin_key)):
    return key


# ─── Admin Endpoints ─────────────────────────────────────────────────────────


@router.post("/admin/invite")
async def create_invite(
    req: InviteRequest,
    _auth=Depends(_verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: Generate invite code for a representative."""
    if req.role not in VALID_ROLES:
        raise HTTPException(400, f"Μη έγκυρος ρόλος. Επιτρέπεται: {', '.join(VALID_ROLES)}")

    code = _generate_invite_code()
    expires = datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)

    await db.execute(text("""
        INSERT INTO rep_invitations (invite_code, role, region, municipality, expires_at)
        VALUES (:code, :role, :region, :municipality, :expires)
    """), {
        "code": code, "role": req.role,
        "region": req.region, "municipality": req.municipality,
        "expires": expires.replace(tzinfo=None),
    })
    await db.commit()

    logger.info("[REP] Invite created: %s role=%s region=%s", code, req.role, req.region)
    return {
        "invite_code": code,
        "role": req.role,
        "region": req.region,
        "municipality": req.municipality,
        "expires_at": expires.isoformat(),
    }


@router.get("/admin/invites")
async def list_invites(
    _auth=Depends(_verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: List all invite codes."""
    result = await db.execute(text(
        "SELECT id, invite_code, ada_number, role, region, municipality, used, expires_at, created_at "
        "FROM rep_invitations ORDER BY created_at DESC LIMIT 100"
    ))
    rows = result.fetchall()
    return [{
        "id": r[0], "invite_code": r[1], "ada_number": r[2], "role": r[3],
        "region": r[4], "municipality": r[5], "used": r[6],
        "expired": r[7] < datetime.now() if r[7] else False,
        "expires_at": r[7].isoformat() if r[7] else None,
        "created_at": r[8].isoformat() if r[8] else None,
    } for r in rows]


# ─── Diavgeia ────────────────────────────────────────────────────────────────


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
    """Verify representative via ADA number + admin invite code. Returns a 24h token."""
    # 1. Validate invite code
    inv_result = await db.execute(text(
        "SELECT id, role, region, municipality, used, expires_at FROM rep_invitations "
        "WHERE invite_code = :code"
    ), {"code": req.invite_code})
    invite = inv_result.fetchone()

    if not invite:
        raise HTTPException(403, "Μη έγκυρος κωδικός πρόσκλησης.")
    if invite[4]:  # used
        raise HTTPException(403, "Ο κωδικός πρόσκλησης έχει ήδη χρησιμοποιηθεί.")
    if invite[5] and invite[5] < datetime.now():
        raise HTTPException(403, "Ο κωδικός πρόσκλησης έχει λήξει.")

    invite_id, role, region, municipality = invite[0], invite[1], invite[2], invite[3]

    # 2. Demo bypass
    if req.ada_number == "DEMO-123":
        ada_info = {"org_label": "Demo Δήμος", "subject": "Demo — Εκπρόσωπος"}
    else:
        # 3. Verify ADA via Diavgeia
        ada_info = await _verify_ada_diavgeia(req.ada_number)
        if not ada_info:
            raise HTTPException(403, "Ο αριθμός ADA δεν βρέθηκε στη Διαύγεια.")

    # 4. Generate token
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    await db.execute(text("""
        INSERT INTO representative_tokens (ada_number, token, role, region, org_label, expires_at)
        VALUES (:ada, :token, :role, :region, :org_label, :expires)
        ON CONFLICT (ada_number) DO UPDATE SET token = :token, role = :role, region = :region,
            expires_at = :expires, org_label = :org_label
    """), {
        "ada": req.ada_number, "token": token, "role": role,
        "region": region or "", "org_label": ada_info.get("org_label", ""),
        "expires": expires.replace(tzinfo=None),
    })

    # 5. Mark invite as used
    await db.execute(text(
        "UPDATE rep_invitations SET used = TRUE, used_at = NOW(), ada_number = :ada WHERE id = :id"
    ), {"ada": req.ada_number, "id": invite_id})
    await db.commit()

    logger.info("[REP] Verified: ada=%s role=%s invite=%s", req.ada_number, role, req.invite_code)
    return {
        "ada_number": req.ada_number,
        "token": token,
        "expires_at": expires.isoformat(),
        "role": role,
        "region": region,
        "org_label": ada_info.get("org_label", ""),
        "subject": ada_info.get("subject", "")[:100] if ada_info.get("subject") else "",
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


# ─── NEA-189: Evaluation Consent ────────────────────────────────────────────


@router.post("/enable-evaluation")
async def enable_evaluation(
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Representative consents to being evaluated by verified citizens."""
    await db.execute(text(
        "UPDATE representative_tokens SET evaluation_enabled = TRUE WHERE ada_number = :ada"
    ), {"ada": rep["ada_number"]})
    await db.commit()
    logger.info("[REP] Evaluation enabled: ada=%s", rep["ada_number"])
    return {"ada_number": rep["ada_number"], "evaluation_enabled": True}


@router.get("/my-scores")
async def get_my_scores(
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Representative views their own evaluation scores."""
    result = await db.execute(text("""
        SELECT eq.id, eq.question_el, eq.category,
               ROUND(AVG(pe.score)::numeric, 2) AS avg_score,
               COUNT(pe.id) AS vote_count
        FROM evaluation_questions eq
        LEFT JOIN politician_evaluations pe
            ON pe.question_id = eq.id AND pe.ada_number = :ada
        WHERE eq.active = TRUE
        GROUP BY eq.id, eq.question_el, eq.category
        ORDER BY eq.id
    """), {"ada": rep["ada_number"]})
    rows = result.fetchall()

    questions = [{
        "question_id": r[0], "question_el": r[1], "category": r[2],
        "avg_score": float(r[3]) if r[3] is not None else None,
        "vote_count": r[4],
    } for r in rows]

    total_avg = None
    total_count = sum(q["vote_count"] for q in questions)
    if total_count > 0:
        scored = [q["avg_score"] for q in questions if q["avg_score"] is not None]
        total_avg = round(sum(scored) / len(scored), 2) if scored else None

    return {
        "ada_number": rep["ada_number"],
        "questions": questions,
        "total_avg": total_avg,
        "total_evaluations": total_count,
    }

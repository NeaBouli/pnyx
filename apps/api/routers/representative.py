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
from services.bill_visibility import is_public_bill, public_bill_filter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rep", tags=["Representative"])

TOKEN_TTL_HOURS = 24
INVITE_TTL_HOURS = 48
ALLOWED_STATUSES = [BillStatus.WINDOW_24H, BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END]
DEMO_PERIFERIA_ID = int(os.getenv("DEMO_REP_PERIFERIA_ID", "6"))
DEMO_DIMOS_ID = int(os.getenv("DEMO_REP_DIMOS_ID", "22"))
DEMO_REGION = os.getenv("DEMO_REP_REGION", "Πελοποννήσου")
DEMO_MUNICIPALITY = os.getenv("DEMO_REP_MUNICIPALITY", "Καλαμάτας")

VALID_ROLES = ["Βουλευτής", "Περιφερειάρχης", "Δήμαρχος", "Δημοτικός Σύμβουλος"]

# ASCII-only header values for X-Rep-Role (Greek labels stay in JSON body only)
ROLE_HEADER_MAP = {
    "Βουλευτής": "MP",
    "Περιφερειάρχης": "REGIONAL",
    "Δήμαρχος": "MUNICIPAL",
    "Δημοτικός Σύμβουλος": "MUNICIPAL",
}


def detect_role_from_org_label(org_label: str) -> dict:
    """Auto-detect role/region/municipality from Diavgeia org_label."""
    label = (org_label or "").upper()
    if "ΒΟΥΛΗ" in label or "ΕΛΛΗΝΩΝ" in label:
        return {"role": "Βουλευτής", "region": None, "municipality": None}
    if "ΠΕΡΙΦΕΡΕΙΑ" in label or "ΠΕΡΙΦ" in label:
        region = org_label.replace("ΠΕΡΙΦΕΡΕΙΑ ", "").replace("Περιφέρεια ", "").strip()
        return {"role": "Περιφερειάρχης", "region": region, "municipality": None}
    if "ΔΗΜΟΣ" in label or "ΔΗΜΟ" in label:
        muni = org_label.replace("ΔΗΜΟΣ ", "").replace("Δήμος ", "").replace("ΔΗΜΟΥ ", "").strip()
        return {"role": "Δήμαρχος", "region": None, "municipality": muni}
    return {"role": None, "region": None, "municipality": None}


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
    periferia_id: int | None = None
    dimos_id: int | None = None


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
        INSERT INTO rep_invitations (invite_code, role, region, municipality, periferia_id, dimos_id, expires_at)
        VALUES (:code, :role, :region, :municipality, :periferia_id, :dimos_id, :expires)
    """), {
        "code": code, "role": req.role,
        "region": req.region, "municipality": req.municipality,
        "periferia_id": req.periferia_id, "dimos_id": req.dimos_id,
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
        "SELECT id, invite_code, ada_number, role, region, municipality, used, expires_at, created_at, periferia_id, dimos_id "
        "FROM rep_invitations ORDER BY created_at DESC LIMIT 100"
    ))
    rows = result.fetchall()
    return [{
        "id": r[0], "invite_code": r[1], "ada_number": r[2], "role": r[3],
        "region": r[4], "municipality": r[5], "used": r[6],
        "expired": r[7] < datetime.now() if r[7] else False,
        "expires_at": r[7].isoformat() if r[7] else None,
        "created_at": r[8].isoformat() if r[8] else None,
        "periferia_id": r[9] if len(r) > 9 else None,
        "dimos_id": r[10] if len(r) > 10 else None,
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
        "SELECT ada_number, role, party, region, org_label, expires_at, municipality, periferia_id, dimos_id "
        "FROM representative_tokens WHERE token = :token AND expires_at > NOW()"
    ), {"token": token})
    row = result.fetchone()
    if not row:
        return None
    return {"ada_number": row[0], "role": row[1], "party": row[2],
            "region": row[3], "org_label": row[4], "expires_at": row[5],
            "municipality": row[6], "periferia_id": row[7], "dimos_id": row[8]}


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
        "SELECT id, role, region, municipality, used, expires_at, periferia_id, dimos_id FROM rep_invitations "
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
    invite_periferia_id = invite[6] if len(invite) > 6 else None
    invite_dimos_id = invite[7] if len(invite) > 7 else None

    # 2. Demo bypass
    if req.ada_number == "DEMO-123":
        ada_info = {"org_label": "Demo Δήμος", "subject": "Demo — Εκπρόσωπος"}
        invite_periferia_id = invite_periferia_id or DEMO_PERIFERIA_ID
        invite_dimos_id = invite_dimos_id or DEMO_DIMOS_ID
        region = region or DEMO_REGION
        municipality = municipality or DEMO_MUNICIPALITY
    else:
        # 3. Verify ADA via Diavgeia
        ada_info = await _verify_ada_diavgeia(req.ada_number)
        if not ada_info:
            raise HTTPException(403, "Ο αριθμός ADA δεν βρέθηκε στη Διαύγεια.")

    # 4. Generate token + auto-detect role from org_label
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    role_suggestion = detect_role_from_org_label(ada_info.get("org_label", ""))

    await db.execute(text("""
        INSERT INTO representative_tokens (ada_number, token, role, region, municipality, periferia_id, dimos_id, org_label, expires_at)
        VALUES (:ada, :token, :role, :region, :municipality, :periferia_id, :dimos_id, :org_label, :expires)
        ON CONFLICT (ada_number) DO UPDATE SET token = :token, role = :role, region = :region,
            municipality = :municipality, periferia_id = :periferia_id, dimos_id = :dimos_id,
            expires_at = :expires, org_label = :org_label,
            evaluation_enabled = representative_tokens.evaluation_enabled
    """), {
        "ada": req.ada_number, "token": token, "role": role,
        "region": region or "", "municipality": municipality or "",
        "periferia_id": invite_periferia_id, "dimos_id": invite_dimos_id,
        "org_label": ada_info.get("org_label", ""),
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
        "municipality": municipality,
        "org_label": ada_info.get("org_label", ""),
        "subject": ada_info.get("subject", "")[:100] if ada_info.get("subject") else "",
        "role_suggestion": role_suggestion,
    }


@router.post("/auth")
async def auth_representative(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with ADA + token."""
    rep = await _get_rep_token(req.token, db)
    if not rep or rep["ada_number"] != req.ada_number:
        raise HTTPException(401, "Invalid credentials")
    return {"authenticated": True, **rep}


def is_bill_visible_for_token(bill, rep: dict) -> bool:
    """Check if a bill is visible for the given representative token.
    Shared by /rep/bills, /rep/results, /rep/divergence.
    """
    if not is_public_bill(bill):
        return False
    role = rep.get("role", "")
    source = getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT"
    gov = bill.governance_level.value if bill.governance_level else "NATIONAL"

    if role == "Βουλευτής":
        return True
    elif role == "Περιφερειάρχης" and rep.get("periferia_id"):
        # PARLIAMENT + own-region REGIONAL bills (deterministic FK match)
        if source == "PARLIAMENT" or source is None:
            return True
        if gov == "REGIONAL" and getattr(bill, "periferia_id", None) == rep["periferia_id"]:
            return True
        return False
    elif role in ("Δήμαρχος", "Δημοτικός Σύμβουλος"):
        # PARLIAMENT always visible + DIAVGEIA MUNICIPAL
        return source == "PARLIAMENT" or source is None or (source == "DIAVGEIA" and gov == "MUNICIPAL")
    else:
        # Fallback (role=None, Περιφερειάρχης without periferia_id): PARLIAMENT only
        return source == "PARLIAMENT" or source is None


@router.get("/bills")
async def get_rep_bills(
    rep: dict = Depends(verify_rep_token),
    db: AsyncSession = Depends(get_db),
):
    """Bills visible to representatives — filtered by role.

    Visibility rules:
    - Βουλευτής: all bills
    - Δήμαρχος/Δημοτικός Σύμβουλος: PARLIAMENT + MUNICIPAL DIAVGEIA (Known Limitation: all municipal, not own-specific)
    - Περιφερειάρχης (with periferia_id): PARLIAMENT + own-region REGIONAL bills (deterministic FK match)
    - Περιφερειάρχης (without periferia_id): PARLIAMENT only (safe fallback)
    - role=None / unknown: PARLIAMENT only (safe fallback)
    """
    from fastapi.responses import JSONResponse
    from sqlalchemy import or_, and_

    role = rep.get("role", "")
    region = rep.get("region", "")
    role_header = ROLE_HEADER_MAP.get(role, "UNKNOWN")

    query = select(ParliamentBill).where(
        ParliamentBill.status.in_(ALLOWED_STATUSES),
        public_bill_filter(),
    )

    periferia_id = rep.get("periferia_id")

    if role == "Βουλευτής":
        pass  # No additional filter — sees all
    elif role == "Περιφερειάρχης" and periferia_id:
        # PARLIAMENT + own-region REGIONAL (deterministic FK match, no string ILIKE)
        query = query.where(or_(
            ParliamentBill.source == "PARLIAMENT",
            ParliamentBill.source.is_(None),
            and_(ParliamentBill.governance_level == "REGIONAL",
                 ParliamentBill.periferia_id == periferia_id),
        ))
    elif role in ("Δήμαρχος", "Δημοτικός Σύμβουλος"):
        query = query.where(or_(
            ParliamentBill.source == "PARLIAMENT",
            ParliamentBill.source.is_(None),
            and_(ParliamentBill.source == "DIAVGEIA", ParliamentBill.governance_level == "MUNICIPAL"),
        ))
    else:
        # Fallback: role=None or Περιφερειάρχης without periferia_id → PARLIAMENT only
        query = query.where(or_(
            ParliamentBill.source == "PARLIAMENT",
            ParliamentBill.source.is_(None),
        ))

    result = await db.execute(
        query.order_by(ParliamentBill.parliament_vote_date.desc().nullslast()).limit(100)
    )
    bills = result.scalars().all()

    data = [{
        "id": b.id, "title_el": b.title_el, "status": b.status.value,
        "source": getattr(b, "source", "PARLIAMENT") or "PARLIAMENT",
        "governance_level": b.governance_level.value if b.governance_level else "NATIONAL",
        "parliament_vote_date": b.parliament_vote_date.isoformat() if b.parliament_vote_date else None,
        "consensus_score": b.consensus_score, "consensus_count": b.consensus_count or 0,
    } for b in bills]

    response = JSONResponse(content=data)
    response.headers["X-Rep-Role"] = role_header
    return response


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
    if not is_bill_visible_for_token(bill, rep):
        raise HTTPException(403, "Αυτό το νομοσχέδιο δεν είναι ορατό για τον ρόλο σας.")

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
    if not is_bill_visible_for_token(bill, rep):
        raise HTTPException(403, "Αυτό το νομοσχέδιο δεν είναι ορατό για τον ρόλο σας.")
    if bill.status not in ALLOWED_STATUSES:
        raise HTTPException(403, "Divergence not available for this bill status")

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

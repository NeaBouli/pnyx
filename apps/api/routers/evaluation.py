"""
NEA-189: Politician Evaluation — Public Endpoints
Bürger bewerten Volksvertreter anhand von 8 Fragen (-5 bis +5).
Voraussetzung: Politiker hat evaluation_enabled=TRUE.
Auth: Ed25519 Signatur (identisch mit Voting-Pattern).
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from keypair import verify_signature
from models import EvaluationQuestion, PoliticianEvaluation, IdentityRecord, KeyStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/politicians", tags=["Evaluation"])

ROLE_GOVERNANCE = {
    "Βουλευτής": "VOULEVTIS",
    "Περιφερειάρχης": "PERIFERIARXIS",
    "Δήμαρχος": "DIMARXOS",
    "Δημοτικός Σύμβουλος": "DIMOTIKOS_SYMVOULOS",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────


class ScoreItem(BaseModel):
    question_id: int
    score: int = Field(..., ge=-5, le=5)


class EvaluateRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    scores: list[ScoreItem] = Field(..., min_length=1, max_length=8)
    signature_hex: str = Field(..., min_length=64)


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _get_enabled_politician(ada_number: str, db: AsyncSession) -> dict:
    """Fetch politician with evaluation_enabled=TRUE or raise 404."""
    result = await db.execute(text(
        "SELECT ada_number, role, region, org_label, evaluation_enabled, periferia_id, dimos_id "
        "FROM representative_tokens WHERE ada_number = :ada"
    ), {"ada": ada_number})
    row = result.fetchone()
    if not row or not row[4]:
        raise HTTPException(404, "Ο εκπρόσωπος δεν βρέθηκε ή δεν έχει ενεργοποιήσει την αξιολόγηση.")
    return {"ada_number": row[0], "role": row[1], "region": row[2], "org_label": row[3],
            "periferia_id": row[5], "dimos_id": row[6]}


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/")
async def list_politicians(db: AsyncSession = Depends(get_db)):
    """Public: all politicians who opted-in to evaluation, with avg scores."""
    result = await db.execute(text("""
        SELECT rt.ada_number, rt.role, rt.region, rt.org_label,
               ROUND(AVG(pe.score)::numeric, 2) AS avg_score,
               COUNT(DISTINCT pe.nullifier_hash) AS evaluator_count
        FROM representative_tokens rt
        LEFT JOIN politician_evaluations pe ON pe.ada_number = rt.ada_number
        WHERE rt.evaluation_enabled = TRUE
        GROUP BY rt.ada_number, rt.role, rt.region, rt.org_label
        ORDER BY rt.role, rt.org_label
    """))
    rows = result.fetchall()
    return [{
        "ada_number": r[0],
        "role": r[1],
        "region": r[2],
        "org_label": r[3],
        "governance_level": ROLE_GOVERNANCE.get(r[1], "VOULEVTIS"),
        "avg_score": float(r[4]) if r[4] is not None else None,
        "evaluator_count": r[5],
    } for r in rows]


@router.get("/my-evaluations/bulk")
async def get_my_evaluations_bulk(
    nullifier_hash: str,
    db: AsyncSession = Depends(get_db),
):
    """Bulk: which politicians has this citizen evaluated? Returns ada_numbers + latest updated_at."""
    result = await db.execute(text("""
        SELECT ada_number, MAX(updated_at) AS last_updated
        FROM politician_evaluations
        WHERE nullifier_hash = :null
        GROUP BY ada_number
    """), {"null": nullifier_hash})
    rows = result.fetchall()
    return [{
        "ada_number": r[0],
        "last_updated": r[1].isoformat() if r[1] else None,
    } for r in rows]


@router.get("/{ada_number}/questions")
async def get_questions(
    ada_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: evaluation questions for a politician (only if enabled)."""
    await _get_enabled_politician(ada_number, db)

    questions = (await db.execute(
        select(EvaluationQuestion).where(EvaluationQuestion.active == True).order_by(EvaluationQuestion.id)
    )).scalars().all()

    return [{
        "id": q.id, "question_el": q.question_el,
        "question_en": q.question_en, "category": q.category,
    } for q in questions]


@router.get("/{ada_number}/my-evaluation")
async def get_my_evaluation(
    ada_number: str,
    nullifier_hash: str,
    db: AsyncSession = Depends(get_db),
):
    """Citizen checks their own evaluation for a politician (by nullifier_hash query param)."""
    result = await db.execute(text("""
        SELECT question_id, score, updated_at
        FROM politician_evaluations
        WHERE ada_number = :ada AND nullifier_hash = :null
        ORDER BY question_id
    """), {"ada": ada_number, "null": nullifier_hash})
    rows = result.fetchall()
    return [{
        "question_id": r[0], "score": r[1],
        "updated_at": r[2].isoformat() if r[2] else None,
    } for r in rows]


@router.post("/{ada_number}/evaluate")
async def evaluate_politician(
    ada_number: str,
    req: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Citizen evaluates a politician. Auth: Ed25519 signature."""
    # 1. Politician must have evaluation enabled
    politician = await _get_enabled_politician(ada_number, db)

    # 2. Citizen must be verified
    identity = (await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )).scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Μη επαληθευμένος πολίτης.")

    # 2b. Region-Lock: citizen must have verified region + match politician's region
    if not getattr(identity, "region_locked", False):
        raise HTTPException(403, "Απαιτείται επαλήθευση περιοχής πριν την αξιολόγηση.")

    pol_role = politician.get("role", "")
    pol_periferia = politician.get("periferia_id")
    pol_dimos = politician.get("dimos_id")

    if pol_role in ("Βουλευτής", "Περιφερειάρχης"):
        if pol_periferia is None or identity.periferia_id != pol_periferia:
            raise HTTPException(403, "Δεν έχετε δικαίωμα αξιολόγησης αυτού του εκπροσώπου (διαφορετική περιφέρεια).")
    elif pol_role in ("Δήμαρχος", "Δημοτικός Σύμβουλος"):
        if pol_dimos is None or identity.dimos_id != pol_dimos:
            raise HTTPException(403, "Δεν έχετε δικαίωμα αξιολόγησης αυτού του εκπροσώπου (διαφορετικός δήμος).")
    else:
        raise HTTPException(403, "Δεν έχετε δικαίωμα αξιολόγησης αυτού του εκπροσώπου.")

    # 3. Verify Ed25519 signature
    # Payload: "evaluate:{ada_number}:{nullifier_hash}"
    payload = f"evaluate:{ada_number}:{req.nullifier_hash}"
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.")

    # 4. Validate question IDs
    valid_ids = {q.id for q in (await db.execute(
        select(EvaluationQuestion).where(EvaluationQuestion.active == True)
    )).scalars().all()}
    for s in req.scores:
        if s.question_id not in valid_ids:
            raise HTTPException(400, f"Μη έγκυρη ερώτηση: {s.question_id}")

    # 5. UPSERT scores
    for s in req.scores:
        await db.execute(text("""
            INSERT INTO politician_evaluations (ada_number, nullifier_hash, question_id, score, updated_at)
            VALUES (:ada, :null, :qid, :score, NOW())
            ON CONFLICT (nullifier_hash, ada_number, question_id)
            DO UPDATE SET score = :score, updated_at = NOW()
        """), {"ada": ada_number, "null": req.nullifier_hash, "qid": s.question_id, "score": s.score})
    await db.commit()

    logger.info("[EVAL] Citizen evaluated %s: %d scores", ada_number, len(req.scores))
    return {"ada_number": ada_number, "scores_submitted": len(req.scores)}


@router.get("/{ada_number}/scores")
async def get_scores(
    ada_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: evaluation scores for a politician."""
    await _get_enabled_politician(ada_number, db)

    result = await db.execute(text("""
        SELECT eq.id, eq.question_el, eq.question_en, eq.category,
               ROUND(AVG(pe.score)::numeric, 2) AS avg_score,
               COUNT(pe.id) AS vote_count
        FROM evaluation_questions eq
        LEFT JOIN politician_evaluations pe
            ON pe.question_id = eq.id AND pe.ada_number = :ada
        WHERE eq.active = TRUE
        GROUP BY eq.id, eq.question_el, eq.question_en, eq.category
        ORDER BY eq.id
    """), {"ada": ada_number})
    rows = result.fetchall()

    questions = [{
        "question_id": r[0], "question_el": r[1], "question_en": r[2],
        "category": r[3],
        "avg_score": float(r[4]) if r[4] is not None else None,
        "vote_count": r[5],
    } for r in rows]

    total_count = sum(q["vote_count"] for q in questions)
    scored = [q["avg_score"] for q in questions if q["avg_score"] is not None]
    total_avg = round(sum(scored) / len(scored), 2) if scored else None

    return {
        "ada_number": ada_number,
        "org_label": (await _get_enabled_politician(ada_number, db))["org_label"],
        "questions": questions,
        "total_avg": total_avg,
        "total_evaluations": total_count,
    }

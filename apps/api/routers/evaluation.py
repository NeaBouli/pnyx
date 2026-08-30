"""
NEA-189: Politician Evaluation — Public Endpoints
Bürger bewerten Volksvertreter anhand von 8 Fragen (-5 bis +5).
Voraussetzung: Politiker hat evaluation_enabled=TRUE.
Auth: Ed25519 Signatur (identisch mit Voting-Pattern).
"""
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from keypair import verify_signature
from models import EvaluationQuestion, PoliticianEvaluation, IdentityRecord, KeyStatus
from services.evaluation_integrity import (
    EVALUATION_K_ANONYMITY_MIN,
    build_evaluation_read_payload,
    build_evaluation_v2_payload,
    evaluation_timestamp_is_fresh,
    evaluation_v2_required,
    public_evaluation_average,
)

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
    payload_version: Literal[1, 2] = 1
    timestamp_ms: int | None = None

    @field_validator("scores")
    @classmethod
    def reject_duplicate_questions(cls, scores: list[ScoreItem]) -> list[ScoreItem]:
        question_ids = [score.question_id for score in scores]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("duplicate question_id")
        return scores


# ─── Helpers ─────────────────────────────────────────────────────────────────


READ_CACHE_HEADERS = {"Cache-Control": "private, no-store"}
ReadTimestamp = Annotated[
    int | None,
    Header(alias="X-Evaluation-Read-Timestamp", ge=0, le=9_007_199_254_740_991),
]
ReadSignature = Annotated[
    str | None,
    Header(alias="X-Evaluation-Read-Signature", pattern=r"^[0-9a-fA-F]{128}$"),
]


async def _authorize_evaluation_read(
    nullifier_hash: str,
    ada_number: str | None,
    timestamp_ms: int | None,
    signature_hex: str | None,
    db: AsyncSession,
) -> str:
    """Only completely unsigned legacy clients may use the migration window."""
    scope = "single" if ada_number is not None else "bulk"
    if timestamp_ms is None and signature_hex is None:
        if evaluation_v2_required():
            raise HTTPException(
                426, "Απαιτείται ενημέρωση της εφαρμογής για ασφαλή αξιολόγηση.",
                headers=READ_CACHE_HEADERS,
            )
        logger.warning("[EVAL] Legacy personal read accepted: scope=%s", scope)
        return "legacy"
    if timestamp_ms is None or signature_hex is None:
        raise HTTPException(401, "Μη έγκυρη υπογραφή.", headers=READ_CACHE_HEADERS)
    if not evaluation_timestamp_is_fresh(timestamp_ms):
        raise HTTPException(
            401, "Η υπογραφή έληξε. Ελέγξτε την ώρα της συσκευής και δοκιμάστε ξανά.",
            headers=READ_CACHE_HEADERS,
        )
    public_key_hex = (await db.execute(text(
        "SELECT public_key_hex FROM identity_records "
        "WHERE nullifier_hash = :nullifier AND status = :status"
    ), {"nullifier": nullifier_hash, "status": KeyStatus.ACTIVE.value})).scalar_one_or_none()
    payload = build_evaluation_read_payload(ada_number, nullifier_hash, timestamp_ms)
    if not public_key_hex or not verify_signature(public_key_hex, payload, signature_hex):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.", headers=READ_CACHE_HEADERS)
    logger.info("[EVAL] Signed personal read accepted: scope=%s", scope)
    return "signed"


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
    politicians = []
    for row in rows:
        evaluator_count = int(row[5])
        scores_hidden = 0 < evaluator_count < EVALUATION_K_ANONYMITY_MIN
        politicians.append({
            "ada_number": row[0],
            "role": row[1],
            "region": row[2],
            "org_label": row[3],
            "governance_level": ROLE_GOVERNANCE.get(row[1], "VOULEVTIS"),
            "avg_score": public_evaluation_average(row[4], evaluator_count),
            "evaluator_count": 0 if scores_hidden else evaluator_count,
            "evaluator_count_hidden": scores_hidden,
            "scores_hidden": scores_hidden,
            "minimum_group_size": EVALUATION_K_ANONYMITY_MIN,
        })
    return politicians


@router.get("/my-evaluations/bulk")
async def get_my_evaluations_bulk(
    nullifier_hash: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    timestamp_ms: ReadTimestamp = None,
    signature_hex: ReadSignature = None,
) -> list[dict[str, object]]:
    """Bulk: which politicians has this citizen evaluated? Returns ada_numbers + latest updated_at."""
    integrity = await _authorize_evaluation_read(
        nullifier_hash, None, timestamp_ms, signature_hex, db,
    )
    response.headers.update(READ_CACHE_HEADERS)
    response.headers["X-Evaluation-Read-Integrity"] = integrity
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
    response: Response,
    db: AsyncSession = Depends(get_db),
    timestamp_ms: ReadTimestamp = None,
    signature_hex: ReadSignature = None,
) -> list[dict[str, object]]:
    """Citizen reads their own scores; signed reads are required after migration."""
    integrity = await _authorize_evaluation_read(
        nullifier_hash, ada_number, timestamp_ms, signature_hex, db,
    )
    response.headers.update(READ_CACHE_HEADERS)
    response.headers["X-Evaluation-Read-Integrity"] = integrity
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

    # 3. Verify Ed25519 signature. v2 binds every score and expires old payloads.
    if req.payload_version == 2:
        if req.timestamp_ms is None:
            raise HTTPException(400, "Απαιτείται χρονική σήμανση για υπογραφή v2.")
        if not evaluation_timestamp_is_fresh(req.timestamp_ms):
            raise HTTPException(
                401,
                "Η υπογραφή έληξε. Ελέγξτε την ώρα της συσκευής και δοκιμάστε ξανά.",
            )
        payload = build_evaluation_v2_payload(
            ada_number,
            req.nullifier_hash,
            req.timestamp_ms,
            req.scores,
        )
        integrity = "bound"
    else:
        if evaluation_v2_required():
            raise HTTPException(426, "Απαιτείται ενημέρωση της εφαρμογής για ασφαλή αξιολόγηση.")
        payload = f"evaluate:{ada_number}:{req.nullifier_hash}"
        integrity = "legacy"
        logger.warning("[EVAL] Legacy evaluation signature accepted: ada=%s", ada_number)

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

    logger.info(
        "[EVAL] Citizen evaluated %s: %d scores, payload_version=%d",
        ada_number, len(req.scores), req.payload_version,
    )
    return {
        "ada_number": ada_number,
        "scores_submitted": len(req.scores),
        "integrity": integrity,
        "payload_version_accepted": req.payload_version,
    }


@router.get("/{ada_number}/scores")
async def get_scores(
    ada_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: evaluation scores for a politician."""
    politician = await _get_enabled_politician(ada_number, db)

    result = await db.execute(text("""
        SELECT eq.id, eq.question_el, eq.question_en, eq.category,
               ROUND(AVG(pe.score)::numeric, 2) AS avg_score,
               COUNT(DISTINCT pe.nullifier_hash) AS vote_count
        FROM evaluation_questions eq
        LEFT JOIN politician_evaluations pe
            ON pe.question_id = eq.id AND pe.ada_number = :ada
        WHERE eq.active = TRUE
        GROUP BY eq.id, eq.question_el, eq.question_en, eq.category
        ORDER BY eq.id
    """), {"ada": ada_number})
    rows = result.fetchall()

    questions = []
    for row in rows:
        vote_count = int(row[5])
        scores_hidden = 0 < vote_count < EVALUATION_K_ANONYMITY_MIN
        questions.append({
            "question_id": row[0], "question_el": row[1], "question_en": row[2],
            "category": row[3],
            "avg_score": public_evaluation_average(row[4], vote_count),
            "vote_count": 0 if scores_hidden else vote_count,
            "vote_count_hidden": scores_hidden,
            "scores_hidden": scores_hidden,
        })

    total_count = sum(q["vote_count"] for q in questions)
    scored = [q["avg_score"] for q in questions if q["avg_score"] is not None]
    total_avg = round(sum(scored) / len(scored), 2) if scored else None

    return {
        "ada_number": ada_number,
        "org_label": politician["org_label"],
        "questions": questions,
        "total_avg": total_avg,
        "total_evaluations": total_count,
        "scores_hidden": any(q["scores_hidden"] for q in questions),
        "minimum_group_size": EVALUATION_K_ANONYMITY_MIN,
    }

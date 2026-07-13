"""
MOD-04: CitizenVote Router
POST /api/v1/vote               — Stimme abgeben (Ed25519 signiert)
PUT  /api/v1/vote/{bill_id}/correct — Einmalige Korrektur (nur WINDOW_24H)
GET  /api/v1/vote/{bill_id}/results — Ergebnisse + Divergence Score
POST /api/v1/vote/{bill_id}/relevance — Up/Down Relevanz (MOD-14)
"""
import hashlib
import hmac
import json
import gc
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, func, union, update, text
from sqlalchemy.exc import IntegrityError

from database import get_db
from models import (
    CitizenVote, VoteChoice, IdentityRecord, KeyStatus,
    ParliamentBill, BillStatus, BillRelevanceVote, ZkVoteReceipt
)
from services.source_links import official_source_url
from services.bill_visibility import is_public_bill, public_bill_filter
from services.zk_tier_lock import (
    VoteScopeType,
    canonical_vote_scope_id,
    tier1_vote_blocked_by_zk_lock,
)
from services.zk_vote_aggregation import aggregate_bill_vote_totals

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import verify_signature

router = APIRouter(prefix="/api/v1/vote", tags=["MOD-04 CitizenVote"])

# ─── Repräsentativität ───────────────────────────────────────────────────────

GREECE_ELIGIBLE_VOTERS = 9_900_000
GREECE_POPULATION = 10_400_000
VOTES_IN_PROGRESS_THRESHOLD_ENV = "VOTES_IN_PROGRESS_THRESHOLD"
ZK_TIER1_GUARD_ENABLED_ENV = "ZK_TIER1_GUARD_ENABLED"

def compute_representativity(total_votes: int) -> dict:
    """Misst Repräsentativität basierend auf Beteiligung vs Wahlberechtigte."""
    if total_votes == 0:
        return {"participation_pct": 0, "level": "none", "color": "#94a3b8",
                "label_el": "Δεν υπάρχουν ψήφοι", "is_representative": False, "score": 0}

    pct = round(total_votes / GREECE_ELIGIBLE_VOTERS * 100, 4)

    if pct >= 1.0:
        level, color, label = "very_high", "#2563eb", "Πολύ Υψηλή Συμμετοχή"
    elif pct >= 0.5:
        level, color, label = "high", "#22c55e", "Υψηλή Συμμετοχή"
    elif pct >= 0.1:
        level, color, label = "medium", "#f59e0b", "Μέτρια Συμμετοχή"
    elif pct >= 0.01:
        level, color, label = "low", "#f97316", "Χαμηλή Συμμετοχή"
    else:
        level, color, label = "very_low", "#ef4444", "Πολύ Χαμηλή Συμμετοχή"

    is_rep = pct >= 0.5
    score = min(100, round(pct / 1.0 * 100, 1))

    return {
        "total_votes": total_votes,
        "eligible_voters": GREECE_ELIGIBLE_VOTERS,
        "population": GREECE_POPULATION,
        "participation_pct": pct,
        "population_pct": round(total_votes / GREECE_POPULATION * 100, 4),
        "level": level, "color": color, "label_el": label,
        "is_representative": is_rep, "score": score,
        "headline_el": f"Η συμμετοχή ({pct:.3f}% εκλογέων) {'καθιστά τα αποτελέσματα αντιπροσωπευτικά' if is_rep else 'δεν είναι αρκετά αντιπροσωπευτική'}.",
    }


def votes_in_progress_threshold() -> int:
    """Return configured landing threshold; invalid values fall back to 50."""
    raw = os.getenv(VOTES_IN_PROGRESS_THRESHOLD_ENV, "50")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 50


def zk_tier1_guard_enabled() -> bool:
    return os.getenv(ZK_TIER1_GUARD_ENABLED_ENV, "false").lower() == "true"


async def raise_if_zk_tier1_locked(
    db: AsyncSession,
    *,
    bill_id: str,
    bill_source: str | None,
    nullifier_hash: str,
) -> None:
    if (bill_source or "PARLIAMENT") != "PARLIAMENT":
        return
    if not zk_tier1_guard_enabled():
        return

    server_salt = os.getenv("SERVER_SALT", "")
    try:
        vote_scope_id = canonical_vote_scope_id(VoteScopeType.BILL, bill_id)
        blocked = await tier1_vote_blocked_by_zk_lock(
            db,
            server_salt=server_salt,
            vote_scope_id=vote_scope_id,
            tier1_nullifier_hash=nullifier_hash,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK tier-lock guard is not configured.",
        ) from exc

    if blocked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Έχετε ενεργοποιήσει τη διαδρομή Semaphore ZK για αυτή την ψηφοφορία. "
                "Η κανονική διαδρομή ψήφου είναι κλειδωμένη για το συγκεκριμένο αντικείμενο."
            ),
        )


def vote_percent(count: int, total: int) -> int:
    return round(count / total * 100) if total > 0 else 0


# ─── Schemas ──────────────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    nullifier_hash: str  = Field(..., min_length=64, max_length=64)
    bill_id:        str
    vote:           str  = Field(..., description="YES | NO | ABSTAIN | UNKNOWN")
    signature_hex:  str  = Field(..., description="Ed25519 Signatur des Payloads")
    # Tier-1 fields (ADR-022) — optional for backward compat
    pk_eph:         str | None = Field(None, description="Ephemeral public key (64 hex)")
    vote_nullifier: str | None = Field(None, description="Bill-specific nullifier (64 hex)")
    linkage_tag:    str | None = Field(None, description="Anti-double-vote proof (64 hex)")
    timestamp_ms:   int | None = Field(None, description="Millisecond timestamp")

class VoteResponse(BaseModel):
    success:    bool
    message:    str
    bill_id:    str
    vote:       str

class VoteStatusResponse(BaseModel):
    bill_id:        str
    status:         str
    has_voted:      bool
    vote:           str | None = None
    is_correction:  bool = False
    can_correct:    bool = False

class DivergenceResult(BaseModel):
    score:             float
    label_el:          str
    citizen_majority:  str
    parliament_result: str | None
    headline_el:       str

class BillResults(BaseModel):
    bill_id:          str
    title_el:         str
    status:           str
    source:           str | None = "PARLIAMENT"
    pill_el:          str | None = None
    summary_short_el: str | None = None
    summary_long_el:  str | None = None
    ai_summary_reviewed: bool = False
    parliament_url:   str | None = None
    official_source_url: str | None = None
    diavgeia_ada:     str | None = None
    total_votes:      int
    tier1_vote_count: int = 0
    zk_vote_count:    int = 0
    yes_count:        int
    no_count:         int
    abstain_count:    int
    unknown_count:    int
    yes_percent:      float
    no_percent:       float
    abstain_percent:  float
    divergence:       DivergenceResult | None
    representativity: dict | None = None
    results_hidden:   bool = False
    parliament_vote_date: str | None = None
    disclaimer_el:    str

class RelevanceRequest(BaseModel):
    nullifier_hash: str
    signal:         int  = Field(..., description="+1 wichtig / -1 unwichtig")
    signature_hex:  str  = Field(..., description="Ed25519 Signatur: relevance:{bill_id}:{signal}:{nullifier_hash}")


# ─── Divergence Score ─────────────────────────────────────────────────────────

def compute_divergence(
    yes: int, no: int, abstain: int,
    parliament_votes: dict | None
) -> DivergenceResult | None:
    """
    Berechnet die Abweichung zwischen Bürgermehrheit und Parlamentsentscheid.
    Nur wenn parliament_votes vorhanden (PARLIAMENT_VOTED oder OPEN_END).
    """
    total = yes + no + abstain
    if total == 0 or not parliament_votes:
        return None

    citizen_yes_pct = yes / total

    # Parlamentsmehrheit: ΝΑΙ-Stimmen / Gesamtstimmen Parteien
    yes_parties = sum(1 for v in parliament_votes.values() if v in ["ΝΑΙ", "YES"])
    total_parties = len(parliament_votes)
    parliament_passed = yes_parties > total_parties / 2 if total_parties > 0 else None

    if parliament_passed is None:
        return None

    parliament_for = 1.0 if parliament_passed else 0.0
    score = abs(citizen_yes_pct - parliament_for)

    citizen_majority = "ΥΠΕΡ" if citizen_yes_pct > 0.5 else "ΚΑΤΑ"
    parl_result = "ΕΓΚΡΙΘΗΚΕ" if parliament_passed else "ΑΠΟΡΡΙΦΘΗΚΕ"

    if score > 0.4:
        label = "Έντονη Απόκλιση"
        against_pct = round((1 - citizen_yes_pct) * 100)
        headline = (
            f"{against_pct}% των πολιτών ΚΑΤΑ — "
            f"η Βουλή {parl_result} παρόλα αυτά."
            if not parliament_passed == (citizen_yes_pct > 0.5)
            else f"Πολίτες και Βουλή σε αντίθεση ({against_pct}% vs Βουλή)."
        )
    elif score > 0.2:
        label = "Μέτρια Απόκλιση"
        headline = "Μέτρια διαφορά μεταξύ πολιτών και Βουλής."
    else:
        label = "Σύγκλιση"
        headline = "Πολίτες και Βουλή σε γενική συμφωνία."

    return DivergenceResult(
        score=round(score, 3),
        label_el=label,
        citizen_majority=citizen_majority,
        parliament_result=parl_result,
        headline_el=headline,
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=VoteResponse)
async def submit_vote(req: VoteRequest, db: AsyncSession = Depends(get_db)):
    """
    Kernfunktion: Bürger-Abstimmung zu einem Parlamentsbeschluss.

    Sicherheitskette:
    1. Nullifier muss ACTIVE sein
    2. Bill muss in ACTIVE, WINDOW_24H oder OPEN_END sein
    3. Ed25519 Signatur muss gültig sein
    4. UNIQUE(nullifier_hash, bill_id) verhindert Doppelstimme auf DB-Ebene

    Stimmänderung:
    - ACTIVE: keine Änderung (Stimme gesperrt)
    - WINDOW_24H + OPEN_END: Änderung erlaubt
    """
    # 1. Identity prüfen
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Δεν έχετε επαληθευτεί ή το κλειδί σας έχει ανακληθεί. Παρακαλώ επαληθεύστε ξανά."
        )

    # 2. Bill-Status prüfen
    bill_query = select(ParliamentBill).where(ParliamentBill.id == req.bill_id)
    if zk_tier1_guard_enabled():
        bill_query = bill_query.with_for_update()
    bill_result = await db.execute(bill_query)
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(status_code=404, detail=f"Το νομοσχέδιο {req.bill_id} δεν βρέθηκε.")

    votable_states = [BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END]
    if bill.status not in votable_states:
        raise HTTPException(
            status_code=400,
            detail=f"Η ψηφοφορία δεν είναι δυνατή. Κατάσταση: {bill.status.value}. "
                   f"Επιτρέπεται: ACTIVE, WINDOW_24H, OPEN_END."
        )

    # 2b. Vote Scope: check governance_level permission
    from models import GovernanceLevel
    gov_level = getattr(bill, "governance_level", None)
    if gov_level and gov_level not in (GovernanceLevel.NATIONAL, GovernanceLevel.INSTITUTIONAL):
        if gov_level == GovernanceLevel.REGIONAL:
            if not identity.periferia_id or identity.periferia_id != bill.periferia_id:
                raise HTTPException(
                    status_code=403,
                    detail="Αυτή η ψηφοφορία αφορά μόνο κατοίκους αυτής της Περιφέρειας."
                )
        elif gov_level == GovernanceLevel.MUNICIPAL:
            if not identity.dimos_id or identity.dimos_id != bill.dimos_id:
                raise HTTPException(
                    status_code=403,
                    detail="Αυτή η ψηφοφορία αφορά μόνο κατοίκους αυτού του Δήμου."
                )

    # 3. Stimme validieren
    try:
        vote_choice = VoteChoice(req.vote.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Μη έγκυρη ψήφος: {req.vote}. Επιτρέπεται: YES, NO, ABSTAIN, UNKNOWN")

    # 4. Ed25519 Signatur verifizieren
    # Payload-Format muss mit Client (crypto-native.ts signVote) übereinstimmen:
    # `${bill_id}:${vote}:${nullifier_hash}`
    payload = f"{req.bill_id}:{req.vote.upper()}:{req.nullifier_hash}".encode()

    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Μη έγκυρη υπογραφή. Η ψήφος απορρίφθηκε."
        )

    await raise_if_zk_tier1_locked(
        db,
        bill_id=req.bill_id,
        bill_source=getattr(bill, "source", None),
        nullifier_hash=req.nullifier_hash,
    )

    # 4b. Tier-1 validation (ADR-022) — if Tier-1 fields present
    if req.pk_eph and req.vote_nullifier and req.linkage_tag:
        try:
            from crypto.nullifier import validate_vote
            tier1_result = validate_vote(
                pk_eph=req.pk_eph,
                vote_nullifier=req.vote_nullifier,
                linkage_tag=req.linkage_tag,
                bill_id=req.bill_id,
                choice=vote_choice.value,
                signature=req.signature_hex,
                timestamp_ms=req.timestamp_ms or 0,
            )
            if tier1_result and hasattr(tier1_result, 'code') and tier1_result.code != "OK":
                logger.warning("Tier-1 validation failed: %s", tier1_result.message)
                # Don't reject — log warning only (Tier-1 validation is advisory during rollout)
        except Exception as e:
            logger.warning("Tier-1 validation error (non-blocking): %s", e)

    # 5. Bestehende Stimme prüfen (Stimmänderung)
    existing_result = await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == req.nullifier_hash,
            CitizenVote.bill_id == req.bill_id
        )
    )
    existing_vote = existing_result.scalar_one_or_none()

    if existing_vote:
        # Stimmänderung nur in WINDOW_24H und OPEN_END erlaubt
        if bill.status == BillStatus.ACTIVE:
            raise HTTPException(
                status_code=409,
                detail="Η ψήφος έχει ήδη καταχωρηθεί. Αλλαγή μόνο στο 24ωρο παράθυρο."
            )
        existing_vote.vote = vote_choice
        existing_vote.signature_hex = req.signature_hex
        existing_vote.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        return VoteResponse(
            success=True,
            message="Η ψήφος άλλαξε επιτυχώς.",
            bill_id=req.bill_id,
            vote=vote_choice.value
        )

    # 6. Neue Stimme speichern
    try:
        new_vote = CitizenVote(
            nullifier_hash=req.nullifier_hash,
            bill_id=req.bill_id,
            vote=vote_choice,
            signature_hex=req.signature_hex,
            # Tier-1 fields (ADR-022) — stored if provided
            pk_eph=req.pk_eph,
            vote_nullifier=req.vote_nullifier,
            linkage_tag=req.linkage_tag,
            timestamp_ms=req.timestamp_ms,
        )
        db.add(new_vote)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Η ψήφος έχει ήδη καταχωρηθεί."
        )

    return VoteResponse(
        success=True,
        message="Η ψήφος καταχωρήθηκε επιτυχώς. Ευχαριστούμε για τη συμμετοχή σας.",
        bill_id=req.bill_id,
        vote=vote_choice.value
    )


# ─── Citizen Vote Status ─────────────────────────────────────────────────────

@router.get("/{bill_id}/status", response_model=VoteStatusResponse)
async def get_vote_status(
    bill_id: str,
    nullifier_hash: str = Query(..., min_length=64, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    """Return whether this anonymous identity has already voted for a bill."""
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, f"Το νομοσχέδιο {bill_id} δεν βρέθηκε.")

    vote_result = await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == nullifier_hash,
            CitizenVote.bill_id == bill_id,
        )
    )
    vote = vote_result.scalar_one_or_none()
    can_correct = bool(
        vote and bill.status == BillStatus.WINDOW_24H and not vote.is_correction
    )
    return VoteStatusResponse(
        bill_id=bill_id,
        status=bill.status.value,
        has_voted=vote is not None,
        vote=vote.vote.value if vote else None,
        is_correction=bool(vote.is_correction) if vote else False,
        can_correct=can_correct,
    )


# ─── Vote Correction (einmalig, nur WINDOW_24H) ──────────────────────────────

class CorrectionRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=64, max_length=64)
    bill_id: str
    vote: str = Field(..., description="YES | NO | ABSTAIN | UNKNOWN")
    signature_hex: str = Field(..., description="Ed25519 Signatur des Payloads")


@router.put("/{bill_id}/correct")
async def correct_vote(bill_id: str, req: CorrectionRequest, db: AsyncSession = Depends(get_db)):
    """
    Einmalige Stimmkorrektur — nur in WINDOW_24H erlaubt.
    - Bill muss Status WINDOW_24H haben
    - Existing Vote muss existieren
    - is_correction darf nicht bereits True sein (einmal = einmal)
    - Ed25519 Signatur wird validiert
    """
    # 1. Bill laden + Status prüfen
    bill_query = select(ParliamentBill).where(ParliamentBill.id == bill_id)
    if zk_tier1_guard_enabled():
        bill_query = bill_query.with_for_update()
    bill_result = await db.execute(bill_query)
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, f"Το νομοσχέδιο {bill_id} δεν βρέθηκε.")

    if bill.status != BillStatus.WINDOW_24H:
        raise HTTPException(
            403,
            f"Η διόρθωση είναι δυνατή μόνο στις τελευταίες 24 ώρες. Τρέχουσα κατάσταση: {bill.status.value}"
        )

    # 2. Identity prüfen
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Δεν έχετε επαληθευτεί ή το κλειδί σας έχει ανακληθεί.")

    # 3. Existing Vote laden
    vote_result = await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == req.nullifier_hash,
            CitizenVote.bill_id == bill_id,
        )
    )
    existing = vote_result.scalar_one_or_none()
    if not existing:
        raise HTTPException(404, "Δεν βρέθηκε ψήφος — δεν έχετε ψηφίσει ακόμα.")

    # 4. Einmal-Korrektur prüfen
    if existing.is_correction:
        raise HTTPException(
            409,
            "Η διόρθωση έχει ήδη χρησιμοποιηθεί — επιτρέπεται μόνο μία διόρθωση ανά ψηφοφορία."
        )

    # 5. Neuen Vote validieren
    try:
        new_choice = VoteChoice(req.vote.upper())
    except ValueError:
        raise HTTPException(400, f"Μη έγκυρη ψήφος: {req.vote}")

    # 6. Ed25519 Signatur prüfen
    payload = f"{bill_id}:{req.vote.upper()}:{req.nullifier_hash}".encode()

    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.")

    await raise_if_zk_tier1_locked(
        db,
        bill_id=bill_id,
        bill_source=getattr(bill, "source", None),
        nullifier_hash=req.nullifier_hash,
    )

    # 7. Korrektur durchführen
    existing.original_vote = existing.vote.value
    existing.vote = new_choice
    existing.signature_hex = req.signature_hex
    existing.is_correction = True
    existing.corrected_at = datetime.now(timezone.utc).replace(tzinfo=None)
    existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()

    return {
        "status": "corrected",
        "bill_id": bill_id,
        "original_vote": existing.original_vote,
        "new_vote": new_choice.value,
        "corrected_at": existing.corrected_at.isoformat(),
    }


@router.get("/results/latest")
async def get_latest_result(db: AsyncSession = Depends(get_db)):
    """Most recent bill with at least 1 vote — for landing page live data."""
    from sqlalchemy import desc
    candidate_bill_ids = union(
        select(CitizenVote.bill_id.label("bill_id")),
        select(
            func.substring(ZkVoteReceipt.vote_scope_id, 6).label("bill_id")
        ).where(ZkVoteReceipt.vote_scope_id.like("bill:%")),
    ).subquery()
    tier1_vote_exists = (
        select(CitizenVote.id)
        .where(CitizenVote.bill_id == ParliamentBill.id)
        .exists()
    )
    parliament_zk_vote_exists = and_(
        func.coalesce(ParliamentBill.source, "PARLIAMENT") == "PARLIAMENT",
        (
            select(ZkVoteReceipt.id)
            .where(
                ZkVoteReceipt.vote_scope_id
                == func.concat("bill:", ParliamentBill.id)
            )
            .exists()
        ),
    )
    result = await db.execute(
        select(ParliamentBill)
        .join(candidate_bill_ids, candidate_bill_ids.c.bill_id == ParliamentBill.id)
        .where(ParliamentBill.status.in_([
            BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END, BillStatus.ACTIVE,
        ]))
        .where(public_bill_filter())
        .where(or_(tier1_vote_exists, parliament_zk_vote_exists))
        .order_by(desc(ParliamentBill.created_at))
        .limit(1)
    )
    bill = result.scalar_one_or_none()
    if bill is None:
        return {"bill_id": None, "total_votes": 0}

    totals = await aggregate_bill_vote_totals(
        db,
        bill.id,
        include_zk=(bill.source or "PARLIAMENT") == "PARLIAMENT",
    )
    total = totals.total
    if total < 1:
        return {"bill_id": None, "total_votes": 0}

    return {
        "bill_id": bill.id,
        "title_el": bill.title_el,
        "title_en": bill.title_en,
        "status": bill.status.value,
        "total_votes": total,
        "yes_pct": round(totals.yes / total * 100),
        "no_pct": round(totals.no / total * 100),
        "abstain_pct": round(totals.abstain / total * 100),
    }


@router.get("/results/in-progress")
async def get_votes_in_progress(db: AsyncSession = Depends(get_db)):
    """Landing page ticker data. Aggregated counts only; no nullifiers or vote rows."""
    threshold = votes_in_progress_threshold()
    result = await db.execute(text("""
        SELECT
            b.id,
            b.title_el,
            b.title_en,
            b.status::text AS status,
            b.governance_level::text AS governance_level,
            (COALESCE(tier.total_votes, 0) + COALESCE(zk.total_votes, 0))::int AS total_votes,
            (COALESCE(tier.yes_count, 0) + COALESCE(zk.yes_count, 0))::int AS yes_count,
            (COALESCE(tier.no_count, 0) + COALESCE(zk.no_count, 0))::int AS no_count,
            (COALESCE(tier.abstain_count, 0) + COALESCE(zk.abstain_count, 0))::int AS abstain_count
        FROM parliament_bills b
        LEFT JOIN (
            SELECT
                bill_id,
                COUNT(id)::int AS total_votes,
                SUM(CASE WHEN vote::text = 'YES' THEN 1 ELSE 0 END)::int AS yes_count,
                SUM(CASE WHEN vote::text = 'NO' THEN 1 ELSE 0 END)::int AS no_count,
                SUM(CASE WHEN vote::text = 'ABSTAIN' THEN 1 ELSE 0 END)::int AS abstain_count
            FROM citizen_votes
            GROUP BY bill_id
        ) tier ON tier.bill_id = b.id
        LEFT JOIN (
            SELECT
                regexp_replace(vote_scope_id, '^bill:', '') AS bill_id,
                COUNT(id)::int AS total_votes,
                SUM(CASE WHEN vote_commitment = 'YES' THEN 1 ELSE 0 END)::int AS yes_count,
                SUM(CASE WHEN vote_commitment = 'NO' THEN 1 ELSE 0 END)::int AS no_count,
                SUM(CASE WHEN vote_commitment = 'ABSTAIN' THEN 1 ELSE 0 END)::int AS abstain_count
            FROM zk_vote_receipts
            WHERE vote_scope_id LIKE 'bill:%'
              AND vote_commitment IN ('YES', 'NO', 'ABSTAIN', 'UNKNOWN')
            GROUP BY regexp_replace(vote_scope_id, '^bill:', '')
        ) zk ON zk.bill_id = b.id
            AND COALESCE(b.source, 'PARLIAMENT') = 'PARLIAMENT'
        WHERE b.admin_hidden IS NOT TRUE
          AND b.id NOT LIKE 'DEMO-%'
          AND (b.parliament_url IS NOT NULL OR b.diavgeia_ada IS NOT NULL)
          AND b.status::text IN ('ACTIVE', 'WINDOW_24H', 'PARLIAMENT_VOTED', 'OPEN_END')
          AND (COALESCE(tier.total_votes, 0) + COALESCE(zk.total_votes, 0)) >= :threshold
        ORDER BY (COALESCE(tier.total_votes, 0) + COALESCE(zk.total_votes, 0)) DESC, b.created_at DESC
        LIMIT 6
    """), {"threshold": threshold})
    bills = []
    for row in result.mappings():
        total = row["total_votes"] or 0
        yes = row["yes_count"] or 0
        no = row["no_count"] or 0
        abstain = row["abstain_count"] or 0
        bills.append({
            "bill_id": row["id"],
            "title_el": row["title_el"],
            "title_en": row["title_en"],
            "status": row["status"],
            "governance_level": row["governance_level"],
            "total_votes": total,
            "yes_pct": vote_percent(yes, total),
            "no_pct": vote_percent(no, total),
            "abstain_pct": vote_percent(abstain, total),
        })
    return {
        "threshold": threshold,
        "count": len(bills),
        "bills": bills,
        "message_el": "Σύντομα θα εμφανιστούν εδώ πραγματικές ψηφοφορίες με επαρκή συμμετοχή.",
        "message_en": "Real votes with enough participation will appear here soon.",
    }


@router.get("/{bill_id}/results", response_model=BillResults)
async def get_results(bill_id: str, db: AsyncSession = Depends(get_db)):
    """
    Abstimmungsergebnisse + Divergence Score.
    Visibility: HIDDEN (default for ACTIVE), WINDOW (24h), ALWAYS.
    PARLIAMENT_VOTED/OPEN_END always visible.
    """
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(status_code=404, detail=f"Το νομοσχέδιο {bill_id} δεν βρέθηκε.")

    # Visibility check
    visibility = getattr(bill, 'results_visibility', 'HIDDEN') or 'HIDDEN'
    always_visible = bill.status in (BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END, BillStatus.WINDOW_24H)
    if visibility == 'HIDDEN' and not always_visible and bill.status == BillStatus.ACTIVE:
        vote_date = bill.parliament_vote_date.strftime("%d/%m/%Y") if bill.parliament_vote_date else None
        return BillResults(
            bill_id=bill_id, title_el=bill.title_el, status=bill.status.value,
            source=bill.source or "PARLIAMENT",
            pill_el=bill.pill_el,
            summary_short_el=bill.summary_short_el,
            summary_long_el=bill.summary_long_el,
            ai_summary_reviewed=bool(bill.ai_summary_reviewed),
            parliament_url=bill.parliament_url,
            official_source_url=official_source_url(bill),
            diavgeia_ada=bill.diavgeia_ada,
            total_votes=0, yes_count=0, no_count=0, abstain_count=0, unknown_count=0,
            tier1_vote_count=0,
            zk_vote_count=0,
            yes_percent=0, no_percent=0, abstain_percent=0, divergence=None,
            representativity=compute_representativity(0),
            results_hidden=True,
            parliament_vote_date=vote_date,
            disclaimer_el="Τα αποτελέσματα θα είναι ορατά μετά τη λήξη της ψηφοφορίας.",
        )

    totals = await aggregate_bill_vote_totals(
        db,
        bill_id,
        include_zk=(bill.source or "PARLIAMENT") == "PARLIAMENT",
    )
    yes_c = totals.yes
    no_c = totals.no
    abs_c = totals.abstain
    unk_c = totals.unknown
    total = totals.total

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    divergence = compute_divergence(yes_c, no_c, abs_c, bill.party_votes_parliament)

    vote_date = bill.parliament_vote_date.strftime("%d/%m/%Y") if bill.parliament_vote_date else None
    return BillResults(
        bill_id=bill_id,
        title_el=bill.title_el,
        status=bill.status.value,
        source=bill.source or "PARLIAMENT",
        pill_el=bill.pill_el,
        summary_short_el=bill.summary_short_el,
        summary_long_el=bill.summary_long_el,
        ai_summary_reviewed=bool(bill.ai_summary_reviewed),
        parliament_url=bill.parliament_url,
        official_source_url=official_source_url(bill),
        diavgeia_ada=bill.diavgeia_ada,
        total_votes=total,
        tier1_vote_count=totals.tier1_total,
        zk_vote_count=totals.zk_total,
        yes_count=yes_c,
        no_count=no_c,
        abstain_count=abs_c,
        unknown_count=unk_c,
        yes_percent=pct(yes_c),
        no_percent=pct(no_c),
        abstain_percent=pct(abs_c),
        divergence=divergence,
        representativity=compute_representativity(total),
        results_hidden=False,
        parliament_vote_date=vote_date,
        disclaimer_el="Η ψηφοφορία αυτή δεν είναι νομικά δεσμευτική και εκφράζει μόνο τη γνώμη των εγγεγραμμένων χρηστών της πλατφόρμας.",
    )


@router.post("/{bill_id}/relevance")
async def vote_relevance(
    bill_id: str,
    req: RelevanceRequest,
    db: AsyncSession = Depends(get_db)
):
    """MOD-14: Up/Down Relevanz-Signal. Getrennt von inhaltlicher Stimme."""
    if req.signal not in [1, -1]:
        raise HTTPException(status_code=400, detail="Το σήμα πρέπει να είναι +1 ή -1.")

    # Identity prüfen
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=403, detail="Δεν έχετε επαληθευτεί.")

    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(status_code=404, detail=f"Το νομοσχέδιο {bill_id} δεν βρέθηκε.")

    # Verify Ed25519 signature
    # Canonical payload: "relevance:{bill_id}:{signal}:{nullifier_hash}"
    payload = f"relevance:{bill_id}:{req.signal}:{req.nullifier_hash}"
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(status_code=401, detail="Μη έγκυρη υπογραφή.")

    # Upsert Relevanz-Signal
    existing = await db.execute(
        select(BillRelevanceVote).where(
            BillRelevanceVote.nullifier_hash == req.nullifier_hash,
            BillRelevanceVote.bill_id == bill_id
        )
    )
    rel_vote = existing.scalar_one_or_none()

    if rel_vote:
        rel_vote.signal = req.signal
    else:
        db.add(BillRelevanceVote(
            nullifier_hash=req.nullifier_hash,
            bill_id=bill_id,
            signal=req.signal
        ))

    await db.commit()
    label = "σημαντικό" if req.signal == 1 else "λιγότερο σημαντικό"
    return {"success": True, "message": f"Το νομοσχέδιο σημειώθηκε ως '{label}'."}


# ─── VoteReceipt (ADR-008 stub) ─────────────────────────────────────────────

@router.get("/{bill_id}/receipt")
async def get_vote_receipt_deprecated(bill_id: str):
    """DEPRECATED: Use POST /{bill_id}/receipt with signed body."""
    raise HTTPException(status_code=410, detail="Endpoint deprecated. Use POST with signature_hex.")


class ReceiptRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    signature_hex: str = Field(..., min_length=64, description="Ed25519: receipt:{bill_id}:{nullifier_hash}")


@router.post("/{bill_id}/receipt")
async def post_vote_receipt(
    bill_id: str,
    req: ReceiptRequest,
    db: AsyncSession = Depends(get_db),
):
    """ADR-008: VoteReceipt — requires Ed25519 signature proof."""
    identity = (await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )).scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found.")

    # Verify Ed25519 signature: "receipt:{bill_id}:{nullifier_hash}"
    payload = f"receipt:{bill_id}:{req.nullifier_hash}"
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(status_code=401, detail="Μη έγκυρη υπογραφή.")

    vote = (await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == req.nullifier_hash,
            CitizenVote.bill_id == bill_id,
        )
    )).scalar_one_or_none()
    if not vote:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε ψήφος.")

    ts = vote.created_at.isoformat() if vote.created_at else datetime.now(timezone.utc).isoformat()
    salt = os.environ.get("SERVER_SALT", "")
    chain_proof = hmac.new(
        salt.encode(),
        f"{bill_id}:{req.nullifier_hash}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "bill_id": bill_id,
        "nullifier_prefix": req.nullifier_hash[:8] + "...",
        "vote": vote.vote.value,
        "timestamp": ts,
        "chain_proof": chain_proof,
        "status": "confirmed",
    }


# ── Post-Vote Consensus (-5 to +5) for OPEN_END Bills ───────────────────────

class ConsensusRequest(BaseModel):
    score: int = Field(..., ge=-5, le=5)
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    signature_hex: str = Field(..., min_length=64)


@router.post("/{bill_id}/consensus")
async def submit_consensus(
    bill_id: str,
    req: ConsensusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Post-vote consensus score for OPEN_END bills. Scale: -5 (full resistance) to +5 (full consensus)."""
    from sqlalchemy import text

    # Bill must exist and be OPEN_END
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, "Το νομοσχέδιο δεν βρέθηκε")
    if bill.status != BillStatus.OPEN_END:
        raise HTTPException(400, "Η συναίνεση είναι δυνατή μόνο για ψηφισμένα νομοσχέδια (OPEN_END)")

    # Verify identity exists
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Η ταυτότητα δεν βρέθηκε ή έχει ανακληθεί")

    # Region-Berechtigung prüfen (gleiche Logik wie Vote)
    from models import GovernanceLevel
    gov_level = getattr(bill, "governance_level", None)
    if gov_level and gov_level not in (GovernanceLevel.NATIONAL, GovernanceLevel.INSTITUTIONAL):
        if gov_level == GovernanceLevel.REGIONAL:
            if not identity.periferia_id or identity.periferia_id != bill.periferia_id:
                raise HTTPException(403, "Αυτή η αξιολόγηση αφορά μόνο κατοίκους αυτής της Περιφέρειας.")
        elif gov_level == GovernanceLevel.MUNICIPAL:
            if not identity.dimos_id or identity.dimos_id != bill.dimos_id:
                raise HTTPException(403, "Αυτή η αξιολόγηση αφορά μόνο κατοίκους αυτού του Δήμου.")

    # Ed25519 Signatur verifizieren
    consensus_payload = f"{bill_id}:{req.score}:{req.nullifier_hash}".encode()
    if not verify_signature(identity.public_key_hex, consensus_payload, req.signature_hex):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.")

    # Upsert consensus vote
    await db.execute(text("""
        INSERT INTO consensus_votes (nullifier_hash, bill_id, score)
        VALUES (:nullifier, :bill_id, :score)
        ON CONFLICT (nullifier_hash, bill_id)
        DO UPDATE SET score = :score, created_at = NOW()
    """), {"nullifier": req.nullifier_hash, "bill_id": bill_id, "score": req.score})

    # Update aggregate on bill
    agg = await db.execute(text("""
        SELECT AVG(score)::float, COUNT(*) FROM consensus_votes WHERE bill_id = :bill_id
    """), {"bill_id": bill_id})
    row = agg.fetchone()
    avg_score = round(row[0], 2) if row[0] is not None else 0.0
    count = row[1] or 0

    bill.consensus_score = avg_score
    bill.consensus_count = count

    # Record in cplm_history
    weight = req.score / 5.0
    await db.execute(text("""
        INSERT INTO cplm_history (nullifier_hash, economic_score, social_score, trigger_type, trigger_bill_id)
        VALUES (:nh, :econ, :soc, 'consensus', :bill_id)
    """), {"nh": req.nullifier_hash, "econ": weight * 0.05, "soc": 0.0, "bill_id": bill_id})

    await db.commit()

    return {
        "bill_id": bill_id,
        "your_score": req.score,
        "consensus_score": avg_score,
        "consensus_count": count,
    }


@router.get("/compass/personal")
async def get_personal_compass_deprecated():
    """DEPRECATED: Use POST /compass/personal with signed body."""
    raise HTTPException(status_code=410, detail="Endpoint deprecated. Use POST with signature_hex.")


class CompassRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    signature_hex: str = Field(..., min_length=64, description="Ed25519: compass_personal:{nullifier_hash}")


@router.post("/compass/personal")
async def post_personal_compass(
    req: CompassRequest,
    db: AsyncSession = Depends(get_db),
):
    """Personal compass position — requires Ed25519 signature proof."""
    from sqlalchemy import text

    identity = (await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )).scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found.")

    # Verify Ed25519 signature: "compass_personal:{nullifier_hash}"
    payload = f"compass_personal:{req.nullifier_hash}"
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(status_code=401, detail="Μη έγκυρη υπογραφή.")

    history = await db.execute(text("""
        SELECT economic_score, social_score, trigger_type, trigger_bill_id, created_at
        FROM cplm_history WHERE nullifier_hash = :nh ORDER BY created_at DESC LIMIT 50
    """), {"nh": req.nullifier_hash})
    entries = [{"economic": r[0], "social": r[1], "type": r[2], "bill_id": r[3],
                "date": r[4].isoformat() if r[4] else None} for r in history]

    x = sum(e["economic"] for e in entries)
    y = sum(e["social"] for e in entries)

    return {
        "nullifier_prefix": req.nullifier_hash[:8] + "...",
        "position": {"x": round(x, 4), "y": round(y, 4)},
        "history": entries,
        "total_entries": len(entries),
    }

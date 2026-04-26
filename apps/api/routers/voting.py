"""
MOD-04: CitizenVote Router
POST /api/v1/vote               — Stimme abgeben (Ed25519 signiert)
GET  /api/v1/vote/{bill_id}/results — Ergebnisse + Divergence Score
POST /api/v1/vote/{bill_id}/relevance — Up/Down Relevanz (MOD-14)
"""
import hashlib
import hmac
import json
import gc
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError

from database import get_db
from models import (
    CitizenVote, VoteChoice, IdentityRecord, KeyStatus,
    ParliamentBill, BillStatus, BillRelevanceVote
)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import verify_signature

router = APIRouter(prefix="/api/v1/vote", tags=["MOD-04 CitizenVote"])

# ─── Repräsentativität ───────────────────────────────────────────────────────

GREECE_ELIGIBLE_VOTERS = 9_900_000
GREECE_POPULATION = 10_400_000

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


# ─── Schemas ──────────────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    nullifier_hash: str  = Field(..., min_length=64, max_length=64)
    bill_id:        str
    vote:           str  = Field(..., description="YES | NO | ABSTAIN | UNKNOWN")
    signature_hex:  str  = Field(..., description="Ed25519 Signatur des Payloads")

class VoteResponse(BaseModel):
    success:    bool
    message:    str
    bill_id:    str
    vote:       str

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
    total_votes:      int
    yes_count:        int
    no_count:         int
    abstain_count:    int
    unknown_count:    int
    yes_percent:      float
    no_percent:       float
    abstain_percent:  float
    divergence:       DivergenceResult | None
    representativity: dict | None = None
    disclaimer_el:    str

class RelevanceRequest(BaseModel):
    nullifier_hash: str
    signal:         int  = Field(..., description="+1 wichtig / -1 unwichtig")


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
            detail="Nicht verifiziert oder Key revoziert. Bitte /identity/verify aufrufen."
        )

    # 2. Bill-Status prüfen
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == req.bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Gesetz {req.bill_id} nicht gefunden.")

    votable_states = [BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END]
    if bill.status not in votable_states:
        raise HTTPException(
            status_code=400,
            detail=f"Abstimmung nicht möglich. Status: {bill.status.value}. "
                   f"Erlaubt: ACTIVE, WINDOW_24H, OPEN_END."
        )

    # 3. Stimme validieren
    try:
        vote_choice = VoteChoice(req.vote.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Ungültige Stimme: {req.vote}. Erlaubt: YES, NO, ABSTAIN, UNKNOWN")

    # 4. Ed25519 Signatur verifizieren
    payload = json.dumps({
        "bill_id":       req.bill_id,
        "vote":          req.vote.upper(),
        "nullifier_hash": req.nullifier_hash,
    }, sort_keys=True).encode()

    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige Signatur. Stimme wird abgelehnt."
        )

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
                detail="Stimme bereits abgegeben. Änderung erst im 24h-Fenster möglich."
            )
        existing_vote.vote = vote_choice
        existing_vote.signature_hex = req.signature_hex
        existing_vote.updated_at = datetime.utcnow()
        await db.commit()
        return VoteResponse(
            success=True,
            message="Stimme erfolgreich geändert.",
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
        )
        db.add(new_vote)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Stimme bereits abgegeben (Race Condition verhindert)."
        )

    return VoteResponse(
        success=True,
        message="Stimme erfolgreich abgegeben. Danke für Ihre Teilnahme.",
        bill_id=req.bill_id,
        vote=vote_choice.value
    )


@router.get("/results/latest")
async def get_latest_result(db: AsyncSession = Depends(get_db)):
    """Most recent bill with at least 1 vote — for landing page live data."""
    from sqlalchemy import desc
    # Find bill with most votes
    result = await db.execute(
        select(ParliamentBill)
        .where(ParliamentBill.status.in_([
            BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END, BillStatus.ACTIVE,
        ]))
        .order_by(desc(ParliamentBill.created_at))
        .limit(5)
    )
    bills = result.scalars().all()
    for bill in bills:
        yes_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.YES))
        no_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.NO))
        abs_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.ABSTAIN))
        yes_c, no_c, abs_c = yes_r.scalar() or 0, no_r.scalar() or 0, abs_r.scalar() or 0
        total = yes_c + no_c + abs_c
        if total > 0:
            return {
                "bill_id": bill.id,
                "title_el": bill.title_el,
                "title_en": bill.title_en,
                "status": bill.status.value,
                "total_votes": total,
                "yes_pct": round(yes_c / total * 100),
                "no_pct": round(no_c / total * 100),
                "abstain_pct": round(abs_c / total * 100),
            }
    return {"bill_id": None, "total_votes": 0}


@router.get("/{bill_id}/results", response_model=BillResults)
async def get_results(bill_id: str, db: AsyncSession = Depends(get_db)):
    """
    Öffentliche Abstimmungsergebnisse + Divergence Score.
    Immer verfügbar — auch während laufender Abstimmung.
    """
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Gesetz {bill_id} nicht gefunden.")

    # Einzelne Counts
    yes_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.YES))
    no_r  = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.NO))
    abs_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.ABSTAIN))
    unk_r = await db.execute(select(func.count()).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.UNKNOWN))

    yes_c = yes_r.scalar() or 0
    no_c  = no_r.scalar()  or 0
    abs_c = abs_r.scalar() or 0
    unk_c = unk_r.scalar() or 0
    total = yes_c + no_c + abs_c + unk_c

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    divergence = compute_divergence(yes_c, no_c, abs_c, bill.party_votes_parliament)

    return BillResults(
        bill_id=bill_id,
        title_el=bill.title_el,
        status=bill.status.value,
        total_votes=total,
        yes_count=yes_c,
        no_count=no_c,
        abstain_count=abs_c,
        unknown_count=unk_c,
        yes_percent=pct(yes_c),
        no_percent=pct(no_c),
        abstain_percent=pct(abs_c),
        divergence=divergence,
        representativity=compute_representativity(total),
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
        raise HTTPException(status_code=400, detail="Signal muss +1 oder -1 sein.")

    # Identity prüfen
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE
        )
    )
    if not id_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Nicht verifiziert.")

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
    label = "wichtig" if req.signal == 1 else "weniger wichtig"
    return {"success": True, "message": f"Gesetz als '{label}' markiert."}


# ─── VoteReceipt (ADR-008 stub) ─────────────────────────────────────────────

@router.get("/{bill_id}/receipt")
async def get_vote_receipt(
    bill_id: str,
    x_nullifier: str = Header(..., alias="X-Nullifier"),
    db: AsyncSession = Depends(get_db),
):
    """
    ADR-008: VoteReceipt — server-signed proof that a vote was recorded.

    Stub implementation using HMAC-SHA256 chain_proof.
    Full Tier-1 receipt (Ed25519 server signature) deferred
    pending mobile schema migration (ADR-022).
    """
    result = await db.execute(
        select(CitizenVote).where(
            CitizenVote.nullifier_hash == x_nullifier,
            CitizenVote.bill_id == bill_id,
        )
    )
    vote = result.scalar_one_or_none()
    if not vote:
        raise HTTPException(status_code=404, detail="Keine Stimme gefunden.")

    ts = vote.created_at.isoformat() if vote.created_at else datetime.utcnow().isoformat()
    salt = os.environ.get("SERVER_SALT", "")
    chain_proof = hmac.new(
        salt.encode(),
        f"{bill_id}:{x_nullifier}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "bill_id": bill_id,
        "nullifier_hash": x_nullifier,
        "vote": vote.vote.value,
        "timestamp": ts,
        "chain_proof": chain_proof,
        "status": "confirmed",
        "note": "Tier-1 full receipt pending mobile schema migration (ADR-022)",
    }

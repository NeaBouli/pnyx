"""
MOD-12: MP Comparison — "Dein Abgeordneter"
Vergleicht Bürger-Stimmen mit Parteistimmen im Parlament.

Daten: party_votes_parliament JSONB (bereits in DB)
Format: {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΠΑΡΩΝ", ...}

@ai-anchor MOD12_MP_COMPARISON
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models import ParliamentBill, CitizenVote, Party, BillStatus, VoteChoice

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/mp", tags=["MOD-12 MP Comparison"])

K_MIN = 10


def normalize_vote(v: str) -> str:
    v = v.upper().strip()
    if v in ("ΝΑΙ", "YES", "NAI"):          return "YES"
    if v in ("ΟΧΙ", "NO", "OXI"):           return "NO"
    if v in ("ΠΑΡΩΝ", "PRESENT", "ABSTAIN"): return "ABSTAIN"
    return "UNKNOWN"


async def get_party_map(db: AsyncSession) -> dict:
    result = await db.execute(select(Party))
    return {p.abbreviation: p for p in result.scalars().all()}


async def citizen_majority_for(db: AsyncSession, bill_id: str):
    """Returns (majority: str, yes: int, no: int, total: int)"""
    yes   = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.YES)) or 0
    no    = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.NO)) or 0
    total = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id)) or 0
    majority = "YES" if yes >= no else "NO"
    return majority, yes, no, total


@router.get("/parties")
async def list_parties(db: AsyncSession = Depends(get_db)):
    """Alle Parteien mit Parlamentspräsenz."""
    result = await db.execute(select(Party).order_by(Party.name_el))
    return {
        "data": [{
            "id": p.id, "name_el": p.name_el, "name_en": p.name_en,
            "abbreviation": p.abbreviation, "color_hex": p.color_hex,
        } for p in result.scalars().all()],
    }


@router.get("/compare/{party_abbr}")
async def party_comparison(party_abbr: str, db: AsyncSession = Depends(get_db)):
    """Vergleicht Bürger-Mehrheit mit Parteistimme für alle abgestimmten Bills."""
    party_map = await get_party_map(db)
    party = party_map.get(party_abbr.upper())

    if not party:
        result = await db.execute(
            select(Party).where(
                Party.abbreviation.ilike(f"%{party_abbr}%") |
                Party.name_el.ilike(f"%{party_abbr}%")
            )
        )
        party = result.scalar_one_or_none()
        if not party:
            raise HTTPException(404, f"Partei '{party_abbr}' nicht gefunden")

    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.status.in_([BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END])
        ).order_by(ParliamentBill.parliament_vote_date.desc().nullslast())
    )
    bills = result.scalars().all()

    comparisons = []
    agree = disagree = no_data = 0

    for bill in bills:
        if not bill.party_votes_parliament:
            no_data += 1; continue
        party_vote_raw = bill.party_votes_parliament.get(party.abbreviation)
        if not party_vote_raw:
            no_data += 1; continue

        party_vote = normalize_vote(party_vote_raw)
        majority, yes, no_cnt, total = await citizen_majority_for(db, bill.id)

        if total < K_MIN:
            no_data += 1; continue

        match = (majority == "YES" and party_vote == "YES") or (majority == "NO" and party_vote == "NO")
        if match: agree += 1
        else:     disagree += 1

        comparisons.append({
            "bill_id": bill.id, "title_el": bill.title_el[:100],
            "date": bill.parliament_vote_date.isoformat() if bill.parliament_vote_date else None,
            "party_vote": party_vote, "citizen_majority": majority,
            "citizen_yes_pct": round(yes / total * 100, 1),
            "citizen_total": total, "match": match,
            "categories": bill.categories or [],
        })

    total_analyzed = agree + disagree
    agreement_pct = round(agree / total_analyzed * 100, 1) if total_analyzed > 0 else None

    return {
        "party": {
            "abbreviation": party.abbreviation, "name_el": party.name_el,
            "name_en": party.name_en, "color_hex": party.color_hex,
        },
        "summary": {
            "bills_analyzed": total_analyzed, "bills_agree": agree,
            "bills_disagree": disagree, "bills_no_data": no_data,
            "agreement_pct": agreement_pct,
            "headline_el": (
                f"Η {party.abbreviation} συμφωνεί με την πλειοψηφία των πολιτών "
                f"σε {agree} από {total_analyzed} νόμους ({agreement_pct}%)"
            ) if total_analyzed > 0 else "Ανεπαρκή δεδομένα",
        },
        "comparisons": comparisons,
        "k_anonymity": f">={K_MIN} Stimmen", "data_license": "CC BY 4.0",
    }


@router.get("/ranking")
async def party_ranking(db: AsyncSession = Depends(get_db)):
    """Rangliste aller Parteien nach Übereinstimmung mit Bürgermehrheit."""
    result = await db.execute(select(Party))
    parties = result.scalars().all()

    bills_result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.status.in_([BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END])
        )
    )
    bills = bills_result.scalars().all()

    ranking = []
    for party in parties:
        agree = disagree = 0
        for bill in bills:
            if not bill.party_votes_parliament:
                continue
            pvr = bill.party_votes_parliament.get(party.abbreviation)
            if not pvr:
                continue
            pv = normalize_vote(pvr)
            majority, yes, no_cnt, total = await citizen_majority_for(db, bill.id)
            if total < K_MIN:
                continue
            if (majority == "YES" and pv == "YES") or (majority == "NO" and pv == "NO"):
                agree += 1
            else:
                disagree += 1

        total_analyzed = agree + disagree
        if total_analyzed == 0:
            continue
        ranking.append({
            "party_abbr": party.abbreviation, "party_name_el": party.name_el,
            "color_hex": party.color_hex,
            "bills_analyzed": total_analyzed, "bills_agree": agree,
            "agreement_pct": round(agree / total_analyzed * 100, 1),
        })

    ranking.sort(key=lambda x: x["agreement_pct"], reverse=True)
    for i, r in enumerate(ranking):
        r["rank"] = i + 1

    return {
        "ranking": ranking,
        "interpretation": "Höherer Wert = Partei stimmt häufiger wie Bürgermehrheit",
        "k_anonymity": f">={K_MIN}", "data_license": "CC BY 4.0",
    }


@router.get("/bill/{bill_id}")
async def bill_party_breakdown(bill_id: str, db: AsyncSession = Depends(get_db)):
    """Alle Parteistimmen vs. Bürgermehrheit für ein Bill."""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")

    majority, yes, no_cnt, total = await citizen_majority_for(db, bill_id)
    party_map = await get_party_map(db)

    breakdown = []
    for abbr, vote_raw in (bill.party_votes_parliament or {}).items():
        party = party_map.get(abbr)
        vote = normalize_vote(vote_raw)
        match = None
        if total >= K_MIN and majority in ("YES", "NO"):
            match = (majority == "YES" and vote == "YES") or (majority == "NO" and vote == "NO")
        breakdown.append({
            "party_abbr": abbr, "party_name": party.name_el if party else abbr,
            "color_hex": party.color_hex if party else "#94a3b8",
            "vote": vote, "vote_raw": vote_raw, "match_citizens": match,
        })

    breakdown.sort(key=lambda x: (x["vote"], x["party_abbr"]))

    return {
        "bill_id": bill_id, "title_el": bill.title_el, "status": bill.status.value,
        "citizen_votes": {"yes": yes, "no": no_cnt, "total": total, "majority": majority,
                          "yes_pct": round(yes / total * 100, 1) if total > 0 else 0},
        "party_votes": breakdown,
        "k_anonymity_met": total >= K_MIN, "data_license": "CC BY 4.0",
    }


@router.get("/info")
async def mp_info():
    return {
        "name": "Ekklesia.gr MP Comparison API",
        "endpoints": {
            "GET /api/v1/mp/parties":         "Alle Parteien",
            "GET /api/v1/mp/ranking":         "Rangliste nach Übereinstimmung",
            "GET /api/v1/mp/compare/{abbr}":  "Partei vs. Bürgermehrheit",
            "GET /api/v1/mp/bill/{id}":       "Parteistimmen für ein Bill",
        },
        "data_license": "CC BY 4.0",
    }

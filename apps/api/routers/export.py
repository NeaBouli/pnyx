"""
MOD-14: Data Export
CSV + JSON Download aller aggregierten Ergebnisse.
NIEMALS: Individual-Votes, Nullifier, persönliche Daten.

Lizenz: CC BY 4.0
Für: NGOs, Medien, Forscher, Bürger

@ai-anchor MOD14_EXPORT
"""
import csv
import io
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models import ParliamentBill, CitizenVote, BillStatus, VoteChoice, Party

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["MOD-14 Data Export"])


async def get_all_results(db: AsyncSession) -> list[dict]:
    """Aggregierte Ergebnisse aller Bills."""
    result = await db.execute(
        select(ParliamentBill).order_by(
            ParliamentBill.parliament_vote_date.desc().nullslast()
        )
    )
    bills = result.scalars().all()

    rows = []
    for bill in bills:
        yes     = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.YES)) or 0
        no      = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.NO)) or 0
        abstain = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.ABSTAIN)) or 0
        total = yes + no + abstain

        def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

        divergence = None
        parliament_result = None
        if bill.party_votes_parliament:
            parl_yes = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΝΑΙ", "YES"))
            parl_no  = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΟΧΙ", "NO"))
            passed = parl_yes >= parl_no
            parliament_result = "APPROVED" if passed else "REJECTED"
            if total > 0:
                divergence = round(abs((yes / total) - (1.0 if passed else 0.0)), 3)

        rows.append({
            "bill_id":              bill.id,
            "title_el":             bill.title_el,
            "title_en":             bill.title_en or "",
            "categories":           ",".join(bill.categories or []),
            "status":               bill.status.value,
            "parliament_vote_date": bill.parliament_vote_date.isoformat() if bill.parliament_vote_date else "",
            "parliament_result":    parliament_result or "",
            "citizen_yes":          yes,
            "citizen_no":           no,
            "citizen_abstain":      abstain,
            "citizen_total":        total,
            "yes_pct":              pct(yes),
            "no_pct":               pct(no),
            "abstain_pct":          pct(abstain),
            "divergence_score":     divergence if divergence is not None else "",
            "arweave_tx_id":        bill.arweave_tx_id or "",
            "arweave_url":          f"https://arweave.net/{bill.arweave_tx_id}" if bill.arweave_tx_id else "",
        })

    return rows


@router.get("/bills.csv")
async def export_bills_csv(db: AsyncSession = Depends(get_db)):
    """Alle Gesetzentwürfe als CSV. Lizenz: CC BY 4.0"""
    rows = await get_all_results(db)

    output = io.StringIO()
    output.write("# ekklesia.gr Data Export\n")
    output.write("# Lizenz: CC BY 4.0\n")
    output.write(f"# Exportiert: {datetime.now(timezone.utc).isoformat()}\n")
    output.write("# NIEMALS ENTHALTEN: Individual-Votes, Nullifier, persoenliche Daten\n#\n")

    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=ekklesia_bills_{datetime.now().strftime('%Y%m%d')}.csv",
            "X-Data-License": "CC BY 4.0",
        }
    )


@router.get("/results.json")
async def export_results_json(db: AsyncSession = Depends(get_db)):
    """Alle Abstimmungsergebnisse als JSON. Lizenz: CC BY 4.0"""
    rows = await get_all_results(db)

    return JSONResponse(
        content={
            "data_license": "CC BY 4.0",
            "source": "ekklesia.gr",
            "source_code": "https://github.com/NeaBouli/pnyx",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(rows),
            "data": rows,
        },
        headers={
            "Content-Disposition": f"attachment; filename=ekklesia_results_{datetime.now().strftime('%Y%m%d')}.json",
            "X-Data-License": "CC BY 4.0",
        }
    )


@router.get("/divergence.csv")
async def export_divergence_csv(
    min_votes: int = Query(10, description="Minimum Stimmen"),
    db: AsyncSession = Depends(get_db)
):
    """Divergence Score Ranking als CSV. Sortiert nach höchster Abweichung."""
    rows = await get_all_results(db)

    diverge_rows = [
        r for r in rows
        if r["citizen_total"] >= min_votes and r["divergence_score"] != ""
    ]
    diverge_rows.sort(
        key=lambda r: float(r["divergence_score"]) if r["divergence_score"] else 0,
        reverse=True
    )

    output = io.StringIO()
    output.write("# ekklesia.gr Divergence Score Export\n")
    output.write("# 0.0 = Uebereinstimmung, 1.0 = Gegensaetzlichkeit\n")
    output.write(f"# Lizenz: CC BY 4.0 — {datetime.now(timezone.utc).isoformat()}\n#\n")

    if diverge_rows:
        fields = ["bill_id", "title_el", "parliament_result", "citizen_yes", "citizen_no",
                  "citizen_total", "yes_pct", "no_pct", "divergence_score",
                  "parliament_vote_date", "arweave_tx_id"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(diverge_rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=ekklesia_divergence_{datetime.now().strftime('%Y%m%d')}.csv",
            "X-Data-License": "CC BY 4.0",
        }
    )


@router.get("/parties.json")
async def export_parties_json(db: AsyncSession = Depends(get_db)):
    """Alle Parteien als JSON."""
    result = await db.execute(select(Party))
    parties = result.scalars().all()

    return JSONResponse(
        content={
            "data_license": "CC BY 4.0",
            "source": "ekklesia.gr",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(parties),
            "data": [{
                "id": p.id, "name_el": p.name_el, "name_en": p.name_en,
                "abbreviation": p.abbreviation, "color_hex": p.color_hex,
            } for p in parties]
        }
    )


@router.get("/info")
async def export_info():
    """Übersicht aller Export-Endpoints."""
    return {
        "name": "Ekklesia.gr Data Export",
        "license": "CC BY 4.0",
        "endpoints": {
            "GET /api/v1/export/bills.csv":      "Alle Bills + Ergebnisse als CSV",
            "GET /api/v1/export/results.json":   "Alle Ergebnisse als JSON",
            "GET /api/v1/export/divergence.csv": "Divergence Score Ranking als CSV",
            "GET /api/v1/export/parties.json":   "Parteien als JSON",
        },
        "never_exported": ["individual_votes", "nullifier_hashes", "phone_numbers", "ip_addresses"],
        "attribution": "Daten von ekklesia.gr (CC BY 4.0)",
    }

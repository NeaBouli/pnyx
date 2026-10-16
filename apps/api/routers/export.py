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
from sqlalchemy import select, func, cast, String, union_all

from database import get_db
from models import ParliamentBill, CitizenVote, BillStatus, VoteChoice, Party, ZkVoteReceipt
from services.bill_visibility import public_bill_filter, results_hidden
from services.small_cell import small_cell_k, suppress_public_cells
from routers.voting import compute_divergence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["MOD-14 Data Export"])


async def get_all_results(db: AsyncSession, min_votes: int = 0) -> list[dict]:
    """Aggregierte Ergebnisse aller Bills."""
    threshold = small_cell_k()
    min_votes = max(min_votes, threshold)
    result = await db.execute(
        select(ParliamentBill).where(public_bill_filter()).order_by(
            ParliamentBill.parliament_vote_date.desc().nullslast()
        )
    )
    bills = result.scalars().all()

    vote_query = (
        select(CitizenVote.bill_id, CitizenVote.vote, func.count(CitizenVote.id))
        .group_by(CitizenVote.bill_id, CitizenVote.vote)
    )
    if threshold:
        # Use the same combined population as public results: a Tier-1-only
        # export could be subtracted from it to recover a small ZK choice.
        events = union_all(
            select(CitizenVote.bill_id, cast(CitizenVote.vote, String).label("vote")),
            select(ParliamentBill.id, ZkVoteReceipt.vote_commitment)
            .join(ParliamentBill, ZkVoteReceipt.vote_scope_id == func.concat("bill:", ParliamentBill.id))
            .where(func.coalesce(ParliamentBill.source, "PARLIAMENT") == "PARLIAMENT",
                   ZkVoteReceipt.vote_commitment.in_([c.value for c in VoteChoice])),
        ).subquery("export_vote_events")
        vote_query = select(events.c.bill_id, events.c.vote, func.count()).group_by(
            events.c.bill_id, events.c.vote)
    vote_result = await db.execute(vote_query)
    vote_counts: dict[str, dict[VoteChoice, int]] = {}
    for bill_id, vote, count in vote_result.all():
        vote_counts.setdefault(bill_id, {})[VoteChoice(vote)] = count

    rows = []
    for bill in bills:
        # A running vote with hidden results exports no counts (T-599).
        counts = {} if results_hidden(bill) else vote_counts.get(bill.id, {})
        yes = counts.get(VoteChoice.YES, 0)
        no = counts.get(VoteChoice.NO, 0)
        abstain = counts.get(VoteChoice.ABSTAIN, 0)
        unknown = counts.get(VoteChoice.UNKNOWN, 0)
        total = yes + no + abstain + unknown
        if total < min_votes:
            continue

        def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

        divergence = compute_divergence(
            yes, no, abstain, bill.party_votes_parliament, unknown
        )
        parliament_result = None
        if divergence is not None:
            parliament_result = (
                "APPROVED"
                if divergence.parliament_result == "ΕΓΚΡΙΘΗΚΕ"
                else "REJECTED"
            )

        rows.append(suppress_public_cells({
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
            "citizen_unknown":      unknown,
            "citizen_total":        total,
            "yes_pct":              pct(yes),
            "no_pct":               pct(no),
            "abstain_pct":          pct(abstain),
            "divergence_score":     divergence.score if divergence is not None else "",
            "arweave_tx_id":        bill.arweave_tx_id or "",
            "arweave_url":          f"https://arweave.net/{bill.arweave_tx_id}" if bill.arweave_tx_id else "",
        }, choices=("citizen_yes", "citizen_no", "citizen_abstain", "citizen_unknown"),
            total="citizen_total", percentages=("yes_pct", "no_pct", "abstain_pct"),
            derived=("divergence_score",), k=threshold))

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
async def export_results_json(
    min_votes: int = Query(0, ge=0, description="Minimum votes; effective minimum is max(min_votes, PUBLIC_RESULTS_MIN_COUNT)"),
    db: AsyncSession = Depends(get_db),
):
    """Alle Abstimmungsergebnisse als JSON. Lizenz: CC BY 4.0"""
    rows = await get_all_results(db, min_votes=min_votes)

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
    min_votes: int = Query(10, ge=0, description="Minimum votes; cannot lower PUBLIC_RESULTS_MIN_COUNT"),
    db: AsyncSession = Depends(get_db)
):
    """Divergence Score Ranking als CSV. Sortiert nach höchster Abweichung."""
    rows = await get_all_results(db, min_votes=min_votes)

    diverge_rows = [
        r for r in rows
        if r["citizen_total"] >= min_votes and r["divergence_score"] not in ("", None)
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
        if small_cell_k():
            fields.extend(["suppressed", "suppression_k"])
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

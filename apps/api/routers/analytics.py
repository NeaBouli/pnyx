"""
MOD-06: Analytics + Demographics
Divergence Trends, Abstimmungsstatistiken, k-Anonymity >= 10.

NIEMALS: Individual-Votes, Nullifier, persönliche Daten.
k-Anonymity: Demografische Daten nur wenn Gruppe >= 10 Stimmen.

@ai-anchor MOD06_ANALYTICS
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import DateTime, String, cast, select, func, and_, extract, Integer, union_all

from database import get_db
from models import ParliamentBill, CitizenVote, BillStatus, VoteChoice, ZkVoteReceipt
from services.bill_visibility import is_public_bill, public_bill_filter, public_bill_with_demo_filter
from services.zk_vote_aggregation import (
    VoteTotals,
    aggregate_bill_vote_totals,
    bill_vote_events_query,
    count_public_votes,
    include_zk_for_bill,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["MOD-06 Analytics"])

K_ANONYMITY_MIN = 10


async def compute_divergence(
    db: AsyncSession,
    bill_id: str,
    bill: ParliamentBill,
    totals: VoteTotals | None = None,
) -> Optional[float]:
    totals = totals or await aggregate_bill_vote_totals(
        db,
        bill_id,
        include_zk=include_zk_for_bill(bill),
    )
    total = totals.total

    if total < K_ANONYMITY_MIN or not bill.party_votes_parliament:
        return None

    yes_pct = totals.yes / total
    parl_yes = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΝΑΙ", "YES"))
    parl_no  = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΟΧΙ", "NO"))
    passed   = parl_yes >= parl_no
    return round(abs(yes_pct - (1.0 if passed else 0.0)), 3)


@router.get("/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    """Plattform-weite Statistiken + Divergence Übersicht."""
    _real = public_bill_with_demo_filter()
    total_bills  = await db.scalar(select(func.count(ParliamentBill.id)).where(_real)) or 0
    total_votes = await count_public_votes(db)
    active_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            _real,
            ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.WINDOW_24H])
        )
    ) or 0
    voted_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            _real,
            ParliamentBill.status == BillStatus.PARLIAMENT_VOTED
        )
    ) or 0

    week_ago = datetime.utcnow() - timedelta(days=7)  # naive to match DB column
    recent_votes = await count_public_votes(db, since=week_ago)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_votes = await count_public_votes(db, since=today)

    result = await db.execute(
        select(ParliamentBill).where(_real, ParliamentBill.status == BillStatus.PARLIAMENT_VOTED)
    )
    voted = result.scalars().all()

    divergence_scores = []
    for bill in voted:
        score = await compute_divergence(db, bill.id, bill)
        if score is not None:
            divergence_scores.append(score)

    avg_divergence = round(sum(divergence_scores) / len(divergence_scores), 3) if divergence_scores else None

    return {
        "platform": "ekklesia.gr",
        "bills":  {"total": total_bills, "active": active_bills, "voted": voted_bills},
        "votes":  {"total": total_votes, "last_7_days": recent_votes, "today": today_votes,
                   "avg_per_bill": round(total_votes / total_bills, 1) if total_bills > 0 else 0},
        "divergence": {
            "bills_analyzed":  len(divergence_scores),
            "average_score":   avg_divergence,
            "high_divergence": sum(1 for s in divergence_scores if s > 0.4),
            "convergence":     sum(1 for s in divergence_scores if s <= 0.2),
        },
        "k_anonymity_min": K_ANONYMITY_MIN,
        "data_license": "CC BY 4.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/divergence-trends")
async def divergence_trends(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Divergence Score Trends über Zeit."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(ParliamentBill).where(
            and_(
                ParliamentBill.status == BillStatus.PARLIAMENT_VOTED,
                public_bill_filter(),
                ParliamentBill.parliament_vote_date >= since.date()
            )
        ).order_by(ParliamentBill.parliament_vote_date)
    )
    bills = result.scalars().all()

    trends = []
    cat_divergence: dict = {}

    for bill in bills:
        totals = await aggregate_bill_vote_totals(
            db,
            bill.id,
            include_zk=include_zk_for_bill(bill),
        )
        score = await compute_divergence(db, bill.id, bill, totals)
        if score is None:
            continue

        total = totals.total

        parl_yes = sum(1 for v in (bill.party_votes_parliament or {}).values() if v in ("ΝΑΙ", "YES"))
        parl_no  = sum(1 for v in (bill.party_votes_parliament or {}).values() if v in ("ΟΧΙ", "NO"))

        trends.append({
            "bill_id":          bill.id,
            "title_el":         bill.title_el[:80],
            "date":             bill.parliament_vote_date.isoformat() if bill.parliament_vote_date else None,
            "divergence_score": score,
            "divergence_label": "high" if score > 0.4 else "medium" if score > 0.2 else "low",
            "citizen_total":    total,
            "citizen_yes_pct":  round(totals.yes / total * 100, 1) if total > 0 else 0,
            "parliament_result": "APPROVED" if parl_yes >= parl_no else "REJECTED",
            "categories":       bill.categories or [],
        })

        for cat in (bill.categories or []):
            cat_divergence.setdefault(cat, []).append(score)

    cat_summary = {
        cat: {"count": len(scores), "avg_score": round(sum(scores) / len(scores), 3)}
        for cat, scores in cat_divergence.items()
    }

    return {
        "period_days": days, "bills_analyzed": len(trends),
        "trends": trends, "by_category": cat_summary,
        "k_anonymity_min": K_ANONYMITY_MIN, "data_license": "CC BY 4.0",
    }


@router.get("/votes-timeline")
async def votes_timeline(
    bill_id: Optional[str] = Query(None),
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Abstimmungs-Zeitverlauf aggregiert nach Tag."""
    try:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        if bill_id:
            bill = await db.get(ParliamentBill, bill_id)
            if not bill or not is_public_bill(bill):
                raise HTTPException(404, f"Bill {bill_id} nicht gefunden")
            events = bill_vote_events_query(
                bill_id,
                include_zk=include_zk_for_bill(bill),
            )
        else:
            tier1_events = (
                select(
                    cast(CitizenVote.created_at, DateTime(timezone=False)).label("created_at"),
                    cast(CitizenVote.vote, String).label("vote"),
                )
                .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
                .where(public_bill_filter(), ~CitizenVote.bill_id.like("DEMO-%"))
            )
            zk_events = (
                select(
                    cast(ZkVoteReceipt.created_at, DateTime(timezone=False)).label("created_at"),
                    ZkVoteReceipt.vote_commitment.label("vote"),
                )
                .join(ParliamentBill, ZkVoteReceipt.vote_scope_id == func.concat("bill:", ParliamentBill.id))
                .where(
                    public_bill_filter(),
                    ParliamentBill.source == "PARLIAMENT",
                    ~ParliamentBill.id.like("DEMO-%"),
                    ZkVoteReceipt.vote_commitment.in_([choice.value for choice in VoteChoice]),
                )
            )
            events = union_all(tier1_events, zk_events).subquery("public_vote_events")

        day_col = func.date_trunc("day", events.c.created_at).label("day")
        query = (
            select(day_col, events.c.vote, func.count().label("count"))
            .where(events.c.created_at >= since)
            .group_by(day_col, events.c.vote)
            .order_by(day_col)
        )
        result = await db.execute(query)
        rows = result.all()
        timeline: dict = {}
        for row in rows:
            day = row.day.strftime("%Y-%m-%d") if row.day else "unknown"
            if day not in timeline:
                timeline[day] = {
                    "date": day,
                    "yes": 0,
                    "no": 0,
                    "abstain": 0,
                    "unknown": 0,
                    "total": 0,
                }
            vote_key = str(row.vote).lower()
            if vote_key in timeline[day]:
                timeline[day][vote_key] = row.count
            timeline[day]["total"] += row.count
        return {
            "period_days": days, "bill_id": bill_id,
            "timeline": sorted(timeline.values(), key=lambda x: x["date"]),
            "note": "Aggregiert nach Tag",
        }
    except (AttributeError, TypeError, ValueError) as e:
        logger.warning("[votes-timeline] Data processing error: %s", e)
        return {"period_days": days, "bill_id": bill_id, "timeline": [], "note": "Keine Daten"}


@router.get("/top-divergence")
async def top_divergence(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Top Bills nach Divergence Score — höchste Abweichung zuerst."""
    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.status == BillStatus.PARLIAMENT_VOTED,
            public_bill_filter(),
        )
    )
    bills = result.scalars().all()

    ranked = []
    for bill in bills:
        totals = await aggregate_bill_vote_totals(
            db,
            bill.id,
            include_zk=include_zk_for_bill(bill),
        )
        score = await compute_divergence(db, bill.id, bill, totals)
        if score is None:
            continue

        parl_yes = sum(1 for v in (bill.party_votes_parliament or {}).values() if v in ("ΝΑΙ", "YES"))
        parl_no  = sum(1 for v in (bill.party_votes_parliament or {}).values() if v in ("ΟΧΙ", "NO"))

        ranked.append({
            "bill_id":          bill.id,
            "title_el":         bill.title_el,
            "divergence_score": score,
            "divergence_pct":   round(score * 100, 1),
            "citizen_total":    totals.total,
            "parliament_result": "APPROVED" if parl_yes >= parl_no else "REJECTED",
            "categories":       bill.categories or [],
            "arweave_url":      f"https://arweave.net/{bill.arweave_tx_id}" if bill.arweave_tx_id else None,
        })

    ranked.sort(key=lambda x: x["divergence_score"], reverse=True)
    for i, r in enumerate(ranked[:limit]):
        r["rank"] = i + 1

    return {
        "count": len(ranked[:limit]), "data": ranked[:limit],
        "k_anonymity": f">={K_ANONYMITY_MIN} Stimmen", "data_license": "CC BY 4.0",
    }


@router.get("/bill/{bill_id}")
async def bill_analytics(bill_id: str, db: AsyncSession = Depends(get_db)):
    """Vollständige Analytik für ein einzelnes Bill."""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")

    totals = await aggregate_bill_vote_totals(
        db,
        bill_id,
        include_zk=include_zk_for_bill(bill),
    )
    yes, no, abstain, unknown = totals.yes, totals.no, totals.abstain, totals.unknown
    total = totals.total

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    divergence = await compute_divergence(db, bill_id, bill, totals)

    events = bill_vote_events_query(
        bill_id,
        include_zk=include_zk_for_bill(bill),
    )
    weekday_result = await db.execute(
        select(
            extract("dow", events.c.created_at).cast(Integer).label("weekday"),
            func.count().label("count")
        ).group_by(extract("dow", events.c.created_at).cast(Integer))
    )
    DAYS = ["Κυρ", "Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ"]
    by_weekday = [
        {"day": DAYS[r.weekday], "count": r.count}
        for r in weekday_result.all()
        if r.count >= K_ANONYMITY_MIN
    ]

    return {
        "bill_id": bill_id, "title_el": bill.title_el, "status": bill.status.value,
        "votes": {"yes": yes, "no": no, "abstain": abstain, "unknown": unknown, "total": total,
                  "tier1_total": totals.tier1_total, "zk_total": totals.zk_total,
                  "yes_pct": pct(yes), "no_pct": pct(no), "abstain_pct": pct(abstain),
                  "unknown_pct": pct(unknown)},
        "divergence": {
            "score": divergence,
            "pct": round(divergence * 100, 1) if divergence is not None else None,
            "label": "high" if divergence is not None and divergence > 0.4 else "medium" if divergence is not None and divergence > 0.2 else "low",
            "available": divergence is not None,
        },
        "by_weekday": by_weekday,
        "k_anonymity_min": K_ANONYMITY_MIN, "data_license": "CC BY 4.0",
    }


async def compute_cumulative_representation(db: AsyncSession) -> dict:
    """
    Kumulative Repräsentation: Durchschnittliche Übereinstimmung zwischen
    Bürgermeinung und Parlamentsentscheid über alle abgestimmten Bills.

    score = 1.0 - avg_divergence → 100% = perfekte Übereinstimmung
    Berechnet über ALLE Bills mit Status PARLIAMENT_VOTED oder OPEN_END
    die mindestens 1 Citizen-Vote haben.
    """
    # Alle Bills mit Votes
    bills_result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.status.in_([BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END]),
            public_bill_filter(),
        )
    )
    bills = bills_result.scalars().all()

    scores = []
    bill_details = []
    total_citizen_votes = 0

    for bill in bills:
        totals = await aggregate_bill_vote_totals(
            db,
            bill.id,
            include_zk=include_zk_for_bill(bill),
        )
        total = totals.total

        if total == 0:
            continue

        total_citizen_votes += total

        # Compute divergence for this bill
        div_score = await compute_divergence(db, bill.id, bill, totals)
        if div_score is not None:
            scores.append(div_score)
            representation = round((1.0 - div_score) * 100, 1)
            bill_details.append({
                "bill_id": bill.id,
                "title_el": bill.title_el[:60] if bill.title_el else "",
                "citizen_votes": total,
                "divergence": round(div_score * 100, 1),
                "representation": representation,
            })

    if not scores:
        return {
            "cumulative_representation": None,
            "cumulative_divergence": None,
            "bills_analyzed": 0,
            "total_citizen_votes": 0,
            "message_el": "Δεν υπάρχουν αρκετά δεδομένα ακόμη.",
            "message_en": "Not enough data yet.",
            "last_bill": None,
            "bills": [],
        }

    avg_div = sum(scores) / len(scores)
    cumulative_rep = round((1.0 - avg_div) * 100, 1)

    # Status label
    if cumulative_rep >= 80:
        label_el, label_en, color = "Υψηλή Αντιπροσωπευτικότητα", "High Representation", "#22c55e"
    elif cumulative_rep >= 50:
        label_el, label_en, color = "Μέτρια Αντιπροσωπευτικότητα", "Moderate Representation", "#f59e0b"
    else:
        label_el, label_en, color = "Χαμηλή Αντιπροσωπευτικότητα", "Low Representation", "#ef4444"

    return {
        "cumulative_representation": cumulative_rep,
        "cumulative_divergence": round(avg_div * 100, 1),
        "bills_analyzed": len(scores),
        "total_citizen_votes": total_citizen_votes,
        "label_el": label_el,
        "label_en": label_en,
        "color": color,
        "last_bill": bill_details[-1] if bill_details else None,
        "bills": bill_details,
    }


@router.get("/representation")
async def cumulative_representation(db: AsyncSession = Depends(get_db)):
    return await compute_cumulative_representation(db)


@router.get("/info")
async def analytics_info():
    """Übersicht aller Analytics-Endpoints."""
    return {
        "name": "Ekklesia.gr Analytics API",
        "privacy": f"k-Anonymity >={K_ANONYMITY_MIN}",
        "endpoints": {
            "GET /api/v1/analytics/overview":          "Plattform-Statistiken",
            "GET /api/v1/analytics/representation":    "Kumulative Repräsentation (live)",
            "GET /api/v1/analytics/divergence-trends": "Divergence Trends über Zeit",
            "GET /api/v1/analytics/votes-timeline":    "Vote Zeitverlauf (aggregiert)",
            "GET /api/v1/analytics/top-divergence":    "Top Bills nach Divergence",
            "GET /api/v1/analytics/bill/{id}":         "Analytik für einzelnes Bill",
        },
        "never_tracked": ["individual_votes", "nullifier_hashes", "phone_numbers"],
    }

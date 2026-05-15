"""
MOD-03: Parliament Router
GET  /api/v1/bills              — Alle Gesetzentwürfe (gefiltert nach Status)
GET  /api/v1/bills/{bill_id}    — Einzelner Gesetzentwurf mit Details
POST /api/v1/bills/{bill_id}/transition — Lifecycle-Übergang (intern/admin)
GET  /api/v1/bills/trending     — Nach Relevanz-Score sortiert
"""
import logging
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db

DISCOURSE_BASE = os.getenv("DISCOURSE_BASE_URL", "https://pnyx.ekklesia.gr")
from dependencies import verify_admin_key
from models import (
    ParliamentBill, BillStatus, BillStatusLog, BillRelevanceVote,
    CitizenVote, VoteChoice,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bills", tags=["MOD-03 Parliament"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BillSummary(BaseModel):
    id:                  str
    title_el:            str
    title_en:            str | None
    pill_el:             str | None
    pill_en:             str | None
    categories:          list | None
    status:              str
    governance_level:    str | None = "NATIONAL"
    parliament_vote_date: str | None
    parliament_url:      str | None = None
    relevance_score:     int | None = 0
    forum_topic_id:      int | None = None
    forum_topic_url:     str | None = None
    created_at:          str | None = None
    ai_summary_reviewed: bool = False
    arweave_tx_id:       str | None = None

class BillDetail(BaseModel):
    id:                     str
    title_el:               str
    title_en:               str | None
    pill_el:                str | None
    pill_en:                str | None
    summary_short_el:       str | None
    summary_short_en:       str | None
    summary_long_el:        str | None
    summary_long_en:        str | None
    categories:             list | None
    party_votes_parliament: dict | None
    status:                 str
    governance_level:       str | None = "NATIONAL"
    parliament_vote_date:   str | None
    parliament_url:         str | None = None
    forum_topic_id:         int | None = None
    forum_topic_url:        str | None = None
    ai_summary_reviewed:    bool

class TransitionRequest(BaseModel):
    new_status: str
    admin_key:  str   # Einfacher Admin-Schutz (Beta)

class BillCreateRequest(BaseModel):
    id:                   str
    title_el:             str
    title_en:             str | None = None
    pill_el:              str | None = None
    pill_en:              str | None = None
    summary_short_el:     str | None = None
    summary_short_en:     str | None = None
    categories:           list | None = None
    parliament_vote_date: str | None = None


# ─── Lifecycle Validator ───────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    BillStatus.ANNOUNCED:        [BillStatus.ACTIVE],
    BillStatus.ACTIVE:           [BillStatus.WINDOW_24H],
    BillStatus.WINDOW_24H:       [BillStatus.PARLIAMENT_VOTED],
    BillStatus.PARLIAMENT_VOTED: [BillStatus.OPEN_END],
    BillStatus.OPEN_END:         [],
}

STATUS_LABELS = {
    "ANNOUNCED":        "Ανακοινώθηκε",
    "ACTIVE":           "Ανοιχτή Ψηφοφορία",
    "WINDOW_24H":       "24ω πριν την Βουλή",
    "PARLIAMENT_VOTED": "Η Βουλή αποφάσισε",
    "OPEN_END":         "Αρχείο — Ανοιχτό",
}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BillSummary])
async def get_bills(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    """Gibt Gesetzentwürfe zurück, optional gefiltert nach Status/Kategorie."""
    query = select(ParliamentBill).order_by(
        ParliamentBill.parliament_vote_date.desc().nullslast(),
        ParliamentBill.created_at.desc()
    ).limit(limit).offset(offset)

    if status_filter:
        try:
            s = BillStatus(status_filter.upper())
            query = query.where(ParliamentBill.status == s)
        except ValueError:
            raise HTTPException(400, f"Ungültiger Status: {status_filter}")

    result = await db.execute(query)
    bills = result.scalars().all()

    return [BillSummary(
        id=b.id,
        title_el=b.title_el,
        title_en=b.title_en,
        pill_el=b.pill_el,
        pill_en=b.pill_en,
        categories=b.categories,
        status=b.status.value,
        governance_level=b.governance_level.value if b.governance_level else "NATIONAL",
        parliament_vote_date=b.parliament_vote_date.isoformat() if b.parliament_vote_date else None,
        parliament_url=b.parliament_url,
        forum_topic_id=b.forum_topic_id,
        forum_topic_url=f"{DISCOURSE_BASE}/t/{b.forum_topic_id}" if b.forum_topic_id else None,
        created_at=b.created_at.isoformat() if b.created_at else None,
        ai_summary_reviewed=b.ai_summary_reviewed or False,
        arweave_tx_id=b.arweave_tx_id,
    ) for b in bills]


@router.get("/trending", response_model=list[BillSummary])
async def get_trending(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Gesetzentwürfe sortiert nach Relevanz-Score (Up/Down Votes, MOD-14).
    Nur ACTIVE + WINDOW_24H Gesetze im Trending Feed.
    """
    # Relevanz-Score: Σ(signal) pro Bill
    relevance_subq = (
        select(
            BillRelevanceVote.bill_id,
            func.sum(BillRelevanceVote.signal).label("score")
        )
        .group_by(BillRelevanceVote.bill_id)
        .subquery()
    )

    query = (
        select(ParliamentBill, relevance_subq.c.score)
        .outerjoin(relevance_subq, ParliamentBill.id == relevance_subq.c.bill_id)
        .where(ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.WINDOW_24H]))
        .order_by(relevance_subq.c.score.desc().nullslast())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [BillSummary(
        id=row[0].id,
        title_el=row[0].title_el,
        title_en=row[0].title_en,
        pill_el=row[0].pill_el,
        pill_en=row[0].pill_en,
        categories=row[0].categories,
        status=row[0].status.value,
        parliament_vote_date=row[0].parliament_vote_date.isoformat() if row[0].parliament_vote_date else None,
        parliament_url=row[0].parliament_url,
        relevance_score=row[1] or 0,
        forum_topic_id=row[0].forum_topic_id,
        forum_topic_url=f"{DISCOURSE_BASE}/t/{row[0].forum_topic_id}" if row[0].forum_topic_id else None,
    ) for row in rows]


@router.get("/{bill_id}", response_model=BillDetail)
async def get_bill(bill_id: str, db: AsyncSession = Depends(get_db)):
    """Einzelner Gesetzentwurf mit vollständigen Details und KI-Zusammenfassungen."""
    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Gesetz {bill_id} nicht gefunden.")

    return BillDetail(
        id=bill.id,
        title_el=bill.title_el,
        title_en=bill.title_en,
        pill_el=bill.pill_el,
        pill_en=bill.pill_en,
        summary_short_el=bill.summary_short_el,
        summary_short_en=bill.summary_short_en,
        summary_long_el=bill.summary_long_el,
        summary_long_en=bill.summary_long_en,
        categories=bill.categories,
        party_votes_parliament=bill.party_votes_parliament,
        status=bill.status.value,
        governance_level=bill.governance_level.value if bill.governance_level else "NATIONAL",
        parliament_vote_date=bill.parliament_vote_date.isoformat() if bill.parliament_vote_date else None,
        parliament_url=bill.parliament_url,
        forum_topic_id=bill.forum_topic_id,
        forum_topic_url=f"{DISCOURSE_BASE}/t/{bill.forum_topic_id}" if bill.forum_topic_id else None,
        ai_summary_reviewed=bill.ai_summary_reviewed,
    )


@router.get("/{bill_id}/summary")
async def get_bill_summary(
    request: Request,
    bill_id: str,
    lang: str = "el",
    db: AsyncSession = Depends(get_db),
):
    """AI-generated plain-language bill summary (cached in Redis 7d)."""
    import redis.asyncio as aioredis
    import os
    from services.ollama_service import summarize_bill

    # Redis cache
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    r = aioredis.from_url(redis_url, decode_responses=True)
    cache_key = f"bill_summary:{bill_id}:{lang}"
    try:
        cached = await r.get(cache_key)
        if cached:
            return {"bill_id": bill_id, "summary": cached, "cached": True, "lang": lang}
    except Exception:
        pass

    # Get bill
    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")

    title = bill.title_el if lang == "el" else (bill.title_en or bill.title_el)
    content = bill.summary_long_el if lang == "el" else (bill.summary_long_en or bill.summary_long_el or "")
    pill = bill.pill_el if lang == "el" else (bill.pill_en or bill.pill_el or "")

    summary = await summarize_bill(
        title, content or "", lang,
        pill=pill or "",
        status=bill.status.value if bill.status else "",
        categories=bill.categories or [],
    )
    if not summary:
        raise HTTPException(status_code=503, detail="AI summary generation failed")

    # Cache 7 days
    try:
        await r.setex(cache_key, 604800, summary)
    except Exception:
        pass

    return {"bill_id": bill_id, "summary": summary, "cached": False, "lang": lang}


@router.post("/{bill_id}/transition")
async def transition_bill(
    bill_id: str,
    req: TransitionRequest,
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Lifecycle-Übergang eines Gesetzentwurfs.
    Nur valide Übergänge laut VALID_TRANSITIONS erlaubt.
    """

    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Gesetz {bill_id} nicht gefunden.")

    try:
        new_status = BillStatus(req.new_status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Ungültiger Status: {req.new_status}")

    allowed = VALID_TRANSITIONS.get(bill.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Übergang {bill.status.value} → {new_status.value} nicht erlaubt. "
                   f"Erlaubt: {[s.value for s in allowed]}"
        )

    old_status = bill.status
    bill.status = new_status
    bill.status_changed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Audit-Log
    log = BillStatusLog(
        bill_id=bill_id,
        from_status=old_status.value,
        to_status=new_status.value,
    )
    db.add(log)
    await db.commit()

    # MOD-08: Arweave Auto-Publish bei PARLIAMENT_VOTED
    arweave_tx_id = None
    if new_status == BillStatus.PARLIAMENT_VOTED:
        try:
            from routers.arweave import build_audit_trail, publish_to_arweave

            logs_result = await db.execute(
                select(BillStatusLog)
                .where(BillStatusLog.bill_id == bill_id)
                .order_by(BillStatusLog.changed_at)
            )
            status_logs = logs_result.scalars().all()

            yes     = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.YES)) or 0
            no      = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.NO)) or 0
            abstain = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.ABSTAIN)) or 0
            total   = yes + no + abstain

            divergence = None
            if total > 0 and bill.party_votes_parliament:
                yes_pct = yes / total
                parliament_yes = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΝΑΙ", "YES"))
                parliament_no  = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΟΧΙ", "NO"))
                authority_passed = parliament_yes >= parliament_no
                divergence = round(abs(yes_pct - (1.0 if authority_passed else 0.0)), 3)

            # Snapshot Timestamp — fixiert zum Zeitpunkt des Parlamentsbeschlusses
            snapshot_timestamp = datetime.now(timezone.utc).isoformat()
            logger.info(f"[MOD-08] Snapshot fixiert: {snapshot_timestamp} für {bill_id}")

            audit_trail = build_audit_trail(
                bill=bill,
                status_logs=status_logs,
                vote_results={"yes": yes, "no": no, "abstain": abstain, "total": total},
                snapshot_timestamp=snapshot_timestamp,
                divergence_score=divergence,
            )

            tx_id = await publish_to_arweave(audit_trail, bill_id)
            if tx_id:
                bill.arweave_tx_id = tx_id
                await db.commit()
                arweave_tx_id = tx_id
                logger.info(f"[MOD-08] Arweave TX: {tx_id}")
        except Exception as arweave_err:
            logger.error(f"[MOD-08] Arweave publish error: {arweave_err}")

    # MOD-07: Notification publishen
    try:
        from routers.notifications import publish_bill_event
        await publish_bill_event("bill.status_changed", bill_id, {
            "old_status": old_status.value,
            "new_status": new_status.value,
            "label_el": STATUS_LABELS.get(new_status.value, new_status.value),
        })
    except Exception as notify_err:
        logger.warning(f"[MOD-07] Notification failed: {notify_err}")

    return {
        "success": True,
        "bill_id": bill_id,
        "from": old_status.value,
        "to": new_status.value,
        "label_el": STATUS_LABELS.get(new_status.value, new_status.value),
        "changed_at": datetime.now(timezone.utc).isoformat(),
        "arweave_tx_id": arweave_tx_id,
    }


@router.post("/admin/create")
async def create_bill(
    req: BillCreateRequest,
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db)
):
    """Admin: Neuen Gesetzentwurf anlegen."""

    existing = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == req.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Gesetz {req.id} existiert bereits.")

    vote_date = None
    if req.parliament_vote_date:
        vote_date = datetime.fromisoformat(req.parliament_vote_date)

    bill = ParliamentBill(
        id=req.id,
        title_el=req.title_el,
        title_en=req.title_en,
        pill_el=req.pill_el,
        pill_en=req.pill_en,
        summary_short_el=req.summary_short_el,
        summary_short_en=req.summary_short_en,
        categories=req.categories,
        parliament_vote_date=vote_date,
        status=BillStatus.ANNOUNCED,
    )
    db.add(bill)
    await db.commit()
    return {"success": True, "bill_id": req.id, "status": "ANNOUNCED"}

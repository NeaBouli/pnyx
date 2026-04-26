"""
MOD-15: Admin Panel
Bill Management, AI Summary Review, Seed Management.

Schutz: ADMIN_KEY (Beta) → gov.gr Auth (Alpha)

@ai-anchor MOD15_ADMIN
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models import (
    ParliamentBill, CitizenVote, BillStatus,
    BillStatusLog, VoteChoice, Party, Statement
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["MOD-15 Admin"])

ADMIN_KEY = os.environ.get("ADMIN_KEY", "dev-admin-key")


def verify_admin(admin_key: str = Query(...)):
    if admin_key != ADMIN_KEY:
        raise HTTPException(403, "Ungültiger Admin-Key")
    return admin_key


class BillUpdateRequest(BaseModel):
    title_el:              Optional[str] = None
    title_en:              Optional[str] = None
    pill_el:               Optional[str] = None
    pill_en:               Optional[str] = None
    summary_short_el:      Optional[str] = None
    summary_short_en:      Optional[str] = None
    summary_long_el:       Optional[str] = None
    summary_long_en:       Optional[str] = None
    categories:            Optional[list] = None
    party_votes_parliament: Optional[dict] = None
    ai_summary_reviewed:   Optional[bool] = None


class BillCreateRequest(BaseModel):
    id:                    str
    title_el:              str
    title_en:              Optional[str] = None
    pill_el:               Optional[str] = None
    pill_en:               Optional[str] = None
    summary_short_el:      Optional[str] = None
    summary_short_en:      Optional[str] = None
    summary_long_el:       Optional[str] = None
    summary_long_en:       Optional[str] = None
    categories:            Optional[list] = None
    parliament_vote_date:  Optional[str] = None
    party_votes_parliament: Optional[dict] = None


@router.get("/dashboard")
async def admin_dashboard(_key=Depends(verify_admin), db: AsyncSession = Depends(get_db)):
    """Admin Dashboard."""
    total_bills   = await db.scalar(select(func.count(ParliamentBill.id))) or 0
    total_votes   = await db.scalar(select(func.count(CitizenVote.id))) or 0
    total_parties = await db.scalar(select(func.count(Party.id))) or 0
    total_stmts   = await db.scalar(select(func.count(Statement.id))) or 0
    unreviewed    = await db.scalar(
        select(func.count(ParliamentBill.id)).where(ParliamentBill.ai_summary_reviewed == False)
    ) or 0

    status_counts = {}
    for status in BillStatus:
        status_counts[status.value] = await db.scalar(
            select(func.count(ParliamentBill.id)).where(ParliamentBill.status == status)
        ) or 0

    result = await db.execute(
        select(ParliamentBill).order_by(ParliamentBill.created_at.desc()).limit(5)
    )
    recent = result.scalars().all()

    return {
        "overview": {
            "total_bills": total_bills, "total_votes": total_votes,
            "total_parties": total_parties, "total_stmts": total_stmts,
            "unreviewed_ai": unreviewed,
        },
        "bills_by_status": status_counts,
        "recent_bills": [{
            "id": b.id, "title_el": b.title_el[:60],
            "status": b.status.value, "reviewed": b.ai_summary_reviewed,
        } for b in recent],
    }


@router.get("/bills")
async def admin_list_bills(
    status: Optional[str] = None, reviewed: Optional[bool] = None,
    limit: int = Query(50, le=200), offset: int = 0,
    _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """Alle Bills mit Admin-Details."""
    query = select(ParliamentBill).order_by(ParliamentBill.created_at.desc()).limit(limit).offset(offset)
    if status:
        try: query = query.where(ParliamentBill.status == BillStatus(status.upper()))
        except ValueError: raise HTTPException(400, f"Ungültiger Status: {status}")
    if reviewed is not None:
        query = query.where(ParliamentBill.ai_summary_reviewed == reviewed)

    result = await db.execute(query)
    bills = result.scalars().all()

    return {"count": len(bills), "data": [{
        "id": b.id, "title_el": b.title_el, "status": b.status.value,
        "ai_summary_reviewed": b.ai_summary_reviewed,
        "has_pill": bool(b.pill_el), "has_summary_short": bool(b.summary_short_el),
        "has_party_votes": bool(b.party_votes_parliament),
        "arweave_tx_id": b.arweave_tx_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    } for b in bills]}


@router.post("/bills")
async def admin_create_bill(req: BillCreateRequest, _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)):
    """Neues Bill anlegen."""
    existing = await db.get(ParliamentBill, req.id)
    if existing:
        raise HTTPException(409, f"Bill {req.id} existiert bereits")

    vote_date = None
    if req.parliament_vote_date:
        from datetime import date
        vote_date = date.fromisoformat(req.parliament_vote_date)

    bill = ParliamentBill(
        id=req.id, title_el=req.title_el, title_en=req.title_en,
        pill_el=req.pill_el, pill_en=req.pill_en,
        summary_short_el=req.summary_short_el, summary_short_en=req.summary_short_en,
        summary_long_el=req.summary_long_el, summary_long_en=req.summary_long_en,
        categories=req.categories or [], parliament_vote_date=vote_date,
        party_votes_parliament=req.party_votes_parliament,
        status=BillStatus.ANNOUNCED, ai_summary_reviewed=False,
    )
    db.add(bill)
    await db.commit()
    logger.info(f"[MOD-15] Bill erstellt: {req.id}")
    return {"success": True, "bill_id": req.id, "status": "ANNOUNCED"}


@router.patch("/bills/{bill_id}")
async def admin_update_bill(
    bill_id: str, req: BillUpdateRequest,
    _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """Bill aktualisieren."""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")

    updates = req.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(bill, field, value)
    await db.commit()

    logger.info(f"[MOD-15] Bill aktualisiert: {bill_id} — {list(updates.keys())}")
    return {"success": True, "bill_id": bill_id, "updated": list(updates.keys())}


@router.post("/bills/{bill_id}/review")
async def admin_review_summary(
    bill_id: str, approved: bool = Query(True),
    _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """KI-Zusammenfassung als geprüft markieren."""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")
    bill.ai_summary_reviewed = approved
    await db.commit()
    return {"success": True, "bill_id": bill_id, "reviewed": approved}


@router.post("/bills/{bill_id}/party-votes")
async def admin_set_party_votes(
    bill_id: str, party_votes: dict,
    _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """Parteistimmen setzen. Format: {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ"}"""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")
    bill.party_votes_parliament = party_votes
    await db.commit()
    return {"success": True, "bill_id": bill_id, "party_votes": party_votes}


@router.delete("/bills/{bill_id}/votes")
async def admin_reset_votes(
    bill_id: str, confirm: str = Query(...),
    _key=Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """DEV ONLY: Alle Votes für ein Bill löschen."""
    if os.environ.get("ENVIRONMENT") == "production":
        raise HTTPException(403, "Reset nicht in Produktion erlaubt")
    if confirm != "CONFIRM_DELETE":
        raise HTTPException(400, "confirm muss 'CONFIRM_DELETE' sein")

    result = await db.execute(select(CitizenVote).where(CitizenVote.bill_id == bill_id))
    votes = result.scalars().all()
    count = len(votes)
    for vote in votes:
        await db.delete(vote)
    await db.commit()

    logger.warning(f"[MOD-15] DEV: {count} Votes für {bill_id} gelöscht")
    return {"success": True, "deleted": count, "bill_id": bill_id}


@router.get("/stats")
async def admin_stats(_key=Depends(verify_admin), db: AsyncSession = Depends(get_db)):
    """Detaillierte Statistiken."""
    yes     = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.vote == VoteChoice.YES)) or 0
    no      = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.vote == VoteChoice.NO)) or 0
    abstain = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.vote == VoteChoice.ABSTAIN)) or 0
    total = yes + no + abstain
    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    return {
        "votes": {"total": total, "yes": yes, "no": no, "abstain": abstain,
                  "yes_pct": pct(yes), "no_pct": pct(no), "abstain_pct": pct(abstain)},
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "admin_key_set": ADMIN_KEY != "dev-admin-key",
    }


@router.post("/scraper/heal-status")
async def admin_heal_status(_key=Depends(verify_admin)):
    """Check auto-healing scraper status and healed selectors."""
    import redis.asyncio as aioredis
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    r = aioredis.from_url(redis_url, decode_responses=True)
    keys = []
    try:
        async for key in r.scan_iter("scraper:healed:*"):
            val = await r.get(key)
            ttl = await r.ttl(key)
            keys.append({"key": key, "selector": val, "ttl_hours": round(ttl / 3600, 1)})
    except Exception:
        pass
    from services.ollama_service import ollama_available
    return {
        "ollama_available": await ollama_available(),
        "healed_selectors": keys,
        "total": len(keys),
    }


@router.post("/logs/explain")
async def admin_explain_logs(
    _key=Depends(verify_admin),
    lines: int = Query(default=30, ge=5, le=200),
):
    """Ask Ollama to analyze recent API container logs."""
    from services.ollama_service import ollama_generate, ollama_available
    if not await ollama_available():
        raise HTTPException(503, "Ollama unavailable")

    import subprocess
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), "/proc/1/fd/2"],
            capture_output=True, text=True, timeout=5,
        )
        log_text = result.stderr or result.stdout or ""
    except Exception:
        log_text = "(Could not read container logs)"

    if not log_text.strip():
        return {"analysis": "No log output available", "lines": 0}

    prompt = (
        "You are a server admin assistant for a Greek democracy platform (ekklesia.gr).\n"
        "Analyze these API server logs. Report:\n"
        "1. Any errors or warnings\n"
        "2. Unusual patterns\n"
        "3. Recommendations\n"
        "Be concise. Answer in English.\n\n"
        f"Logs:\n{log_text[:3000]}\n\n"
        "Analysis:"
    )
    analysis = await ollama_generate(prompt, max_tokens=300)
    return {"analysis": analysis, "lines": lines}


@router.get("/deepl/usage")
async def deepl_usage():
    """Public: DeepL API usage stats (no auth needed — no sensitive data)."""
    import httpx
    api_key = os.getenv("DEEPL_API_KEY", "")
    if not api_key:
        return {"available": False, "character_count": 0, "character_limit": 0}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api-free.deepl.com/v2/usage",
                headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "available": True,
                "character_count": data.get("character_count", 0),
                "character_limit": data.get("character_limit", 0),
            }
    except Exception:
        return {"available": False, "character_count": 0, "character_limit": 0}


@router.post("/bills/{bill_id}/fetch-text")
async def admin_fetch_bill_text(
    bill_id: str,
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Fetch bill text from parliament via Jina Reader + update DB."""
    import redis.asyncio as aioredis
    from services.parliament_fetcher import enrich_bill_with_text
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    r = aioredis.from_url(redis_url, decode_responses=True)
    result = await enrich_bill_with_text(bill_id, db, r)
    return result


@router.post("/bills/{bill_id}/set-text")
async def admin_set_bill_text(
    bill_id: str,
    text: str = "",
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually set bill text (for when auto-fetch fails)."""
    import redis.asyncio as aioredis
    from sqlalchemy import select
    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} not found")
    bill.summary_long_el = text
    await db.commit()
    # Clear cache
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    r = aioredis.from_url(redis_url, decode_responses=True)
    await r.delete(f"bill_summary:{bill_id}:el")
    await r.delete(f"bill_summary:{bill_id}:en")
    return {"success": True, "bill_id": bill_id, "text_length": len(text)}


# ── Compass Question Generator ────────────────────────────────────────────

@router.post("/compass/generate-questions")
async def admin_generate_compass(
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate new compass questions from recent bills (Ollama + DeepL)."""
    from services.compass_generator import run_compass_update
    questions = await run_compass_update(db)
    return {
        "generated": len(questions),
        "status": "pending",
        "questions": questions,
    }


@router.get("/compass/pending-review")
async def admin_compass_pending(
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all pending (unapproved) compass questions."""
    result = await db.execute(
        select(Statement)
        .where(Statement.is_active == False, Statement.generated_by == "ollama")
        .order_by(Statement.created_at.desc())
    )
    pending = result.scalars().all()
    return {
        "pending": [
            {
                "id": s.id,
                "text_el": s.text_el,
                "text_en": s.text_en,
                "explanation_el": s.explanation_el,
                "category": s.category,
                "source_bill_id": s.source_bill_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in pending
        ],
        "count": len(pending),
    }


@router.post("/compass/approve/{question_id}")
async def admin_compass_approve(
    question_id: int,
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending compass question → goes live."""
    stmt = await db.get(Statement, question_id)
    if not stmt:
        raise HTTPException(404, "Question not found")
    stmt.is_active = True
    await db.commit()
    return {"success": True, "id": question_id, "status": "active"}


@router.post("/compass/reject/{question_id}")
async def admin_compass_reject(
    question_id: int,
    _key=Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending compass question."""
    stmt = await db.get(Statement, question_id)
    if not stmt:
        raise HTTPException(404, "Question not found")
    await db.delete(stmt)
    await db.commit()
    return {"success": True, "id": question_id, "status": "rejected"}

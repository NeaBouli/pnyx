"""
MOD-22: RAG Agent — Citizen Q&A powered by Ollama
POST /api/v1/agent/ask — Answer citizen questions using DB context
Rate limited: 5 requests/minute per IP (Ollama is CPU-intensive)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import get_db
from models import ParliamentBill, BillStatus
from services.ollama_service import answer_citizen_question, ollama_available

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    lang: str = "el"


@router.post("/ask")
@limiter.limit("5/minute")
async def ask_agent(
    request: Request,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
):
    """RAG Agent — answer citizen questions using DB context."""
    if not await ollama_available():
        raise HTTPException(503, "AI assistant temporarily unavailable")

    # Build context from active bills
    result = await db.execute(
        select(ParliamentBill)
        .where(ParliamentBill.status.in_([
            BillStatus.ACTIVE, BillStatus.ANNOUNCED, BillStatus.WINDOW_24H,
            BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END,
        ]))
        .order_by(ParliamentBill.created_at.desc())
        .limit(10)
    )
    bills = result.scalars().all()

    context_parts = []
    for b in bills:
        title = b.title_el or b.title_en or b.id
        ctx = f"- {b.id}: {title} (Status: {b.status.value})"
        if b.pill_el:
            ctx += f" — {b.pill_el[:200]}"
        context_parts.append(ctx)

    context = "\n".join(context_parts) if context_parts else (
        "Δεν υπάρχουν νομοσχέδια αυτή τη στιγμή."
        if req.lang == "el"
        else "No bills available at the moment."
    )

    answer = await answer_citizen_question(req.question, context, req.lang)

    sources = [
        {"bill_id": b.id, "title": b.title_el or b.title_en}
        for b in bills[:5]
    ]

    return {
        "question": req.question,
        "answer": answer,
        "sources": sources,
        "lang": req.lang,
    }

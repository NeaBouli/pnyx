"""
Claude API Hybrid Agent — for complex citizen questions
GET  /api/v1/claude/budget  — Live budget status (public)
POST /api/v1/claude/ask     — Ask Claude Haiku (rate limited)
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
import redis.asyncio as aioredis
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/claude", tags=["Claude Agent"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DAILY_TOKEN_LIMIT = 50000
MONTHLY_BUDGET_EUR = float(os.getenv("CLAUDE_MONTHLY_BUDGET_EUR", "10.0"))

SYSTEM_PROMPT = (
    "You are the ekklesia AI assistant — helping Greek citizens understand "
    "democracy, parliamentary bills, and civic participation.\n\n"
    "About ekklesia:\n"
    "- Independent civic initiative for direct democracy in Greece\n"
    "- Citizens vote anonymously on real Hellenic Parliament bills\n"
    "- NOT a government service — votes have no legal binding\n"
    "- Uses Ed25519 cryptography — phone number never stored\n"
    "- Open source (MIT), runs on Hetzner (GDPR compliant)\n"
    "- pnyx.ekklesia.gr is the community discussion forum\n\n"
    "Today's date: " + datetime.now().strftime("%d %B %Y") + ". Current year: 2026.\n"
    "Always respond in the same language as the question.\n"
    "Be concise, helpful, and politically neutral."
)


def _get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


limiter = Limiter(key_func=_get_real_ip)


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


class ClaudeRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    lang: str = "el"


@router.get("/budget")
async def get_budget():
    """Live budget status for community.html tile."""
    r = await _redis()
    now = datetime.now(timezone.utc)
    today_key = f"claude:tokens:{now.strftime('%Y-%m-%d')}"
    month_key = f"claude:tokens:{now.strftime('%Y-%m')}"

    tokens_today = int(await r.get(today_key) or 0)
    tokens_month = int(await r.get(month_key) or 0)
    last_error = await r.get("claude:last_error") or ""
    is_active = bool(ANTHROPIC_API_KEY) and last_error != "credit_balance"

    return {
        "tokens_today": tokens_today,
        "tokens_month": tokens_month,
        "is_active": is_active,
        "error": last_error if last_error else None,
    }


@router.post("/ask")
@limiter.limit("3/minute")
async def claude_ask(request: Request, req: ClaudeRequest):
    """Claude Haiku endpoint for complex citizen questions."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "Claude AI temporarily unavailable")

    r = await _redis()
    now = datetime.now(timezone.utc)
    today_key = f"claude:tokens:{now.strftime('%Y-%m-%d')}"
    month_key = f"claude:tokens:{now.strftime('%Y-%m')}"

    # Check if credits depleted
    last_error = await r.get("claude:last_error") or ""
    if last_error == "credit_balance":
        raise HTTPException(402, "AI credits depleted — please donate to reactivate")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 500,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": req.question}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            month_key = f"claude:tokens:{now.strftime('%Y-%m')}"
            await r.incrby(today_key, total_tokens)
            await r.expire(today_key, 86400 * 2)
            await r.incrby(month_key, total_tokens)
            await r.expire(month_key, 86400 * 35)

            answer = data["content"][0]["text"]

            # Append disclaimer
            disclaimer = (
                "\n\n---\n⚠️ Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία."
                if req.lang == "el"
                else "\n\n---\n⚠️ This is not a government platform."
            )

            return {
                "answer": answer + disclaimer,
                "model": "claude-haiku",
                "tokens_used": total_tokens,
                "lang": req.lang,
            }

    except httpx.HTTPStatusError as e:
        logger.error("Claude API error: %s %s", e.response.status_code, e.response.text[:100])
        if e.response.status_code == 400 and "credit" in e.response.text.lower():
            await r.set("claude:last_error", "credit_balance")
            raise HTTPException(402, "AI credits depleted")
        if e.response.status_code == 429:
            raise HTTPException(429, "API rate limited — try again later")
        raise HTTPException(503, "Claude AI temporarily unavailable")

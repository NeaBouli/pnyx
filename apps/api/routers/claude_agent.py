"""
Claude budget status — read-only operations surface.
GET /api/v1/claude/budget — Live budget status (public)

EKA-61: The public POST /api/v1/claude/ask endpoint was removed fail-closed.
It bypassed every guardrail and tracked the token budget only post-hoc.
Usage tracking for internal analysis jobs stays in services/claude_usage.py.
"""
import os

from fastapi import APIRouter
import redis.asyncio as aioredis

from services.claude_usage import read_budget

router = APIRouter(prefix="/api/v1/claude", tags=["Claude Agent"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


@router.get("/budget")
async def get_budget():
    """Live budget status for community.html tile."""
    r = await _redis()
    return await read_budget(r, api_key_configured=bool(ANTHROPIC_API_KEY))

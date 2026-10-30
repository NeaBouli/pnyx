"""
Claude budget status — read-only operations surface.
GET /api/v1/claude/budget — Live budget status (public)

EKA-61: The public POST /api/v1/claude/ask endpoint was removed fail-closed.
It bypassed every guardrail and tracked the token budget only post-hoc.
Usage tracking for internal analysis jobs stays in services/claude_usage.py.
"""
from rate_limit import enforce_route_limit, public_read
import os

from fastapi import APIRouter, Depends, Request
import redis.asyncio as aioredis

from services.claude_usage import read_budget

router = APIRouter(prefix="/api/v1/claude", tags=["AI Assistant"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


async def _redis():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


@router.get("/budget", dependencies=[Depends(enforce_route_limit)])
@public_read
async def get_budget(request: Request = None):
    """Live budget status for community.html tile."""
    r = await _redis()
    return await read_budget(r, api_key_configured=bool(ANTHROPIC_API_KEY))

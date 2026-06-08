"""Claude token/cost tracking helpers shared by API routes and analysis jobs."""
import os
from datetime import datetime, timezone
from typing import Any


MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
DAILY_TOKEN_LIMIT = int(os.getenv("CLAUDE_DAILY_TOKEN_LIMIT", "50000"))
MONTHLY_BUDGET_EUR = float(os.getenv("CLAUDE_MONTHLY_BUDGET_EUR", "10.0"))

# Anthropic Claude Haiku 4.5 native API list price, configurable for future changes.
INPUT_USD_PER_MTOK = float(os.getenv("CLAUDE_HAIKU_INPUT_USD_PER_MTOK", "1.0"))
OUTPUT_USD_PER_MTOK = float(os.getenv("CLAUDE_HAIKU_OUTPUT_USD_PER_MTOK", "5.0"))


def token_total(usage: dict[str, Any]) -> int:
    return int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)


def estimate_cost_usd(usage: dict[str, Any]) -> float:
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return round(
        (input_tokens / 1_000_000 * INPUT_USD_PER_MTOK)
        + (output_tokens / 1_000_000 * OUTPUT_USD_PER_MTOK),
        6,
    )


def _keys(now: datetime, purpose: str) -> dict[str, str]:
    day = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    return {
        "today": f"claude:tokens:{day}",
        "month": f"claude:tokens:{month}",
        "purpose_today": f"claude:tokens:{purpose}:{day}",
        "purpose_month": f"claude:tokens:{purpose}:{month}",
        "cost_today": f"claude:cost_usd:{day}",
        "cost_month": f"claude:cost_usd:{month}",
        "purpose_cost_today": f"claude:cost_usd:{purpose}:{day}",
        "purpose_cost_month": f"claude:cost_usd:{purpose}:{month}",
    }


async def track_usage(redis_client: Any, usage: dict[str, Any], *, purpose: str = "chat") -> int:
    """Track total and purpose-specific Claude token/cost usage in Redis."""
    total = token_total(usage)
    if total <= 0:
        return 0
    cost = estimate_cost_usd(usage)
    now = datetime.now(timezone.utc)
    keys = _keys(now, purpose)

    await redis_client.incrby(keys["today"], total)
    await redis_client.expire(keys["today"], 86400 * 2)
    await redis_client.incrby(keys["month"], total)
    await redis_client.expire(keys["month"], 86400 * 35)
    await redis_client.incrby(keys["purpose_today"], total)
    await redis_client.expire(keys["purpose_today"], 86400 * 2)
    await redis_client.incrby(keys["purpose_month"], total)
    await redis_client.expire(keys["purpose_month"], 86400 * 35)

    if cost > 0:
        await redis_client.incrbyfloat(keys["cost_today"], cost)
        await redis_client.expire(keys["cost_today"], 86400 * 2)
        await redis_client.incrbyfloat(keys["cost_month"], cost)
        await redis_client.expire(keys["cost_month"], 86400 * 35)
        await redis_client.incrbyfloat(keys["purpose_cost_today"], cost)
        await redis_client.expire(keys["purpose_cost_today"], 86400 * 2)
        await redis_client.incrbyfloat(keys["purpose_cost_month"], cost)
        await redis_client.expire(keys["purpose_cost_month"], 86400 * 35)
    return total


async def read_budget(redis_client: Any, *, api_key_configured: bool) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    async def get_int(key: str) -> int:
        return int(await redis_client.get(key) or 0)

    async def get_float(key: str) -> float:
        return round(float(await redis_client.get(key) or 0), 6)

    tokens_today = await get_int(f"claude:tokens:{day}")
    tokens_month = await get_int(f"claude:tokens:{month}")
    analysis_today = await get_int(f"claude:tokens:analysis:{day}")
    analysis_month = await get_int(f"claude:tokens:analysis:{month}")
    chat_today = max(0, tokens_today - analysis_today)
    chat_month = max(0, tokens_month - analysis_month)
    last_error = await redis_client.get("claude:last_error") or ""

    return {
        "model": MODEL,
        "tokens_today": tokens_today,
        "tokens_month": tokens_month,
        "chat_tokens_today": chat_today,
        "chat_tokens_month": chat_month,
        "analysis_tokens_today": analysis_today,
        "analysis_tokens_month": analysis_month,
        "estimated_cost_usd_today": await get_float(f"claude:cost_usd:{day}"),
        "estimated_cost_usd_month": await get_float(f"claude:cost_usd:{month}"),
        "estimated_analysis_cost_usd_month": await get_float(f"claude:cost_usd:analysis:{month}"),
        "daily_token_limit": DAILY_TOKEN_LIMIT,
        "monthly_budget_eur": MONTHLY_BUDGET_EUR,
        "balance_available": False,
        "is_active": api_key_configured and last_error != "credit_balance",
        "error": last_error if last_error else None,
    }

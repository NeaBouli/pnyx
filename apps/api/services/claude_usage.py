"""Claude token/cost tracking helpers shared by API routes and analysis jobs."""
import os
from dataclasses import dataclass
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
    await _record_usage(redis_client, total, estimate_cost_usd(usage), purpose)
    return total


async def _record_usage(redis_client: Any, total: int, cost: float, purpose: str) -> None:
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


# ── Fail-closed pre-call budget gate ───────────────────────────────────────
# One Lua script decides and reserves atomically: today's tokens plus in-flight
# token reservations must stay within DAILY_TOKEN_LIMIT, and this month's cost
# plus in-flight cost reservations within MONTHLY_BUDGET_EUR. Cost is tracked in
# USD and compared 1:1 with the EUR budget, which is conservative (1 USD < 1 EUR).
_RESERVE_SCRIPT = """
local used_tokens = tonumber(redis.call('GET', KEYS[1]) or '0')
local held_tokens = tonumber(redis.call('GET', KEYS[2]) or '0')
local used_cost = tonumber(redis.call('GET', KEYS[3]) or '0')
local held_cost = tonumber(redis.call('GET', KEYS[4]) or '0')
local want_tokens = tonumber(ARGV[1])
local want_cost = tonumber(ARGV[2])
if used_tokens + held_tokens + want_tokens > tonumber(ARGV[3]) then return 0 end
if used_cost + held_cost + want_cost > tonumber(ARGV[4]) then return 0 end
redis.call('INCRBY', KEYS[2], want_tokens)
redis.call('EXPIRE', KEYS[2], 172800)
redis.call('INCRBYFLOAT', KEYS[4], ARGV[2])
redis.call('EXPIRE', KEYS[4], 3024000)
return 1
"""


@dataclass(frozen=True)
class Reservation:
    tokens_key: str
    cost_key: str
    tokens: int
    cost: float


def reservation_size(system: str, user: str, max_output_tokens: int) -> tuple[int, float]:
    """Proven upper bound for one call: a BPE token covers at least one UTF-8 byte,
    so input tokens <= prompt bytes; output is capped by max_tokens."""
    input_bound = len(system.encode("utf-8")) + len(user.encode("utf-8"))
    usage = {"input_tokens": input_bound, "output_tokens": max_output_tokens}
    return token_total(usage), estimate_cost_usd(usage)


async def reserve_budget(redis_client: Any, tokens: int, cost: float) -> Reservation | None:
    """Atomically reserve tokens and cost, or return None (limit reached or Redis error)."""
    try:
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        reservation = Reservation(
            tokens_key=f"claude:reserved_tokens:{day}",
            cost_key=f"claude:reserved_cost_usd:{month}",
            tokens=int(tokens),
            cost=float(cost),
        )
        admitted = await redis_client.eval(
            _RESERVE_SCRIPT,
            4,
            f"claude:tokens:{day}",
            reservation.tokens_key,
            f"claude:cost_usd:{month}",
            reservation.cost_key,
            reservation.tokens,
            repr(reservation.cost),
            DAILY_TOKEN_LIMIT,
            repr(MONTHLY_BUDGET_EUR),
        )
        return reservation if int(admitted) == 1 else None
    except Exception:
        return None


async def charge_reservation(redis_client: Any, reservation: Reservation, *, purpose: str = "chat") -> bool:
    """Book the full reservation as spent when the real usage is unknown after a call."""
    try:
        await _record_usage(redis_client, reservation.tokens, reservation.cost, purpose)
        return True
    except Exception:
        return False


async def release_budget(redis_client: Any, reservation: Reservation) -> None:
    """Drop an in-flight reservation (only after the call's cost has been booked)."""
    try:
        await redis_client.decrby(reservation.tokens_key, reservation.tokens)
        await redis_client.incrbyfloat(reservation.cost_key, -reservation.cost)
    except Exception:
        pass

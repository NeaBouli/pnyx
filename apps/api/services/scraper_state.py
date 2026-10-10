"""Redis-backed scraper job state tracking + circuit breaker."""

import logging
import os
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_H = 24
# Latest-outcome visibility (independent of circuit error_count).
OUTCOME_TTL_S = 14 * 24 * 3600
OUTCOMES = {"clean", "degraded", "failed"}
OUTCOME_REASONS = {"none", "scrape_errors", "conversion_failed", "exception"}


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def record_run(name: str) -> None:
    r = await _redis()
    try:
        await r.set(f"scraper:{name}:last_run", datetime.now(timezone.utc).isoformat())
    finally:
        await r.aclose()


async def record_success(name: str, outcome: str = "clean", reason: str = "none", count: int = 0) -> None:
    """Record success; latest outcome (clean|degraded) is queued in the same pipeline."""
    r = await _redis()
    try:
        pipe = r.pipeline()
        now = datetime.now(timezone.utc).isoformat()
        pipe.set(f"scraper:{name}:last_success", now)
        pipe.set(f"scraper:{name}:error_count", 0)
        pipe.delete(f"scraper:{name}:last_error")
        _queue_outcome(pipe, name, outcome, reason, count)
        await pipe.execute()
    finally:
        await r.aclose()


async def record_failure(name: str, error: str) -> int:
    """Record failure, return new error count."""
    r = await _redis()
    try:
        pipe = r.pipeline()
        pipe.incr(f"scraper:{name}:error_count")
        pipe.set(f"scraper:{name}:last_error", error[:500])
        pipe.set(f"scraper:{name}:last_error_time", datetime.now(timezone.utc).isoformat())
        _queue_outcome(pipe, name, "failed", "exception", 1)
        results = await pipe.execute()
        return int(results[0])
    finally:
        await r.aclose()


def _queue_outcome(pipe, name: str, outcome: str, reason: str, count: int) -> None:
    """Queue bounded latest-outcome keys; only fixed codes, never raw error text."""
    if outcome not in OUTCOMES:
        outcome = "failed"
    if reason not in OUTCOME_REASONS:
        reason = "exception"
    try:
        count = max(0, min(int(count), 10_000))
    except (TypeError, ValueError):
        count = 0
    now = datetime.now(timezone.utc).isoformat()
    pipe.set(f"scraper:{name}:last_outcome", outcome, ex=OUTCOME_TTL_S)
    pipe.set(f"scraper:{name}:last_outcome_reason", reason, ex=OUTCOME_TTL_S)
    pipe.set(f"scraper:{name}:last_outcome_count", count, ex=OUTCOME_TTL_S)
    pipe.set(f"scraper:{name}:last_outcome_time", now, ex=OUTCOME_TTL_S)
    if outcome != "clean":
        pipe.set(f"scraper:{name}:last_nonclean_time", now, ex=OUTCOME_TTL_S)


async def is_circuit_open(name: str) -> bool:
    """True if circuit breaker is tripped (too many errors, cooldown not elapsed)."""
    r = await _redis()
    try:
        count = int(await r.get(f"scraper:{name}:error_count") or 0)
        if count < CIRCUIT_BREAKER_THRESHOLD:
            return False
        last_err = await r.get(f"scraper:{name}:last_error_time")
        if not last_err:
            return False
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last_err)
        if elapsed > timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_H):
            # Cooldown elapsed — reset and allow retry
            await r.set(f"scraper:{name}:error_count", 0)
            logger.info("Circuit breaker reset for %s after %dh cooldown", name, CIRCUIT_BREAKER_COOLDOWN_H)
            return False
        return True
    finally:
        await r.aclose()


def _safe_time(v) -> str | None:
    """Valid tz-aware ISO timestamp -> UTC ISO; anything else (bytes, junk, naive) -> None."""
    if not isinstance(v, str) or len(v) > 64:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _safe_int(v) -> int | None:
    if not isinstance(v, str) or not v.lstrip("-").isdigit() or len(v) > 12:
        return None
    return int(v)


def safe_outcome(outcome, reason, count, time, nonclean_time) -> dict:
    """Whitelist latest-outcome fields; never echoes stored text outside fixed codes."""
    c = _safe_int(count)
    return {
        "last_outcome": outcome if isinstance(outcome, str) and outcome in OUTCOMES else "unknown",
        "last_outcome_reason": reason if isinstance(reason, str) and reason in OUTCOME_REASONS else "unknown",
        "last_outcome_count": None if c is None else max(0, min(c, 10_000)),
        "last_outcome_time": _safe_time(time),
        "last_nonclean_time": _safe_time(nonclean_time),
    }


def classify(error_count: int | None, last_outcome: str) -> str:
    """Legacy circuit/warning first; then latest outcome; no outcome evidence -> unknown."""
    if error_count is not None and error_count >= CIRCUIT_BREAKER_THRESHOLD:
        return "circuit_open"
    if error_count is not None and error_count > 0:
        return "warning"
    if last_outcome in ("degraded", "failed"):
        return "warning"
    if last_outcome == "clean" and error_count == 0:
        return "ok"
    return "unknown"


async def get_all_states(names: list[str]) -> list[dict]:
    """Get state for all named scrapers (read-only)."""
    r = await _redis()
    try:
        states = []
        for name in names:
            pipe = r.pipeline()
            pipe.get(f"scraper:{name}:last_run")
            pipe.get(f"scraper:{name}:last_success")
            pipe.get(f"scraper:{name}:last_error")
            pipe.get(f"scraper:{name}:error_count")
            pipe.get(f"scraper:{name}:last_error_time")
            pipe.get(f"scraper:{name}:last_outcome")
            pipe.get(f"scraper:{name}:last_outcome_reason")
            pipe.get(f"scraper:{name}:last_outcome_count")
            pipe.get(f"scraper:{name}:last_outcome_time")
            pipe.get(f"scraper:{name}:last_nonclean_time")
            vals = await pipe.execute()
            # Absent key = 0 (producer default); malformed = None (no evidence).
            parsed = 0 if vals[3] is None else _safe_int(vals[3])
            error_count = None if parsed is None else max(0, parsed)
            outcome = safe_outcome(*vals[5:10])
            states.append({
                "name": name,
                "last_run": vals[0],
                "last_success": vals[1],
                "last_error": vals[2],
                "error_count": error_count or 0,
                "status": classify(error_count, outcome["last_outcome"]),
                **outcome,
            })
        return states
    finally:
        await r.aclose()

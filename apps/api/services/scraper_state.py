"""Redis-backed scraper job state tracking + circuit breaker."""

import logging
import os
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_H = 24


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def record_run(name: str) -> None:
    r = await _redis()
    try:
        await r.set(f"scraper:{name}:last_run", datetime.now(timezone.utc).isoformat())
    finally:
        await r.aclose()


async def record_success(name: str) -> None:
    r = await _redis()
    try:
        pipe = r.pipeline()
        now = datetime.now(timezone.utc).isoformat()
        pipe.set(f"scraper:{name}:last_success", now)
        pipe.set(f"scraper:{name}:error_count", 0)
        pipe.delete(f"scraper:{name}:last_error")
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
        results = await pipe.execute()
        return int(results[0])
    finally:
        await r.aclose()


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


async def get_all_states(names: list[str]) -> list[dict]:
    """Get state for all named scrapers."""
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
            vals = await pipe.execute()
            error_count = int(vals[3] or 0)
            status = "ok"
            if error_count >= CIRCUIT_BREAKER_THRESHOLD:
                status = "circuit_open"
            elif error_count > 0:
                status = "warning"
            states.append({
                "name": name,
                "last_run": vals[0],
                "last_success": vals[1],
                "last_error": vals[2],
                "error_count": error_count,
                "status": status,
            })
        return states
    finally:
        await r.aclose()

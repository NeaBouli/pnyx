"""Public source freshness from successful ingestion, never bill publication dates."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from services import scraper_state

logger = logging.getLogger(__name__)
_blocked_at: str | None = None


async def record_source_blocked() -> None:
    global _blocked_at
    _blocked_at = datetime.now(timezone.utc).isoformat()
    client = None
    try:
        async with asyncio.timeout(1):
            client = await scraper_state._redis()
            await client.set("scraper:parliament:source_blocked", _blocked_at)
    except Exception:
        logger.warning("Could not persist Parliament source_blocked")
    finally:
        if client is not None:
            await client.aclose()


def source_status(last_success, blocked_at=None, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    last_success = scraper_state._safe_time(last_success)
    blocked_at = scraper_state._safe_time(blocked_at)
    last = datetime.fromisoformat(last_success) if last_success else None
    blocked = bool(blocked_at and (last is None or datetime.fromisoformat(blocked_at) > last))
    return {"last_success": last_success, "source_blocked": blocked,
            "stale": last is None or last > now or now - last > timedelta(hours=48)}


async def get_source_freshness() -> dict[str, dict]:
    values = [None, _blocked_at, None]
    client = None
    try:
        async with asyncio.timeout(1):
            client = await scraper_state._redis()
            values = await client.mget("scraper:parliament:last_success",
                                       "scraper:parliament:source_blocked",
                                       "scraper:diavgeia_municipal:last_success")
            values[1] = max(filter(None, (scraper_state._safe_time(values[1]), _blocked_at)), default=None)
    except Exception:
        logger.warning("Source freshness unavailable")
    finally:
        if client is not None:
            await client.aclose()
    return {"PARLIAMENT": source_status(values[0], values[1]),
            "DIAVGEIA": source_status(values[2])}


def bill_freshness(sources: dict, source: str | None) -> dict:
    state = sources.get(source or "PARLIAMENT", source_status(None))
    return {"source_last_success": state["last_success"],
            "source_blocked": state["source_blocked"], "source_stale": state["stale"]}

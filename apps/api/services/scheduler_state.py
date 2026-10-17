"""Restore interval schedules from dashboard job state and serialize workers."""

import asyncio
import logging
import random
import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from functools import partial

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services import scraper_state

logger = logging.getLogger(__name__)
STARTUP_JITTER_SECONDS = (120, 300)
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


def _last_run_time(value: str | None) -> datetime | None:
    safe = scraper_state._safe_time(value)
    return datetime.fromisoformat(safe) if safe else None


def next_interval_run(
    last_run: str | None,
    interval: timedelta,
    *,
    now: datetime | None = None,
) -> datetime:
    """Keep the persisted cadence; defer missing/overdue history past startup."""
    now = now or datetime.now(timezone.utc)
    previous = _last_run_time(last_run)
    if previous is not None and previous + interval > now:
        return previous + interval
    return now + timedelta(seconds=random.randint(*STARTUP_JITTER_SECONDS))


async def run_interval_job(
    *,
    scheduler: BaseScheduler,
    job_id: str,
    name: str,
    interval: timedelta,
    func: Callable[[], Awaitable[None]],
) -> None:
    """Lease the existing job body and recheck history after acquiring it.

    The recheck also excludes a second worker whose startup jitter expires
    after the first worker has already finished and released its lease.
    """
    client = await scraper_state._redis()
    key = f"scheduler:{name}:lock"
    token = secrets.token_urlsafe(24)
    lease_seconds = int(interval.total_seconds())
    acquired = False
    next_run = None
    try:
        acquired = await client.set(key, token, nx=True, ex=lease_seconds)
        if not acquired:
            return
        previous = _last_run_time(await client.get(f"scraper:{name}:last_run"))
        if previous is not None and previous + interval > datetime.now(timezone.utc):
            # Another worker may have run since registration. Move this worker's
            # timer to the new due time, including small execution delays, so a
            # skipped tick cannot postpone the job for another full interval.
            next_run = previous + interval
        else:
            # Stop before the lease expires, even if a provider call hangs.
            try:
                async with asyncio.timeout(lease_seconds - 30):
                    await func()
            except TimeoutError:
                await scraper_state.record_failure(name, "Scheduler job exceeded its worker lease")
                raise
    finally:
        if acquired:
            try:
                await client.eval(_RELEASE_LOCK_SCRIPT, 1, key, token)
            except Exception:
                logger.warning("[Scheduler] Could not release %s lease", name, exc_info=True)
        await client.aclose()
    if next_run is not None:
        # Cleanup can cross the due time. Queue the modification after this
        # coroutine finishes, letting APScheduler clear its running-instance
        # count before it wakes up to execute an already-due replacement tick.
        asyncio.get_running_loop().call_soon(
            partial(scheduler.modify_job, job_id, next_run_time=next_run),
        )


async def add_persisted_interval_job(
    scheduler: BaseScheduler,
    func: Callable[[], Awaitable[None]],
    *,
    name: str,
    hours: int,
    job_id: str | None = None,
) -> None:
    """Register one interval job, reading the same Redis URL as its producer."""
    interval = timedelta(hours=hours)
    last_run = None
    try:
        client = await scraper_state._redis()
        try:
            last_run = await client.get(f"scraper:{name}:last_run")
        finally:
            await client.aclose()
    except Exception:
        logger.warning("[Scheduler] Could not read %s history; deferring after startup", name, exc_info=True)
    next_run = next_interval_run(last_run, interval)
    job_id = job_id or name
    scheduler.add_job(
        run_interval_job,
        IntervalTrigger(hours=hours),
        id=job_id,
        kwargs={
            "scheduler": scheduler,
            "job_id": job_id,
            "name": name,
            "interval": interval,
            "func": func,
        },
        next_run_time=next_run,
        replace_existing=True,
    )
    logger.info("[Scheduler] %s next run at %s", name, next_run.isoformat())

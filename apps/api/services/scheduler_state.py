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
LAST_RUN_SKEW_TOLERANCE = timedelta(minutes=5)
COORDINATION_RETRY_SECONDS = (300, 600)
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


def _next_due_time(value: str | None, interval: timedelta, *, now: datetime) -> datetime | None:
    """Validate history identically at registration and after taking the lease."""
    safe = scraper_state._safe_time(value)
    if safe is None:
        return None
    previous = datetime.fromisoformat(safe)
    if previous - now > LAST_RUN_SKEW_TOLERANCE:
        logger.warning("[Scheduler] Ignoring future job history")
        return None
    try:
        due = min(previous, now) + interval
    except OverflowError:
        logger.warning("[Scheduler] Ignoring job history with overflowing interval")
        return None
    return due if due > now else None


def next_interval_run(
    last_run: str | None,
    interval: timedelta,
    *,
    now: datetime | None = None,
) -> datetime:
    """Keep the persisted cadence; defer missing/overdue history past startup."""
    now = now or datetime.now(timezone.utc)
    due = _next_due_time(last_run, interval, now=now)
    if due is not None:
        return due
    return now + timedelta(seconds=random.randint(*STARTUP_JITTER_SECONDS))


async def run_interval_job(
    *,
    scheduler: BaseScheduler,
    job_id: str,
    name: str,
    interval: timedelta,
    func: Callable[[], Awaitable[None]],
    pending_release: str | None = None,
) -> None:
    """Lease the existing job body and recheck history after acquiring it.

    The recheck also excludes a second worker whose startup jitter expires
    after the first worker has already finished and released its lease.
    """
    client = None
    key = f"scheduler:{name}:lock"
    token = secrets.token_urlsafe(24)
    lease_seconds = int(interval.total_seconds())
    acquired = False
    next_run = None
    previous_pending_release = pending_release
    try:
        try:
            client = await scraper_state._redis()
            if pending_release is not None:
                # A failed SET response or history read can leave our lease
                # behind. Remove only that token before trying again.
                await client.eval(_RELEASE_LOCK_SCRIPT, 1, key, pending_release)
                pending_release = None
            acquired = await client.set(key, token, nx=True, ex=lease_seconds)
            if not acquired:
                return
            last_run = await client.get(f"scraper:{name}:last_run")
        except Exception:
            # The body never started. Retry coordination without changing the
            # interval trigger or allowing an unguarded provider call.
            delay = random.randint(*COORDINATION_RETRY_SECONDS)
            pending_release = pending_release or token
            next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.warning("[Scheduler] %s coordination unavailable; retrying in %ds", name, delay)
        else:
            # Another worker may have run since registration. Move this
            # worker's timer to that attempt's due time if necessary.
            next_run = _next_due_time(last_run, interval, now=datetime.now(timezone.utc))
            if next_run is None:
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
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.warning("[Scheduler] Could not close %s coordination client", name)
    changes = {}
    if pending_release != previous_pending_release:
        kwargs = dict(scheduler.get_job(job_id).kwargs)
        if pending_release is None:
            kwargs.pop("pending_release", None)
        else:
            kwargs["pending_release"] = pending_release
        changes["kwargs"] = kwargs
    if next_run is not None:
        changes["next_run_time"] = next_run
    if changes:
        # Cleanup can cross the due time. Queue the modification after this
        # coroutine finishes, letting APScheduler clear its running-instance
        # count before it wakes up to execute an already-due replacement tick.
        asyncio.get_running_loop().call_soon(
            partial(scheduler.modify_job, job_id, **changes),
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
        # Startup work may finish after the restored due time. Execute one
        # catch-up tick regardless of that delay, then resume the interval.
        misfire_grace_time=None,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("[Scheduler] %s next run at %s", name, next_run.isoformat())

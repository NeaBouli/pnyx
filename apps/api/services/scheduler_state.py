"""Restore interval schedules from dashboard job state and serialize workers."""

import asyncio
import logging
import random
import secrets
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from functools import partial

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.events import EVENT_JOB_MODIFIED, EVENT_JOB_SUBMITTED, EVENT_SCHEDULER_STARTED
from apscheduler.triggers.interval import IntervalTrigger

from services import scraper_state, scheduler_observability as obs

logger = logging.getLogger("scheduler")
STARTUP_JITTER_SECONDS = (120, 300)
LAST_RUN_SKEW_TOLERANCE = timedelta(minutes=5)
COORDINATION_RETRY_SECONDS = (300, 600)
JOB_TIMEOUT_SECONDS = 3600
LEASE_MARGIN_SECONDS = 30
JOB_TIMEOUTS = {"forum_sync": 510, "finance_export": 240, "push_categories": 1200,
                "notify_new_bills": 1200, "notify_results": 1200, "zk_arweave_publication": 1200}
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
    interval: timedelta | None,
    func: Callable[[], Awaitable[None]],
    pending_release: str | None = None,
    timeout_s: float = JOB_TIMEOUT_SECONDS,
) -> None:
    """Lease the existing job body and recheck history after acquiring it.

    The recheck also excludes a second worker whose startup jitter expires
    after the first worker has already finished and released its lease.
    """
    client = None
    key = f"scheduler:{name}:lock"
    token = secrets.token_urlsafe(24)
    lease_seconds = max(1, int(timeout_s + LEASE_MARGIN_SECONDS))
    acquired = False
    next_run = None
    previous_pending_release = pending_release
    outcome = "skipped"
    started = False
    clock_started = time.monotonic()
    context = obs.attempt.set({"name": name, "outcome": "success"})
    logger.info("event=start job=%s outcome=running duration_s=0 next_run=%s", name,
                _log_time(_job_next_run(scheduler, job_id)))
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
                outcome = "lock_busy"
                next_run = datetime.now(timezone.utc) + timedelta(seconds=random.randint(*COORDINATION_RETRY_SECONDS))
            else:
                last_run = await client.get(f"scraper:{name}:last_run")
                await obs.recover_interrupted(client, name, token=token)
        except Exception:
            # The body never started. Retry coordination without changing the
            # interval trigger or allowing an unguarded provider call.
            delay = random.randint(*COORDINATION_RETRY_SECONDS)
            pending_release = pending_release or token
            next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.warning("[Scheduler] %s coordination unavailable; retrying in %ds", name, delay)
            outcome = "failed"
        else:
            # Another worker may have run since registration. Move this
            # worker's timer to that attempt's due time if necessary.
            if acquired:
                next_run = _next_due_time(last_run, interval, now=datetime.now(timezone.utc)) if interval else None
            if acquired and next_run is None:
                # Stop before the lease expires, even if a provider call hangs.
                try:
                    async with asyncio.timeout(max(0, timeout_s - (time.monotonic() - clock_started))):
                        started = True
                        await obs.record_started(client, name, datetime.now(timezone.utc))
                        await obs.persist_next_run(client, name, _job_next_run(scheduler, job_id))
                        await func()
                    outcome = obs.attempt.get()["outcome"]
                except asyncio.CancelledError:
                    outcome = "interrupted"
                    raise
                except Exception as exc:
                    outcome = "failed"
                    try:
                        if obs.attempt.get()["outcome"] != "failed":
                            await scraper_state.record_failure(name, type(exc).__name__)
                    except Exception:
                        logger.warning("Could not record %s failure", name)
                    raise
    finally:
        duration = max(0, time.monotonic() - clock_started)
        effective_next = next_run or _job_next_run(scheduler, job_id)
        try:
            if client is not None:
                if started:
                    await obs.record_finished(client, name, outcome, duration, effective_next)
                else:
                    # Coordination never started a body. Preserve any active
                    # worker's start/finish timestamps and failure streak.
                    if outcome == "lock_busy":
                        await client.set(f"scheduler:{name}:last_outcome", outcome)
                    await obs.persist_next_run(client, name, effective_next)
        except Exception:
            logger.warning("Could not persist %s scheduler state", name)
        finally:
            obs.attempt.reset(context)
            logger.info("event=end job=%s outcome=%s duration_s=%.3f next_run=%s",
                        name, outcome, duration, _log_time(effective_next))
        if client is not None:
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


def _job_next_run(scheduler: BaseScheduler, job_id: str) -> datetime | None:
    job = scheduler.get_job(job_id)
    return getattr(job, "next_run_time", None) if job else None


def _log_time(value: datetime | None) -> str:
    return value.isoformat() if value else "unknown"


def add_observed_job(scheduler: BaseScheduler, func, trigger, *, name: str) -> None:
    """Use the same bounded lease and lifecycle reporting for short/cron jobs."""
    scheduler.add_job(
        run_interval_job, trigger, id=name, replace_existing=True, coalesce=True,
        kwargs={"scheduler": scheduler, "job_id": name, "name": name,
                "interval": None, "func": func, "timeout_s": JOB_TIMEOUTS.get(name, JOB_TIMEOUT_SECONDS)},
    )


def install_schedule_listener(scheduler: BaseScheduler) -> None:
    """Publish dates after APScheduler advances a trigger or accepts a retry."""
    if not hasattr(scheduler, "add_listener"):
        return

    async def publish(job_id):
        client = None
        try:
            client = await scraper_state._redis()
            jobs = [scheduler.get_job(job_id)] if job_id else scheduler.get_jobs()
            for job in jobs:
                if job and job.kwargs.get("name"):
                    await obs.persist_next_run(client, job.kwargs["name"], _job_next_run(scheduler, job.id))
        except Exception:
            logger.warning("Could not publish scheduler dates")
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    logger.warning("Could not close scheduler dates client")

    # Lifespan can be entered repeatedly in tests; install only once per instance.
    if not getattr(scheduler, "_observability_listener", False):
        scheduler.add_listener(
            lambda event: asyncio.create_task(publish(getattr(event, "job_id", None))),
            EVENT_JOB_MODIFIED | EVENT_JOB_SUBMITTED | EVENT_SCHEDULER_STARTED,
        )
        scheduler._observability_listener = True


async def initialize_job_states(scheduler: BaseScheduler) -> None:
    """Recover stale attempts before starting; publish APScheduler's actual dates."""
    if not hasattr(scheduler, "get_jobs"):
        return

    try:
        client = await scraper_state._redis()
        try:
            for job in scheduler.get_jobs():
                name = job.kwargs.get("name")
                if name:
                    await obs.recover_interrupted(client, name)
                    next_run = getattr(job, "next_run_time", None)
                    if next_run is None:
                        next_run = job.trigger.get_next_fire_time(None, datetime.now(timezone.utc))
                    await obs.persist_next_run(client, name, next_run)
        finally:
            await client.aclose()
    except Exception:
        logger.warning("Could not initialize scheduler observability", exc_info=True)


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

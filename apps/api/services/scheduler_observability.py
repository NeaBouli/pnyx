"""Scheduler lifecycle state, separate from the legacy scraper quality metadata.

Lifecycle keys live under scheduler:<job>:; scraper:<job>:last_run remains the
attempt start time. Readers never need to infer completion from last_run.
"""

import logging
import math
from contextvars import ContextVar
from datetime import datetime, timezone

from services import scraper_state

logger = logging.getLogger("scheduler")
JOB_NAMES = (
    "parliament", "diavgeia_municipal", "notify_new_bills", "notify_results",
    "forum_sync", "bill_lifecycle", "cplm_refresh", "greek_topics",
    "completeness_check", "push_categories", "weekly_digest",
    "zk_arweave_publication", "finance_export", "monthly_newsletter",
)
OUTCOMES = {"success", "failed", "skipped", "interrupted", "lock_busy"}
FIELDS = ("last_started", "last_finished", "last_outcome", "last_duration_s", "next_run", "consecutive_failures")
# A mutable value lets the existing job bodies report swallowed failures without
# a second Redis read, and keeps simultaneous jobs isolated in their own task.
attempt: ContextVar[dict | None] = ContextVar("scheduler_attempt", default=None)
_INTERRUPTED_SCRIPT = """
local lease = redis.call('get', KEYS[1])
if lease and lease ~= ARGV[1] then return 0 end
if redis.call('get', KEYS[2]) ~= ARGV[2] then return 0 end
if (redis.call('get', KEYS[3]) or '') ~= ARGV[3] then return 0 end
redis.call('set', KEYS[3], ARGV[4])
redis.call('set', KEYS[4], 'interrupted')
redis.call('set', KEYS[5], ARGV[5])
redis.call('incr', KEYS[6])
return 1
"""


def configure_logging() -> None:
    """Emit scheduler INFO even with Uvicorn's default WARNING root logger."""
    logger.setLevel(logging.INFO)
    if not any(getattr(h, "scheduler_handler", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.scheduler_handler = True
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    for name in ("httpx", "httpcore", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)


def report_outcome(outcome: str) -> None:
    current = attempt.get()
    if current is not None:
        current["outcome"] = outcome


async def persist_next_run(client, name: str, next_run: datetime | None) -> None:
    if next_run is not None:
        await client.set(f"scheduler:{name}:next_run", next_run.astimezone(timezone.utc).isoformat())


async def recover_interrupted(client, name: str, *, token: str = "") -> bool:
    """Compare-and-set stale attempts; an active worker's lease wins.

    A hard-killed worker's lease may survive startup. The bounded TTL lets the
    next lease holder perform this same check before starting a new attempt.
    """
    prefix = f"scheduler:{name}:"
    started = await client.get(prefix + "last_started")
    finished = await client.get(prefix + "last_finished")
    safe_started, safe_finished = scraper_state._safe_time(started), scraper_state._safe_time(finished)
    if safe_started is None:
        return False
    start = datetime.fromisoformat(safe_started)
    now = datetime.now(timezone.utc)
    if start > now or (safe_finished and start <= datetime.fromisoformat(safe_finished)):
        return False
    return bool(await client.eval(
        _INTERRUPTED_SCRIPT, 6, f"scheduler:{name}:lock",
        prefix + "last_started", prefix + "last_finished", prefix + "last_outcome",
        prefix + "last_duration_s", prefix + "consecutive_failures",
        token, started, finished or "", now.isoformat(), max(0, (now - start).total_seconds()),
    ))


async def record_started(client, name: str, started: datetime) -> None:
    stamp = started.isoformat()
    pipe = client.pipeline()
    pipe.set(f"scheduler:{name}:last_started", stamp)
    pipe.set(f"scraper:{name}:last_run", stamp)
    await pipe.execute()


async def record_finished(client, name: str, outcome: str, duration: float, next_run: datetime | None) -> None:
    prefix = f"scheduler:{name}:"
    pipe = client.pipeline()
    pipe.set(prefix + "last_finished", datetime.now(timezone.utc).isoformat())
    pipe.set(prefix + "last_outcome", outcome)
    pipe.set(prefix + "last_duration_s", round(duration, 3))
    if outcome in {"failed", "interrupted"}:
        pipe.incr(prefix + "consecutive_failures")
    elif outcome == "success":
        pipe.set(prefix + "consecutive_failures", 0)
    if next_run is not None:
        pipe.set(prefix + "next_run", next_run.astimezone(timezone.utc).isoformat())
    await pipe.execute()


def safe_state(values: list) -> dict:
    data = dict(zip(FIELDS, values))
    try:
        duration = float(data.get("last_duration_s"))
        if not math.isfinite(duration) or duration < 0:
            duration = None
    except (TypeError, ValueError):
        duration = None
    return {
        "last_started": scraper_state._safe_time(data.get("last_started")),
        "last_finished": scraper_state._safe_time(data.get("last_finished")),
        "last_outcome": data.get("last_outcome") if data.get("last_outcome") in OUTCOMES else "unknown",
        "last_duration_s": duration,
        "next_run": scraper_state._safe_time(data.get("next_run")),
        "consecutive_failures": scraper_state.parse_error_count(data.get("consecutive_failures")),
    }

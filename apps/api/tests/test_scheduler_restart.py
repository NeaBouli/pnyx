"""Restart cadence and worker exclusion, with real APScheduler jobs and fake Redis."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import main
from services import scheduler_state, scraper_state

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
INTERVAL = timedelta(hours=48)
NAME = "diavgeia_municipal"
RUN_KEY = f"scraper:{NAME}:last_run"
LOCK_KEY = f"scheduler:{NAME}:lock"
LONG_JOBS = {
    "completeness_check": ("completeness_check", 6, "scheduled_completeness_check"),
    "parliament_scrape": ("parliament", 12, "scheduled_scrape"),
    "diavgeia_municipal": ("diavgeia_municipal", 48, "scheduled_diavgeia_scrape"),
    "cplm_refresh": ("cplm_refresh", 6, "scheduled_cplm_refresh"),
    "greek_topics": ("greek_topics", 6, "scheduled_greek_topics"),
}


class FakeRedis:
    def __init__(self, state):
        self.state = state
        self.closed = False

    async def get(self, key):
        self.state["reads"].append(key)
        if self.state["down"]:
            raise ConnectionError("Redis unavailable")
        return self.state["store"].get(key)

    async def set(self, key, value, *, nx=False, ex=None):
        if self.state["down"]:
            raise ConnectionError("Redis unavailable")
        store = self.state["store"]
        self.state["sets"].append((key, value, nx, ex))
        if nx and key in store:
            return False
        store[key] = value
        return True

    async def eval(self, script, num_keys, key, token):
        assert num_keys == 1
        assert "redis.call('get', KEYS[1]) == ARGV[1]" in script
        if self.state["store"].get(key) == token:
            del self.state["store"][key]
            return 1
        return 0

    async def aclose(self):
        self.closed = True


@pytest.fixture
def state(monkeypatch):
    state = {"store": {}, "reads": [], "sets": [], "clients": [], "down": False, "now": NOW}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = state["now"]
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    def client(*_args, **_kwargs):
        result = FakeRedis(state)
        state["clients"].append(result)
        return result

    async def redis_client():
        return client()

    monkeypatch.setattr(scheduler_state, "datetime", Clock)
    monkeypatch.setattr(scraper_state, "datetime", Clock)
    monkeypatch.setattr(scraper_state, "_redis", redis_client)
    # The remaining short-interval catch-up uses the legacy Redis constructor.
    monkeypatch.setattr(scraper_state.aioredis, "Redis", client)
    return state


async def register(scheduler=None, func=None):
    scheduler = scheduler if scheduler is not None else AsyncIOScheduler(timezone=timezone.utc)
    func = func if func is not None else AsyncMock()
    await scheduler_state.add_persisted_interval_job(scheduler, func, name=NAME, hours=48)
    return scheduler, scheduler.get_job(NAME), func


@pytest.mark.parametrize("age_hours", [40, 50, 48, None])
async def test_restart_restores_next_run_from_persisted_attempt(state, age_hours):
    if age_hours is not None:
        state["store"][RUN_KEY] = (NOW - timedelta(hours=age_hours)).isoformat()
        # A later completion must not reset the attempt-based cadence.
        state["store"][f"scraper:{NAME}:last_success"] = NOW.isoformat()

    _, job, func = await register()

    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval == INTERVAL
    if age_hours == 40:
        assert job.next_run_time == NOW + timedelta(hours=8)
    else:
        assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)
    func.assert_not_awaited()
    assert all(client.closed for client in state["clients"])


async def test_repeated_restarts_do_not_reset_the_remaining_countdown(state):
    state["store"][RUN_KEY] = (NOW - timedelta(hours=40)).isoformat()
    _, first, _ = await register()
    state["now"] += timedelta(hours=3)

    _, restarted, _ = await register()

    assert restarted.next_run_time == first.next_run_time == NOW + timedelta(hours=8)


@pytest.mark.parametrize("history", ["garbage", "2026-10-18T00:00:00", "99999999999999999999999"])
async def test_invalid_history_gets_startup_delay(state, history):
    state["store"][RUN_KEY] = history

    _, job, _ = await register()

    assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)


@pytest.mark.parametrize("seconds", [120, 300])
def test_startup_jitter_boundaries(monkeypatch, seconds):
    def randint(low, high):
        assert (low, high) == (120, 300)
        return seconds

    monkeypatch.setattr(scheduler_state.random, "randint", randint)
    assert scheduler_state.next_interval_run(None, INTERVAL, now=NOW) == NOW + timedelta(seconds=seconds)


@pytest.mark.parametrize("history", ["recent", "overdue", "missing"])
async def test_lifespan_restores_all_long_jobs_before_scheduler_starts(state, monkeypatch, history):
    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    started = []

    def start():
        assert all(scheduler.get_job(job_id) is not None for job_id in LONG_JOBS)
        started.append(True)

    monkeypatch.setattr(main, "scheduler", scheduler)
    monkeypatch.setattr(scheduler, "start", start)
    monkeypatch.setattr(scheduler, "shutdown", lambda: None)
    monkeypatch.setattr(main, "validate_server_salt_config", lambda: None)
    monkeypatch.setattr(main, "validate_identity_kdf_config", lambda: None)
    monkeypatch.setattr(main.sso, "validate_forum_sso_config", lambda: None)
    for name, hours, _ in LONG_JOBS.values():
        if history != "missing":
            age = timedelta(hours=hours - 1 if history == "recent" else hours + 1)
            state["store"][f"scraper:{name}:last_run"] = (NOW - age).isoformat()
    for name in ("bill_lifecycle", "forum_sync"):
        state["store"][f"scraper:{name}:last_run"] = datetime.now(timezone.utc).isoformat()

    async with main.lifespan(main.app):
        assert started == [True]
        assert len(scheduler.get_jobs()) == 14
        for job_id, (name, hours, function_name) in LONG_JOBS.items():
            job = scheduler.get_job(job_id)
            assert job.trigger.interval == timedelta(hours=hours)
            assert job.func is scheduler_state.run_interval_job
            assert job.kwargs["func"] is getattr(main, function_name)
            assert job.kwargs["name"] == name
            assert f"scraper:{name}:last_run" in state["reads"]
            if history == "recent":
                assert job.next_run_time == NOW + timedelta(hours=1)
            else:
                assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)
        assert not any(job.id.startswith("catchup_") for job in scheduler.get_jobs())


async def test_existing_worker_lock_excludes_execution_and_preserves_history(state):
    state["store"][LOCK_KEY] = "another-worker"
    state["store"][RUN_KEY] = (NOW - timedelta(hours=50)).isoformat()
    snapshot = dict(state["store"])
    _, job, func = await register()

    await job.func(**job.kwargs)

    func.assert_not_awaited()
    assert state["store"] == snapshot
    key, _, nx, expiry = state["sets"][-1]
    assert (key, nx, expiry) == (LOCK_KEY, True, 48 * 3600)
    assert all(client.closed for client in state["clients"])


async def test_concurrent_and_staggered_workers_run_once(state):
    entered, finish = asyncio.Event(), asyncio.Event()

    async def body():
        await scraper_state.record_run(NAME)
        entered.set()
        await finish.wait()

    func = AsyncMock(side_effect=body)
    _, first, _ = await register(func=func)
    second_scheduler, second, _ = await register(func=func)
    first_task = asyncio.create_task(first.func(**first.kwargs))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        await second.func(**second.kwargs)
        func.assert_awaited_once()
    finally:
        finish.set()
        await first_task
    assert LOCK_KEY not in state["store"]

    # A second worker can wake several minutes later, after the lease release.
    state["now"] += timedelta(minutes=3)
    await second.func(**second.kwargs)
    await asyncio.sleep(0)

    func.assert_awaited_once()
    assert second_scheduler.get_job(NAME).next_run_time == NOW + INTERVAL
    assert LOCK_KEY not in state["store"]


async def test_execution_delay_reschedules_instead_of_skipping_a_full_interval(state):
    state["store"][RUN_KEY] = (NOW - INTERVAL + timedelta(seconds=1)).isoformat()

    async def body():
        await scraper_state.record_run(NAME)

    func = AsyncMock(side_effect=body)
    scheduler, job, _ = await register(func=func)
    await job.func(**job.kwargs)
    await asyncio.sleep(0)
    func.assert_not_awaited()
    assert scheduler.get_job(NAME).next_run_time == NOW + timedelta(seconds=1)

    state["now"] += timedelta(seconds=1)
    await job.func(**job.kwargs)
    func.assert_awaited_once()


async def test_running_scheduler_does_not_lose_due_tick_during_lease_cleanup(state, monkeypatch):
    state["now"] = datetime.now(timezone.utc)
    due = state["now"] + timedelta(milliseconds=100)
    state["store"][RUN_KEY] = (due - INTERVAL).isoformat()
    ran = asyncio.Event()
    original_eval = FakeRedis.eval
    first_release = True

    async def slow_release(client, *args):
        nonlocal first_release
        if first_release:
            first_release = False
            # Make the replacement tick become due while the first invocation
            # is still counted as running by APScheduler (max_instances=1).
            delay = max((due - datetime.now(timezone.utc)).total_seconds(), 0)
            await asyncio.sleep(delay + 0.02)
            state["now"] = datetime.now(timezone.utc)
        return await original_eval(client, *args)

    async def body():
        await scraper_state.record_run(NAME)
        ran.set()

    monkeypatch.setattr(FakeRedis, "eval", slow_release)
    func = AsyncMock(side_effect=body)
    scheduler, job, _ = await register(func=func)
    scheduler.modify_job(NAME, next_run_time=datetime.now(timezone.utc))
    scheduler.start()
    try:
        await asyncio.wait_for(ran.wait(), timeout=3)
        func.assert_awaited_once()
        assert not first_release
    finally:
        scheduler.shutdown()
        await asyncio.sleep(0)


@pytest.mark.parametrize("error", [RuntimeError("provider failed"), asyncio.CancelledError()])
async def test_failure_or_shutdown_releases_owned_lease(state, error):
    _, job, _ = await register(func=AsyncMock(side_effect=error))

    with pytest.raises(type(error)):
        await job.func(**job.kwargs)

    assert LOCK_KEY not in state["store"]
    assert all(client.closed for client in state["clients"])


async def test_release_does_not_delete_another_workers_lease(state):
    async def body():
        state["store"][LOCK_KEY] = "replacement-owner"

    _, job, _ = await register(func=body)
    await job.func(**job.kwargs)

    assert state["store"][LOCK_KEY] == "replacement-owner"


async def test_redis_outage_defers_startup_and_prevents_unguarded_execution(state):
    state["down"] = True

    _, job, func = await register()

    assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)
    with pytest.raises(ConnectionError):
        await job.func(**job.kwargs)
    func.assert_not_awaited()
    assert all(client.closed for client in state["clients"])

"""Restart cadence and worker exclusion, with real APScheduler jobs and fake Redis."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import main
from services import scheduler_state, scraper_state, scheduler_observability as obs

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
        store[key] = str(value)
        return True

    def pipeline(self):
        client = self

        class Pipe:
            def __init__(self):
                self.ops = []

            def set(self, key, value, ex=None):
                self.ops.append(("set", key, value))

            def incr(self, key):
                self.ops.append(("incr", key, None))

            def delete(self, key):
                self.ops.append(("delete", key, None))

            async def execute(self):
                results = []
                for op, key, value in self.ops:
                    if op == "delete":
                        client.state["store"].pop(key, None)
                        results.append(1)
                        continue
                    if op == "incr":
                        value = int(await client.get(key) or 0) + 1
                    await client.set(key, value)
                    results.append(value)
                return results

        return Pipe()

    async def eval(self, script, num_keys, *args):
        if self.state["down"]:
            raise ConnectionError("Redis unavailable")
        store = self.state["store"]
        if num_keys == 2:
            assert script == obs._NEXT_RUN_SCRIPT
            lock, next_run, token, stamp = args
            if store.get(lock) and store[lock] != token:
                return 0
            store[next_run] = stamp
            return 1
        if num_keys == 8:
            assert script == obs._NOT_STARTED_SCRIPT
            lock, finish, outcome, duration, next_run, failures, coordination, failed_at, token, result, stamp, seconds, due = args
            if result == "failed":
                store[failures] = str(int(store.get(failures, 0)) + 1)
                store[coordination] = str(int(store.get(coordination, 0)) + 1)
                store[failed_at] = stamp
            if (store.get(lock) and store[lock] != token) or (result == "skipped" and store.get(lock) != token):
                return 0
            store.update({finish: stamp, outcome: result, duration: str(seconds)})
            if due:
                store[next_run] = due
            if result == "skipped":
                store[coordination] = "0"
            return 1
        if num_keys == 6:
            lock, start, finish, outcome, duration, failures, token, expected_start, expected_finish, now, seconds = args
            if (store.get(lock) and store[lock] != token) or store.get(start) != expected_start or store.get(finish, "") != expected_finish:
                return 0
            store.update({finish: now, outcome: "interrupted", duration: str(seconds), failures: str(int(store.get(failures, 0)) + 1)})
            return 1
        key, token = args
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
    monkeypatch.setattr(obs, "datetime", Clock)
    monkeypatch.setattr(scheduler_state.logger, "propagate", True)
    monkeypatch.setattr(scheduler_state.logger, "level", logging.WARNING)
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


@pytest.mark.parametrize("history", [
    (NOW + timedelta(minutes=5, microseconds=1)).isoformat(),
    (NOW + timedelta(days=365)).isoformat(),
    "9999-12-31T23:59:59+00:00",
])
async def test_future_history_uses_jitter_and_does_not_block_execution(state, caplog, history):
    state["store"][RUN_KEY] = history

    _, job, func = await register()

    assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)
    assert len(caplog.records) == 1
    assert history not in caplog.text
    assert caplog.records[0].exc_info is None

    caplog.clear()
    await job.func(**job.kwargs)

    func.assert_awaited_once()
    assert LOCK_KEY not in state["store"]
    assert len(caplog.records) == 1
    assert history not in caplog.text


@pytest.mark.parametrize("skew", [timedelta(seconds=1), timedelta(minutes=5)])
async def test_small_future_skew_is_clamped_to_now(state, skew):
    state["store"][RUN_KEY] = (NOW + skew).isoformat()
    scheduler, job, func = await register()

    assert job.next_run_time == NOW + INTERVAL
    await job.func(**job.kwargs)
    await asyncio.sleep(0)

    func.assert_not_awaited()
    assert scheduler.get_job(NAME).next_run_time == NOW + INTERVAL


async def test_interval_arithmetic_overflow_uses_jitter(state, caplog):
    state["now"] = datetime(9999, 12, 30, tzinfo=timezone.utc)
    state["store"][RUN_KEY] = state["now"].isoformat()

    _, job, func = await register()

    assert state["now"] + timedelta(minutes=2) <= job.next_run_time <= state["now"] + timedelta(minutes=5)
    assert len(caplog.records) == 1
    assert state["store"][RUN_KEY] not in caplog.text
    await job.func(**job.kwargs)
    func.assert_awaited_once()


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
            assert job.coalesce is True
            assert job.misfire_grace_time is None or job.misfire_grace_time >= 300
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
    scheduler, job, func = await register()

    await job.func(**job.kwargs)
    await asyncio.sleep(0)

    func.assert_not_awaited()
    assert all(state["store"][key] == value for key, value in snapshot.items())
    assert state["store"][f"scheduler:{NAME}:last_lock_busy_at"] == NOW.isoformat()
    assert f"scheduler:{NAME}:last_outcome" not in state["store"]
    assert f"scheduler:{NAME}:next_run" not in state["store"]
    assert NOW + timedelta(minutes=5) <= scheduler.get_job(NAME).next_run_time <= NOW + timedelta(minutes=10)
    key, _, nx, expiry = next(item for item in state["sets"] if item[0] == LOCK_KEY)
    assert (key, nx, expiry) == (LOCK_KEY, True, scheduler_state.JOB_TIMEOUT_SECONDS + scheduler_state.LEASE_MARGIN_SECONDS)
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


async def test_delayed_standby_contention_preserves_completed_run_and_shared_schedule(state, monkeypatch):
    prefix = f"scheduler:{NAME}:"
    entered, finish, busy = asyncio.Event(), asyncio.Event(), asyncio.Event()
    completed = asyncio.Event()
    original_set = FakeRedis.set

    async def body():
        entered.set()
        await finish.wait()

    async def delayed_contention(client, key, value, **kwargs):
        if key == prefix + "last_lock_busy_at":
            busy.set()
            await completed.wait()
        return await original_set(client, key, value, **kwargs)

    active_scheduler, active, _ = await register(func=body)
    shared_next = NOW + INTERVAL
    active_scheduler.modify_job(NAME, next_run_time=shared_next)
    standby_scheduler, standby, func = await register()
    scheduler_state.install_schedule_listener(standby_scheduler)
    monkeypatch.setattr(FakeRedis, "set", delayed_contention)
    active_task = asyncio.create_task(active.func(**active.kwargs))
    standby_task = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        # Also exercise a standby schedule event while the active lease exists.
        standby_scheduler.modify_job(NAME, next_run_time=NOW + timedelta(minutes=1))
        await asyncio.sleep(0)
        assert state["store"][prefix + "next_run"] == shared_next.isoformat()
        standby_task = asyncio.create_task(standby.func(**standby.kwargs))
        await asyncio.wait_for(busy.wait(), timeout=1)
        finish.set()
        await active_task
        snapshot = dict(state["store"])
        completed.set()
        await standby_task
        # Drain the retry modification and its asynchronous schedule listener.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert all(state["store"][key] == value for key, value in snapshot.items())
        assert state["store"][prefix + "last_outcome"] == "success"
        assert state["store"][prefix + "next_run"] == shared_next.isoformat()
        assert state["store"][prefix + "last_lock_busy_at"] == NOW.isoformat()
        assert standby_scheduler.get_job(NAME).next_run_time < shared_next
        func.assert_not_awaited()
    finally:
        finish.set()
        completed.set()
        await active_task
        if standby_task is not None:
            await standby_task


async def test_not_due_skip_preserves_body_history_and_failures_without_false_interruption(state):
    prefix = f"scheduler:{NAME}:"
    previous = (NOW - timedelta(hours=1)).isoformat()
    state["store"].update({RUN_KEY: previous, prefix + "last_started": previous,
                           prefix + "last_finished": previous, prefix + "last_outcome": "failed",
                           prefix + "consecutive_failures": "2", prefix + "consecutive_coordination_failures": "3"})
    scheduler, job, func = await register()
    await job.func(**job.kwargs)
    await asyncio.sleep(0)

    func.assert_not_awaited()
    assert state["store"][RUN_KEY] == state["store"][prefix + "last_started"] == previous
    assert state["store"][prefix + "last_finished"] == NOW.isoformat()
    assert state["store"][prefix + "last_outcome"] == "skipped"
    assert state["store"][prefix + "consecutive_failures"] == "2"
    assert state["store"][prefix + "consecutive_coordination_failures"] == "0"
    await scheduler_state.initialize_job_states(scheduler)
    assert state["store"][prefix + "last_outcome"] == "skipped"
    assert state["store"][prefix + "consecutive_failures"] == "2"


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
    prefix = f"scheduler:{NAME}:"
    assert state["store"][prefix + "last_outcome"] == "skipped"
    assert state["store"][prefix + "last_finished"] == NOW.isoformat()
    assert float(state["store"][prefix + "last_duration_s"]) >= 0
    assert prefix + "last_started" not in state["store"]
    assert state["store"][prefix + "next_run"] == (NOW + timedelta(seconds=1)).isoformat()

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


async def test_restored_due_run_survives_slow_startup(state):
    state["now"] = datetime.now(timezone.utc)
    due = state["now"] + timedelta(milliseconds=100)
    state["store"][RUN_KEY] = (due - INTERVAL).isoformat()
    ran = asyncio.Event()

    async def body():
        await scraper_state.record_run(NAME)
        ran.set()

    scheduler, job, func = await register(func=AsyncMock(side_effect=body))
    assert job.next_run_time == due
    await asyncio.sleep(1.2)
    state["now"] = datetime.now(timezone.utc)
    scheduler.start()
    try:
        await asyncio.wait_for(ran.wait(), timeout=3)
        func.assert_awaited_once()
        assert scheduler.get_job(NAME).trigger.interval == INTERVAL
    finally:
        scheduler.shutdown()
        await asyncio.sleep(0)


@pytest.mark.parametrize("error", [
    RuntimeError("provider failed"),
    ConnectionError("provider failed"),
    asyncio.CancelledError(),
])
async def test_failure_or_shutdown_releases_owned_lease(state, error):
    scheduler, job, _ = await register(func=AsyncMock(side_effect=error))
    next_run = job.next_run_time

    with pytest.raises(type(error)):
        await job.func(**job.kwargs)

    assert LOCK_KEY not in state["store"]
    assert all(client.closed for client in state["clients"])
    await asyncio.sleep(0)
    assert scheduler.get_job(NAME).next_run_time == next_run


async def test_release_does_not_delete_another_workers_lease(state):
    async def body():
        state["store"][LOCK_KEY] = "replacement-owner"

    _, job, _ = await register(func=body)
    await job.func(**job.kwargs)

    assert state["store"][LOCK_KEY] == "replacement-owner"


@pytest.mark.parametrize("failure_at", ["client", "lease", "lease_response", "history", "close"])
async def test_redis_outage_retries_until_recovery_without_unguarded_execution(state, monkeypatch, failure_at):
    state["down"] = True

    async def body():
        await scraper_state.record_run(NAME)

    scheduler, job, func = await register(func=AsyncMock(side_effect=body))

    assert NOW + timedelta(minutes=2) <= job.next_run_time <= NOW + timedelta(minutes=5)
    original_redis, original_set = scraper_state._redis, FakeRedis.set
    original_close = FakeRedis.aclose

    async def unavailable_client():
        if state["down"]:
            raise ConnectionError("Redis unavailable")
        return await original_redis()

    async def acquire_before_failed_read(client, *args, **kwargs):
        state["down"] = False
        try:
            return await original_set(client, *args, **kwargs)
        finally:
            state["down"] = True

    async def lost_lease_response(client, *args, **kwargs):
        await acquire_before_failed_read(client, *args, **kwargs)
        raise ConnectionError("Lease response lost")

    async def failed_close(client):
        await original_close(client)
        raise ConnectionError("Close failed")

    if failure_at == "client":
        monkeypatch.setattr(scraper_state, "_redis", unavailable_client)
    elif failure_at == "history":
        monkeypatch.setattr(FakeRedis, "set", acquire_before_failed_read)
    elif failure_at == "lease_response":
        monkeypatch.setattr(FakeRedis, "set", lost_lease_response)
    elif failure_at == "close":
        monkeypatch.setattr(FakeRedis, "aclose", failed_close)

    for _ in range(3):
        state["now"] = scheduler.get_job(NAME).next_run_time
        await job.func(**job.kwargs)
        await asyncio.sleep(0)
        func.assert_not_awaited()
        retry = scheduler.get_job(NAME)
        assert state["now"] + timedelta(minutes=5) <= retry.next_run_time <= state["now"] + timedelta(minutes=10)
        assert retry.trigger.interval == INTERVAL
        assert (LOCK_KEY in state["store"]) == (failure_at in {"history", "lease_response"})

    state["down"] = False
    monkeypatch.setattr(FakeRedis, "set", original_set)
    monkeypatch.setattr(FakeRedis, "aclose", original_close)
    state["now"] = scheduler.get_job(NAME).next_run_time
    await job.func(**job.kwargs)
    await asyncio.sleep(0)

    func.assert_awaited_once()
    assert state["store"][RUN_KEY] == state["now"].isoformat()
    assert LOCK_KEY not in state["store"]
    assert "pending_release" not in scheduler.get_job(NAME).kwargs
    assert all(client.closed for client in state["clients"])


@pytest.mark.parametrize("failure_at", ["client", "lease", "lease_response", "history", "recovery", "pending_release"])
async def test_coordination_failures_record_timestamps_and_streak_then_reset_after_recovery(state, monkeypatch, failure_at):
    prefix = f"scheduler:{NAME}:"
    scheduler, job, func = await register()
    original_redis, original_set = scraper_state._redis, FakeRedis.set
    original_get, original_eval = FakeRedis.get, FakeRedis.eval
    calls = 0

    async def failing_client():
        nonlocal calls
        calls += 1
        if calls % 2:
            raise ConnectionError("Client creation failed")
        return await original_redis()

    async def failing_set(client, key, *args, **kwargs):
        if key == LOCK_KEY:
            if failure_at == "lease_response":
                await original_set(client, key, *args, **kwargs)
            raise ConnectionError("Lease failed")
        return await original_set(client, key, *args, **kwargs)

    async def failing_get(client, key):
        if key == (RUN_KEY if failure_at == "history" else prefix + "last_started"):
            raise ConnectionError("History unavailable")
        return await original_get(client, key)

    async def failing_eval(client, script, num_keys, *args):
        if script == scheduler_state._RELEASE_LOCK_SCRIPT and args[-1] == "pending":
            raise ConnectionError("Coordination script failed")
        return await original_eval(client, script, num_keys, *args)

    if failure_at == "recovery":
        previous = (NOW - timedelta(hours=50)).isoformat()
        state["store"].update({RUN_KEY: previous, prefix + "last_started": previous})
    if failure_at == "pending_release":
        job.kwargs["pending_release"] = "pending"
    with monkeypatch.context() as faults:
        if failure_at == "client":
            faults.setattr(scraper_state, "_redis", failing_client)
        elif failure_at in {"lease", "lease_response"}:
            faults.setattr(FakeRedis, "set", failing_set)
        elif failure_at in {"history", "recovery"}:
            faults.setattr(FakeRedis, "get", failing_get)
        else:
            faults.setattr(FakeRedis, "eval", failing_eval)
        for failures in range(1, 4):
            await job.func(**job.kwargs)
            await asyncio.sleep(0)
            job = scheduler.get_job(NAME)
            func.assert_not_awaited()
            assert state["store"][prefix + "last_outcome"] == "failed"
            assert state["store"][prefix + "last_finished"] == state["now"].isoformat()
            assert state["store"][prefix + "last_coordination_failure_at"] == state["now"].isoformat()
            assert state["store"][prefix + "consecutive_failures"] == str(failures)
            assert state["store"][prefix + "consecutive_coordination_failures"] == str(failures)
            assert state["store"][prefix + "next_run"] == job.next_run_time.isoformat()
            assert float(state["store"][prefix + "last_duration_s"]) >= 0
            state["now"] = job.next_run_time

    await scheduler_state.initialize_job_states(scheduler)
    assert state["store"][prefix + "last_outcome"] == "failed"
    assert state["store"][prefix + "consecutive_failures"] == "3"
    await job.func(**job.kwargs)
    func.assert_awaited_once()
    assert state["store"][prefix + "last_outcome"] == "success"
    assert state["store"][prefix + "consecutive_failures"] == "0"
    assert state["store"][prefix + "consecutive_coordination_failures"] == "0"
    assert all(client.closed for client in state["clients"])


async def test_coordination_failure_preserves_live_workers_completion_and_next_run(state, monkeypatch):
    prefix = f"scheduler:{NAME}:"
    active_state = {LOCK_KEY: "active-worker", prefix + "last_started": NOW.isoformat(),
                    prefix + "last_finished": (NOW - INTERVAL).isoformat(), prefix + "last_outcome": "success",
                    prefix + "next_run": (NOW + INTERVAL).isoformat()}
    state["store"].update(active_state)
    scheduler, job, func = await register()
    job.kwargs["pending_release"] = "pending"
    original_eval = FakeRedis.eval

    async def unavailable_cleanup(client, script, num_keys, *args):
        if script == scheduler_state._RELEASE_LOCK_SCRIPT and args[-1] == "pending":
            raise ConnectionError("Cleanup unavailable")
        return await original_eval(client, script, num_keys, *args)

    monkeypatch.setattr(FakeRedis, "eval", unavailable_cleanup)
    await job.func(**job.kwargs)
    await asyncio.sleep(0)
    func.assert_not_awaited()
    assert all(state["store"][key] == value for key, value in active_state.items())
    assert state["store"][prefix + "consecutive_failures"] == "1"
    assert state["store"][prefix + "consecutive_coordination_failures"] == "1"
    assert state["store"][prefix + "last_coordination_failure_at"] == NOW.isoformat()


async def test_retry_cleanup_preserves_another_workers_lease(state):
    state["down"] = True
    scheduler, job, func = await register()
    await job.func(**job.kwargs)
    await asyncio.sleep(0)
    assert scheduler.get_job(NAME).kwargs["pending_release"]

    state["down"] = False
    state["store"][LOCK_KEY] = "another-worker"
    await job.func(**job.kwargs)

    func.assert_not_awaited()
    assert state["store"][LOCK_KEY] == "another-worker"
    assert all(client.closed for client in state["clients"])


async def test_running_scheduler_retries_missed_body_after_redis_recovery(state, monkeypatch):
    state["now"] = datetime.now(timezone.utc)
    state["down"] = True
    monkeypatch.setattr(scheduler_state, "COORDINATION_RETRY_SECONDS", (1, 1))
    tick = asyncio.Event()
    ran = asyncio.Event()

    async def body():
        await scraper_state.record_run(NAME)
        ran.set()

    scheduler, job, func = await register(func=AsyncMock(side_effect=body))
    scheduler.add_listener(lambda event: tick.set(), EVENT_JOB_EXECUTED)
    scheduler.modify_job(NAME, next_run_time=state["now"])
    scheduler.start()
    try:
        await asyncio.wait_for(tick.wait(), timeout=3)
        func.assert_not_awaited()
        assert scheduler.get_job(NAME).next_run_time == state["now"] + timedelta(seconds=1)
        state["down"] = False
        state["now"] = datetime.now(timezone.utc)
        await asyncio.wait_for(ran.wait(), timeout=3)
        func.assert_awaited_once()
        assert scheduler.get_job(NAME).trigger.interval == INTERVAL
        assert scheduler.get_job(NAME).next_run_time >= state["now"] + INTERVAL
    finally:
        scheduler.shutdown()
        await asyncio.sleep(0)


@pytest.mark.parametrize("outcome", ["success", "failed", "skipped", "interrupted"])
async def test_lifecycle_records_start_finish_duration_and_streak(state, outcome):
    prefix = f"scheduler:{NAME}:"
    state["store"][prefix + "consecutive_failures"] = "2"

    async def body():
        assert state["store"][prefix + "last_started"] == state["store"][RUN_KEY] == NOW.isoformat()
        assert prefix + "last_finished" not in state["store"]
        state["now"] += timedelta(seconds=7)
        if outcome == "interrupted":
            raise asyncio.CancelledError()
        obs.report_outcome(outcome)

    _, job, _ = await register(func=body)
    if outcome == "interrupted":
        with pytest.raises(asyncio.CancelledError):
            await job.func(**job.kwargs)
    else:
        await job.func(**job.kwargs)
    assert state["store"][prefix + "last_finished"] == state["now"].isoformat()
    assert state["store"][prefix + "last_outcome"] == outcome
    assert float(state["store"][prefix + "last_duration_s"]) >= 0
    assert state["store"][prefix + "next_run"] == job.next_run_time.isoformat()
    assert state["store"][prefix + "consecutive_failures"] == ("0" if outcome == "success" else "2" if outcome == "skipped" else "3")
    assert LOCK_KEY not in state["store"]


@pytest.mark.parametrize("live_lease", [False, True])
async def test_startup_marks_stale_attempt_interrupted_once_and_preserves_live_worker(state, live_lease):
    prefix = f"scheduler:{NAME}:"
    state["store"][prefix + "last_started"] = (NOW - timedelta(minutes=8)).isoformat()
    state["store"][prefix + "last_finished"] = (NOW - timedelta(hours=49)).isoformat()
    if live_lease:
        state["store"][LOCK_KEY] = "other-worker"
    scheduler, _, _ = await register()
    await scheduler_state.initialize_job_states(scheduler)
    await scheduler_state.initialize_job_states(scheduler)
    if live_lease:
        assert prefix + "last_outcome" not in state["store"]
    else:
        assert state["store"][prefix + "last_outcome"] == "interrupted"
        assert state["store"][prefix + "last_finished"] == NOW.isoformat()
        assert state["store"][prefix + "consecutive_failures"] == "1"
        assert float(state["store"][prefix + "last_duration_s"]) == 480


async def test_stale_attempt_recovers_after_dead_workers_lease_expires(state):
    prefix = f"scheduler:{NAME}:"
    state["store"][prefix + "last_started"] = (NOW - timedelta(hours=2)).isoformat()
    state["store"][LOCK_KEY] = "dead-worker"
    scheduler, job, _ = await register()
    await scheduler_state.initialize_job_states(scheduler)
    del state["store"][LOCK_KEY]  # Redis expires the bounded lease.
    state["store"][prefix + "consecutive_failures"] = "1"

    async def body():
        assert state["store"][prefix + "consecutive_failures"] == "2"
        obs.report_outcome("skipped")

    job.kwargs["func"] = body
    await job.func(**job.kwargs)
    assert state["store"][prefix + "consecutive_failures"] == "2"


async def test_expired_dead_lease_is_recovered_before_cadence_recheck(state):
    prefix = f"scheduler:{NAME}:"
    previous = (NOW - timedelta(hours=2)).isoformat()
    state["store"].update({prefix + "last_started": previous, RUN_KEY: previous,
                           LOCK_KEY: "dead-worker"})
    scheduler, job, func = await register()
    await scheduler_state.initialize_job_states(scheduler)
    assert prefix + "last_finished" not in state["store"]
    del state["store"][LOCK_KEY]
    await job.func(**job.kwargs)
    await asyncio.sleep(0)
    func.assert_not_awaited()
    assert state["store"][prefix + "last_outcome"] == "skipped"
    assert state["store"][prefix + "last_finished"] == NOW.isoformat()
    assert state["store"][prefix + "consecutive_failures"] == "1"
    assert scheduler.get_job(NAME).next_run_time == NOW + timedelta(hours=46)


@pytest.mark.parametrize("preflight", ["is_circuit_open", "record_run"])
async def test_real_job_records_preflight_exception(state, monkeypatch, preflight):
    monkeypatch.setattr(scraper_state, preflight, AsyncMock(side_effect=RuntimeError("preflight failed")))
    _, job, _ = await register(func=main.scheduled_diavgeia_scrape)
    await job.func(**job.kwargs)
    prefix = f"scheduler:{NAME}:"
    assert state["store"][prefix + "last_outcome"] == "failed"
    assert state["store"][prefix + "consecutive_failures"] == "1"
    assert prefix + "last_finished" in state["store"]
    assert state["store"][f"scraper:{NAME}:error_count"] == "1"


async def test_timeout_records_failure_and_releases_lease(state):
    async def hung():
        await asyncio.Event().wait()

    _, job, _ = await register(func=hung)
    with pytest.raises(TimeoutError):
        await job.func(**job.kwargs, timeout_s=0.01)
    assert state["store"][f"scheduler:{NAME}:last_outcome"] == "failed"
    assert state["store"][f"scheduler:{NAME}:consecutive_failures"] == "1"
    assert LOCK_KEY not in state["store"]


async def test_start_end_log_format_and_logger_levels(state, caplog, monkeypatch):
    import re
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(scheduler_state.logger, "level", logging.INFO)
    _, job, _ = await register()
    caplog.clear()
    await job.func(**job.kwargs)
    lines = [r.getMessage() for r in caplog.records if r.name == "scheduler"]
    assert len(lines) == 2
    for event, line in zip(("start", "end"), lines):
        assert re.fullmatch(rf"event={event} job={NAME} outcome=\w+ duration_s=[0-9.]+ next_run=\S+", line)
    assert "outcome=success" in lines[1]

    root_level = logging.getLogger().level
    obs.configure_logging()
    assert logging.getLogger("scheduler").level == logging.INFO
    assert logging.getLogger("scheduler").propagate is False
    assert any(h.scheduler_handler for h in logging.getLogger("scheduler").handlers if hasattr(h, "scheduler_handler"))
    assert logging.getLogger().level == root_level
    assert all(logging.getLogger(name).level == logging.WARNING for name in ("httpx", "httpcore", "apscheduler"))


async def test_running_scheduler_publishes_advanced_next_run_before_body_finishes(state):
    state["now"] = datetime.now(timezone.utc)
    entered, release = asyncio.Event(), asyncio.Event()

    async def body():
        entered.set()
        await release.wait()

    scheduler, _, _ = await register(func=body)
    scheduler_state.install_schedule_listener(scheduler)
    scheduler.modify_job(NAME, next_run_time=state["now"])
    scheduler.start()
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert datetime.fromisoformat(state["store"][f"scheduler:{NAME}:next_run"]) == scheduler.get_job(NAME).next_run_time
        assert scheduler.get_job(NAME).next_run_time > state["now"]
    finally:
        release.set()
        await asyncio.sleep(0.02)
        scheduler.shutdown()
        await asyncio.sleep(0)

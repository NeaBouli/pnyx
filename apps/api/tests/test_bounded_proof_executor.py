"""Actual executor submissions stay bounded through timeouts and cancellation."""
import asyncio
from collections import OrderedDict
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest

import main
from routers import zk
from services.request_work import BoundedExecutor, SingleFlight
from tests.test_released_mobile_client_flow import Rows


@pytest.mark.asyncio
async def test_sixty_cancelled_root_fills_leave_only_pool_size_running_and_no_queue(monkeypatch):
    pool = BoundedExecutor(capacity=8, thread_name_prefix="test-cancelled-proofs")
    monkeypatch.setattr(zk, "_root_members_workers", pool)
    monkeypatch.setattr(zk, "_root_members_cache", OrderedDict())
    monkeypatch.setattr(zk, "_root_members_flights", SingleFlight(capacity=1, reject_on_capacity=False, wait_timeout=0.001))
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", AsyncMock())
    monkeypatch.setattr(zk, "list_public_group_members_for_scope", AsyncMock(return_value=["1", "2"]))
    release = threading.Event()
    lock = threading.Lock()
    active = peak = submitted = 0
    original_submit = pool.executor.submit

    def submit(*args, **kwargs):
        nonlocal submitted
        submitted += 1
        return original_submit(*args, **kwargs)

    monkeypatch.setattr(pool.executor, "submit", submit)

    def build(members):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            assert release.wait(5), "Test failed to release proof threads"
            return SimpleNamespace(root="3", size=2)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(zk, "build_semaphore_group_root", build)
    root = SimpleNamespace(id=1, merkle_root="3", merkle_depth=16, group_size=2,
                           commitment_version="semaphore-v4", status="OPEN")
    db = SimpleNamespace(execute=AsyncMock(return_value=Rows(root)))
    tasks = [asyncio.create_task(zk.get_current_zk_root_members(vote_scope_id=f"bill:GR-{i}", db=db))
             for i in range(60)]
    try:
        async def all_running():
            while active < pool.capacity:
                await asyncio.sleep(0.001)
        await asyncio.wait_for(all_running(), 1)
        for task in tasks:
            task.cancel()
        assert all(isinstance(result, asyncio.CancelledError)
                   for result in await asyncio.gather(*tasks, return_exceptions=True))
        assert active == peak == submitted == pool.capacity
        assert pool.executor._work_queue.qsize() == 0
        assert not zk._root_members_flights._pending()
        assert len([thread for thread in threading.enumerate() if thread.name.startswith("test-cancelled-proofs")]) == 8
        print(f"60 cancelled fills: running={active}, submitted={submitted}, queued=0 (pool=8)")
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        pool.shutdown()
    assert active == 0
    assert not any(thread.name.startswith("test-cancelled-proofs") for thread in threading.enumerate())
    print("Proof executor shutdown: 0 leaked threads")


@pytest.mark.asyncio
async def test_singleflight_timeout_fallback_and_cancelled_leader_cannot_bypass_executor():
    pool = BoundedExecutor(capacity=1, wait_timeout=0.02, thread_name_prefix="test-fallback-proof")
    flight = SingleFlight(capacity=1, reject_on_capacity=False, wait_timeout=0.001)
    release, entered = threading.Event(), threading.Event()

    def build():
        entered.set()
        assert release.wait(5)
        return 42

    leader = asyncio.create_task(flight.run("root", lambda: pool.run(build)))
    try:
        while not entered.is_set():
            await asyncio.sleep(0.001)
        with pytest.raises(HTTPException) as exc:
            await flight.run("root", lambda: pool.run(build))
        assert exc.value.status_code == 503 and exc.value.headers == {"Retry-After": "1"}
        leader.cancel()
        with pytest.raises(asyncio.CancelledError):
            await leader
        with pytest.raises(HTTPException) as exc:
            await pool.run(build)
        assert exc.value.status_code == 503
        assert pool.executor._work_queue.qsize() == 0
        release.set()
        assert await pool.run(lambda: 43) == 43
        print("Follower timeout + cancelled leader: submissions stay bounded; true CPU saturation=503 Retry-After=1")
    finally:
        release.set()
        await asyncio.gather(leader, return_exceptions=True)
        pool.shutdown()

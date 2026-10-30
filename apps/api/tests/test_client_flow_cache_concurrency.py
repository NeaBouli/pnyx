"""Client cache saturation must never throttle released navigation or polling."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
import pytest

import main
from routers import parliament, zk
from services import client_flow_cache, request_work
from tests.test_released_mobile_client_flow import Rows, released_backend


@pytest.fixture
def slow_released_sql(released_backend, monkeypatch):
    _, db, _ = released_backend
    original = db.execute.side_effect

    async def execute(statement, *args):
        await asyncio.sleep(0.02)
        sql = str(statement)
        if "FROM periferia WHERE" in sql:
            return Rows(1)
        if "FROM dimos WHERE" in sql:
            return Rows((args[0]["dimos_id"] - 1) % 13 + 1)
        if "FROM representative_tokens WHERE ada_number" in sql:
            return Rows((args[0]["ada"], "Βουλευτής", "Region", "Politician", True, 1, None))
        if "zk_merkle_roots" in sql:
            return Rows(SimpleNamespace(
                id=1, vote_scope_id=statement.compile().params["vote_scope_id_1"],
                merkle_root="3", merkle_depth=16, group_size=2,
                commitment_version="semaphore-v4", status="OPEN",
            ))
        return await original(statement, *args)

    monkeypatch.setattr(db.execute, "side_effect", execute)
    return db


@pytest.mark.asyncio
async def test_twenty_simultaneous_distinct_politician_mounts_behind_nat(slow_released_sql):
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as client:
        responses = await asyncio.gather(*(
            client.get(f"/api/v1/politicians/ADA-{target}/{suffix}")
            for target in range(20) for suffix in ("questions", "scores")
        ))
    assert [response.status_code for response in responses] == [200] * 40
    assert slow_released_sql.execute.await_count == 120  # Fresh eligibility, then each leader's lookup + scan.
    print("NAT distinct-politicians=20 simultaneous-reads=40 SQL-latency=20ms: zero 429/5xx")


@pytest.mark.asyncio
async def test_fifty_simultaneous_localized_bills_mounts_behind_nat(slow_released_sql):
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as client:
        responses = await asyncio.gather(*(
            client.get("/api/v1/bills", params={
                "periferia_id": (target - 1) % 13 + 1, "dimos_id": target,
                "limit": limit, **filters,
            })
            for target in range(1, 51)
            for limit, filters in ((40, {}), (4, {"governance": "NATIONAL", "source": "PARLIAMENT"}))
        ))
    assert [response.status_code for response in responses] == [200] * 100
    assert all(response.json() == [] for response in responses)
    assert slow_released_sql.execute.await_count == 300  # Two validations + one list per variant.
    print("NAT localized-bills=50 simultaneous-reads=100 SQL-latency=20ms: zero 429/5xx")


@pytest.mark.asyncio
async def test_simultaneous_distinct_root_member_reads_with_followers(slow_released_sql, monkeypatch):
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", AsyncMock())
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as client:
        responses = await asyncio.gather(*(
            client.get(f"/api/v1/zk/roots/bill%3AGR-{target}/members")
            for target in range(20) for _ in range(2)
        ))
    assert [response.status_code for response in responses] == [200] * 40
    assert all(response.json()["members"] == ["1", "2"] for response in responses)
    assert not zk._root_members_flights._pending()


@pytest.mark.asyncio
async def test_invalid_param_flood_does_not_account_or_affect_another_ip(released_backend, monkeypatch):
    clock, db, _ = released_backend
    budget = parliament.get_bills.public_fill_budget
    monkeypatch.setattr(budget, "started", clock.now)
    monkeypatch.setattr(budget, "count", 0)
    before = budget.count
    invalid = [
        "status=INVALID", "status_any=ACTIVE,INVALID", "governance=INVALID",
        "status=INVALID&status_any=ACTIVE", "limit=0", "limit=501", "offset=-1",
        "periferia_id=0", "dimos_id=-1", "q=", "periferia_id=abc",
    ]
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as first:
        responses = await asyncio.gather(*(
            first.get("/api/v1/bills?" + invalid[index % len(invalid)]) for index in range(120)
        ))
        assert {response.status_code for response in responses} == {422}
        db.execute.assert_not_awaited()
        assert budget.count == before
        assert not parliament.get_bills.public_cache.entries
        assert not parliament.get_bills.public_cache.flights._pending()
        # Unknown but syntactically valid regions require validation SQL only.
        assert (await first.get("/api/v1/bills?periferia_id=999")).status_code == 422
        assert (await first.get("/api/v1/consensus/representation?dimos_id=999")).status_code == 422
        assert (await first.get("/api/v1/periferia/-1/dimos")).status_code == 422
        assert budget.count == before
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("203.0.113.9", 1234)),
                           base_url="http://test") as second:
        response = await second.get("/api/v1/bills")
    assert response.status_code == 200
    assert budget.count == before + 1
    assert not any("cache-fill:routers" in key for key in main.app.state.limiter._storage.storage)
    print("Invalid-param flood IP A=120: all 422, zero fills; valid IP B=200")


@pytest.mark.asyncio
async def test_cold_burst_exceeding_entry_and_flight_capacity_serves_every_key():
    workers = request_work.WaitingWorkSlots(capacity=16)
    cache = client_flow_cache.ClientFlowCache(capacity=8, workers=workers)
    active = peak = 0

    async def fill(key):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return key

    values = await asyncio.gather(*(cache.get_or_fill(key, lambda key=key: fill(key)) for key in range(100)))
    assert values == list(range(100))
    assert peak == 16
    assert len(cache.entries) == 8
    assert not cache.flights._pending()


@pytest.mark.asyncio
async def test_expired_values_return_immediately_and_single_refresh_failure_preserves_stale(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache()
    assert await cache.get_or_fill("key", AsyncMock(return_value="last-good")) == "last-good"
    now[0] += 5
    entered, release = asyncio.Event(), asyncio.Event()

    async def failing():
        entered.set()
        await release.wait()
        raise RuntimeError("database unavailable")

    refresh = AsyncMock(side_effect=failing)
    values = await asyncio.gather(*(cache.get_or_fill("key", refresh) for _ in range(50)))
    assert values == ["last-good"] * 50
    await entered.wait()
    assert refresh.await_count == 1
    pending = list(cache.flights._tasks)
    release.set()
    await asyncio.gather(*pending, return_exceptions=True)
    assert cache.entries["key"] == (105.0, "last-good")
    assert not cache.flights._pending()
    assert await cache.get_or_fill("key", AsyncMock(return_value="new")) == "last-good"
    await asyncio.gather(*cache.flights._tasks)
    assert await cache.get_or_fill("key", refresh) == "new"


@pytest.mark.asyncio
async def test_worker_fifo_queue_timeout_overflow_and_cancellation_release_slots():
    pool = request_work.WaitingWorkSlots(capacity=1, queue_capacity=2, wait_timeout=0.05)
    entered, release = asyncio.Event(), asyncio.Event()
    order = []

    async def blocked():
        entered.set()
        await release.wait()
        return "leader"

    leader = asyncio.create_task(pool.run(blocked))
    await entered.wait()

    async def value(index):
        order.append(index)
        return index

    queued = [asyncio.create_task(pool.run(lambda index=index: value(index))) for index in range(2)]
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.gather(leader, *queued) == ["leader", 0, 1]
    assert order == [0, 1]

    entered.clear()
    release.clear()
    leader = asyncio.create_task(pool.run(blocked))
    await entered.wait()
    # Two admitted waiters and one queue overflow all compute inline at deadline.
    assert await asyncio.gather(*(pool.run(lambda index=index: value(index)) for index in range(3))) == [0, 1, 2]
    assert not leader.done()
    leader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await leader
    assert await pool.run(lambda: value(3)) == 3
    assert pool._loops[asyncio.get_running_loop()]["waiting"] == 0


@pytest.mark.asyncio
async def test_singleflight_follower_deadline_computes_inline_without_cancelling_leader():
    flight = request_work.SingleFlight(capacity=1, reject_on_capacity=False, wait_timeout=0.01)
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await release.wait()
        return "leader"

    leader = asyncio.create_task(flight.run("key", slow))
    await entered.wait()
    assert await flight.run("key", AsyncMock(return_value="inline")) == "inline"
    assert not leader.done()
    release.set()
    assert await leader == "leader"


@pytest.mark.asyncio
async def test_cold_follower_of_deferred_refresh_computes_after_stale_entry_eviction(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    pool = request_work.WaitingWorkSlots(capacity=1, queue_capacity=1, wait_timeout=0.01)
    cache = client_flow_cache.ClientFlowCache(workers=pool)
    assert await cache.get_or_fill("key", AsyncMock(return_value="old")) == "old"
    entered, release = asyncio.Event(), asyncio.Event()

    async def block():
        entered.set()
        await release.wait()

    leader = asyncio.create_task(pool.run(block))
    await entered.wait()
    try:
        now[0] += 5
        assert await cache.get_or_fill("key", AsyncMock(return_value="unused")) == "old"
        # Model eviction before a cold follower arrives for that same key.
        cache.entries.pop("key")
        assert await cache.get_or_fill("key", AsyncMock(return_value="fresh")) == "fresh"
        assert not cache.flights._pending()
    finally:
        release.set()
        await leader


@pytest.mark.asyncio
async def test_saturated_aggregates_do_not_block_ordinary_reads():
    entered, release = asyncio.Event(), asyncio.Event()

    async def block():
        entered.set()
        await release.wait()

    leaders = [asyncio.create_task(client_flow_cache._aggregate_slots.run(block))
               for _ in range(client_flow_cache._aggregate_slots.capacity)]
    await entered.wait()
    try:
        cache = client_flow_cache.ClientFlowCache()
        assert await asyncio.wait_for(cache.get_or_fill("ordinary", AsyncMock(return_value=42)), 0.2) == 42
    finally:
        release.set()
        await asyncio.gather(*leaders)


@pytest.mark.asyncio
async def test_background_refresh_owns_db_and_invalidation_separates_inflight_generations(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    request_db, refresh_db = object(), object()
    seen = []
    entered, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    @asynccontextmanager
    async def session():
        try:
            yield refresh_db
        finally:
            closed.set()

    monkeypatch.setattr("database.AsyncSessionLocal", session)

    @client_flow_cache.public_client_cache(quota="1/minute")
    async def read(db):
        seen.append(db)
        if db is refresh_db:
            entered.set()
            await release.wait()
        return len(seen)

    assert await read(request_db) == 1
    now[0] += 5
    assert await read(request_db) == 1
    await entered.wait()
    read.public_cache.clear()
    assert await read(request_db) == 3
    release.set()
    await asyncio.gather(*read.public_cache.flights._tasks)
    assert closed.is_set()
    assert seen == [request_db, refresh_db, request_db]
    assert await read(request_db) == 3


@pytest.mark.asyncio
async def test_http_stale_bill_list_survives_refresh_failure(released_backend, monkeypatch):
    clock, db, _ = released_backend
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        first = await client.get("/api/v1/bills")
        assert first.status_code == 200
        clock.now += 5
        monkeypatch.setattr(db.execute, "side_effect", RuntimeError("SQL failed"))
        stale = await client.get("/api/v1/bills")
        assert stale.status_code == 200 and stale.json() == first.json()
        await asyncio.gather(*parliament.get_bills.public_cache.flights._tasks, return_exceptions=True)
        stale_again = await client.get("/api/v1/bills")
        assert stale_again.status_code == 200 and stale_again.json() == first.json()

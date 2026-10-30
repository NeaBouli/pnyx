"""Public cache bodies cannot outlive bill visibility in another worker."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

import main
from models import BillStatus, GovernanceLevel, ParliamentBill
from routers import parliament
from scripts import redact_sensitive_diavgeia_public_topics as redaction
from services import client_flow_cache, public_visibility_cache, representation_cache
from tests.test_released_mobile_client_flow import Rows, released_backend


@pytest.fixture
def worker_lists(released_backend, monkeypatch):
    clock, db, _ = released_backend
    bills = [ParliamentBill(
        id=bill_id, title_el=bill_id, status=BillStatus.ACTIVE,
        source="PARLIAMENT", governance_level=GovernanceLevel.NATIONAL,
        results_visibility="HIDDEN", admin_hidden=False, categories=[],
    ) for bill_id in ("GR-hidden", "GR-visible")]
    state = SimpleNamespace(fail_refresh=False, fail_visibility=False)

    async def execute(statement, *_args):
        sql = str(statement)
        if sql.startswith("SELECT parliament_bills.id \n"):
            if state.fail_visibility:
                raise RuntimeError("visibility query unavailable")
            return Rows([bill.id for bill in bills if not bill.admin_hidden])
        if statement.compile().params.get("id_1") in {bill.id for bill in bills}:
            return Rows(bills[0])
        if state.fail_refresh:
            raise RuntimeError("list refresh unavailable")
        visible = [bill for bill in bills if not bill.admin_hidden]
        return Rows([(bill, 1) for bill in visible] if "bill_relevance_votes" in sql else visible)

    db.execute.side_effect = execute
    # The route closures belong to worker B. The writer's local registry is A.
    worker_a = client_flow_cache.ClientFlowCache()
    monkeypatch.setattr(client_flow_cache, "public_caches", {"worker-a": worker_a})
    return clock, db, bills, state, worker_a


@pytest.fixture
def writer_redis(monkeypatch, visibility_redis):
    @asynccontextmanager
    async def connection(*_args, **_kwargs):
        yield visibility_redis

    async def keys(**_kwargs):
        return
        yield

    visibility_redis.scan_iter = keys
    monkeypatch.setattr(representation_cache.aioredis, "from_url", connection)
    return visibility_redis


@pytest.mark.parametrize("path,route", [
    ("/api/v1/bills", parliament.get_bills),
    ("/api/v1/bills/trending", parliament.get_trending),
])
@pytest.mark.parametrize("age", [0, 60])
@pytest.mark.parametrize("fail_refresh", [False, True])
async def test_worker_a_hide_invalidates_worker_b_immediately(
    worker_lists, writer_redis, monkeypatch, path, route, age, fail_refresh,
):
    clock, db, bills, state, worker_a = worker_lists
    async with AsyncClient(transport=ASGITransport(app=main.app, raise_app_exceptions=False),
                           base_url="http://test") as client:
        assert len((await client.get(path)).json()) == 2
        before = dict(route.public_cache.entries)
        await worker_a.get_or_fill("local", AsyncMock(return_value="old"))
        writer = SimpleNamespace(execute=AsyncMock(return_value=Rows([bills[0]])), commit=AsyncMock())

        @asynccontextmanager
        async def session():
            yield writer

        monkeypatch.setattr(redaction, "AsyncSessionLocal", session)
        assert await redaction._mark_hidden(["GR-hidden"]) == 1
        assert not worker_a.entries
        assert route.public_cache.entries == before  # Worker B was not cleared locally.
        assert writer_redis.generation == 1
        assert (await client.get("/api/v1/bills/GR-hidden")).status_code == 404
        clock.now += age
        state.fail_refresh = fail_refresh
        response = await client.get(path)
        if fail_refresh:
            assert response.status_code == 500  # Never fall back to the invalid body.
        else:
            assert response.status_code == 200
            assert [row["id"] for row in response.json()] == ["GR-visible"]


@pytest.mark.parametrize("path,route", [
    ("/api/v1/bills", parliament.get_bills),
    ("/api/v1/bills/trending", parliament.get_trending),
])
@pytest.mark.parametrize("age", [0, 60])
async def test_visibility_query_closes_generation_window_even_if_refresh_fails(worker_lists, path, route, age):
    clock, db, bills, state, _ = worker_lists
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        assert len((await client.get(path)).json()) == 2
        bills[0].admin_hidden = True  # Committed before the Redis bump, or bump failed.
        state.fail_refresh = True
        clock.now += age
        response = await client.get(path)
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == ["GR-visible"]
        await asyncio.gather(*route.public_cache.flights._tasks, return_exceptions=True)
        # Filtering must not modify the cached list itself.
        assert len(next(iter(route.public_cache.entries.values()))[1]) == 2
        state.fail_visibility = True
        with pytest.raises(RuntimeError, match="visibility query unavailable"):
            await client.get(path)
        await asyncio.gather(*route.public_cache.flights._tasks, return_exceptions=True)


@pytest.mark.parametrize("path", ["/api/v1/bills", "/api/v1/bills/trending"])
@pytest.mark.parametrize("fail_refresh", [False, True])
async def test_redis_down_never_serves_cached_lists(worker_lists, visibility_redis, path, fail_refresh):
    clock, db, bills, state, _ = worker_lists
    async with AsyncClient(transport=ASGITransport(app=main.app, raise_app_exceptions=False),
                           base_url="http://test") as client:
        assert len((await client.get(path)).json()) == 2
        bills[0].admin_hidden = True
        visibility_redis.down = True
        state.fail_refresh = fail_refresh
        clock.now += 60
        response = await client.get(path)
        assert response.status_code == (500 if fail_refresh else 200)
        if not fail_refresh:
            assert [row["id"] for row in response.json()] == ["GR-visible"]


@pytest.mark.parametrize("down", [False, True])
async def test_generation_miss_or_outage_coalesces_with_bounded_wait(visibility_redis, down):
    cache = client_flow_cache.ClientFlowCache(visibility_sensitive=True, wait_timeout=0.1)
    await cache.get_or_fill("list", AsyncMock(return_value="old"))
    visibility_redis.generation += 1
    visibility_redis.down = down
    entered, release = asyncio.Event(), asyncio.Event()

    async def fresh():
        entered.set()
        await release.wait()
        return "fresh"

    calculate = AsyncMock(side_effect=fresh)
    reads = [asyncio.create_task(cache.get_or_fill("list", calculate)) for _ in range(20)]
    await entered.wait()
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.gather(*reads) == ["fresh"] * 20
    calculate.assert_awaited_once()
    visibility_redis.generation += 1
    with pytest.raises(HTTPException) as exc:
        await cache.get_or_fill("list", asyncio.Event().wait)
    assert exc.value.status_code == 504
    assert not cache.flights._pending()


async def test_generation_change_fences_a_racing_fill(visibility_redis):
    cache = client_flow_cache.ClientFlowCache(visibility_sensitive=True)
    entered, release = asyncio.Event(), asyncio.Event()

    async def old():
        entered.set()
        await release.wait()
        return "before-hide"

    attempts = 0

    async def fill():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return await old()
        return "after-hide"

    read = asyncio.create_task(cache.get_or_fill("list", fill))
    await entered.wait()
    visibility_redis.generation += 1
    release.set()
    assert await read == "after-hide"
    assert attempts == 2
    assert cache.entries["list"][2] == visibility_redis.generation


@pytest.mark.parametrize("commit_fails", [False, True])
async def test_inventory_boundary_bumps_only_after_successful_commit(writer_redis, commit_fails):
    events = []
    increment = writer_redis.incr

    async def incr(key):
        events.append("bump")
        return await increment(key)

    writer_redis.incr = incr

    async def commit():
        events.append("commit")
        if commit_fails:
            raise RuntimeError("commit failed")

    if commit_fails:
        with pytest.raises(RuntimeError, match="commit failed"):
            await representation_cache.commit_and_invalidate_representation(SimpleNamespace(commit=commit))
        assert events == ["commit"]
    else:
        await representation_cache.commit_and_invalidate_representation(SimpleNamespace(commit=commit))
        assert events == ["commit", "bump"]
        writer_redis.down = True
        # Best-effort Redis failure cannot fail an already committed write.
        await representation_cache.commit_and_invalidate_representation(SimpleNamespace(commit=commit))


async def test_generation_bump_is_independent_of_representation_deletion(writer_redis):
    async def broken_scan(**_kwargs):
        raise TimeoutError("scan deadline")
        yield

    writer_redis.scan_iter = broken_scan
    await representation_cache.invalidate_representation_cache()
    assert writer_redis.generation == 1

    scanned = []

    async def scan(**_kwargs):
        scanned.append(True)
        return
        yield

    writer_redis.scan_iter = scan
    writer_redis.down = True
    await representation_cache.invalidate_representation_cache()
    assert scanned == [True]


@pytest.mark.parametrize("value,expected", [(None, 0), ("7", 7), ("invalid", None)])
async def test_generation_read_handles_missing_and_invalid_counters(value, expected):
    cache = SimpleNamespace(get=AsyncMock(return_value=value))
    assert await public_visibility_cache.public_visibility_generation(cache) == expected

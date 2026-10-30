"""Hard stale deadlines and fresh policy checks, including real HTTP reads."""
import asyncio
from unittest.mock import AsyncMock

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

import main
from rate_limit import limiter
from routers import evaluation, voting, zk
from services import client_flow_cache
from services.zk_vote_aggregation import VoteTotals
from tests.test_released_mobile_client_flow import released_backend


@pytest.mark.parametrize("max_stale", [30, 600])
@pytest.mark.asyncio
async def test_failed_refreshes_never_extend_maximum_stale_age(monkeypatch, max_stale):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache(max_stale=max_stale)
    assert await cache.get_or_fill("key", AsyncMock(return_value="old")) == "old"
    failing = AsyncMock(side_effect=RuntimeError("database unavailable"))
    now[0] = 105 + max_stale - 0.001
    assert await cache.get_or_fill("key", failing) == "old"
    await asyncio.gather(*cache.flights._tasks, return_exceptions=True)
    now[0] = 105 + max_stale
    with pytest.raises(RuntimeError, match="database unavailable"):
        await cache.get_or_fill("key", failing)
    now[0] += 86400
    with pytest.raises(RuntimeError):
        await cache.get_or_fill("key", failing)
    assert await cache.get_or_fill("key", AsyncMock(return_value="fresh")) == "fresh"


@pytest.mark.asyncio
async def test_hard_expired_request_has_a_bounded_fresh_wait(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache(max_stale=30, wait_timeout=0.01)
    await cache.get_or_fill("key", AsyncMock(return_value="old"))
    now[0] += 35
    with pytest.raises(HTTPException) as exc:
        await cache.get_or_fill("key", asyncio.Event().wait)
    assert exc.value.status_code == 504
    assert not cache.flights._pending()


@pytest.mark.asyncio
async def test_evicted_inflight_result_also_obeys_hard_age(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache(capacity=1, max_stale=30)
    entered, finish = asyncio.Event(), asyncio.Event()

    async def old_work():
        entered.set()
        await finish.wait()
        return "old-calculation"

    leader = asyncio.create_task(cache.get_or_fill("key", old_work))
    await entered.wait()
    fresh = AsyncMock(return_value="fresh")
    follower = asyncio.create_task(cache.get_or_fill("key", fresh))
    await asyncio.sleep(0)
    now[0] += 36
    # Eviction must not remove the age of a shared in-flight result.
    cache.clear()
    finish.set()
    assert await follower == "fresh"
    assert await leader == "old-calculation"  # Its retry starts at the current time.
    fresh.assert_awaited_once()


@pytest.mark.parametrize("code", [403, 404, 410])
@pytest.mark.asyncio
async def test_refresh_denial_invalidates_and_fences_older_inflight_work(monkeypatch, code):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache()
    await cache.get_or_fill("key", AsyncMock(return_value="old"))
    entered, finish = asyncio.Event(), asyncio.Event()

    async def old_work():
        entered.set()
        await finish.wait()
        return "before-denial"

    other = asyncio.create_task(cache.get_or_fill("other", old_work))
    await entered.wait()
    now[0] += 5
    assert await cache.get_or_fill("key", AsyncMock(side_effect=HTTPException(code))) == "old"
    await asyncio.gather(*cache.flights._tasks, return_exceptions=True)
    assert not cache.entries
    finish.set()
    await other
    assert not cache.entries


@pytest.mark.asyncio
async def test_denied_entry_does_not_flush_unrelated_cached_bodies():
    cache = client_flow_cache.ClientFlowCache()
    await cache.get_or_fill("allowed", AsyncMock(return_value="public"))
    with pytest.raises(HTTPException):
        await cache.get_or_fill("denied", AsyncMock(), validate=AsyncMock(side_effect=HTTPException(404)))
    assert cache.entries["allowed"][1] == "public"


@pytest.mark.asyncio
async def test_http_refresh_time_politician_404_invalidates_immediately(released_backend, monkeypatch):
    clock, db, _ = released_backend
    path = "/api/v1/politicians/ADA-released/scores"
    cache = evaluation.get_scores.public_cache
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        assert (await client.get(path)).status_code == 200
        clock.now += 5
        monkeypatch.setattr(evaluation, "_get_enabled_politician", AsyncMock(side_effect=[
            {"org_label": "Public"}, HTTPException(404),
        ]))
        assert (await client.get(path)).status_code == 200
        await asyncio.gather(*cache.flights._tasks, return_exceptions=True)
        assert not cache.entries
        monkeypatch.setattr(evaluation, "_get_enabled_politician", AsyncMock(side_effect=HTTPException(404)))
        assert (await client.get(path)).status_code == 404


@pytest.mark.parametrize("suffix", ["questions", "scores"])
@pytest.mark.asyncio
async def test_politician_eligibility_checked_before_fresh_or_stale_cached_body(released_backend, monkeypatch, suffix):
    clock, db, _ = released_backend
    path = f"/api/v1/politicians/ADA-released/{suffix}"
    cache = getattr(evaluation, f"get_{suffix}").public_cache
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        for age in (0, 6):
            monkeypatch.setattr(evaluation, "_get_enabled_politician", AsyncMock(return_value={"org_label": "Public"}))
            assert (await client.get(path)).status_code == 200
            clock.now += age
            monkeypatch.setattr(evaluation, "_get_enabled_politician", AsyncMock(side_effect=HTTPException(404)))
            assert (await client.get(path)).status_code == 404
            assert not cache.entries


@pytest.mark.asyncio
async def test_http_day_old_can_vote_and_totals_are_never_served_after_refresh_failure(released_backend, monkeypatch):
    clock, db, _ = released_backend
    counts = AsyncMock(return_value=2)
    totals = AsyncMock(return_value=VoteTotals(yes=2, no=1, abstain=0, unknown=0, tier1_total=3, zk_total=0))
    monkeypatch.setattr(zk, "_count_rows", counts)
    monkeypatch.setattr(voting, "aggregate_bill_vote_totals", totals)
    paths = ("/api/v1/zk/scopes/bill%3AGR-released/status", "/api/v1/vote/GR-released/results")
    async with AsyncClient(transport=ASGITransport(app=main.app, raise_app_exceptions=False), base_url="http://test") as client:
        assert (await client.get(paths[0])).json()["can_vote"] is True
        assert (await client.get(paths[1])).json()["total_votes"] == 3
        clock.now += 5
        counts.side_effect = totals.side_effect = RuntimeError("database unavailable")
        assert [(await client.get(path)).status_code for path in paths] == [200, 200]
        await asyncio.gather(*client_flow_cache.scope_status_cache.flights._tasks,
                             *client_flow_cache.results_cache.flights._tasks, return_exceptions=True)
        for age in (30, 86400):
            clock.now += age
            assert [(await client.get(path)).status_code for path in paths] == [500, 500]
        counts.side_effect = totals.side_effect = None
        totals.return_value = VoteTotals(yes=4, no=1, abstain=0, unknown=0, tier1_total=5, zk_total=0)
        assert (await client.get(paths[1])).json()["total_votes"] == 5
    print("HTTP can_vote/totals: failed refresh at TTL+30s and day-old age never returns cached 200")


@pytest.mark.asyncio
async def test_scope_and_results_denial_immediately_invalidates_entries(released_backend, monkeypatch):
    _, db, _ = released_backend
    monkeypatch.setattr(limiter, "enabled", False)
    await zk.get_zk_scope_status(vote_scope_id="bill:GR-released", db=db)
    await voting.get_results("GR-released", db=db)
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", AsyncMock(side_effect=HTTPException(404)))
    monkeypatch.setattr(voting, "is_public_bill", lambda bill: False)
    with pytest.raises(HTTPException):
        await zk.get_zk_scope_status(vote_scope_id="bill:GR-released", db=db)
    with pytest.raises(HTTPException):
        await voting.get_results("GR-released", db=db)
    assert not client_flow_cache.scope_status_cache.entries
    assert not client_flow_cache.results_cache.entries

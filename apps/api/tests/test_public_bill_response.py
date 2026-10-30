"""All bill schemas remain safe after a lost invalidation, even on fresh hits."""
from copy import deepcopy
from inspect import unwrap
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from services import client_flow_cache
from services import cplm
import main
from routers import analytics, consensus_results, mp
from services.public_bill_response import (
    BODY_KEY, IDS_KEY, capture_public_bill_body, serve_public_bill_body,
)
from tests.test_analytics_representation import bill, db
from tests.test_released_mobile_client_flow import Rows, released_backend


@pytest.mark.parametrize("schema", ["rows", "point", "representation", "aggregate", "history"])
async def test_every_bill_schema_rechecks_the_database_after_hide(db, schema):
    await bill(db, "H", title="Hidden title")
    await bill(db, "V", title="Visible title")
    rows = [{"id": "H", "title": "Hidden title", "votes": 17}, {"id": "V", "title": "Visible title", "votes": 10}]
    representation = {"bills": [{"bill_id": row["id"], "title": row["title"], "votes": row["votes"]} for row in rows],
                      "last_bill": {"bill_id": "H", "title": "Hidden title", "votes": 17},
                      "total_citizen_votes": 27, "bills_analyzed": 2, "cumulative_representation": 50,
                      "cumulative_divergence": 50, "label_en": "Old aggregate", "color": "red"}
    snapshot = {IDS_KEY: ["H", "V"], BODY_KEY: representation if schema == "representation" else {"votes": 27}}
    body = {"rows": rows, "point": rows[0], "representation": snapshot, "aggregate": snapshot,
            "history": [snapshot, {IDS_KEY: ["V"], BODY_KEY: {"votes": 10}}, {"votes": 27}]}[schema]
    original = deepcopy(body)
    await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE WHERE id = 'H'"))
    await db.commit()
    refresh = AsyncMock(return_value={IDS_KEY: ["V"], BODY_KEY: {"votes": 10}})
    if schema == "point":
        with pytest.raises(HTTPException) as exc:
            await serve_public_bill_body(body, db=db, schema=schema, bill_ids=["H"])
        assert exc.value.status_code == 404
    else:
        result = await serve_public_bill_body(body, db=db, schema=schema, refresh=refresh)
        assert "Hidden title" not in str(result)
        if schema == "rows":
            assert result == [rows[1]]
        elif schema == "history":
            assert result == [{"votes": 10}]
        elif schema == "aggregate":
            assert result == {"votes": 10}
            refresh.assert_awaited_once()
        else:
            assert [row["bill_id"] for row in result["bills"]] == ["V"]
            assert result["last_bill"] is None
            assert all(result[key] is None for key in ("total_citizen_votes", "bills_analyzed",
                                                       "cumulative_representation", "cumulative_divergence", "label_en", "color"))
            refresh.assert_not_awaited()
    assert body == original


async def test_hidden_contributor_outside_representation_details_withholds_aggregates(db):
    await bill(db, "VISIBLE")
    snapshot = {IDS_KEY: ["HIDDEN-OUTSIDE-200", "VISIBLE"], BODY_KEY: {
        "bills": [{"bill_id": "VISIBLE"}], "last_bill": {"bill_id": "VISIBLE"},
        "total_citizen_votes": 2010, "bills_analyzed": 201, "cumulative_divergence": 10,
    }}
    result = await serve_public_bill_body(snapshot, db=db, schema="representation")
    assert result["bills"] == [{"bill_id": "VISIBLE"}]
    assert result["last_bill"] == {"bill_id": "VISIBLE"}
    assert result["total_citizen_votes"] is result["bills_analyzed"] is result["cumulative_divergence"] is None


@pytest.mark.parametrize("schema", ["rows", "point", "representation", "aggregate", "history"])
async def test_failed_visibility_query_never_authorizes_a_cached_body(schema):
    db = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("visibility unavailable")))
    snapshot = {IDS_KEY: ["H"], BODY_KEY: {"bills": [], "last_bill": None, "votes": 17}}
    body = {"rows": [{"id": "H"}], "point": {"id": "H"}, "representation": snapshot,
            "aggregate": snapshot, "history": [snapshot]}[schema]
    with pytest.raises(RuntimeError, match="visibility unavailable"):
        await serve_public_bill_body(body, db=db, schema=schema, bill_ids=["H"])


async def test_capture_before_calculation_rejects_a_racing_hide(db):
    await bill(db, "H")
    async def calculate():
        await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE"))
        await db.commit()
        return {"votes": 17}
    snapshot = await capture_public_bill_body(calculate, db=db)
    assert snapshot[IDS_KEY] == ["H"]
    assert await serve_public_bill_body(snapshot, db=db, schema="aggregate") is None


@pytest.mark.parametrize("schema", ["independent", "rows", "aggregate", "representation"])
async def test_cache_factory_always_invokes_the_shared_helper(db, monkeypatch, schema):
    spy = AsyncMock(return_value={"filtered": True})
    monkeypatch.setattr(client_flow_cache, "serve_public_bill_body", spy)
    @client_flow_cache.public_client_cache(bill_schema=schema)
    async def read(*, db):
        return [] if schema == "rows" else {"bills": [], "last_bill": None}
    name = f"{read.__module__}.{read.__name__}"
    try:
        assert await read(db=db) == {"filtered": True}
        assert await read(db=db) == {"filtered": True}
        assert spy.await_count == 2  # A fresh hit still passes through the helper.
        assert all(call.kwargs["schema"] == schema for call in spy.await_args_list)
    finally:
        client_flow_cache.public_caches.pop(name, None)


@pytest.mark.parametrize("route,path,values,old,fresh", [
    (analytics.analytics_overview, "/api/v1/analytics/overview", {},
     {"bills": {"total": 2}, "votes": {"total": 27}, "divergence": {"average_score": .5}},
     {"bills": {"total": 1}, "votes": {"total": 10}, "divergence": {"average_score": .1}}),
    (mp.party_ranking, "/api/v1/mp/ranking", {},
     {"ranking": [{"bills_analyzed": 2, "agreement_pct": 50}]},
     {"ranking": [{"bills_analyzed": 1, "agreement_pct": 100}]}),
    (consensus_results.get_consensus_representation, "/api/v1/consensus/representation",
     {"dimos_id": None, "periferia_id": None, "limit": 20},
     {"coverage": {"total_diavgeia_bills": 2}, "views": {"national": {"votes": 27}}},
     {"coverage": {"total_diavgeia_bills": 1}, "views": {"national": {"votes": 10}}}),
])
@pytest.mark.parametrize("refresh_fails", [False, True])
async def test_registered_aggregate_rejects_a_one_second_old_body_after_hide(
    released_backend, monkeypatch, route, path, values, old, fresh, refresh_fails,
):
    clock, db, _ = released_backend
    visible = {"H", "V"}
    db.execute = AsyncMock(side_effect=lambda *_: Rows(sorted(visible)))
    function = unwrap(route)
    thresholds = tuple((name, function.__globals__[name]) for name in
                       ("K_MIN", "K_ANONYMITY_MIN", "EVALUATION_K_ANONYMITY_MIN")
                       if name in function.__globals__)
    key = (tuple(sorted(values.items())), client_flow_cache.public_policy_key(), thresholds)
    cache = route.public_cache
    cache.public_generation = 0
    cache.entries[key] = (clock.now + cache.ttl, {IDS_KEY: ["H", "V"], BODY_KEY: old}, 0)
    async with AsyncClient(transport=ASGITransport(app=main.app, raise_app_exceptions=False), base_url="http://test") as http:
        assert (await http.get(path)).json() == old
        visible.remove("H")
        clock.now += 1
        capture = AsyncMock(return_value={IDS_KEY: ["V"], BODY_KEY: fresh},
                            side_effect=RuntimeError("refresh unavailable") if refresh_fails else None)
        monkeypatch.setattr(client_flow_cache, "capture_public_bill_body", capture)
        response = await http.get(path)
        assert response.status_code == (500 if refresh_fails else 200)
        if not refresh_fails:
            assert response.json() == fresh
        capture.assert_awaited_once()


@pytest.mark.parametrize("refresh_fails", [False, True])
async def test_cplm_cache_history_and_trend_recheck_bill_provenance(db, monkeypatch, refresh_fails):
    await bill(db, "H")
    await bill(db, "V")
    values, history = {}, []
    class Redis:
        async def get(self, key): return values.get(key)
        async def setex(self, key, _ttl, value): values[key] = value
        async def lindex(self, *_): return history[0] if history else None
        async def lpush(self, _key, value): history.insert(0, value)
        async def ltrim(self, *_): pass
        async def lrange(self, *_): return history[:]
        async def aclose(self): pass
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: Redis())
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    async def compute(_):
        count = await db.scalar(text("SELECT COUNT(*) FROM parliament_bills WHERE admin_hidden = FALSE"))
        return {"x": .2 if count == 2 else .1, "y": 0, "total_votes": 27 if count == 2 else 10,
                "trend": {"x_delta": 0, "y_delta": 0, "direction": "stable"}}
    calculate = AsyncMock(side_effect=compute)
    monkeypatch.setattr(cplm, "compute_cplm", calculate)
    assert (await cplm.get_cplm_cached(db))["total_votes"] == 27
    stored = dict(values)
    await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE WHERE id = 'H'"))
    await db.commit()  # No invalidation reached Redis; its old body is still fresh.
    if refresh_fails:
        calculate.side_effect = RuntimeError("refresh unavailable")
        with pytest.raises(RuntimeError, match="refresh unavailable"):
            await cplm.get_cplm_cached(db)
        assert values == stored
        assert await cplm.get_cplm_history(db=db) == []
    else:
        result = await cplm.get_cplm_cached(db)
        assert result["total_votes"] == 10 and result["x"] == .1
        assert result["trend"]["x_delta"] == 0  # A hidden historical contribution cannot enter a delta.
        assert await cplm.get_cplm_history(db=db) == [result]
    assert calculate.await_count == 2

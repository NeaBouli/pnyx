"""Execute the reported races against real aggregate SQL and lost Redis writes."""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from database import Base, get_db
from models import BillStatus, CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from routers import analytics, voting
from services import cplm, public_bill_response as response
from services.client_flow_cache import results_cache
from services.public_bill_snapshot import building_snapshot, read_visibility_snapshot
from services.zk_vote_aggregation import aggregate_bill_vote_totals


@pytest.fixture
async def snapshot_db(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def concat(connection, _):
        connection.create_function("concat", -1, lambda *args: "".join(str(a) for a in args))
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: metadata.create_all(sync, tables=[
            metadata.tables[name] for name in ("parliament_bills", "citizen_votes", "zk_vote_receipts")
        ]))
        await connection.execute(text("CREATE TABLE consensus_votes (nullifier_hash TEXT, bill_id TEXT, score INTEGER)"))
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            yield db
    finally:
        await engine.dispose()


class Redis:
    def __init__(self):
        self.values, self.history, self.down = {}, [], False
    def check(self):
        if self.down:
            raise RedisConnectionError("Redis unavailable")
    async def get(self, key):
        self.check()
        return self.values.get(key)
    async def setex(self, key, _ttl, value):
        self.check()
        self.values[key] = value
    async def lindex(self, *_):
        self.check()
        return self.history[0] if self.history else None
    async def lpush(self, _key, value):
        self.check()
        self.history.insert(0, value)
    async def ltrim(self, *_): self.check()
    async def lrange(self, *_):
        self.check()
        return self.history[:]
    async def aclose(self): pass


async def seventeen_votes(db, *, hidden=False, status=BillStatus.ACTIVE):
    bill = ParliamentBill(id="RACE", title_el="Snapshot regression", source="PARLIAMENT",
                          status=status, results_visibility="ALWAYS", admin_hidden=hidden)
    db.add(bill)
    db.add_all([CitizenVote(bill_id=bill.id, vote=VoteChoice.YES, nullifier_hash=f"voter-{i}",
                            signature_hex="test", created_at=datetime.utcnow()) for i in range(17)])
    await db.commit()
    return bill


@pytest.mark.parametrize("redis_down", [False, True])
async def test_bill_made_public_during_cplm_compute_cannot_enter_body_or_history(
    snapshot_db, monkeypatch, visibility_redis, redis_down,
):
    db = snapshot_db
    await seventeen_votes(db, hidden=True)
    redis = Redis()
    redis.down = visibility_redis.down = redis_down
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: redis)
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    original = cplm.compute_cplm
    async def make_public_then_compute(db):
        assert building_snapshot.get().listed == frozenset()
        await db.execute(text("UPDATE parliament_bills SET admin_hidden = FALSE"))
        await db.commit()
        return await original(db)
    monkeypatch.setattr(cplm, "compute_cplm", make_public_then_compute)
    result = await cplm.get_cplm_cached(db)
    assert result["total_votes"] == result["total_voters"] == 0
    for stored in redis.values.values():
        assert json.loads(stored)[response.RESULTS_IDS_KEY] == []
    await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE"))
    await db.commit()
    monkeypatch.setattr(cplm, "compute_cplm", original)
    assert (await cplm.get_cplm_cached(db))["total_votes"] == 0
    assert all(entry["total_votes"] == 0 for entry in await cplm.get_cplm_history(db=db))
    if not redis_down:
        assert len(redis.history) == 1


@pytest.mark.parametrize("redis_down", [False, True])
@pytest.mark.parametrize("change", ["results_visibility = 'HIDDEN'", "status = 'ACTIVE', results_visibility = NULL"])
async def test_overview_revalidates_result_visibility_after_failed_invalidation(
    snapshot_db, monkeypatch, visibility_redis, redis_down, change,
):
    db = snapshot_db
    bill = await seventeen_votes(db, status=BillStatus.OPEN_END if "status" in change else BillStatus.ACTIVE)
    app = FastAPI()
    app.include_router(analytics.router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/analytics/overview")).json()["votes"]["total"] == 17
        cache = analytics.analytics_overview.public_cache
        envelope = next(iter(cache.entries.values()))[1]
        assert envelope[response.RESULTS_IDS_KEY] == ["RACE"]
        await db.execute(text(f"UPDATE parliament_bills SET {change}"))
        await db.commit()  # Redis receives neither deletion nor a generation bump.
        visibility_redis.down = redis_down
        assert bill.results_visibility == "ALWAYS"  # Deliberately stale ORM object.
        result = (await client.get("/api/v1/analytics/overview")).json()
        assert result["votes"]["total"] == 0
        assert result["bills"]["total"] == 1
        assert (await analytics.count_public_votes(db)) == 0
        assert envelope[response.BODY_KEY]["votes"]["total"] == 17  # No subtraction/mutation.


@pytest.mark.parametrize("change", ["results_visibility = 'HIDDEN'", "admin_hidden = TRUE"])
async def test_cplm_historical_votes_and_trend_are_withheld_when_visibility_shrinks(snapshot_db, monkeypatch, change):
    db = snapshot_db
    await seventeen_votes(db)
    redis = Redis()
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: redis)
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    assert (await cplm.get_cplm_cached(db))["total_votes"] == 17
    assert json.loads(redis.history[0])[response.RESULTS_IDS_KEY] == ["RACE"]
    await db.execute(text(f"UPDATE parliament_bills SET {change}"))
    await db.commit()
    assert await cplm.get_cplm_history(db=db) == []
    fresh = await cplm.get_cplm_cached(db)
    assert fresh["total_votes"] == 0
    assert fresh["trend"]["x_delta"] == 0
    assert await cplm.get_cplm_history(db=db) == [fresh]


async def test_snapshot_is_one_statement_and_observes_small_cell_sources(snapshot_db, monkeypatch):
    db = snapshot_db
    await seventeen_votes(db)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    sql = []
    def record(_conn, _cursor, statement, *_): sql.append(statement)
    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        snapshot = await read_visibility_snapshot(db)
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)
    assert len(sql) == 1
    assert snapshot.listed == {"RACE"} and snapshot.results == set()
    await db.execute(text("DELETE FROM citizen_votes"))
    db.add_all([CitizenVote(bill_id="RACE", vote=choice, nullifier_hash=f"{choice}-{i}", signature_hex="test")
                for choice in VoteChoice for i in range(10)])
    await db.commit()
    assert (await read_visibility_snapshot(db)).results == {"RACE"}
    db.add(ZkVoteReceipt(vote_scope_id="bill:RACE", vote_commitment="YES", semaphore_nullifier="1",
                         merkle_root="1", merkle_depth=16, signal_hash="1", external_nullifier="1",
                         proof_public_json={}, verifier_version="test", circuit_version="test",
                         created_at=datetime.utcnow()))
    await db.commit()
    assert (await read_visibility_snapshot(db)).results == set()


@pytest.mark.parametrize("schema", ["aggregate", "history", "point"])
@pytest.mark.parametrize("missing", [response.IDS_KEY, response.RESULTS_IDS_KEY])
async def test_legacy_envelope_missing_either_contributor_set_is_never_served(snapshot_db, missing, schema):
    envelope = {response.IDS_KEY: [], response.RESULTS_IDS_KEY: [], response.BODY_KEY: {"votes": 17}}
    del envelope[missing]
    body = [envelope] if schema == "history" else envelope
    assert await response.serve_public_bill_body(
        body, db=snapshot_db, schema=schema, point_results=schema == "point",
    ) == ([] if schema == "history" else None)


@pytest.mark.parametrize("k,initial_count,refresh_fails", [
    (0, 10, False), (0, 11, False), (10, 10, False), (10, 11, False), (10, 10, True),
])
@pytest.mark.parametrize("age", [0, 6])
async def test_point_results_revalidate_window_correction_without_invalidation(
    snapshot_db, monkeypatch, visibility_redis, k, age, initial_count, refresh_fails,
):
    from types import SimpleNamespace
    from services import client_flow_cache

    db = snapshot_db
    @asynccontextmanager
    async def background_session():
        async with AsyncSession(db.bind, expire_on_commit=False) as session:
            yield session
    monkeypatch.setattr("database.AsyncSessionLocal", background_session)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(k))
    clock = SimpleNamespace(now=1000)
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: clock.now)
    bill = ParliamentBill(id="CORRECTION", title_el="Point snapshot regression", source="PARLIAMENT",
                          status=BillStatus.WINDOW_24H, results_visibility="WINDOW")
    db.add(bill)
    db.add_all([CitizenVote(bill_id=bill.id, vote=choice, nullifier_hash=f"{choice.value}-{i}",
                            signature_hex="test") for choice in VoteChoice for i in range(initial_count)])
    await db.commit()
    app = FastAPI()
    app.include_router(voting.router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        path = f"/api/v1/vote/{bill.id}/results"
        before = (await client.get(path)).json()
        assert [before[f"{choice}_count"] for choice in ("yes", "no", "abstain", "unknown")] == [initial_count] * 4
        cached = next(iter(results_cache.entries.values()))[1]
        if k:
            inputs = cached[response.RESULTS_INPUTS_KEY][bill.id]
            assert (inputs.k, inputs.status, inputs.results_visibility) == (10, "WINDOW_24H", "WINDOW")
        await db.execute(text("UPDATE citizen_votes SET vote = 'NO', is_correction = TRUE "
                              "WHERE nullifier_hash = 'YES-0'"))
        await db.commit()  # Worker B receives no deletion or generation bump.
        clock.now += age
        if refresh_fails:
            monkeypatch.setattr(voting, "aggregate_bill_vote_totals", AsyncMock(side_effect=RuntimeError("refresh failed")))
            assert (await client.get(path)).status_code == 500
            await asyncio.gather(*results_cache.flights._tasks, return_exceptions=True)
            monkeypatch.setattr(voting, "aggregate_bill_vote_totals", aggregate_bill_vote_totals)
        after_response = await client.get(path)
        assert after_response.status_code == 200
        after = after_response.json()
        if k and initial_count == 10:
            assert after["suppressed"] is True
            for key in ("total_votes", "yes_count", "no_count", "abstain_count", "unknown_count",
                        "tier1_vote_count", "zk_vote_count", "yes_percent", "no_percent",
                        "abstain_percent", "unknown_percent", "divergence", "representativity"):
                assert after[key] is None
        elif k:
            assert after["suppressed"] is False
            assert [after[f"{choice}_count"] for choice in ("yes", "no", "abstain", "unknown")] == [10, 12, 11, 11]
        else:
            assert after == before  # The existing bounded stale cache remains available with k disabled.
            assert "suppressed" not in after and "suppression_k" not in after
        assert visibility_redis.generation == 0
        if k:
            assert cached[response.BODY_KEY].yes == initial_count  # Never mutate the old entry.
        await asyncio.gather(*results_cache.flights._tasks, return_exceptions=True)
        results_cache.clear()
        fresh = (await client.get(path)).json()
        if k:
            assert fresh == after
        else:
            assert [fresh[f"{choice}_count"] for choice in ("yes", "no", "abstain", "unknown")] == [
                initial_count - 1, initial_count + 1, initial_count, initial_count,
            ]
            assert "suppressed" not in fresh


@pytest.mark.parametrize("missing", [response.IDS_KEY, response.RESULTS_IDS_KEY, response.RESULTS_INPUTS_KEY])
async def test_point_guard_requires_contributors_and_result_inputs(snapshot_db, monkeypatch, missing):
    db = snapshot_db
    bill = await seventeen_votes(db)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    envelope = await response.capture_public_bill_body(
        lambda: aggregate_bill_vote_totals(db, bill.id, include_zk=True), db=db, point_results=bill.id,
    )
    assert await response.serve_public_bill_body(
        envelope, db=db, schema="point", bill_ids=(bill.id,), point_results=True,
    ) is not None
    del envelope[missing]
    assert await response.serve_public_bill_body(
        envelope, db=db, schema="point", bill_ids=(bill.id,), point_results=True,
    ) is None


@pytest.mark.parametrize("change", ["k", "status", "results_visibility", "counts"])
async def test_point_guard_revalidates_every_result_input(snapshot_db, monkeypatch, change):
    db = snapshot_db
    bill = await seventeen_votes(db)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    envelope = await response.capture_public_bill_body(
        lambda: aggregate_bill_vote_totals(db, bill.id, include_zk=True), db=db, point_results=bill.id,
    )
    if change == "k":
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "11")
    else:
        statement = {"status": "UPDATE parliament_bills SET status = 'WINDOW_24H'",
                     "results_visibility": "UPDATE parliament_bills SET results_visibility = 'WINDOW'",
                     "counts": "UPDATE citizen_votes SET vote = 'NO' WHERE nullifier_hash = 'voter-0'"}[change]
        await db.execute(text(statement))
        await db.commit()
    assert await response.serve_public_bill_body(
        envelope, db=db, schema="point", bill_ids=(bill.id,), point_results=True,
    ) is None


async def test_cplm_trend_retains_previous_contributors_even_when_votes_disappear(snapshot_db, monkeypatch):
    db = snapshot_db
    await seventeen_votes(db)
    redis = Redis()
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: redis)
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    assert (await cplm.get_cplm_cached(db))["x"] == .05
    await db.execute(text("DELETE FROM citizen_votes"))
    await db.commit()
    changed = await cplm._fresh_cplm(db)
    assert changed[response.BODY_KEY]["trend"]["x_delta"] == -.05
    assert changed[response.RESULTS_IDS_KEY] == ["RACE"]
    await db.execute(text("UPDATE parliament_bills SET results_visibility = 'HIDDEN'"))
    await db.commit()
    assert await cplm.get_cplm_history(db=db) == []
    assert (await cplm.get_cplm_cached(db))["trend"]["x_delta"] == 0


async def test_fifty_unsafe_cplm_hits_share_one_rebuild(snapshot_db, monkeypatch):
    import asyncio
    db = snapshot_db
    await seventeen_votes(db)
    redis = Redis()
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: redis)
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    assert (await cplm.get_cplm_cached(db))["total_votes"] == 17
    await db.execute(text("UPDATE parliament_bills SET results_visibility = 'HIDDEN'"))
    await db.commit()
    original = cplm.compute_cplm
    async def delayed(db):
        await asyncio.sleep(.01)
        return await original(db)
    calculate = AsyncMock(side_effect=delayed)
    monkeypatch.setattr(cplm, "compute_cplm", calculate)
    results = await asyncio.gather(*(cplm.get_cplm_cached(db) for _ in range(50)))
    assert all(result["total_votes"] == 0 for result in results)
    calculate.assert_awaited_once()


async def test_cache_and_history_revalidate_small_cell_policy_without_invalidation(snapshot_db, monkeypatch):
    db = snapshot_db
    await seventeen_votes(db)
    await db.execute(text("DELETE FROM citizen_votes"))
    db.add_all([CitizenVote(bill_id="RACE", vote=choice, nullifier_hash=f"{choice}-{i}", signature_hex="test")
                for choice in VoteChoice for i in range(10)])
    await db.commit()
    redis = Redis()
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: redis)
    monkeypatch.setattr(cplm, "cache_fill_quota", AsyncMock())
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    assert (await cplm.get_cplm_cached(db))["total_votes"] == 40
    await db.execute(text("DELETE FROM citizen_votes WHERE nullifier_hash = 'VoteChoice.YES-0'"))
    await db.commit()
    assert await cplm.get_cplm_history(db=db) == []
    rebuilt = await cplm.get_cplm_cached(db)
    assert rebuilt["total_votes"] is None and rebuilt["suppressed"] is True

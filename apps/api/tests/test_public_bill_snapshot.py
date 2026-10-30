"""Execute the reported races against real aggregate SQL and lost Redis writes."""
import json
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
from routers import analytics
from services import cplm, public_bill_response as response
from services.public_bill_snapshot import building_snapshot, read_visibility_snapshot


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


@pytest.mark.parametrize("missing", [response.IDS_KEY, response.RESULTS_IDS_KEY])
async def test_legacy_envelope_missing_either_contributor_set_is_never_served(snapshot_db, missing):
    envelope = {response.IDS_KEY: [], response.RESULTS_IDS_KEY: [], response.BODY_KEY: {"votes": 17}}
    del envelope[missing]
    assert await response.serve_public_bill_body(envelope, db=snapshot_db, schema="aggregate") is None
    assert await response.serve_public_bill_body([envelope], db=snapshot_db, schema="history") == []


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

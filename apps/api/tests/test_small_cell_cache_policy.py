"""Suppression-dependent bodies share concurrent work, never completed results."""
import asyncio
from datetime import datetime, timedelta
from fnmatch import fnmatchcase
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from database import get_db
from models import BillStatus, CitizenVote, ParliamentBill, VoteChoice
from routers import analytics, voting
from services import client_flow_cache, cplm
from services.public_bill_snapshot import read_visibility_snapshot
from services.result_cache_policy import result_cache_policy
from tests.test_public_bill_snapshot import snapshot_db


@pytest.mark.parametrize("initial_k", [0, 10])
async def test_overview_balanced_corrections_recompute_window_suppression(snapshot_db, monkeypatch, initial_k):
    db = snapshot_db
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(initial_k))
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    db.add(ParliamentBill(id="WINDOWS", title_el="Window regression", source="PARLIAMENT",
                          status=BillStatus.OPEN_END, results_visibility="ALWAYS"))
    db.add_all([CitizenVote(bill_id="WINDOWS", vote=choice, nullifier_hash=f"{day}-{choice.value}-{i}",
                            signature_hex="test", created_at=today - timedelta(days=day))
                for day in (0, 1) for choice in VoteChoice for i in range(10)])
    await db.commit()
    count = AsyncMock(wraps=analytics.count_public_votes)
    monkeypatch.setattr(analytics, "count_public_votes", count)
    app = FastAPI()
    app.include_router(analytics.router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = (await client.get("/api/v1/analytics/overview")).json()
        assert before["votes"]["today"] == 40
        if initial_k:
            assert before["votes"]["suppressed"] is False
        snapshot = await read_visibility_snapshot(db)
        await db.execute(text("UPDATE citizen_votes SET vote = 'NO', is_correction = TRUE "
                              "WHERE nullifier_hash = '1-YES-0'"))
        await db.execute(text("UPDATE citizen_votes SET vote = 'YES', is_correction = TRUE "
                              "WHERE nullifier_hash = '0-NO-0'"))
        await db.commit()  # No invalidation; all-time/source decision inputs are unchanged.
        assert (await read_visibility_snapshot(db)).result_inputs == snapshot.result_inputs
        after = (await client.get("/api/v1/analytics/overview")).json()
        assert after["votes"]["total"] == 80
        cache = analytics.analytics_overview.public_cache
        assert count.await_count == (6 if initial_k else 3)
        assert bool(cache.entries) is (initial_k == 0)
        if initial_k:
            assert after["votes"]["today"] is None and after["votes"]["suppressed"] is True
        else:
            assert after == before
            monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
            after = (await client.get("/api/v1/analytics/overview")).json()
            assert after["votes"]["today"] is None and after["votes"]["suppressed"] is True
            assert not cache.entries
            # Disabling suppression resumes caching without reviving the original body.
            monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
            assert (await client.get("/api/v1/analytics/overview")).json()["votes"]["today"] == 40
            assert cache.entries
            calls = count.await_count
            await client.get("/api/v1/analytics/overview")
            assert count.await_count == calls


async def test_per_bill_policy_toggle_never_revives_unsuppressed_totals(snapshot_db, monkeypatch):
    db = snapshot_db
    db.add(ParliamentBill(id="POINT", title_el="Point regression", source="PARLIAMENT",
                          status=BillStatus.OPEN_END, results_visibility="ALWAYS"))
    db.add_all([CitizenVote(bill_id="POINT", vote=choice, nullifier_hash=f"{choice.value}-{i}",
                            signature_hex="test") for choice in VoteChoice for i in range(10)])
    await db.commit()
    assert (await voting.get_results("POINT", db=db)).total_votes == 40
    await db.execute(text("DELETE FROM citizen_votes WHERE nullifier_hash = 'YES-0'"))
    await db.commit()
    assert (await voting.get_results("POINT", db=db)).total_votes == 40
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    suppressed = await voting.get_results("POINT", db=db)
    assert suppressed.total_votes is None and suppressed.suppressed is True
    assert not client_flow_cache.results_cache.entries
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    assert (await voting.get_results("POINT", db=db)).total_votes == 39
    assert client_flow_cache.results_cache.entries


@pytest.mark.parametrize("schema", ["aggregate", "representation", "rows"])
async def test_small_cell_bodies_never_reach_shared_memory_storage(snapshot_db, monkeypatch, schema):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    calls = 0

    @client_flow_cache.public_client_cache(bill_schema=schema, aggregate=True)
    async def read(*, db):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return [] if schema == "rows" else {"total": calls}

    cache = read.public_cache
    monkeypatch.setattr(cache, "_get_or_fill", AsyncMock(side_effect=AssertionError("shared cache used")))
    try:
        responses = await asyncio.gather(*(read(db=snapshot_db) for _ in range(20)))
        assert calls == 1 and all(response == responses[0] for response in responses)
        await read(db=snapshot_db)
        assert calls == 2 and not cache.entries and not cache.flights._pending()
    finally:
        client_flow_cache.public_caches.pop(f"{read.__module__}.{read.__name__}", None)


async def test_policy_toggle_fences_running_memory_fill_and_purges_all_affected_caches(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    caches = [client_flow_cache.ClientFlowCache(suppression_sensitive=True) for _ in range(2)]
    await caches[1].get_or_fill("other", AsyncMock(return_value="old"))
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def calculate():
        nonlocal calls
        calls += 1
        k = result_cache_policy.current()[0]
        if calls == 1:
            entered.set()
            await release.wait()
        return k

    leader = asyncio.create_task(caches[0].get_or_fill("key", calculate))
    await entered.wait()
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    assert await caches[0].get_or_fill("key", calculate) == 10
    assert all(not cache.entries for cache in caches)
    release.set()
    assert await leader == 10
    assert all(not cache.entries for cache in caches)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    assert await caches[0].get_or_fill("key", calculate) == 0
    calls_before = calls
    assert await caches[0].get_or_fill("key", calculate) == 0
    assert calls == calls_before


@pytest.mark.parametrize("before,after", [(0, 10), (10, 0)])
async def test_policy_is_rechecked_after_public_visibility_authorization(monkeypatch, before, after):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(before))
    calculate = AsyncMock(side_effect=lambda: {"k": result_cache_policy.current()[0]})

    @client_flow_cache.public_client_cache(bill_schema="aggregate")
    async def read(*, db):
        return await calculate()

    async def capture(factory, **_):
        return await factory()

    async def serve(body, **_):
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(after))
        await asyncio.sleep(0)
        return body

    monkeypatch.setattr(client_flow_cache, "capture_public_bill_body", capture)
    monkeypatch.setattr(client_flow_cache, "serve_public_bill_body", serve)
    try:
        assert await read(db=None) == {"k": after}
        assert calculate.await_count == 2
    finally:
        client_flow_cache.public_caches.pop(f"{read.__module__}.{read.__name__}", None)


class Redis:
    def __init__(self):
        self.values = {}
        self.history = {}
        self.body_calls = []
        self.down = False

    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def aclose(self): pass

    async def scan_iter(self, *, match):
        if self.down:
            raise OSError("Redis unavailable")
        for key in list(self.values) + list(self.history):
            if fnmatchcase(key, match):
                yield key

    async def delete(self, key):
        self.values.pop(key, None)
        self.history.pop(key, None)

    async def get(self, key):
        self.body_calls.append(("get", key))
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.body_calls.append(("setex", key))
        self.values[key] = value

    async def lindex(self, key, index):
        self.body_calls.append(("lindex", key))
        values = self.history.get(key, [])
        return values[index] if values else None

    async def lpush(self, key, value):
        self.body_calls.append(("lpush", key))
        self.history.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, *_): self.body_calls.append(("ltrim", key))

    async def lrange(self, key, *_):
        self.body_calls.append(("lrange", key))
        return self.history.get(key, [])


@pytest.mark.parametrize("family", ["representation", "cplm"])
@pytest.mark.parametrize("purge_down", [False, True])
async def test_redis_small_cell_bodies_bypass_reads_writes_and_retire_policy_variants(
    snapshot_db, monkeypatch, family, purge_down,
):
    store = Redis()
    monkeypatch.setattr(analytics.aioredis, "from_url", lambda *_, **__: store)
    module = analytics if family == "representation" else cplm
    name = "compute_cumulative_representation" if family == "representation" else "compute_cplm"
    read = analytics.get_cached_representation if family == "representation" else cplm.get_cplm_cached
    payload = ({"cumulative_representation": 75, "bills": [], "total_citizen_votes": 40}
               if family == "representation" else {"x": 0, "y": 0, "total_votes": 40})

    async def calculate(_db):
        await asyncio.sleep(0.02)
        return dict(payload)

    compute = AsyncMock(side_effect=calculate)
    monkeypatch.setattr(module, name, compute)
    monkeypatch.setattr(module, "cache_fill_quota", AsyncMock())
    assert await read(snapshot_db) == payload
    assert await read(snapshot_db) == payload
    assert compute.await_count == 1
    old_keys = set(store.values) | set(store.history)
    assert old_keys
    for k in (10, 11):
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(k))
        store.down = purge_down
        store.body_calls.clear()
        responses = await asyncio.gather(*(read(snapshot_db) for _ in range(20)))
        assert all(response == payload for response in responses)
        assert compute.await_count == (2 if k == 10 else 4)
        await read(snapshot_db)
        if family == "cplm":
            assert await cplm.get_cplm_history(db=snapshot_db) == []
        assert store.body_calls == []  # Purge commands are allowed; body reads/writes are forbidden.
        if not purge_down:
            assert not store.values and not store.history
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    payload = dict(payload, **({"total_citizen_votes": 80} if family == "representation" else {"total_votes": 80}))
    fresh = await read(snapshot_db)
    assert fresh == payload
    new_keys = (set(store.values) | set(store.history)) - old_keys
    assert new_keys  # Failed purges cannot resurrect pre-toggle values.
    calls = compute.await_count
    assert await read(snapshot_db) == fresh
    assert compute.await_count == calls


@pytest.mark.parametrize("family", ["representation", "cplm"])
async def test_policy_change_during_redis_write_cannot_restore_retired_body(snapshot_db, monkeypatch, family):
    store = Redis()
    monkeypatch.setattr(analytics.aioredis, "from_url", lambda *_, **__: store)
    module = analytics if family == "representation" else cplm
    name = "compute_cumulative_representation" if family == "representation" else "compute_cplm"
    read = analytics.get_cached_representation if family == "representation" else cplm.get_cplm_cached
    payload = ({"cumulative_representation": 75, "bills": []}
               if family == "representation" else {"x": 0, "y": 0})
    monkeypatch.setattr(module, name, AsyncMock(side_effect=lambda _db: dict(payload)))
    monkeypatch.setattr(module, "cache_fill_quota", AsyncMock())
    entered, release = asyncio.Event(), asyncio.Event()
    setex = store.setex

    async def delayed_setex(*args):
        entered.set()
        await release.wait()
        await setex(*args)

    monkeypatch.setattr(store, "setex", delayed_setex)
    leader = asyncio.create_task(read(snapshot_db))
    await entered.wait()
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    assert await read(snapshot_db) == payload
    release.set()
    assert await leader == payload
    assert not store.values and not store.history

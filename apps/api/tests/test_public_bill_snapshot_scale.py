"""Exercise provenance at asyncpg scale, independent of response detail limits."""
import asyncio
import importlib.util
from pathlib import Path
import re
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.dialects.postgresql import asyncpg
from sqlalchemy.schema import CreateIndex

from models import ParliamentBill
from routers import analytics, consensus_results, mp
from services import cplm, public_bill_response as response
from services.public_bill_snapshot import (
    BillVisibilitySnapshot, building_snapshot, read_visibility_snapshot,
    snapshot_bill_filter, snapshot_raw_filter, visibility_snapshot_query,
)
from services.request_work import SingleFlight
from services.public_bill_index import PUBLIC_BILL_INDEX, SENSITIVE_PATTERN
from tests.test_public_bill_snapshot import snapshot_db, seventeen_votes


def compile_asyncpg(query):
    dialect = asyncpg.dialect()
    dialect._backslash_escapes = False  # PostgreSQL default, discovered on connect.
    return query.compile(dialect=dialect, compile_kwargs={"render_postcompile": True})


def test_metadata_index_and_prepared_queries_share_the_frozen_visibility_policy():
    from services.bill_visibility import DIAVGEIA_SENSITIVE_PUBLIC_TERMS, public_bill_metadata_sql
    assert SENSITIVE_PATTERN == "|".join(re.escape(term) for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS)
    index = next(i for i in ParliamentBill.__table__.indexes if i.name == PUBLIC_BILL_INDEX)
    ddl = str(CreateIndex(index).compile(dialect=asyncpg.dialect()))
    predicate, params = public_bill_metadata_sql("b")
    def normalize(sql):
        return re.sub(r"\s+", "", sql.lower()).replace("b.", "")
    assert normalize(ddl.split(" WHERE ")[1]) == normalize(predicate)
    assert not params
    path = Path(__file__).resolve().parents[1] / "alembic/versions/z902a2b3c4d5_public_bill_metadata_index.py"
    spec = importlib.util.spec_from_file_location("metadata_migration_policy", path)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    assert normalize(revision.PREDICATE) == normalize(predicate)
    query = compile_asyncpg(visibility_snapshot_query(candidates=["B1"]))
    assert SENSITIVE_PATTERN in str(query)
    assert not any(value == SENSITIVE_PATTERN for value in query.params.values())


@pytest.mark.parametrize("k", [0, 10])
def test_forty_thousand_ids_keep_bind_counts_constant(k):
    counts = []
    for size in (1, 40_000):
        ids = frozenset(f"B{i}" for i in range(size))
        token = building_snapshot.set(BillVisibilitySnapshot(ids, ids))
        try:
            queries = [
                visibility_snapshot_query(candidates=ids, k=k),
                select(ParliamentBill.id).where(snapshot_bill_filter()),
                select(ParliamentBill.id).where(snapshot_bill_filter(results=True)),
            ]
            compiled = [compile_asyncpg(query) for query in queries]
            raw, params = snapshot_raw_filter("b", results=True)
            assert "IN (SELECT unnest(CAST(:snapshot_b_ids AS VARCHAR[])))" in raw
            assert len(params) == 1 and len(params["snapshot_b_ids"]) == size
            aggregate, aggregate_params = analytics.representation_query()
            assert len(aggregate_params["snapshot_b_ids"]) == size
            assert all("IN (SELECT unnest(" in str(query) and "::VARCHAR[]" in str(query) for query in compiled)
            assert all("POSTCOMPILE" not in str(query) for query in compiled)
            counts.append([len(query.positiontup) for query in compiled] + [len(params), len(aggregate_params)])
        finally:
            building_snapshot.reset(token)
    assert counts[0] == counts[1]
    assert max(counts[1]) < 64
    print(f"k={k} IDs=1/40000: constant binds validation/ORM/raw/aggregate={counts[1]}")


async def test_large_snapshot_capture_raw_filter_and_validation_execute_with_one_id_bind(snapshot_db):
    db = snapshot_db
    await db.execute(text("""
        WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i < 40000)
        INSERT INTO parliament_bills (id, title_el, source, status, governance_level, admin_hidden)
        SELECT 'B' || i, 'Bill', 'PARLIAMENT', 'OPEN_END', 'NATIONAL', FALSE FROM n
    """))
    await db.commit()
    ids = {f"B{i}" for i in range(1, 40_001)}
    seen = []
    def record(_conn, _cursor, sql, params, *_):
        seen.append((sql, len(params)))
    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        async def compute():
            guard, params = snapshot_raw_filter("b", db=db)
            return await db.scalar(text(f"SELECT count(*) FROM parliament_bills b WHERE {guard}"), params)
        envelope = await response.capture_public_bill_body(compute, db=db, candidates=ids)
        assert len(envelope[response.IDS_KEY]) == 40_000
        assert await response.serve_public_bill_body(envelope, db=db, schema="aggregate") == 40_000
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)
    assert len(seen) == 3 and max(count for _, count in seen) < 16
    assert all("json_each" in sql for sql, _ in seen)


@pytest.mark.parametrize("child_task", [False, True])
async def test_cold_owner_never_waits_on_its_own_flight(child_task):
    flight = SingleFlight(reject_on_capacity=False, wait_timeout=10)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0
    async def inner():
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return 42
    async def owner():
        nested = flight.run("cold", inner)
        return await asyncio.create_task(nested) if child_task else await nested
    leader = asyncio.create_task(flight.run("cold", owner))
    follower = None
    try:
        await asyncio.wait_for(entered.wait(), .5)
        follower = asyncio.create_task(flight.run("cold", AsyncMock(side_effect=AssertionError("duplicate fill"))))
        await asyncio.sleep(0)
        assert not follower.done() and calls == 1
        release.set()
        assert await asyncio.wait_for(asyncio.gather(leader, follower), .5) == [42, 42]
        assert not flight._pending()
    finally:
        release.set()
        leader.cancel()
        if follower:
            follower.cancel()
        await asyncio.gather(leader, *([follower] if follower else []), return_exceptions=True)


async def test_finished_owner_context_does_not_own_a_later_fill():
    flight = SingleFlight(reject_on_capacity=False)
    begin, entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    tasks = []
    async def delayed_child():
        await begin.wait()
        return await flight.run("key", AsyncMock(side_effect=AssertionError("stale ownership")))
    async def first():
        tasks.append(asyncio.create_task(delayed_child()))
        return 1
    async def second():
        entered.set()
        await release.wait()
        return 2
    try:
        assert await flight.run("key", first) == 1
        tasks.append(asyncio.create_task(flight.run("key", second)))
        await asyncio.wait_for(entered.wait(), .5)
        begin.set()
        await asyncio.sleep(0)
        assert not tasks[0].done()
        release.set()
        assert await asyncio.wait_for(asyncio.gather(*tasks), .5) == [2, 2]
    finally:
        begin.set()
        release.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("route,expected,absent", [
    (analytics.analytics_overview, {"RACE", "UNVOTED", "UNVOTED-PARTY"}, {"DEMO-X"}),
    (mp.party_ranking, {"RACE"}, {"UNVOTED", "UNVOTED-PARTY", "DEMO-X"}),
    (consensus_results.get_consensus_representation, {"UNVOTED"}, {"RACE", "UNVOTED-PARTY", "DEMO-X"}),
])
async def test_route_capture_and_warm_revalidation_scope(snapshot_db, monkeypatch, route, expected, absent):
    db = snapshot_db
    race = await seventeen_votes(db)
    from models import BillStatus
    race.status = BillStatus.PARLIAMENT_VOTED
    race.party_votes_parliament = {"ND": "YES"}
    db.add_all([
        ParliamentBill(id="UNVOTED", title_el="Coverage dependency", source="DIAVGEIA"),
        ParliamentBill(id="DEMO-X", title_el="Demo", source="PARLIAMENT"),
        ParliamentBill(id="UNVOTED-PARTY", title_el="No citizen turnout", source="PARLIAMENT",
                       status=BillStatus.PARLIAMENT_VOTED, party_votes_parliament={"ND": "YES"}),
    ])
    await db.commit()
    async def fake_compute(*_, **__):
        return {"ok": True}
    # Exercise the real capture/query/decorator without route-specific aggregate SQL.
    # The registered scope is exposed for this contract by the cache decorator.
    from services.client_flow_cache import public_client_cache, public_caches
    @public_client_cache(bill_schema="aggregate", bill_candidates=route.public_bill_candidates)
    async def scoped(*, db):
        return await fake_compute()
    try:
        assert await scoped(db=db) == {"ok": True}
        envelope = next(iter(scoped.public_cache.entries.values()))[1]
        assert set(envelope[response.IDS_KEY]) == expected
        assert absent.isdisjoint(envelope[response.IDS_KEY])
        spy = AsyncMock(wraps=response.read_visibility_snapshot)
        monkeypatch.setattr(response, "read_visibility_snapshot", spy)
        assert await scoped(db=db) == {"ok": True}
        assert spy.await_count == 1 and set(spy.await_args.kwargs["candidates"]) == expected
    finally:
        public_caches.pop(f"{scoped.__module__}.{scoped.__name__}", None)


async def test_point_and_cplm_ignore_unrelated_text_and_history_keeps_previous_ids(snapshot_db, monkeypatch):
    db = snapshot_db
    await seventeen_votes(db)
    db.add(ParliamentBill(id="UNRELATED", title_el="Other bill", source="DIAVGEIA", summary_long_el="slow text"))
    await db.commit()
    calls = []
    connection = await db.connection()
    raw = await connection.get_raw_connection()
    def regexp(pattern, value):
        calls.append(value)
        assert value != "slow text", "Unrelated bill text entered a scoped snapshot"
        return bool(re.search(pattern, value or ""))
    await raw.driver_connection.create_function("regexp", 2, regexp)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    from services.zk_vote_aggregation import aggregate_bill_vote_totals
    envelope = await response.capture_public_bill_body(
        lambda: aggregate_bill_vote_totals(db, "RACE", include_zk=True), db=db, point_results="RACE",
    )
    assert envelope[response.IDS_KEY] == ["RACE"]
    assert await response.serve_public_bill_body(
        envelope, db=db, schema="point", bill_ids=("RACE",), point_results=True,
    ) is not None
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    captured = await cplm._capture_cplm(db)
    assert captured[response.IDS_KEY] == ["RACE"]
    assert await response.serve_public_bill_body([captured], db=db, schema="history") == [captured[response.BODY_KEY]]

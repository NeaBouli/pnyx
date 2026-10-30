"""Actual PostgreSQL/asyncpg execution and EXPLAIN; uses a disposable schema.

Run with the existing PNYX_TEST_POSTGRES_URL (loopback, pnyx_test_* DB).
No planner switches disable sequential scans or force a particular plan.
"""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from services.public_bill_index import PUBLIC_BILL_INDEX
from services.public_bill_snapshot import visibility_snapshot_query
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
async def postgres():
    engine = create_async_engine(disposable_postgres_url())
    schema = "snapshot_" + uuid4().hex
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
        try:
            await connection.exec_driver_sql(f"SET search_path TO {schema}")
            await connection.exec_driver_sql("SET plan_cache_mode = force_generic_plan")
            for sql in (
                "CREATE TYPE billstatus AS ENUM ('ANNOUNCED','ACTIVE','WINDOW_24H','PARLIAMENT_VOTED','OPEN_END')",
                "CREATE TYPE votechoice AS ENUM ('YES','NO','ABSTAIN','UNKNOWN')",
                """CREATE TABLE parliament_bills (
                    id varchar(50) PRIMARY KEY, title_el text, summary_short_el text, summary_long_el text,
                    source varchar(20), status billstatus, results_visibility varchar(10), admin_hidden boolean,
                    governance_level text, dimos_id integer, periferia_id integer)""",
                "CREATE TABLE citizen_votes (bill_id varchar(50), vote votechoice)",
                "CREATE INDEX idx_votes_bill ON citizen_votes (bill_id)",
                "CREATE TABLE zk_vote_receipts (vote_scope_id varchar(128), vote_commitment varchar(10))",
                "CREATE INDEX idx_zk_receipts_scope ON zk_vote_receipts (vote_scope_id)",
                """INSERT INTO parliament_bills
                    SELECT 'B' || g, 'Public bill', '', repeat('ordinary public text ', 150),
                           'PARLIAMENT', 'OPEN_END', 'ALWAYS', FALSE, 'NATIONAL', NULL, NULL
                    FROM generate_series(1,40000) g""",
                "INSERT INTO citizen_votes SELECT id, 'YES' FROM parliament_bills",
                "INSERT INTO zk_vote_receipts SELECT 'bill:' || id, 'YES' FROM parliament_bills",
            ):
                await connection.exec_driver_sql(sql)
            path = Path(__file__).resolve().parents[1] / "alembic/versions/z902a2b3c4d5_public_bill_metadata_index.py"
            spec = importlib.util.spec_from_file_location("metadata_index_migration", path)
            revision = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(revision)
            await connection.commit()
            def migrate(sync):
                context = MigrationContext.configure(sync)
                with context.begin_transaction(), patch.object(revision, "op", Operations(context)):
                    revision.upgrade()
            await connection.run_sync(migrate)
            for table in ("parliament_bills", "citizen_votes", "zk_vote_receipts"):
                await connection.exec_driver_sql(f"VACUUM (ANALYZE) {table}")
            yield connection, revision
        finally:
            await connection.exec_driver_sql("SET search_path TO public")
            await connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
    await engine.dispose()


def nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


async def explain(connection, query):
    compiled = query.compile(dialect=connection.dialect, compile_kwargs={"render_postcompile": True})
    result = await connection.exec_driver_sql(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + str(compiled),
        tuple(compiled.params[name] for name in compiled.positiontup),
    )
    payload = result.scalar_one()
    return (json.loads(payload) if isinstance(payload, str) else payload)[0]["Plan"]


async def test_public_metadata_uses_covering_index_for_full_counts_and_warm_ids(postgres):
    connection, _ = postgres
    for candidates in (None, ("B1", "B2", "B3")):
        plan = await explain(connection, visibility_snapshot_query(candidates=candidates))
        scans = list(nodes(plan))
        assert any(n.get("Index Name") == PUBLIC_BILL_INDEX and n["Node Type"] == "Index Only Scan" for n in scans)
        assert not any(n.get("Relation Name") == "parliament_bills" and n["Node Type"] == "Seq Scan" for n in scans)
        assert not any("summary_long_el" in n.get("Filter", "") for n in scans)
        print("metadata population=", "all" if candidates is None else "three", "index-only; no text filter")


async def test_suppression_groups_only_indexed_candidate_votes(postgres):
    connection, _ = postgres
    plan = await explain(connection, visibility_snapshot_query(candidates=("B1", "B2", "B3"), k=10))
    scans = list(nodes(plan))
    for table, index in (("citizen_votes", "idx_votes_bill"), ("zk_vote_receipts", "idx_zk_receipts_scope")):
        assert any(n.get("Index Name") == index for n in scans), json.dumps(plan)
        assert not any(n.get("Relation Name") == table and n["Node Type"] == "Seq Scan" for n in scans)
        assert sum(n.get("Actual Rows", 0) * n.get("Actual Loops", 1) for n in scans
                   if n.get("Relation Name") == table) <= 3
    print("k=10 three candidates: idx_votes_bill + idx_zk_receipts_scope before grouping")


async def test_generic_plan_expands_large_id_population_once(postgres):
    connection, _ = postgres
    ids = [f"B{i}" for i in range(1, 40_001)]
    plan = await explain(connection, visibility_snapshot_query(candidates=ids))
    scans = list(nodes(plan))
    expansions = [node for node in scans if node["Node Type"] == "ProjectSet"]
    assert expansions and sum(node["Actual Loops"] for node in expansions) == 1, json.dumps(plan)
    assert sum(node["Actual Rows"] for node in expansions) == len(ids)
    assert not any("summary_long_el" in node.get("Filter", "") for node in scans)
    print("generic plan 40000 contributor IDs: one unnest; no per-bill array scan or text filter")


async def test_asyncpg_executes_forty_thousand_ids_and_migration_round_trip(postgres):
    connection, revision = postgres
    ids = [f"B{i}" for i in range(1, 40_001)]
    assert len((await connection.execute(visibility_snapshot_query(candidates=ids))).all()) == 40_000
    assert await connection.scalar(text(
        "SELECT count(*) FROM parliament_bills b WHERE b.id IN (SELECT unnest(CAST(:ids AS VARCHAR[])))"
    ), {"ids": ids}) == 40_000
    await connection.commit()
    def cycle(sync):
        context = MigrationContext.configure(sync)
        with context.begin_transaction(), patch.object(revision, "op", Operations(context)):
            revision.downgrade()
            revision.upgrade()
    await connection.run_sync(cycle)
    assert await connection.scalar(text(
        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
        "WHERE c.relname=:name AND c.relnamespace=current_schema()::regnamespace"
    ), {"name": PUBLIC_BILL_INDEX}) is True
    print("asyncpg: 40000 IDs execute via one array bind; concurrent migration down/up valid")

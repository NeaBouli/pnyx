"""Actual PostgreSQL/asyncpg execution and EXPLAIN; uses a disposable schema.

Run with the existing PNYX_TEST_POSTGRES_URL (loopback, pnyx_test_* DB).
No planner switches disable sequential scans or force a particular plan.
"""
from collections.abc import AsyncIterator, Iterator
import itertools
import json
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.sql import Select

from models import ParliamentBill
from services.bill_visibility import (
    DIAVGEIA_SENSITIVE_PUBLIC_TERMS, is_public_bill, public_bill_filter,
    public_bill_with_demo_filter, sensitive_diavgeia_filter,
)
from services.public_bill_index import PUBLIC_BILL_INDEX
from services.public_bill_snapshot import visibility_snapshot_query
from tests.pg_public_bill_schema import public_metadata_revision
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
async def postgres(request: pytest.FixtureRequest) -> AsyncIterator[tuple[AsyncConnection, ModuleType]]:
    cold = getattr(request, "param", False)
    engine = create_async_engine(disposable_postgres_url())
    schema = "snapshot_" + uuid4().hex
    try:
        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
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
            ):
                await connection.exec_driver_sql(sql)
            if cold:
                # Disable autovacuum as well: no visibility-map shortcut may hide the
                # planner regression. Incompressible synthetic hashes force real TOAST.
                await connection.exec_driver_sql(
                    "ALTER TABLE parliament_bills SET (autovacuum_enabled = false, toast.autovacuum_enabled = false)"
                )
                await connection.exec_driver_sql("""INSERT INTO parliament_bills
                    SELECT CASE WHEN g % 29 = 0 THEN 'DEMO-' ELSE 'B' END || g,
                           CASE WHEN g % 19 = 0 THEN 'AMKA' ELSE 'Public procurement' END,
                           left(payload, 4096), payload,
                           CASE WHEN g % 10 = 0 THEN 'PARLIAMENT' ELSE 'DIAVGEIA' END,
                           'OPEN_END', 'ALWAYS', g % 23 = 0, 'NATIONAL', NULL, NULL
                    FROM generate_series(1,12000) g
                    CROSS JOIN LATERAL (
                        SELECT string_agg(md5(g::text || ':' || j::text), ' ') AS payload
                        FROM generate_series(1,256) j
                    ) synthetic""")
            else:
                await connection.exec_driver_sql("""INSERT INTO parliament_bills
                    SELECT 'B' || g, 'Public bill', '', repeat('ordinary public text ', 150),
                           'PARLIAMENT', 'OPEN_END', 'ALWAYS', FALSE, 'NATIONAL', NULL, NULL
                    FROM generate_series(1,40000) g""")
            for sql in (
                "INSERT INTO citizen_votes SELECT id, 'YES' FROM parliament_bills",
                "INSERT INTO zk_vote_receipts SELECT 'bill:' || id, 'YES' FROM parliament_bills",
            ):
                await connection.exec_driver_sql(sql)
            revision = public_metadata_revision()
            await migrate(connection, public_metadata_revision(legacy=True), "upgrade")
            await migrate(connection, revision, "upgrade")
            for table in ("parliament_bills", "citizen_votes", "zk_vote_receipts"):
                await connection.exec_driver_sql(f"ANALYZE {table}" if cold else f"VACUUM (ANALYZE) {table}")
            yield connection, revision
    finally:
        async with engine.connect() as cleanup:
            cleanup = await cleanup.execution_options(isolation_level="AUTOCOMMIT")
            await cleanup.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        await engine.dispose()


async def migrate(connection: AsyncConnection, revision: ModuleType, action: str) -> None:
    schema = await connection.scalar(text("SELECT current_schema()"))

    def run(sync: Connection) -> None:
        context = MigrationContext.configure(sync)
        with context.begin_transaction(), patch.object(revision, "op", Operations(context)):
            getattr(revision, action)()

    # autocommit_block() restores server-default isolation. Every migration, including
    # down/up tests, gets its own connection; the fixture keeps its AUTOCOMMIT setting.
    async with connection.engine.connect() as migration:
        await migration.exec_driver_sql(f"SET search_path TO {schema}")
        await migration.commit()
        await migration.run_sync(run)


def nodes(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


async def explain(connection: AsyncConnection, query: Select[Any]) -> dict[str, Any]:
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
    await migrate(connection, revision, "downgrade")
    assert await connection.scalar(text("SELECT to_regclass(:name)"), {"name": PUBLIC_BILL_INDEX}) is None
    assert await connection.scalar(text("SELECT to_regclass(:name)"), {"name": revision.LEGACY_INDEX_NAME}) is not None
    assert await connection.scalar(text(
        "SELECT to_regprocedure('public_bill_sensitive(text,text,text,text)')"
    )) is None
    legacy = public_metadata_revision(legacy=True)
    legacy_definition = await connection.scalar(text(
        "SELECT pg_get_expr(indpred, indrelid) FROM pg_index WHERE indexrelid = to_regclass(:name)"
    ), {"name": legacy.INDEX_NAME})
    assert "public_bill_sensitive" not in legacy_definition
    assert legacy_definition.count(" ~ ") == 3
    await migrate(connection, revision, "upgrade")
    assert await connection.scalar(text(
        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
        "WHERE c.relname=:name AND c.relnamespace=current_schema()::regnamespace"
    ), {"name": PUBLIC_BILL_INDEX}) is True
    assert await connection.scalar(text("SELECT to_regclass(:name)"), {"name": revision.LEGACY_INDEX_NAME}) is None
    print("asyncpg: 40000 IDs execute via one array bind; concurrent migration down/up valid")


@pytest.mark.parametrize("postgres", [True], indirect=True)
async def test_cold_toasted_population_uses_v2_without_vacuum(postgres: Any) -> None:
    connection, _ = postgres
    assert await connection.scalar(text("SHOW enable_seqscan")) == "on"
    assert await connection.scalar(text(
        "SELECT relallvisible FROM pg_class WHERE oid = 'parliament_bills'::regclass"
    )) == 0
    assert await connection.scalar(text(
        "SELECT pg_relation_size(reltoastrelid) FROM pg_class WHERE oid = 'parliament_bills'::regclass"
    )) > 100_000_000
    for label, query in (
        ("count(id), public + non-demo", select(func.count(ParliamentBill.id)).where(public_bill_with_demo_filter())),
        ("visibility snapshot k=0", visibility_snapshot_query(k=0)),
        ("visibility snapshot k=5", visibility_snapshot_query(k=5)),
    ):
        plan = await explain(connection, query)
        scans = list(nodes(plan))
        assert any(n.get("Index Name") == PUBLIC_BILL_INDEX for n in scans), json.dumps(plan)
        assert not any(n.get("Relation Name") == "parliament_bills" and "Seq Scan" in n["Node Type"]
                       for n in scans), json.dumps(plan)
        assert not any("public_bill_sensitive" in n.get("Filter", "") for n in scans), json.dumps(plan)
        print(f"\nEXPLAIN {label}:\n{json.dumps(plan, indent=2)}")


async def test_function_matches_python_visibility_on_edge_cases(postgres: Any) -> None:
    connection, _ = postgres
    samples = [None, "", "ordinary hospital procurement", "αXμXκXα", "a.m.k.a", "α.μ.κ", "am\nka"]
    for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS:
        samples.extend((term, term.upper(), "prefix" + term + "suffix", "\n" + term + "\n"))
    cases = []
    fields = ("title_el", "summary_short_el", "summary_long_el")
    for source, hidden, field, sample in itertools.product(
        (None, "DIAVGEIA", "PARLIAMENT", "OTHER", "diavgeia"), (None, False, True), fields, samples,
    ):
        row = dict(id=f"EDGE-{len(cases)}", source=source, admin_hidden=hidden,
                   title_el=None, summary_short_el=None, summary_long_el=None)
        row[field] = sample
        cases.append(row)
    cases.extend((
        dict(id="EDGE-split", source="DIAVGEIA", admin_hidden=False,
             title_el="am", summary_short_el="ka", summary_long_el=None),
        dict(id="EDGE-long", source="DIAVGEIA", admin_hidden=False,
             title_el=None, summary_short_el=None, summary_long_el="x" * 100_000 + "ΑΣΘΕΝ"),
    ))
    await connection.execute(text(
        "INSERT INTO parliament_bills (id, source, admin_hidden, title_el, summary_short_el, summary_long_el) "
        "VALUES (:id, :source, :admin_hidden, :title_el, :summary_short_el, :summary_long_el)"
    ), cases)
    expected = {row["id"]: row for row in cases}
    query = select(
        ParliamentBill.id, sensitive_diavgeia_filter(), public_bill_filter(),
    ).where(ParliamentBill.id.like("EDGE-%"))
    for bill_id, sensitive, public in (await connection.execute(query)).all():
        row = expected.pop(bill_id)
        assert sensitive is not None
        assert sensitive is (not is_public_bill(SimpleNamespace(**{**row, "admin_hidden": False}))), row
        assert public is is_public_bill(SimpleNamespace(**row)), row
    assert not expected
    properties = (await connection.execute(text(
        "SELECT l.lanname, p.provolatile, p.proparallel, p.procost, p.proisstrict "
        "FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang "
        "WHERE p.oid = 'public_bill_sensitive(text,text,text,text)'::regprocedure"
    ))).one()
    assert tuple(properties) == ("plpgsql", "i", "s", 10000, False)

"""Synthetic PostgreSQL regressions for z904 and the authenticated admin path."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import itertools
from types import ModuleType
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from models import AuditLog, Dimos, ParliamentBill, Periferia
from routers import admin
from services.bill_visibility import DIAVGEIA_SENSITIVE_PUBLIC_TERMS, is_public_bill, public_bill_filter
from tests.pg_public_bill_schema import public_metadata_revision, sensitivity_revision
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres
from tests.test_public_bill_snapshot_pg import migrate

pytestmark = requires_postgres


@pytest.fixture
async def old_schema() -> AsyncIterator[tuple[AsyncConnection, ModuleType]]:
    engine = create_async_engine(disposable_postgres_url())
    schema = "sensitivity_" + uuid4().hex
    try:
        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
            await connection.exec_driver_sql(f"SET search_path TO {schema}")
            await connection.run_sync(lambda sync: ParliamentBill.metadata.create_all(sync, tables=[
                Periferia.__table__, Dimos.__table__, ParliamentBill.__table__, AuditLog.__table__,
            ]))
            # Reconstruct the actual pre-z904 table, including its working v2 index.
            await connection.exec_driver_sql("""ALTER TABLE parliament_bills
                DROP COLUMN sensitive_public_block, DROP COLUMN sensitive_override,
                DROP COLUMN sensitive_override_reason""")
            await migrate(connection, public_metadata_revision(), "upgrade")
            yield connection, sensitivity_revision()
    finally:
        async with engine.connect() as cleanup:
            cleanup = await cleanup.execution_options(isolation_level="AUTOCOMMIT")
            await cleanup.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        await engine.dispose()


@asynccontextmanager
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    schema = await connection.scalar(text("SELECT current_schema()"))
    async with connection.engine.connect() as other:
        await other.exec_driver_sql(f"SET search_path TO {schema}")
        await other.commit()
        async with AsyncSession(other, expire_on_commit=False) as db:
            yield db


async def seed(connection: AsyncConnection, rows: list[dict]) -> None:
    await connection.execute(text("""INSERT INTO parliament_bills
        (id, source, title_el, summary_short_el, summary_long_el, admin_hidden, status, governance_level)
        VALUES (:id, :source, :title_el, :summary_short_el, :summary_long_el, :admin_hidden,
                'OPEN_END', 'NATIONAL')"""), rows)


def bill_row(bill_id: str, **values) -> dict:
    return dict(id=bill_id, **{**dict(source="DIAVGEIA", title_el="Synthetic procurement",
                summary_short_el=None, summary_long_el=None, admin_hidden=False), **values})


async def test_backfill_preserves_all_visible_ids_and_hides_null_predicates(old_schema) -> None:
    connection, revision = old_schema
    samples = [None, "", "ordinary", "αXμXκXα", "am\nka"]
    for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS:
        samples.extend((term, term.upper(), "prefix" + term + "suffix"))
    rows = []
    for source, hidden, field, sample in itertools.product(
        (None, "DIAVGEIA", "PARLIAMENT", "OTHER", "diavgeia"), (None, True, False),
        ("title_el", "summary_short_el", "summary_long_el"), samples,
    ):
        if field == "title_el" and sample is None:
            continue  # title_el is NOT NULL in the schema (and in production)
        rows.append(bill_row(f"EDGE-{len(rows):05}", source=source, admin_hidden=hidden,
                             **{field: sample}))
    rows.extend([
        bill_row("split", title_el="am", summary_short_el="ka"),
        bill_row("long", summary_long_el="x" * 100_000 + "ΑΣΘΕΝ"),
    ])
    await seed(connection, rows)
    old = dict((await connection.execute(text(
        f"SELECT id, ({revision.LEGACY_PREDICATE}) IS TRUE FROM parliament_bills"
    ))).all())
    batches: list[int] = []

    def record(_conn, _cursor, sql, parameters, _context, _many):
        if "WITH batch AS" in sql:
            assert "LIMIT" in sql
            batches.append(revision.BATCH_SIZE)

    event.listen(connection.engine.sync_engine, "before_cursor_execute", record)
    try:
        await migrate(connection, revision, "upgrade")
    finally:
        event.remove(connection.engine.sync_engine, "before_cursor_execute", record)
    assert len(rows) > 1000 and len(batches) >= 3
    current = dict((await connection.execute(select(ParliamentBill.id, public_bill_filter()))).all())
    assert current == old  # No hidden-to-public or public-to-hidden flips.
    async with session(connection) as db:
        for bill in (await db.scalars(select(ParliamentBill))).all():
            assert is_public_bill(bill) is old[bill.id]
    raw = (await connection.execute(text("""SELECT id, sensitive_public_block,
        public_bill_sensitive(source, title_el, summary_short_el, summary_long_el)
        FROM parliament_bills"""))).all()
    assert any(sensitive is None for _, _, sensitive in raw)
    assert all(blocked is (sensitive is not False) for _, blocked, sensitive in raw)


@pytest.mark.parametrize("writer", ["orm", "sql"])
async def test_marker_removal_cannot_publish(old_schema, writer: str) -> None:
    connection, revision = old_schema
    await seed(connection, [bill_row("S", summary_long_el="Synthetic AMKA marker")])
    await migrate(connection, revision, "upgrade")
    async with session(connection) as db:
        bill = await db.get(ParliamentBill, "S")
        assert bill.sensitive_public_block is True
        if writer == "orm":
            bill.summary_long_el = "Regenerated ordinary summary"
            await db.flush()
            # The ORM fetches trigger output before publishing hooks use the object.
            assert not is_public_bill(bill)
        else:
            await db.execute(text("UPDATE parliament_bills SET summary_long_el = NULL WHERE id = 'S'"))
        await db.commit()
        await db.refresh(bill)
        assert bill.sensitive_public_block is True
        assert not is_public_bill(bill)
        assert (await db.scalars(select(ParliamentBill.id).where(public_bill_filter()))).all() == []


async def test_insert_and_text_updates_latch_new_markers_in_orm_and_raw_sql(old_schema) -> None:
    connection, revision = old_schema
    await migrate(connection, revision, "upgrade")
    async with session(connection) as db:
        bill = ParliamentBill(id="INSERT", source="DIAVGEIA", title_el="AMKA")
        db.add(bill)
        await db.flush()
        assert bill.sensitive_public_block is True and not is_public_bill(bill)
        safe = ParliamentBill(id="UPDATE", source="DIAVGEIA", title_el="Ordinary")
        db.add(safe)
        await db.flush()
        assert safe.sensitive_public_block is False
        safe.summary_long_el = "ΑΣΘΕΝ"
        await db.flush()
        assert safe.sensitive_public_block is True and not is_public_bill(safe)
        await db.commit()
    await seed(connection, [bill_row("RAW", source=None, summary_short_el="EOPYY")])
    assert await connection.scalar(text(
        "SELECT sensitive_public_block FROM parliament_bills WHERE id = 'RAW'"
    )) is True
    await connection.exec_driver_sql("UPDATE parliament_bills SET source = 'PARLIAMENT', summary_short_el = NULL")
    assert await connection.scalar(select(ParliamentBill.id).where(public_bill_filter())) is None


async def test_trigger_closes_marker_removal_race_before_backfill(old_schema, monkeypatch) -> None:
    connection, revision = old_schema
    await seed(connection, [bill_row("RACE", summary_long_el="AMKA")])
    backfill = revision._backfill

    def concurrent_cleanup(bind):
        # DDL is committed and the trigger is active, but this row still has its default flag.
        assert bind.scalar(text("SELECT sensitive_public_block FROM parliament_bills")) is False
        schema = bind.scalar(text("SELECT current_schema()"))
        with bind.engine.connect() as writer:
            writer.exec_driver_sql(f"SET search_path TO {schema}")
            writer.exec_driver_sql("SET LOCAL lock_timeout = '2s'")
            # A separate writer must not wait on a migration-wide table/DDL lock.
            writer.execute(text("UPDATE parliament_bills SET summary_long_el = NULL"))
            writer.commit()
        assert bind.scalar(text("SELECT sensitive_public_block FROM parliament_bills")) is True
        backfill(bind)

    monkeypatch.setattr(revision, "_backfill", concurrent_cleanup)
    await migrate(connection, revision, "upgrade")
    assert await connection.scalar(select(ParliamentBill.id).where(public_bill_filter())) is None


async def test_admin_overrides_audit_and_explicit_clear_are_atomic(old_schema, monkeypatch) -> None:
    connection, revision = old_schema
    await seed(connection, [bill_row("S", summary_long_el="AMKA")])
    await migrate(connection, revision, "upgrade")
    invalidate = AsyncMock()
    monkeypatch.setattr("services.representation_cache.invalidate_representation_cache", invalidate)
    async with session(connection) as db:
        for override, public in ((False, True), (True, False), (None, False)):
            response = await admin.admin_set_bill_sensitivity(
                "S", admin.BillSensitivityRequest(sensitive_override=override, reason="Synthetic review"),
                _key=True, db=db,
            )
            assert response["sensitive_override"] is override
            bill = await db.get(ParliamentBill, "S")
            assert is_public_bill(bill) is public
            assert bool((await db.scalars(select(ParliamentBill.id).where(public_bill_filter()))).all()) is public
            assert bill.sensitive_public_block is True
        await admin.admin_set_bill_sensitivity(
            "S", admin.BillSensitivityRequest(sensitive_override=None, reason="Explicit synthetic clear",
                                               clear_sensitive_public_block=True), _key=True, db=db,
        )
        bill = await db.get(ParliamentBill, "S")
        assert bill.sensitive_public_block is False and is_public_bill(bill)
        await db.execute(text("UPDATE parliament_bills SET summary_long_el = NULL WHERE id = 'S'"))
        await db.commit()
        await db.refresh(bill)
        assert bill.sensitive_public_block is False  # Removing an OLD marker preserves an explicit clear.
        bill.summary_long_el = "AMKA again"
        await db.commit()
        assert bill.sensitive_public_block is True
        audits = (await db.scalars(select(AuditLog).order_by(AuditLog.created_at))).all()
        assert len(audits) == invalidate.await_count == 4
        assert all(a.actor == "admin_api_key" and a.target_id == "S" for a in audits)
        assert audits[0].details["before"]["sensitive_override"] is None
        assert audits[0].details["after"]["sensitive_override"] is False
        assert audits[-1].details["after"]["sensitive_public_block"] is False


async def test_failed_audit_rolls_back_decision_and_clear(old_schema, monkeypatch) -> None:
    connection, revision = old_schema
    await seed(connection, [bill_row("S", summary_long_el="AMKA")])
    await migrate(connection, revision, "upgrade")
    invalidation = AsyncMock()
    monkeypatch.setattr("services.representation_cache.invalidate_representation_cache", invalidation)

    await connection.exec_driver_sql("""ALTER TABLE audit_log ADD CONSTRAINT synthetic_audit_failure
        CHECK (action <> 'bill.sensitivity_override')""")

    async with session(connection) as db:
        with pytest.raises(IntegrityError, match="synthetic_audit_failure"):
            await admin.admin_set_bill_sensitivity("S", admin.BillSensitivityRequest(
                sensitive_override=False, reason="Synthetic review", clear_sensitive_public_block=True,
            ), _key=True, db=db)
        await db.rollback()
        bill = await db.get(ParliamentBill, "S")
        assert bill.sensitive_public_block is True and bill.sensitive_override is None
        assert bill.sensitive_override_reason is None
        assert await db.scalar(select(func.count()).select_from(AuditLog)) == 0
        invalidation.assert_not_awaited()


async def test_owner_clear_with_text_change_still_latches_markers(old_schema) -> None:
    connection, revision = old_schema
    await seed(connection, [bill_row("S", summary_long_el="AMKA")])
    await migrate(connection, revision, "upgrade")
    async with session(connection) as db:
        await db.execute(text("""UPDATE parliament_bills SET summary_long_el = 'AMKA again',
            sensitive_public_block = false WHERE id = 'S'"""))
        await db.commit()
        assert (await db.get(ParliamentBill, "S")).sensitive_public_block is True

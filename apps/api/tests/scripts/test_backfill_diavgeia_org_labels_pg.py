"""Execute the repair SQL and #715 trigger event list in a disposable PG schema."""
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest

from scripts import backfill_diavgeia_org_labels as script
from tests.pg_public_bill_schema import public_metadata_revision, sensitivity_revision
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
async def postgres():
    conn = await asyncpg.connect(disposable_postgres_url().replace("postgresql+asyncpg://", "postgresql://"))
    schema = "org_labels_" + uuid4().hex
    try:
        await conn.execute(f"CREATE SCHEMA {schema}")
        await conn.execute(f"SET search_path TO {schema}")
        await conn.execute("""CREATE TABLE parliament_bills (
            id text PRIMARY KEY, source text, pill_el text, org_label text,
            title_el text, summary_short_el text, summary_long_el text,
            generated_content_provenance jsonb, updated_at timestamp DEFAULT now(),
            sensitive_public_block boolean NOT NULL DEFAULT false,
            sensitive_override boolean, sensitive_override_reason text)""")
        await conn.execute(public_metadata_revision().FUNCTION_DDL)
        revision = sensitivity_revision()
        await conn.execute(revision.TRIGGER_FUNCTION_DDL)
        await conn.execute(revision.TRIGGER_DDL)
        yield conn
    finally:
        await conn.execute(f"DROP SCHEMA {schema} CASCADE")
        await conn.close()


async def test_real_sql_preserves_all_other_columns_and_never_fires_sensitivity_trigger(postgres, tmp_path, monkeypatch):
    conn = postgres
    resolve = AsyncMock(return_value="SYNTHETIC AGENCY AE")
    invalidate = AsyncMock()
    monkeypatch.setattr(script, "resolve_org_label", resolve)
    monkeypatch.setattr(script, "invalidate_representation_cache", invalidate)
    values = [
        ("null", "DIAVGEIA", "Διαύγεια: [unknown:42]", None),
        ("unknown", "DIAVGEIA", "Διαύγεια: [unknown:42]", "[unknown:42]"),
        ("plain", "DIAVGEIA", "Διαύγεια: [unknown:42]", "unknown"),
        ("keep", "DIAVGEIA", "Διαύγεια: [unknown:42]", "Retained label"),
        ("other", "PARLIAMENT", "Διαύγεια: [unknown:42]", None),
        ("prefix", "DIAVGEIA", "prefix Διαύγεια: [unknown:42]", None),
        ("suffix", "DIAVGEIA", "Διαύγεια: [unknown:42] suffix", None),
        ("newline", "DIAVGEIA", "Διαύγεια: [unknown:42]\n", None),
        ("good", "DIAVGEIA", "Διαύγεια: Known label", None),
    ]
    await conn.executemany("""INSERT INTO parliament_bills
        (id, source, pill_el, org_label, title_el, summary_short_el, summary_long_el,
         sensitive_public_block, sensitive_override, sensitive_override_reason, generated_content_provenance)
        VALUES ($1, $2, $3, $4, 'Synthetic title', 'Synthetic AMKA', 'Retained prose',
                true, false, 'Retained review', '{"summary_short_el":"synthetic"}')""", values)
    before = {r["id"]: dict(r) for r in await conn.fetch("SELECT * FROM parliament_bills")}
    plan, backup = tmp_path / "plan.csv", tmp_path / "backup.csv"
    await script.backfill(conn, plan_path=plan)
    assert resolve.await_count == 1
    resolve.side_effect = AssertionError("No HTTP while applying")
    # Keep the actual migration's trigger/event list but replace its function
    # with a trap. Any invocation (even one returning unchanged flags) fails.
    await conn.execute("""CREATE OR REPLACE FUNCTION maintain_bill_sensitivity()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'Sensitivity trigger fired on label-only update'; END $$""")
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=4, backup_path=backup) == 4
    after = {r["id"]: dict(r) for r in await conn.fetch("SELECT * FROM parliament_bills")}
    for bill_id, original in before.items():
        expected = original.copy()
        if bill_id in {"null", "unknown", "plain", "keep"}:
            expected["pill_el"] = "Διαύγεια: SYNTHETIC AGENCY AE"
            expected["org_label"] = "Retained label" if bill_id == "keep" else "SYNTHETIC AGENCY AE"
        assert after[bill_id] == expected
    invalidate.assert_awaited_once()
    # Exercise the SQL's concurrent old-value guards directly on real NULLs.
    assert await conn.execute(script.UPDATE_SQL, "null", "stale pill", "New", None, "New") == "UPDATE 0"
    assert await conn.execute(script.UPDATE_SQL, "null", after["null"]["pill_el"], "New", None, "New") == "UPDATE 0"

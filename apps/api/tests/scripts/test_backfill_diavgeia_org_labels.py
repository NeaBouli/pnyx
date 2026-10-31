"""Guard rails for a metadata-only repair; all rows/labels are synthetic."""
import copy
import csv
import json
import re
import stat
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts import backfill_diavgeia_org_labels as script
from tests.pg_public_bill_schema import sensitivity_revision


def test_label_columns_remain_outside_sensitivity_trigger_event_list():
    ddl = sensitivity_revision().TRIGGER_DDL
    match = re.search(r"UPDATE OF (.*?) ON parliament_bills", ddl, re.DOTALL)
    assert match
    trigger_columns = {name.strip() for name in match.group(1).split(",")}
    assignments = script.UPDATE_SQL.split("WHERE", 1)[0]
    assigned_columns = set(re.findall(r"(?:SET|,)\s*([a-z_]+)\s*=", assignments, re.IGNORECASE))
    assert assigned_columns == {"pill_el", "org_label"}
    assert assigned_columns.isdisjoint(trigger_columns)


def row(bill_id="DIAV-1", uid="42", **changes):
    return dict(id=bill_id, source="DIAVGEIA", pill_el=f"Διαύγεια: [unknown:{uid}]", org_label=None,
                title_el="Synthetic official title", summary_short_el="Synthetic AMKA",
                summary_long_el="Synthetic retained summary", sensitive_public_block=True,
                sensitive_override=False, sensitive_override_reason="Synthetic review", **changes)


class Connection:
    def __init__(self, rows, backup=None):
        self.rows = copy.deepcopy(rows)
        self.backup = backup
        self.writes = []
        self.transactions = []
        self.race = None
        self.fail_id = None

    @asynccontextmanager
    async def transaction(self, *, readonly=False):
        self.transactions.append(readonly)
        if not readonly and self.race:
            self.race(self.rows)
            self.race = None
        before = copy.deepcopy(self.rows)
        try:
            yield
        except Exception:
            self.rows = before
            raise

    async def cursor(self, query, pattern, *, prefetch):
        assert query == script.SELECT_SQL and "source = 'DIAVGEIA'" in query
        assert pattern == script.UNKNOWN_PILL_SQL_PATTERN and prefetch == script.BATCH_SIZE
        for item in self.rows:
            if item["source"] == "DIAVGEIA" and script.UNKNOWN_PILL_RE.fullmatch(item["pill_el"] or ""):
                yield item.copy()

    async def execute(self, query, *values):
        assert query == script.UPDATE_SQL
        # Backup is private and complete before the very first database write.
        assert self.backup and stat.S_IMODE(self.backup.stat().st_mode) == 0o600
        with self.backup.open(newline="", encoding="utf-8") as stream:
            assert any(entry["id"] == values[0] for entry in csv.DictReader(stream))
        self.writes.append((query, values))
        bill_id, old, new, old_label, label = values
        if bill_id == self.fail_id:
            raise RuntimeError("Synthetic batch failure")
        for item in self.rows:
            if (item["id"], item["source"], item["pill_el"], item["org_label"]) == (bill_id, "DIAVGEIA", old, old_label):
                item["pill_el"] = new
                if script.clean_org_label(old_label) is None:
                    item["org_label"] = label
                return "UPDATE 1"
        return "UPDATE 0"


@pytest.fixture
def resolver(monkeypatch):
    resolver = AsyncMock(side_effect=lambda uid: {"42": "SYNTHETIC AGENCY AE"}.get(uid))
    monkeypatch.setattr(script, "resolve_org_label", resolver)
    return resolver


@pytest.fixture
def invalidate(monkeypatch):
    invalidate = AsyncMock()
    monkeypatch.setattr(script, "invalidate_representation_cache", invalidate)
    return invalidate


async def make_plan(tmp_path, rows):
    plan = tmp_path / "plan.csv"
    await script.backfill(Connection(rows), plan_path=plan)
    return plan


async def test_dry_run_counts_samples_and_unique_uid_lookups(tmp_path, resolver, invalidate, capsys):
    rows = [row(), row("DIAV-2"), row("DIAV-3", "99")]
    conn = Connection(rows)
    assert await script.backfill(conn, sample_limit=2) == 0
    assert conn.rows == rows and not conn.writes and conn.transactions == [True]
    assert resolver.await_count == 2
    output = capsys.readouterr().out
    assert "DRY-RUN: unknown pills=3; planned=3; resolved=2; neutral=1" in output
    assert "Sample ids: DIAV-1,DIAV-2" in output
    assert "Synthetic retained summary" not in output
    assert list(tmp_path.iterdir()) == []
    invalidate.assert_not_awaited()


async def test_plan_is_private_exact_and_exclusive(tmp_path, resolver, invalidate):
    plan = await make_plan(tmp_path, [row(), row("DIAV-2", "99")])
    assert stat.S_IMODE(plan.stat().st_mode) == 0o600
    with plan.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == script.PLAN_HEADER
        entries = list(reader)
    assert entries == [dict(id="DIAV-1", old_pill_sha256=script.pill_sha256(row()["pill_el"]),
                            uid="42", new_pill="Διαύγεια: SYNTHETIC AGENCY AE"),
                       dict(id="DIAV-2", old_pill_sha256=script.pill_sha256(row(uid="99")["pill_el"]),
                            uid="99", new_pill="Διαύγεια")]
    assert "Synthetic retained summary" not in plan.read_text()
    with pytest.raises(FileExistsError):
        await script.backfill(Connection([row()]), plan_path=plan)
    invalidate.assert_not_awaited()


@pytest.mark.parametrize("kwargs", [{}, {"max_rows": 1}, {"expect_from": Path("missing.csv")},
                                   {"expect_from": Path("missing.csv"), "max_rows": 1}])
async def test_apply_rails_fail_before_io(tmp_path, kwargs):
    with pytest.raises(ValueError, match="--apply requires"):
        await script.backfill(None, apply=True, **kwargs)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("limit", [-1, True, False, "1", 1.0, float("nan"), float("inf")])
async def test_invalid_limits_fail_before_io(limit):
    with pytest.raises(ValueError, match="nonnegative integer"):
        await script.backfill(None, max_rows=limit)


@pytest.mark.parametrize("changes", [{}, {"org_label": "[unknown:42]"}, {"org_label": "unknown"},
                                     {"org_label": "Retained official name"}])
async def test_apply_only_two_columns_and_uses_reviewed_label_without_http(
    tmp_path, resolver, invalidate, changes,
):
    original = row()
    original.update(changes)
    plan = await make_plan(tmp_path, [original])
    resolver.reset_mock(side_effect=True)
    resolver.side_effect = AssertionError("Apply must not resolve labels again")
    conn = Connection([original], tmp_path / "backup.csv")
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup) == 1
    expected = {**original, "pill_el": "Διαύγεια: SYNTHETIC AGENCY AE"}
    expected["org_label"] = changes.get("org_label") if changes.get("org_label") == "Retained official name" else "SYNTHETIC AGENCY AE"
    assert conn.rows == [expected]
    with conn.backup.open(newline="", encoding="utf-8") as stream:
        backup = list(csv.DictReader(stream))
    assert json.loads(backup[0]["old_org_label_json"]) == original["org_label"]
    assert backup[0]["old_pill"] == original["pill_el"]
    assert conn.transactions == [True, False]
    invalidate.assert_awaited_once()
    resolver.assert_not_awaited()


async def test_neutral_fallback_backed_up_and_unknown_label_cleared(tmp_path, resolver, invalidate):
    original = row(uid="99")
    original["org_label"] = "[unknown:99]"
    plan = await make_plan(tmp_path, [original])
    conn = Connection([original], tmp_path / "backup.csv")
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup) == 1
    assert conn.rows == [{**original, "pill_el": "Διαύγεια", "org_label": None}]


async def test_clean_stored_label_is_a_fallback_if_live_resolution_fails(tmp_path, resolver, invalidate):
    original = row(uid="99")
    original["org_label"] = "Stored official label"
    plan = await make_plan(tmp_path, [original])
    conn = Connection([original], tmp_path / "backup.csv")
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup) == 1
    assert conn.rows == [{**original, "pill_el": "Διαύγεια: Stored official label"}]


async def test_row_bound_aborts_before_backup_and_writes(tmp_path, resolver, invalidate):
    rows = [row(), row("DIAV-2")]
    plan = await make_plan(tmp_path, rows)
    conn = Connection(rows, tmp_path / "backup.csv")
    with pytest.raises(ValueError, match="exceed --max-rows"):
        await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup)
    assert not conn.writes and not conn.backup.exists() and conn.rows == rows
    invalidate.assert_not_awaited()


async def test_existing_backup_never_overwritten(tmp_path, resolver, invalidate):
    plan = await make_plan(tmp_path, [row()])
    conn = Connection([row()], tmp_path / "backup.csv")
    conn.backup.write_text("keep existing backup")
    with pytest.raises(FileExistsError):
        await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup)
    assert not conn.writes and conn.backup.read_text() == "keep existing backup"
    invalidate.assert_not_awaited()


async def test_exact_source_pill_and_plan_scope_and_rerun(tmp_path, resolver, invalidate):
    originals = [row(), row("DIAV-2"), row("DIAV-3")]
    plan = await make_plan(tmp_path, originals)
    rows = [*originals, row("new"), row("other")]
    rows[1]["pill_el"] = "Διαύγεια: [unknown:99]"  # changed UID since plan
    rows[2]["source"] = "PARLIAMENT"
    rows[4]["pill_el"] = "prefix Διαύγεια: [unknown:42]"
    conn = Connection(rows, tmp_path / "backup.csv")
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=10, backup_path=conn.backup) == 1
    assert conn.rows[1:] == rows[1:]
    second_backup = tmp_path / "unused.csv"
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=10, backup_path=second_backup) == 0
    assert not second_backup.exists()


@pytest.mark.parametrize("field,value", [("pill_el", "Concurrent pill"), ("org_label", "Concurrent agency")])
async def test_rechecks_old_columns_at_update(tmp_path, resolver, invalidate, field, value):
    plan = await make_plan(tmp_path, [row()])
    conn = Connection([row()], tmp_path / "backup.csv")
    conn.race = lambda rows: rows[0].update({field: value})
    assert await script.backfill(conn, apply=True, expect_from=plan, max_rows=1, backup_path=conn.backup) == 0
    assert conn.rows == [{**row(), field: value}]
    invalidate.assert_not_awaited()


async def test_bounded_transactions_rollback_and_invalidate_committed_batches(tmp_path, resolver, invalidate, monkeypatch):
    monkeypatch.setattr(script, "BATCH_SIZE", 2)
    originals = [row(f"DIAV-{i}") for i in range(5)]
    plan = await make_plan(tmp_path, originals)
    conn = Connection(originals, tmp_path / "backup.csv")
    conn.fail_id = "DIAV-3"
    with pytest.raises(RuntimeError, match="batch failure"):
        await script.backfill(conn, apply=True, expect_from=plan, max_rows=5, backup_path=conn.backup)
    assert all(item["pill_el"] == "Διαύγεια: SYNTHETIC AGENCY AE" for item in conn.rows[:2])
    assert conn.rows[2:] == originals[2:]
    invalidate.assert_awaited_once()
    assert conn.transactions == [True, False, False]


@pytest.mark.parametrize("args", [["--apply"], ["--apply", "--expect-from", "p.csv", "--max-rows", "1"],
                                 ["--max-rows", "-1"], ["--max-rows", "nan"], ["--samples", "-1"]])
def test_cli_rejects_missing_rails_and_bad_limits(args):
    with pytest.raises(SystemExit) as exc:
        script.parse_args(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("change", [{"uid": "../42"}, {"old_pill_sha256": "wrong"},
                                    {"new_pill": "Διαύγεια: [unknown:42]"}, {"new_pill": "Other pill"}])
async def test_malformed_plan_fails_before_database_io(tmp_path, resolver, change):
    plan = await make_plan(tmp_path, [row()])
    with plan.open(newline="", encoding="utf-8") as stream:
        entries = list(csv.DictReader(stream))
    entries[0].update(change)
    with plan.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=script.PLAN_HEADER)
        writer.writeheader()
        writer.writerows(entries)
    with pytest.raises(ValueError):
        await script.backfill(None, apply=True, expect_from=plan, max_rows=1, backup_path=tmp_path / "backup.csv")

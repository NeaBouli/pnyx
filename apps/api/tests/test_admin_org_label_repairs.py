"""Both manual repairs share the import resolver and repair pill metadata."""
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routers import admin
from services import diavgeia_org_lookup as lookup


@pytest.mark.parametrize("label", ["SYNTHETIC AGENCY AE", None])
async def test_old_repair_updates_exact_pills_and_missing_org_label(monkeypatch, label):
    rows = [("DIAV-1", "Διαύγεια: [unknown:42]", None, None), ("DIAV-2", "Διαύγεια: [unknown:42]", None, None),
            ("skip", "prefix Διαύγεια: [unknown:42]", None, None)]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: rows), SimpleNamespace(rowcount=1), SimpleNamespace(rowcount=1),
    ]))
    resolve = AsyncMock(return_value=label)
    monkeypatch.setattr(lookup, "resolve_org_label", resolve)
    commit = AsyncMock()
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", commit)
    stats = await inspect.unwrap(admin.admin_resolve_orgs)(_key=True, db=db, request=None)
    resolve.assert_awaited_once_with("42")
    assert stats["resolved"] == (2 if label else 0)
    assert stats["failed"] == (0 if label else 2)
    for call in db.execute.await_args_list[1:]:
        sql, params = call.args
        assert "source = 'DIAVGEIA' AND pill_el = :old_pill" in str(sql)
        assert "org_label = :label" in str(sql)
        assert params["pill"] == lookup.org_pill(label) and params["label"] == label
        assert not any(name in str(sql) for name in ("summary_", "title_", "sensitive_", "updated_at"))
    commit.assert_awaited_once_with(db)


async def test_maintenance_repairs_pills_after_decisions_and_org_labels(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: [("42", "[unknown:42]")]),
        SimpleNamespace(rowcount=2),  # decisions
        SimpleNamespace(fetchall=lambda: [("DIAV-1", None, "SYNTHETIC AGENCY AE")]),
        SimpleNamespace(rowcount=1),  # bill org_label
        SimpleNamespace(fetchall=lambda: [("DIAV-1", "Διαύγεια: [unknown:42]", None, None)]),
        SimpleNamespace(rowcount=1),  # bill pill + label
    ]))
    resolve = AsyncMock(return_value="SYNTHETIC AGENCY AE")
    monkeypatch.setattr(lookup, "resolve_org_label", resolve)
    commit = AsyncMock()
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", commit)
    stats = await inspect.unwrap(admin.admin_resolve_org_labels)(_key=True, db=db, request=None)
    assert stats["step1_resolve"]["resolved"] == 2
    assert stats["step2_backfill"]["bills_updated"] == 1
    assert stats["step3_pills"]["resolved"] == 1
    assert db.execute.await_args.args[1]["pill"] == "Διαύγεια: SYNTHETIC AGENCY AE"
    commit.assert_awaited_once_with(db)


@pytest.mark.parametrize("label", ["Synthetic agency", None])
async def test_repair_counts_only_updated_rows_and_reports_concurrent_skips(monkeypatch, label):
    rows = [(f"DIAV-{i}", "Διαύγεια: [unknown:42]", None, None) for i in range(3)]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: rows), *(SimpleNamespace(rowcount=n) for n in (0, 1, 0)),
    ]))
    monkeypatch.setattr(lookup, "resolve_org_label", AsyncMock(return_value=label))
    stats = await admin._repair_diavgeia_org_pills(db)
    assert stats == {"success": True, "resolved": int(label is not None), "failed": int(label is None),
                     "concurrent_skipped": 2, "total": 3}


@pytest.mark.parametrize("raw", [" Α\u0301\x00\u202e\tAgency  ", "Α" * 191, "<img src=x>", "\u200b[unknown:42]"])
async def test_maintenance_normalizes_decision_labels_before_copying(monkeypatch, raw):
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: []),
        SimpleNamespace(fetchall=lambda: [("DIAV-1", None, raw)]),
        *([SimpleNamespace(rowcount=1)] if lookup.clean_org_label(raw) else []),
        SimpleNamespace(fetchall=lambda: []),
    ]))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    stats = await inspect.unwrap(admin.admin_resolve_org_labels)(_key=True, db=db, request=None)
    label = lookup.clean_org_label(raw)
    assert stats["step2_backfill"]["bills_updated"] == int(label is not None)
    if label:
        sql, params = db.execute.await_args_list[2].args
        assert params["label"] == label and params["decision_label"] == raw
        assert "dd.organization_label IS NOT DISTINCT FROM :decision_label" in str(sql)


async def test_maintenance_reports_guarded_update_skips(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: [("42", "[unknown:42]")]), SimpleNamespace(rowcount=0),
        SimpleNamespace(fetchall=lambda: [("DIAV-1", None, "Stored agency")]), SimpleNamespace(rowcount=0),
        SimpleNamespace(fetchall=lambda: []),
    ]))
    monkeypatch.setattr(lookup, "resolve_org_label", AsyncMock(return_value="Live agency"))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    stats = await inspect.unwrap(admin.admin_resolve_org_labels)(_key=True, db=db, request=None)
    assert stats["step1_resolve"]["resolved"] == stats["step2_backfill"]["bills_updated"] == 0
    assert stats["step1_resolve"]["concurrent_skipped"] == stats["step2_backfill"]["concurrent_skipped"] == 1


@pytest.mark.parametrize("rowcount", [0, 1])
async def test_neutral_import_fallback_can_be_repaired_using_stored_uid(monkeypatch, rowcount):
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: [("DIAV-1", "Διαύγεια", None, "42")]),
        SimpleNamespace(rowcount=rowcount),
    ]))
    monkeypatch.setattr(lookup, "resolve_org_label", AsyncMock(return_value="Recovered agency"))
    stats = await admin._repair_diavgeia_org_pills(db)
    assert stats["resolved"] == rowcount and stats["concurrent_skipped"] == 1 - rowcount
    sql, params = db.execute.await_args.args
    assert params["old_pill"] == "Διαύγεια" and params["pill"] == "Διαύγεια: Recovered agency"
    assert params["uid"] == "42" and "d.organization_uid = :uid" in str(sql)

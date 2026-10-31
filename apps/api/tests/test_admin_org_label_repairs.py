"""Both manual repairs share the import resolver and repair pill metadata."""
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routers import admin
from services import diavgeia_org_lookup as lookup


@pytest.mark.parametrize("label", ["SYNTHETIC AGENCY AE", None])
async def test_old_repair_updates_exact_pills_and_missing_org_label(monkeypatch, label):
    rows = [("DIAV-1", "Διαύγεια: [unknown:42]", None), ("DIAV-2", "Διαύγεια: [unknown:42]", None),
            ("skip", "prefix Διαύγεια: [unknown:42]", None)]
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: rows)))
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
        assert "org_label = CASE WHEN" in str(sql)
        assert params["pill"] == lookup.org_pill(label) and params["label"] == label
        assert not any(name in str(sql) for name in ("summary_", "title_", "sensitive_", "updated_at"))
    commit.assert_awaited_once_with(db)


async def test_maintenance_repairs_pills_after_decisions_and_org_labels(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(fetchall=lambda: [("42", "[unknown:42]")]),
        SimpleNamespace(rowcount=2),  # decisions
        SimpleNamespace(rowcount=2),  # bill org_label
        SimpleNamespace(fetchall=lambda: [("DIAV-1", "Διαύγεια: [unknown:42]", None)]),
        SimpleNamespace(rowcount=1),  # bill pill + label
    ]))
    resolve = AsyncMock(return_value="SYNTHETIC AGENCY AE")
    monkeypatch.setattr(lookup, "resolve_org_label", resolve)
    commit = AsyncMock()
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", commit)
    stats = await inspect.unwrap(admin.admin_resolve_org_labels)(_key=True, db=db, request=None)
    assert stats["step1_resolve"]["resolved"] == 1
    assert stats["step2_backfill"]["bills_updated"] == 2
    assert stats["step3_pills"]["resolved"] == 1
    assert db.execute.await_args.args[1]["pill"] == "Διαύγεια: SYNTHETIC AGENCY AE"
    commit.assert_awaited_once_with(db)

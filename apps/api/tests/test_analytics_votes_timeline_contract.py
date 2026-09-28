"""EKA-20 HIGH-01: votes-timeline must not mask failures as empty success."""
import json
import logging
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from routers import analytics

LEGACY_KEYS = {"period_days", "bill_id", "timeline", "note"}
SECRET = "SECRET-ROW-DETAIL-4711"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Db:
    def __init__(self, *, rows=None, bill=None, execute_error=None):
        self._rows = rows or []
        self._bill = bill
        self._execute_error = execute_error
        self.executed = 0

    async def get(self, _model, _bill_id):
        return self._bill

    async def execute(self, _statement):
        self.executed += 1
        if self._execute_error is not None:
            raise self._execute_error
        return _Result(self._rows)


class _BrokenDay:
    def __bool__(self):
        return True

    def strftime(self, _fmt):
        raise ValueError(SECRET)


@pytest.mark.asyncio
async def test_success_keeps_legacy_keys_and_adds_status_ok():
    rows = [
        SimpleNamespace(day=datetime(2026, 7, 17), vote="NO", count=1),
        SimpleNamespace(day=datetime(2026, 7, 16), vote="YES", count=3),
        SimpleNamespace(day=datetime(2026, 7, 16), vote="ABSTAIN", count=1),
    ]
    result = await analytics.votes_timeline(bill_id=None, days=30, db=_Db(rows=rows))

    assert LEGACY_KEYS <= set(result)
    assert result["status"] == "ok"
    assert "error" not in result
    assert result["note"] == "Aggregiert nach Tag"
    assert result["period_days"] == 30
    assert result["bill_id"] is None
    assert result["timeline"] == [
        {"date": "2026-07-16", "yes": 3, "no": 0, "abstain": 1, "unknown": 0, "total": 4},
        {"date": "2026-07-17", "yes": 0, "no": 1, "abstain": 0, "unknown": 0, "total": 1},
    ]


@pytest.mark.asyncio
async def test_empty_result_is_ok_not_degraded():
    result = await analytics.votes_timeline(bill_id=None, days=7, db=_Db(rows=[]))

    assert result["status"] == "ok"
    assert result["timeline"] == []


@pytest.mark.asyncio
async def test_row_processing_error_is_degraded_without_leaking(caplog):
    rows = [SimpleNamespace(day=_BrokenDay(), vote="YES", count=1)]
    with caplog.at_level(logging.ERROR, logger=analytics.logger.name):
        result = await analytics.votes_timeline(bill_id=None, days=30, db=_Db(rows=rows))

    assert LEGACY_KEYS <= set(result)
    assert result["status"] == "degraded"
    assert result["error"] == "timeline_processing_failed"
    assert result["timeline"] == []
    assert result["note"] != "Keine Daten"
    assert SECRET not in json.dumps(result, ensure_ascii=False)

    records = [r for r in caplog.records if "votes-timeline" in r.getMessage()]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert SECRET not in records[0].getMessage()


@pytest.mark.asyncio
async def test_db_execute_error_propagates():
    db = _Db(execute_error=OperationalError("SELECT 1", {}, Exception("db down")))
    with pytest.raises(OperationalError):
        await analytics.votes_timeline(bill_id=None, days=30, db=db)
    assert db.executed == 1


@pytest.mark.asyncio
async def test_query_construction_error_propagates(monkeypatch):
    def broken_query(_bill_id, *, include_zk):
        raise AttributeError("model drift")

    monkeypatch.setattr(analytics, "bill_vote_events_query", broken_query)
    bill = SimpleNamespace(id="GR-1", source="PARLIAMENT", admin_hidden=False)
    db = _Db(bill=bill)
    with pytest.raises(AttributeError):
        await analytics.votes_timeline(bill_id="GR-1", days=30, db=db)
    assert db.executed == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bill",
    [None, SimpleNamespace(id="GR-HIDDEN", source="PARLIAMENT", admin_hidden=True)],
)
async def test_missing_or_non_public_bill_raises_404(bill):
    db = _Db(bill=bill)
    with pytest.raises(HTTPException) as exc:
        await analytics.votes_timeline(bill_id="GR-HIDDEN", days=30, db=db)
    assert exc.value.status_code == 404
    assert db.executed == 0

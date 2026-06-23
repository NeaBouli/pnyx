from datetime import datetime, timezone

import pytest

from services.diavgeia_scraper import _to_naive_utc, backfill_diavgeia_bill_dates


def test_diavgeia_publish_timestamp_converts_to_naive_utc_for_bill_date():
    value = datetime(2026, 6, 23, 7, 44, 10, tzinfo=timezone.utc)

    assert _to_naive_utc(value) == datetime(2026, 6, 23, 7, 44, 10)


def test_diavgeia_naive_timestamp_is_preserved():
    value = datetime(2026, 6, 23, 7, 44, 10)

    assert _to_naive_utc(value) == value


class FakeBackfillResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.committed = False

    async def execute(self, statement):
        self.sql = str(statement)
        return FakeBackfillResult(self.rows)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_backfill_diavgeia_bill_dates_is_narrow_and_commits_when_rows_changed():
    session = FakeSession(rows=[("DIAV-1",), ("DIAV-2",)])

    count = await backfill_diavgeia_bill_dates(session)

    assert count == 2
    assert session.committed is True
    assert "pb.source = 'DIAVGEIA'" in session.sql
    assert "pb.submitted_date IS NULL" in session.sql
    assert "dd.publish_timestamp IS NOT NULL" in session.sql


@pytest.mark.asyncio
async def test_backfill_diavgeia_bill_dates_does_not_commit_when_nothing_changed():
    session = FakeSession(rows=[])

    count = await backfill_diavgeia_bill_dates(session)

    assert count == 0
    assert session.committed is False

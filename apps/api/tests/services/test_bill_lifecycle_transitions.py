from datetime import datetime, timedelta, timezone
import os
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from models import BillStatus  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from services import bill_lifecycle, telegram_community  # noqa: E402
from services.bill_lifecycle import (  # noqa: E402
    _hook_telegram_community,
    _lifecycle_candidate_statement,
    due_lifecycle_transitions,
)
from services.zk_vote_aggregation import VoteTotals  # noqa: E402


def test_lifecycle_candidates_are_row_locked_to_prevent_duplicate_workers():
    sql = str(_lifecycle_candidate_statement().compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "parliament_vote_date IS NOT NULL" in sql
    assert "OPEN_END" not in sql


def test_overdue_announced_bill_opens_only_one_step_per_run():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(days=1)

    due = due_lifecycle_transitions(BillStatus.ANNOUNCED, vote_date, now)

    assert due == [BillStatus.ACTIVE]


def test_old_announced_bill_does_not_skip_public_vote_window():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(days=8)

    due = due_lifecycle_transitions(BillStatus.ANNOUNCED, vote_date, now)

    assert due == [BillStatus.ACTIVE]


def test_future_active_bill_does_not_enter_window_early():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now + timedelta(days=2)

    due = due_lifecycle_transitions(BillStatus.ACTIVE, vote_date, now)

    assert due == []


def test_active_bill_enters_window_when_vote_is_within_24h():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now + timedelta(hours=12)

    due = due_lifecycle_transitions(BillStatus.ACTIVE, vote_date, now)

    assert due == [BillStatus.WINDOW_24H]


def test_window_bill_does_not_close_before_24h_public_window_age():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(hours=1)
    status_changed_at = now - timedelta(hours=23, minutes=59)

    due = due_lifecycle_transitions(
        BillStatus.WINDOW_24H,
        vote_date,
        now,
        status_changed_at=status_changed_at,
    )

    assert due == []


def test_window_bill_closes_after_full_24h_public_window_age():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(hours=1)
    status_changed_at = now - timedelta(hours=24)

    due = due_lifecycle_transitions(
        BillStatus.WINDOW_24H,
        vote_date,
        now,
        status_changed_at=status_changed_at,
    )

    assert due == [BillStatus.PARLIAMENT_VOTED]


def test_old_parliament_voted_bill_moves_to_open_end_one_step():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(days=8)

    due = due_lifecycle_transitions(BillStatus.PARLIAMENT_VOTED, vote_date, now)

    assert due == [BillStatus.OPEN_END]


@pytest.mark.asyncio
async def test_parliament_telegram_count_includes_zk_votes(monkeypatch):
    bill = SimpleNamespace(
        id="GR-70a42ec9",
        title_el="Test bill",
        governance_level=None,
        source="PARLIAMENT",
    )
    sent = {}

    async def fake_aggregate(db, bill_id, *, include_zk):
        assert bill_id == bill.id
        assert include_zk is True
        return VoteTotals(
            yes=0,
            no=1,
            abstain=0,
            unknown=0,
            tier1_total=0,
            zk_total=1,
        )

    async def fake_notify(bill_id, title, citizen_votes=0):
        sent.update(
            bill_id=bill_id,
            title=title,
            citizen_votes=citizen_votes,
        )

    monkeypatch.setattr(bill_lifecycle, "aggregate_bill_vote_totals", fake_aggregate)
    monkeypatch.setattr(telegram_community, "notify_parliament_voted", fake_notify)

    await _hook_telegram_community(
        bill,
        BillStatus.PARLIAMENT_VOTED,
        db=object(),
    )

    assert sent == {
        "bill_id": bill.id,
        "title": bill.title_el,
        "citizen_votes": 1,
    }


@pytest.mark.asyncio
async def test_non_parliament_telegram_count_excludes_zk_votes(monkeypatch):
    bill = SimpleNamespace(
        id="DIAV-TEST",
        title_el="Municipal test bill",
        governance_level=None,
        source="DIAVGEIA",
    )
    sent = {}

    async def fake_aggregate(db, bill_id, *, include_zk):
        assert bill_id == bill.id
        assert include_zk is False
        return VoteTotals(
            yes=2,
            no=0,
            abstain=0,
            unknown=0,
            tier1_total=2,
            zk_total=0,
        )

    async def fake_notify(bill_id, title, citizen_votes=0):
        sent["citizen_votes"] = citizen_votes

    monkeypatch.setattr(bill_lifecycle, "aggregate_bill_vote_totals", fake_aggregate)
    monkeypatch.setattr(telegram_community, "notify_parliament_voted", fake_notify)

    await _hook_telegram_community(
        bill,
        BillStatus.PARLIAMENT_VOTED,
        db=object(),
    )

    assert sent == {"citizen_votes": 2}

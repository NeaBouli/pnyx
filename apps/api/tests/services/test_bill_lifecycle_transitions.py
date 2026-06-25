from datetime import datetime, timedelta, timezone
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from models import BillStatus  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from services.bill_lifecycle import (  # noqa: E402
    _lifecycle_candidate_statement,
    due_lifecycle_transitions,
)


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

from datetime import datetime, timedelta, timezone
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from models import BillStatus  # noqa: E402
from services.bill_lifecycle import due_lifecycle_transitions  # noqa: E402


def test_overdue_announced_bill_catches_up_to_parliament_voted_in_one_run():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(days=1)

    due = due_lifecycle_transitions(BillStatus.ANNOUNCED, vote_date, now)

    assert due == [
        BillStatus.ACTIVE,
        BillStatus.WINDOW_24H,
        BillStatus.PARLIAMENT_VOTED,
    ]


def test_old_parliament_bill_catches_up_to_open_end_in_one_run():
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    vote_date = now - timedelta(days=8)

    due = due_lifecycle_transitions(BillStatus.ANNOUNCED, vote_date, now)

    assert due == [
        BillStatus.ACTIVE,
        BillStatus.WINDOW_24H,
        BillStatus.PARLIAMENT_VOTED,
        BillStatus.OPEN_END,
    ]


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


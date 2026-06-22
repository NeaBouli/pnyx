from datetime import datetime, timedelta, timezone

from routers.admin import _catchup_decision


def test_catchup_force_runs_even_when_last_run_is_recent():
    now = datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc)
    last_run = (now - timedelta(minutes=2)).isoformat()

    should_trigger, reason = _catchup_decision(
        last_run,
        12 * 3600,
        force=True,
        now=now,
    )

    assert should_trigger is True
    assert reason == "forced"


def test_catchup_recent_run_is_skipped_without_force():
    now = datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc)
    last_run = (now - timedelta(minutes=2)).isoformat()

    should_trigger, reason = _catchup_decision(
        last_run,
        12 * 3600,
        now=now,
    )

    assert should_trigger is False
    assert reason == "recent"


def test_catchup_overdue_run_triggers_without_force():
    now = datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc)
    last_run = (now - timedelta(hours=13)).isoformat()

    should_trigger, reason = _catchup_decision(
        last_run,
        12 * 3600,
        now=now,
    )

    assert should_trigger is True
    assert reason == "overdue"

"""Scheduler misses use persisted APScheduler dates and existing alert cooldowns."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.test_monitor_alert_dedupe import FakeRedis, monitor

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


@pytest.fixture
def state(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(monitor, "datetime", Clock)
    monkeypatch.setattr(monitor, "SCHEDULER_MISS_GRACE_SECONDS", 900)
    return FakeRedis()


@pytest.mark.parametrize("late_seconds, alert", [(-3600, False), (0, False), (899, False), (900, False), (901, True)])
def test_miss_requires_next_run_plus_grace(state, late_seconds, alert):
    state.values["scheduler:diavgeia_municipal:next_run"] = (NOW - timedelta(seconds=late_seconds)).isoformat()
    found = monitor.check_scraper_jobs(state)
    assert bool(found) is alert
    if found:
        assert found[0].type == "scraper_job_errors" and found[0].recovery_allowed is False
        assert "Job diavgeia_municipal:" in found[0].message


@pytest.mark.parametrize("failures, alert", [(0, False), (1, False), (2, False), (3, True), (4, True)])
def test_failure_streak_threshold(state, failures, alert):
    state.values["scheduler:parliament:consecutive_failures"] = str(failures)
    state.values["scheduler:parliament:next_run"] = (NOW + timedelta(hours=12)).isoformat()
    assert bool(monitor.check_scraper_jobs(state)) is alert


@pytest.mark.parametrize("failures, alert", [(0, False), (1, False), (2, False), (3, True), (4, True)])
def test_coordination_failure_threshold_with_future_retry_and_deduplication(state, failures, alert):
    state.values.update({
        "scheduler:parliament:consecutive_coordination_failures": str(failures),
        "scheduler:parliament:consecutive_failures": "0",
        "scheduler:parliament:last_outcome": "success",
        "scheduler:parliament:next_run": (NOW + timedelta(minutes=10)).isoformat(),
    })
    found = monitor.check_scraper_jobs(state)
    assert bool(found) is alert
    if found:
        assert len(found) == 1
        assert "coordination failures" in found[0].message
        identity = monitor.alert_identity(found[0])
        assert monitor.prepare_alert_notifications(found, state)[identity] is True
        monitor.commit_alert_cooldown(found[0], state)
        monitor.record_active_alerts(found, state)
        state.values["scheduler:parliament:consecutive_failures"] = "3"
        state.values["scheduler:parliament:next_run"] = (NOW - timedelta(hours=1)).isoformat()
        again = monitor.check_scraper_jobs(state)
        assert len(again) == 1
        assert monitor.prepare_alert_notifications(again, state)[identity] is False


@pytest.mark.parametrize("invalid", [None, "NaN", "9" * 400, b"\xff"])
def test_invalid_coordination_count_does_not_hide_missed_schedule(state, invalid):
    state.values["scheduler:parliament:consecutive_coordination_failures"] = invalid
    state.values["scheduler:parliament:next_run"] = (NOW - timedelta(hours=1)).isoformat()
    assert len(monitor.check_scraper_jobs(state)) == 1


@pytest.mark.parametrize("outcome", ["success", "skipped", "interrupted", "lock_busy", "failed", "degraded"])
def test_single_outcome_and_old_success_age_never_alert(state, outcome):
    state.values.update({
        "scheduler:parliament:last_outcome": outcome,
        "scheduler:parliament:next_run": (NOW + timedelta(hours=12)).isoformat(),
        "scheduler:parliament:consecutive_failures": "1",
        "scraper:parliament:last_success": (NOW - timedelta(days=7)).isoformat(),
        "scraper:parliament:last_outcome": outcome,
        "scraper:parliament:error_count": "99",
    })
    assert monitor.check_scraper_jobs(state) == []
    assert monitor.check_scraper_stale(state) == []


def test_miss_and_failure_share_incident_and_existing_cooldown_dedupes(state):
    state.values["scheduler:parliament:next_run"] = (NOW - timedelta(hours=1)).isoformat()
    first = monitor.check_scraper_jobs(state)
    assert len(first) == 1
    identity = monitor.alert_identity(first[0])
    assert monitor.prepare_alert_notifications(first, state)[identity] is True
    monitor.commit_alert_cooldown(first[0], state)
    monitor.record_active_alerts(first, state)

    state.values["scheduler:parliament:consecutive_failures"] = "4"
    state.values["scheduler:diavgeia_municipal:consecutive_failures"] = "3"
    again = monitor.check_scraper_jobs(state)
    assert len(again) == 2
    due = monitor.prepare_alert_notifications(again, state)
    assert due[identity] is False
    assert sum(due.values()) == 1  # Another job is a separate incident.


@pytest.mark.parametrize("invalid", [None, "junk", "2026-10-17T12:00:00", "9" * 400, b"\xff"])
def test_unknown_next_run_is_not_a_miss_and_does_not_hide_failures(state, invalid):
    state.values["scheduler:parliament:next_run"] = invalid
    assert monitor.check_scraper_jobs(state) == []
    state.values["scheduler:parliament:consecutive_failures"] = "3"
    assert len(monitor.check_scraper_jobs(state)) == 1


def test_invalid_count_does_not_hide_missed_schedule(state):
    state.values["scheduler:parliament:consecutive_failures"] = "NaN"
    state.values["scheduler:parliament:next_run"] = (NOW - timedelta(hours=1)).isoformat()
    assert len(monitor.check_scraper_jobs(state)) == 1


def test_cron_jobs_are_monitored_too(state):
    state.values["scheduler:monthly_newsletter:next_run"] = (NOW - timedelta(hours=1)).isoformat()
    assert "Job monthly_newsletter:" in monitor.check_scraper_jobs(state)[0].message

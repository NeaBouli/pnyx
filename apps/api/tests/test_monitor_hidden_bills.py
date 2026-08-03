import os
import sys
import types
from datetime import datetime, timedelta

import pytest


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeCursor:
    def __init__(self, *, rows=None, one=None):
        self.rows = rows or []
        self.one = one
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, *args, **_kwargs):
        self.statements.append(statement)
        self.params.append(args[0] if args else None)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (self.one,)


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj


def test_forum_missing_query_selects_only_public_actionable_bills():
    cursor = FakeCursor(rows=[])
    alerts = monitor.check_forum_missing(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "category = 'public_actionable'" in sql
    assert "THEN 'technical_test'" in sql
    assert "THEN 'operator_hidden'" in sql
    assert "THEN 'sensitive_diavgeia'" in sql


def test_forum_completeness_catalogs_non_public_rows_without_alerting():
    cursor = FakeCursor(rows=[
        ("technical_test", 1),
        ("operator_hidden", 3),
        ("sensitive_diavgeia", 4),
    ])
    alerts = monitor.check_forum_completeness(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "GROUP BY category" in sql
    assert "forum_topic_id IS NULL" in sql


def test_forum_catalog_has_stable_mutually_exclusive_categories():
    cursor = FakeCursor(rows=[("public_actionable", 2), ("sync_grace", 5)])

    catalog = monitor.get_forum_missing_catalog(FakeConn(cursor))

    assert set(catalog) == set(monitor.FORUM_MISSING_CATEGORIES)
    assert catalog["public_actionable"] == 2
    assert catalog["sync_grace"] == 5
    assert catalog["technical_test"] == 0
    assert sum(catalog.values()) == 7


def test_forum_catalog_rejects_unknown_categories():
    cursor = FakeCursor(rows=[("uncatalogued", 1)])

    with pytest.raises(ValueError, match="uncatalogued"):
        monitor.get_forum_missing_catalog(FakeConn(cursor))


def test_forum_completeness_alert_separates_public_and_catalogued_counts():
    cursor = FakeCursor(rows=[
        ("public_actionable", 2),
        ("technical_test", 1),
        ("sensitive_diavgeia", 7),
    ])

    alerts = monitor.check_forum_completeness(FakeConn(cursor))

    assert len(alerts) == 1
    assert alerts[0].type == "forum_content_empty"
    assert "2 öffentliche fällige Bills" in alerts[0].message
    assert "8 katalogisiert, nicht alarmierend" in alerts[0].message
    assert "sensitive" not in alerts[0].message


def test_forum_completeness_gives_diavgeia_backlog_longer_grace():
    cursor = FakeCursor(rows=[])
    monitor.check_forum_completeness(FakeConn(cursor))

    sql = cursor.statements[0]
    assert "COALESCE(source, 'PARLIAMENT') = 'PARLIAMENT'" in sql
    assert "INTERVAL '1 hour'" in sql
    assert "COALESCE(source, 'PARLIAMENT') != 'PARLIAMENT'" in sql
    assert "INTERVAL '6 hours'" in sql


def test_lifecycle_stuck_query_gives_recent_scraper_updates_short_grace():
    cursor = FakeCursor(rows=[])
    alerts = monitor.check_lifecycle_stuck(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "parliament_vote_date < %s" in sql
    assert "COALESCE(updated_at, TIMESTAMP '1970-01-01') < %s" in sql
    assert len(cursor.params[0]) == 2


def test_lifecycle_fast_forward_alerts_on_skipped_public_window():
    voted_at = datetime(2026, 6, 18, 11, 38)
    window_at = voted_at - timedelta(minutes=0)
    active_at = voted_at - timedelta(minutes=1)
    cursor = FakeCursor(rows=[("GR-09e240aa", active_at, window_at, voted_at)])

    alerts = monitor.check_lifecycle_fast_forward(FakeConn(cursor))

    assert len(alerts) == 1
    assert alerts[0].type == "lifecycle_fast_forward"
    assert alerts[0].recovery_allowed is False
    assert "GR-09e240aa" in alerts[0].message
    sql = cursor.statements[0]
    assert "bill_status_logs" in sql
    assert "l.changed_at > NOW() - INTERVAL '24 hours'" in sql
    assert "voted_at - window_at < INTERVAL '24 hours'" in sql
    assert "COALESCE(b.source, 'PARLIAMENT') = 'PARLIAMENT'" in sql


def test_monitor_startup_grace_delays_first_daemon_check(monkeypatch):
    sleeps = []
    monkeypatch.setattr(monitor, "STARTUP_GRACE_SECONDS", 3)
    monkeypatch.setattr(monitor.time, "sleep", sleeps.append)

    monitor.apply_startup_grace()

    assert sleeps == [3]


def test_monitor_startup_grace_can_be_disabled(monkeypatch):
    sleeps = []
    monkeypatch.setattr(monitor, "STARTUP_GRACE_SECONDS", 0)
    monkeypatch.setattr(monitor.time, "sleep", sleeps.append)

    monitor.apply_startup_grace()

    assert sleeps == []

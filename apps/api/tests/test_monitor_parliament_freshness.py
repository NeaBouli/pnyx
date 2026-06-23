import os
import sys
import types
from datetime import datetime, timezone


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeCursor:
    def __init__(self, latest):
        self.latest = latest

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return (self.latest,)


class FakeConn:
    def __init__(self, latest):
        self.latest = latest

    def cursor(self):
        return FakeCursor(self.latest)


class FakeResponse:
    status_code = 200

    def __init__(self, bills):
        self._bills = bills

    def json(self):
        return {"bills": self._bills}


def test_parliament_source_freshness_alerts_when_source_is_newer_than_db(monkeypatch):
    monkeypatch.setattr(monitor, "PARLIAMENT_SOURCE_MAX_LAG_HOURS", 24)
    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse([
            {"submitted_date": "2026-06-10T00:00:00+00:00", "date": None},
        ]),
    )

    alerts = monitor.check_parliament_source_freshness(
        FakeConn(datetime(2026, 6, 8, tzinfo=timezone.utc))
    )

    assert len(alerts) == 1
    assert alerts[0].type == "parliament_source_lag"
    assert alerts[0].recovery_allowed is True
    assert monitor.T1_MAPPING["parliament_source_lag"].endswith("?force=parliament")
    assert "Quelle 10.06.2026" in alerts[0].message
    assert "DB 08.06.2026" in alerts[0].message


def test_parliament_source_freshness_passes_when_db_matches_source(monkeypatch):
    monkeypatch.setattr(monitor, "PARLIAMENT_SOURCE_MAX_LAG_HOURS", 24)
    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse([
            {"submitted_date": "2026-06-10T00:00:00+00:00", "date": None},
        ]),
    )

    alerts = monitor.check_parliament_source_freshness(
        FakeConn(datetime(2026, 6, 10, tzinfo=timezone.utc))
    )

    assert alerts == []


def test_parliament_source_freshness_reports_probe_without_dated_bills(monkeypatch):
    class EmptyProbeResponse(FakeResponse):
        def json(self):
            return {
                "count": 3,
                "dated_count": 0,
                "source_latest": None,
                "bills": [
                    {"title_el": "title only", "date": None, "submitted_date": None},
                ],
            }

    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: EmptyProbeResponse([]),
    )

    alerts = monitor.check_parliament_source_freshness(
        FakeConn(datetime(2026, 6, 10, tzinfo=timezone.utc))
    )

    assert len(alerts) == 1
    assert alerts[0].type == "parliament_source_check_failed"
    assert alerts[0].recovery_allowed is False
    assert "count=3" in alerts[0].message
    assert "dated_count=0" in alerts[0].message

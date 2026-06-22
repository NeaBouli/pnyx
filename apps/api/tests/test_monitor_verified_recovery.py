import os
import sys
import types
from datetime import datetime, timezone


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, bills=None):
        self.status_code = status_code
        self._bills = bills or []

    def json(self):
        return {"bills": self._bills}


class FakeRedis:
    def __init__(self, lock_ok=True):
        self.lock_ok = lock_ok
        self.deleted = []

    def set(self, *_args, **_kwargs):
        return self.lock_ok

    def delete(self, key):
        self.deleted.append(key)


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


def _source_bill(date_value):
    return {"date": date_value, "submitted_date": None}


def test_verified_recovery_returns_t1v_only_after_source_lag_is_proven_repaired(monkeypatch):
    sent = []
    monkeypatch.setattr(monitor, "ADMIN_KEY", "test-key")
    monkeypatch.setattr(monitor, "REPAIR_VERIFY_WAIT_SECONDS", 0)
    monkeypatch.setattr(monitor, "PARLIAMENT_SOURCE_MAX_LAG_HOURS", 24)
    monkeypatch.setattr(monitor, "send_telegram", sent.append)

    def fake_post(*_args, **_kwargs):
        return FakeResponse(status_code=200)

    def fake_get(*_args, **_kwargs):
        return FakeResponse(bills=[_source_bill("2026-06-10T00:00:00+00:00")])

    monkeypatch.setattr(monitor.httpx, "post", fake_post)
    monkeypatch.setattr(monitor.httpx, "get", fake_get)

    alert = monitor.Alert(
        "parliament_source_lag",
        "ekklesia-api",
        "warning",
        "Parliament-DB hinter Quelle",
        True,
    )

    tier = monitor.attempt_recovery(
        alert,
        FakeRedis(lock_ok=True),
        FakeConn(datetime(2026, 6, 10, tzinfo=timezone.utc)),
    )

    assert tier == "T1V"
    assert len(sent) == 1
    assert "Auto-Recovery verified" in sent[0]


def test_verified_recovery_keeps_alert_unresolved_when_proof_fails(monkeypatch):
    sent = []
    monkeypatch.setattr(monitor, "ADMIN_KEY", "test-key")
    monkeypatch.setattr(monitor, "REPAIR_VERIFY_WAIT_SECONDS", 0)
    monkeypatch.setattr(monitor, "PARLIAMENT_SOURCE_MAX_LAG_HOURS", 24)
    monkeypatch.setattr(monitor, "send_telegram", sent.append)
    monkeypatch.setattr(monitor.httpx, "post", lambda *_args, **_kwargs: FakeResponse(status_code=200))
    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse(bills=[_source_bill("2026-06-10T00:00:00+00:00")]),
    )

    alert = monitor.Alert(
        "parliament_source_lag",
        "ekklesia-api",
        "warning",
        "Parliament-DB hinter Quelle",
        True,
    )

    tier = monitor.attempt_recovery(
        alert,
        FakeRedis(lock_ok=True),
        FakeConn(datetime(2026, 6, 1, tzinfo=timezone.utc)),
    )

    assert tier == "T1"
    assert sent == []


def test_verified_recovery_lock_does_not_claim_success(monkeypatch):
    post_calls = []
    monkeypatch.setattr(monitor, "ADMIN_KEY", "test-key")
    monkeypatch.setattr(monitor.httpx, "post", lambda *_args, **_kwargs: post_calls.append(True))

    alert = monitor.Alert(
        "parliament_source_lag",
        "ekklesia-api",
        "warning",
        "Parliament-DB hinter Quelle",
        True,
    )

    tier = monitor.attempt_recovery(
        alert,
        FakeRedis(lock_ok=False),
        FakeConn(datetime(2026, 6, 10, tzinfo=timezone.utc)),
    )

    assert tier == "T1L"
    assert post_calls == []

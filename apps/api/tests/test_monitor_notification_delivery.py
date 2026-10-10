"""Offline regressions: cooldown and Entwarnung state follow confirmed delivery."""
import os
import sys
import types

import pytest

sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))
sys.path.insert(0, os.path.dirname(__file__))

import monitor  # noqa: E402
from test_monitor_alert_dedupe import FakeRedis  # noqa: E402


class ClosingRedis(FakeRedis):
    def close(self):
        pass


class FakeDb:
    def close(self):
        pass


CHECKS = [name for name in dir(monitor) if name.startswith("check_")]


def _alert(severity="critical", message="Disk 92% voll — 2.6 GB frei"):
    return monitor.Alert("disk_critical", "", severity, message, False)


class Harness:
    def __init__(self, monkeypatch):
        self.redis = ClosingRedis()
        self.alerts: list = []
        self.sent: list[str] = []
        self.results: list[bool] = []
        monkeypatch.setattr(monitor, "ALERT_NOTIFY_COOLDOWN_SECONDS", 3600)
        monkeypatch.setattr(monitor, "ALERT_RESOLVED_NOTIFICATIONS_ENABLED", True)
        monkeypatch.setattr(monitor, "get_redis", lambda: self.redis)
        monkeypatch.setattr(monitor, "get_db", lambda: FakeDb())
        for name in CHECKS:
            monkeypatch.setattr(monitor, name, lambda *a, **k: [])
        monkeypatch.setattr(monitor, "check_disk_usage", lambda *a, **k: list(self.alerts))
        monkeypatch.setattr(monitor, "send_telegram", self._send)

    def _send(self, msg):
        self.sent.append(msg)
        return self.results.pop(0) if self.results else True

    def run(self, *results):
        self.sent.clear()
        self.results = list(results)
        return monitor.run_checks()


def _cooldown(h, alert):
    return h.redis.values.get(f"{monitor._alert_state_key(monitor.alert_identity(alert))}:last_sent")


def test_failure_retry_success_then_suppression(monkeypatch):
    h = Harness(monkeypatch)
    alert = _alert()
    h.alerts = [alert]

    h.run(False, False)  # T3 + summary both fail
    assert len(h.sent) == 2
    assert _cooldown(h, alert) is None

    h.run(True, True)
    assert len(h.sent) == 2
    assert _cooldown(h, alert) == "critical"

    h.run()
    assert h.sent == []


@pytest.mark.parametrize("results", [(True, False), (False, True)])
def test_one_successful_message_commits_cooldown(monkeypatch, results):
    h = Harness(monkeypatch)
    alert = _alert()
    h.alerts = [alert]
    h.run(*results)
    assert _cooldown(h, alert) == "critical"
    h.run()
    assert h.sent == []


def test_severity_escalation_retries_despite_lower_cooldown(monkeypatch):
    h = Harness(monkeypatch)
    h.alerts = [_alert("warning")]
    h.run(True, True)

    h.alerts = [_alert("critical")]
    h.run(False, False)
    assert len(h.sent) == 2
    assert _cooldown(h, h.alerts[0]) == "warning"

    h.run(True, True)  # observed severity was persisted, ack was not
    assert len(h.sent) == 2
    assert _cooldown(h, h.alerts[0]) == "critical"
    h.run()
    assert h.sent == []


def test_pending_resolved_survives_failure_and_clears_once(monkeypatch):
    h = Harness(monkeypatch)
    alert = _alert()
    h.alerts = [alert]
    h.run(True, True)

    h.alerts = []
    h.run(False)
    assert len(h.sent) == 1 and "Entwarnung" in h.sent[0]
    identity = monitor.alert_identity(alert)
    assert identity in h.redis.smembers(monitor.ALERT_STATE_SET_KEY)
    assert monitor._load_alert_state(h.redis, identity)["type"] == "disk_critical"

    h.run(True)
    assert len(h.sent) == 1 and "disk_critical" in h.sent[0]
    assert identity not in h.redis.smembers(monitor.ALERT_STATE_SET_KEY)

    h.run()
    assert h.sent == []


def test_resolved_disabled_does_not_accumulate(monkeypatch):
    h = Harness(monkeypatch)
    h.alerts = [_alert()]
    h.run(True, True)
    monkeypatch.setattr(monitor, "ALERT_RESOLVED_NOTIFICATIONS_ENABLED", False)
    h.alerts = []
    h.run()
    assert h.sent == []
    assert h.redis.smembers(monitor.ALERT_STATE_SET_KEY) == set()


def test_truncated_summary_does_not_stamp_omitted_incidents(monkeypatch):
    h = Harness(monkeypatch)
    alerts = [
        monitor.Alert("lifecycle_stuck", "", "warning", f"Bill GR-{i:08d} " + "x" * 300, False)
        for i in range(20)
    ]
    h.alerts = alerts
    h.results = []
    # T3 for each alert fails, summary succeeds but is truncated.
    h.run(*([False] * len(alerts) + [True]))
    stamped = [a for a in alerts if _cooldown(h, a)]
    assert 0 < len(stamped) < len(alerts)
    assert stamped == alerts[: len(stamped)]


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.mark.parametrize(
    ("resp", "expected"),
    [
        (Resp(200, {"ok": True}), True),
        (Resp(200, {"ok": False}), False),
        (Resp(200, {}), False),
        (Resp(200, ValueError("bad json")), False),
        (Resp(500, {"ok": True}), False),
    ],
)
def test_send_telegram_requires_provider_ack(monkeypatch, resp, expected):
    monkeypatch.setattr(monitor, "TG_TOKEN", "fake-tok")
    monkeypatch.setattr(monitor, "TG_CHAT", "fake-chat")
    monkeypatch.setattr(monitor.httpx, "post", lambda *a, **k: resp)
    assert monitor.send_telegram("hi") is expected


def test_send_telegram_exception_and_missing_config(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(monitor.httpx, "post", boom)
    monkeypatch.setattr(monitor, "TG_TOKEN", "fake-tok")
    monkeypatch.setattr(monitor, "TG_CHAT", "fake-chat")
    assert monitor.send_telegram("hi") is False
    monkeypatch.setattr(monitor, "TG_TOKEN", "")
    assert monitor.send_telegram("hi") is False

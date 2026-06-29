import os
import sys
import types
from datetime import datetime, timezone


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}
        self.deleted = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, *keys):
        for key in keys:
            self.deleted.append(key)
            self.values.pop(key, None)
            self.sets.pop(key, None)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def srem(self, key, *values):
        current = self.sets.setdefault(key, set())
        for value in values:
            current.discard(value)


def _disk_alert(message):
    return monitor.Alert("disk_critical", "", "critical", message, False)


def test_disk_alert_identity_ignores_volatile_free_gb():
    first = _disk_alert("Disk 92% voll — 2.6 GB frei")
    second = _disk_alert("Disk 92% voll — 2.5 GB frei")

    assert monitor.alert_identity(first) == monitor.alert_identity(second)


def test_repeated_active_alert_is_suppressed_within_cooldown(monkeypatch):
    monkeypatch.setattr(monitor, "ALERT_NOTIFY_COOLDOWN_SECONDS", 3600)
    redis = FakeRedis()
    first = _disk_alert("Disk 92% voll — 2.6 GB frei")
    second = _disk_alert("Disk 92% voll — 2.5 GB frei")

    first_due = monitor.prepare_alert_notifications([first], redis)
    monitor.record_active_alerts([first], redis)
    second_due = monitor.prepare_alert_notifications([second], redis)

    assert first_due[monitor.alert_identity(first)] is True
    assert second_due[monitor.alert_identity(second)] is False


def test_different_lifecycle_bills_do_not_share_cooldown(monkeypatch):
    monkeypatch.setattr(monitor, "ALERT_NOTIFY_COOLDOWN_SECONDS", 3600)
    redis = FakeRedis()
    first = monitor.Alert(
        "lifecycle_stuck",
        "ekklesia-api",
        "warning",
        "Bill GR-11111111 stuck in WINDOW_24H (vote: 25.06.2026)",
        False,
    )
    second = monitor.Alert(
        "lifecycle_stuck",
        "ekklesia-api",
        "warning",
        "Bill GR-22222222 stuck in WINDOW_24H (vote: 25.06.2026)",
        False,
    )

    first_due = monitor.prepare_alert_notifications([first], redis)
    monitor.record_active_alerts([first], redis)
    second_due = monitor.prepare_alert_notifications([second], redis)

    assert monitor.alert_identity(first) != monitor.alert_identity(second)
    assert first_due[monitor.alert_identity(first)] is True
    assert second_due[monitor.alert_identity(second)] is True


def test_resolved_notification_is_sent_once(monkeypatch):
    redis = FakeRedis()
    sent = []
    now = datetime(2026, 6, 29, 20, 0, tzinfo=timezone.utc)
    alert = _disk_alert("Disk 92% voll — 2.6 GB frei")

    monitor.record_active_alerts([alert], redis, now=now)
    previous_keys = redis.smembers(monitor.ALERT_STATE_SET_KEY)
    monkeypatch.setattr(monitor, "send_telegram", sent.append)

    monitor.send_resolved_notifications([], redis, now=now, previous_keys=previous_keys)
    monitor.record_active_alerts([], redis, now=now)
    monitor.send_resolved_notifications([], redis, now=now, previous_keys=redis.smembers(monitor.ALERT_STATE_SET_KEY))

    assert len(sent) == 1
    assert "Monitor Entwarnung" in sent[0]
    assert "disk_critical" in sent[0]

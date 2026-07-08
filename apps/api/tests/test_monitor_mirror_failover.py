import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_api_down_alert_reports_readonly_mirror_online(monkeypatch):
    def fake_get(url, **_kwargs):
        if url == "http://api:8000/api/v1/bills?limit=1":
            raise OSError("connection refused")
        if url.endswith("/mirror-status.json"):
            return FakeResponse(200)
        if url.endswith("/api/v1/bills?limit=1"):
            return FakeResponse(200)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(monitor.httpx, "get", fake_get)

    alerts = monitor.check_api_health()

    assert len(alerts) == 1
    assert alerts[0].type == "api_unhealthy"
    assert "API nicht erreichbar" in alerts[0].message
    assert "Mirror serving read-only" in alerts[0].message
    assert alerts[0].recovery_allowed is True


def test_api_down_alert_reports_readonly_mirror_unavailable(monkeypatch):
    def fake_get(url, **_kwargs):
        if url == "http://api:8000/api/v1/bills?limit=1":
            raise OSError("connection refused")
        raise OSError("mirror refused")

    monkeypatch.setattr(monitor.httpx, "get", fake_get)

    alerts = monitor.check_api_health()

    assert len(alerts) == 1
    assert "Mirror read-only nicht erreichbar" in alerts[0].message

import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class _Response:
    def __init__(self, remaining: int):
        self.status_code = 200
        self._remaining = remaining

    def json(self):
        return {"primary": {"remaining": self._remaining}}


def test_hlr_credit_monitor_uses_protected_exact_schema(monkeypatch):
    monkeypatch.setattr(monitor, "ADMIN_KEY", "synthetic-admin-key")
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return _Response(99)

    monkeypatch.setattr(monitor.httpx, "get", fake_get)

    alerts = monitor.check_hlr_credits()

    assert captured["url"].endswith("/api/v1/admin/hlr/credits")
    assert captured["headers"] == {"Authorization": "Bearer synthetic-admin-key"}
    assert len(alerts) == 1
    assert alerts[0].type == "hlr_low"
    assert "99" in alerts[0].message


def test_hlr_credit_monitor_accepts_healthy_remaining_balance(monkeypatch):
    monkeypatch.setattr(monitor, "ADMIN_KEY", "synthetic-admin-key")
    monkeypatch.setattr(monitor.httpx, "get", lambda *_args, **_kwargs: _Response(100))

    assert monitor.check_hlr_credits() == []


def test_hlr_credit_monitor_skips_without_admin_key(monkeypatch):
    monkeypatch.setattr(monitor, "ADMIN_KEY", "")

    def unexpected_get(*_args, **_kwargs):
        raise AssertionError("HTTP request must not run without ADMIN_KEY")

    monkeypatch.setattr(monitor.httpx, "get", unexpected_get)

    assert monitor.check_hlr_credits() == []

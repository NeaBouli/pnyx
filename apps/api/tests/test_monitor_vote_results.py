import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_latest_vote_result_health_accepts_healthy_endpoint(monkeypatch):
    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: _Response(200),
    )

    assert monitor.check_vote_results_health() == []


def test_latest_vote_result_health_alerts_without_restart_loop(monkeypatch):
    monkeypatch.setattr(
        monitor.httpx,
        "get",
        lambda *_args, **_kwargs: _Response(500),
    )

    alerts = monitor.check_vote_results_health()

    assert len(alerts) == 1
    assert alerts[0].type == "vote_results_unhealthy"
    assert alerts[0].service == "ekklesia-api"
    assert alerts[0].severity == "warning"
    assert alerts[0].recovery_allowed is False
    assert "HTTP 500" in alerts[0].message


def test_latest_vote_result_health_alerts_on_connection_error(monkeypatch):
    def raise_connection_error(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(monitor.httpx, "get", raise_connection_error)

    alerts = monitor.check_vote_results_health()

    assert len(alerts) == 1
    assert alerts[0].type == "vote_results_unhealthy"
    assert "connection refused" in alerts[0].message

"""FastAPI's native OpenTelemetry must stay off (anonymity guard, T-607)."""
import fastapi.telemetry._asgi as telemetry_asgi

from main import app


def test_native_telemetry_is_explicitly_disabled() -> None:
    config = app._telemetry
    for key in ("tracing", "metrics", "logs", "operation_spans", "auto_configure"):
        assert config[key] is False, key


def test_native_telemetry_stays_disabled_with_a_configured_provider(monkeypatch) -> None:
    # Even if some component installs a global tracer/meter/logger provider,
    # FastAPI must not start instrumenting requests.
    monkeypatch.setattr(telemetry_asgi, "_unconfigured", lambda provider: False)
    assert app._native_telemetry.enabled() is False

"""T-572: capture_error() isolates per-event context and avoids the deprecated push_scope."""

import warnings

import sentry_sdk

import main
from tests.test_sentry_secret_scrubbing import _events, _init_sdk, sdk_reset  # noqa: F401


def test_capture_error_attaches_context_only_to_its_own_event(sdk_reset, monkeypatch):
    transport = _init_sdk()
    monkeypatch.setattr(main, "SENTRY_ENABLED", True)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        main.capture_error(ValueError("first"), {"bill_id": "B-1"})
        main.capture_error(ValueError("second"))
    sentry_sdk.flush()
    events = _events(transport)
    assert len(events) == 2
    first, second = events
    assert first.get("extra", {}).get("bill_id") == "B-1"
    assert "bill_id" not in second.get("extra", {})


def test_capture_error_without_sentry_logs_locally(monkeypatch, caplog):
    monkeypatch.setattr(main, "SENTRY_ENABLED", False)
    with caplog.at_level("ERROR"):
        main.capture_error(RuntimeError("offline"), {"k": "v"})
    assert any("[LOCAL] RuntimeError: offline" in r.getMessage() for r in caplog.records)

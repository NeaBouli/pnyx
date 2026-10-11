"""EVA-008: uvicorn access-log redaction of citizen identifiers and secrets.

Prod runs `uvicorn main:app --workers 2` with the default access log, which
embeds the full path + query string in every line. These tests emit real
uvicorn.access LogRecords (same format string and arg tuple as uvicorn 0.30)
and assert the filter installed by `import main` rewrites the request target:
query values of sensitive keys and the newsletter confirm path token become
`[redacted]`, while method, path shape and status survive. Fail-safe: malformed
records are logged unchanged and never dropped.
"""
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
from database import get_db
from models import BillStatus
from routers import voting

NULLIFIER = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
PUBLIC_KEY = "b" * 64
SIGNATURE = "c" * 128
NONCE = "nonceValue123"
SSO_PAYLOAD = "ssopayloadvalue"
SSO_SIG = "ssosigvalue"
OAUTH_CODE = "oauthcodevalue"
OAUTH_STATE = "oauthstatevalue"
CONFIRM_TOKEN = "confirm-token-value"

UVICORN_ACCESS_FORMAT = '%s - "%s %s HTTP/%s" %d'


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def access_log_capture() -> Any:
    """Attach a capturing handler to the real uvicorn.access logger."""
    access_logger = logging.getLogger("uvicorn.access")
    handler = _CaptureHandler()
    old_level = access_logger.level
    old_propagate = access_logger.propagate
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    try:
        yield handler
    finally:
        access_logger.removeHandler(handler)
        access_logger.setLevel(old_level)
        access_logger.propagate = old_propagate


def _emit(method: str, target: str, status: int = 200) -> None:
    """Emit an access record exactly like uvicorn's HTTP protocol does."""
    logging.getLogger("uvicorn.access").info(
        UVICORN_ACCESS_FORMAT,
        "203.0.113.10:5000",
        method,
        target,
        "1.1",
        status,
    )


def _only_message(handler: _CaptureHandler) -> str:
    assert len(handler.records) == 1
    return handler.records[0].getMessage()


def test_filter_is_installed_on_uvicorn_access_logger() -> None:
    filters = logging.getLogger("uvicorn.access").filters
    assert any(isinstance(f, main.AccessLogRedactionFilter) for f in filters)


def test_legacy_vote_status_nullifier_is_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/vote/GR-0490a766/status?nullifier_hash={NULLIFIER}")
    message = _only_message(access_log_capture)
    assert NULLIFIER not in message
    assert '"GET /api/v1/vote/GR-0490a766/status?nullifier_hash=[redacted] HTTP/1.1" 200' in message


def test_evaluation_read_nullifier_is_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/politicians/ADA-1/my-evaluation?nullifier_hash={NULLIFIER}")
    message = _only_message(access_log_capture)
    assert NULLIFIER not in message
    assert "nullifier_hash=[redacted]" in message


def test_sso_callback_secrets_are_redacted(access_log_capture: Any) -> None:
    _emit(
        "GET",
        "/api/v1/sso/callback"
        f"?public_key_hex={PUBLIC_KEY}&signature_hex={SIGNATURE}&nonce={NONCE}",
    )
    message = _only_message(access_log_capture)
    for secret in (PUBLIC_KEY, SIGNATURE, NONCE):
        assert secret not in message
    assert "public_key_hex=[redacted]" in message
    assert "signature_hex=[redacted]" in message
    assert "nonce=[redacted]" in message


def test_discourse_sso_params_are_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/sso/discourse?sso={SSO_PAYLOAD}&sig={SSO_SIG}")
    message = _only_message(access_log_capture)
    assert SSO_PAYLOAD not in message
    assert SSO_SIG not in message
    assert "sso=[redacted]&sig=[redacted]" in message


def test_govgr_oauth_code_and_state_are_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/auth/govgr/callback?code={OAUTH_CODE}&state={OAUTH_STATE}")
    message = _only_message(access_log_capture)
    assert OAUTH_CODE not in message
    assert OAUTH_STATE not in message
    assert "code=[redacted]&state=[redacted]" in message


def test_newsletter_confirm_token_in_path_is_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/newsletter/confirm/{CONFIRM_TOKEN}")
    message = _only_message(access_log_capture)
    assert CONFIRM_TOKEN not in message
    assert "/api/v1/newsletter/confirm/[redacted]" in message


def test_mixed_query_keeps_non_sensitive_parts_verbatim(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/vote/GR-1/status?page=2&nullifier_hash={NULLIFIER}&status=ACTIVE")
    message = _only_message(access_log_capture)
    assert NULLIFIER not in message
    assert "page=2&nullifier_hash=[redacted]&status=ACTIVE" in message


def test_percent_encoded_and_uppercase_keys_are_redacted(access_log_capture: Any) -> None:
    _emit("GET", f"/api/v1/vote/GR-1/status?Nullifier_Hash={NULLIFIER}&token={CONFIRM_TOKEN}")
    message = _only_message(access_log_capture)
    assert NULLIFIER not in message
    assert CONFIRM_TOKEN not in message


def test_non_sensitive_url_is_unchanged(access_log_capture: Any) -> None:
    target = "/api/v1/bills?page=2&status=ACTIVE&q=δημοκρατία"
    _emit("GET", target, 404)
    message = _only_message(access_log_capture)
    assert f'"GET {target} HTTP/1.1" 404' in message


def test_filter_does_not_mutate_args_when_nothing_is_sensitive() -> None:
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access", logging.INFO, __file__, 0,
        UVICORN_ACCESS_FORMAT,
        ("203.0.113.10:5000", "GET", "/health", "1.1", 200),
        None,
    )
    args_before = record.args
    assert main.AccessLogRedactionFilter().filter(record) is True
    assert record.args is args_before


@pytest.mark.parametrize("msg,args", [
    ("plain message without placeholders", None),
    ("plain message without placeholders", ()),
    ("%s", ("1.1",)),
    ('%s "%s"', ("client", "GET")),
    (UVICORN_ACCESS_FORMAT, ("client", "GET", None, "1.1", 200)),
    (UVICORN_ACCESS_FORMAT, ("client", "GET", 12345, "1.1", 200)),
    (UVICORN_ACCESS_FORMAT, ("client", "GET", b"/bytes-path", "1.1", 200)),
])
def test_malformed_records_never_raise_and_are_kept(msg: str, args: Any) -> None:
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access", logging.INFO, __file__, 0, msg, args, None,
    )
    assert main.AccessLogRedactionFilter().filter(record) is True
    assert record.getMessage()  # still renderable, line never dropped


def test_mapping_style_args_are_left_untouched() -> None:
    # logger.info("%(target)s", {...}) arrives as a tuple holding a mapping;
    # the filter must ignore it, not crash on it.
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access", logging.INFO, __file__, 0,
        "%(target)s", ({"target": f"/x?nullifier_hash={NULLIFIER}"},), None,
    )
    assert main.AccessLogRedactionFilter().filter(record) is True
    assert NULLIFIER in record.getMessage()  # unchanged, line never dropped


class _MissingBillSession:
    """Minimal async-session stand-in: bill lookup returns None (→ 404)."""

    async def execute(self, statement: Any, params: Any = None) -> Any:
        assert "parliament_bills" in str(statement)
        return SimpleNamespace(scalar_one_or_none=lambda: None)


def test_vote_status_get_404_carries_no_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOTE_STATUS_REQUIRE_SIGNED", raising=False)
    app = FastAPI()
    app.include_router(voting.router)
    app.dependency_overrides[get_db] = lambda: _MissingBillSession()
    with TestClient(app) as http:
        response = http.get(
            "/api/v1/vote/GR-MISSING/status", params={"nullifier_hash": NULLIFIER},
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "private, no-store"

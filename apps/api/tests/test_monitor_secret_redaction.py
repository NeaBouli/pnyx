import logging
import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


def test_redacts_telegram_bot_token_from_logged_url() -> None:
    raw = "POST https://api.telegram.org/botsecret-token/sendMessage"

    clean = monitor._redact_log_secrets(raw)

    assert clean == "POST https://api.telegram.org/bot<redacted>/sendMessage"
    assert "secret-token" not in clean


def test_redaction_filter_sanitizes_record_args() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: %s",
        args=("https://api.telegram.org/botsecret-token/sendMessage",),
        exc_info=None,
    )

    assert monitor.SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "HTTP Request: https://api.telegram.org/bot<redacted>/sendMessage"


def test_redaction_filter_preserves_non_secret_numeric_format_args() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP %d",
        args=(200,),
        exc_info=None,
    )

    assert monitor.SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "HTTP 200"

"""EVA-036: citizen identifiers and one-time secrets must not reach Sentry Cloud."""
import copy

import main

NULLIFIER = "ab" * 32
SIGNATURE = "cd" * 64
PUBLIC_KEY = "ef" * 32
QR_SESSION = "qrSessionSecretZ9"
CONFIRM = "confirmTokenZ9"
VALUES = (NULLIFIER, SIGNATURE, PUBLIC_KEY, QR_SESSION, CONFIRM, "oauthCodeZ9", "oauthStateZ9", "ssoZ9", "sigZ9", "nonceZ9")


def _event() -> dict:
    return {
        "event_id": "x",
        "request": {
            "url": f"https://api.ekklesia.gr/api/v1/polis/qr-session/{QR_SESSION}",
            "method": "GET",
            "query_string": (
                f"nullifier_hash={NULLIFIER}&signature_hex={SIGNATURE}&public_key_hex={PUBLIC_KEY}"
                "&code=oauthCodeZ9&state=oauthStateZ9&sso=ssoZ9&sig=sigZ9&nonce=nonceZ9&page=2"
            ),
            "headers": {"content-type": "application/json"},
        },
        "breadcrumbs": {"values": [
            {"type": "http", "data": {"url": f"https://api.ekklesia.gr/api/v1/newsletter/confirm/{CONFIRM}", "status_code": 410}},
            {"type": "http", "data": {"url": f"https://x.test/a?nullifier_hash={NULLIFIER}&b=1", "status_code": 200}},
        ]},
    }


def test_identifiers_and_secrets_are_scrubbed_from_query_url_and_breadcrumbs() -> None:
    result = main._before_send_filter(copy.deepcopy(_event()), {})

    text = repr(result)
    for value in VALUES:
        assert value not in text
    assert "page=2" in result["request"]["query_string"]
    assert result["request"]["url"].endswith("/polis/qr-session/[redacted]")
    assert result["breadcrumbs"]["values"][0]["data"]["url"].endswith("/newsletter/confirm/[redacted]")
    assert result["breadcrumbs"]["values"][1]["data"]["url"].endswith("?nullifier_hash=[redacted]&b=1")


def test_status_code_and_other_dict_keys_are_not_over_redacted() -> None:
    result = main._before_send_filter(copy.deepcopy(_event()), {})

    assert result["breadcrumbs"]["values"][0]["data"]["status_code"] == 410


def test_list_style_breadcrumbs_and_missing_fields_are_tolerated() -> None:
    event = {"event_id": "y", "breadcrumbs": [{"data": {"url": f"/x?signature_hex={SIGNATURE}"}}, {"message": "m"}],
             "request": {"url": None}}
    result = main._before_send_filter(event, {})

    assert SIGNATURE not in repr(result)
    assert result["request"]["url"] is None


def test_raw_url_transaction_name_and_http_query_are_scrubbed() -> None:
    event = {
        "transaction": f"/api/v1/polis/qr-session/{QR_SESSION}/",
        "transaction_info": {"source": "url"},
        "breadcrumbs": {"values": [{"data": {"url": "https://x.test/a", "http.query": f"nullifier_hash={NULLIFIER}"}}]},
        "spans": [{"description": f"GET https://x.test/a?nullifier_hash={NULLIFIER}",
                   "data": {"http.query": f"signature_hex={SIGNATURE}", "url": "https://x.test/a"}}],
    }
    result = main._before_send_filter(event, {})

    text = repr(result)
    assert QR_SESSION not in text and NULLIFIER not in text and SIGNATURE not in text
    assert result["transaction"] == "/api/v1/polis/qr-session/[redacted]/"


def test_route_template_transaction_name_is_kept() -> None:
    event = {"transaction": "/api/v1/polis/qr-session/{session_id}", "transaction_info": {"source": "route"}}

    assert main._before_send_filter(event, {})["transaction"] == "/api/v1/polis/qr-session/{session_id}"


def test_citizen_signature_headers_and_camelcase_query_keys_are_scrubbed() -> None:
    event = {"request": {
        "headers": {"X-Evaluation-Read-Signature": SIGNATURE, "X-Nullifier-Hash": NULLIFIER,
                    "content-type": "application/json", "accept-encoding": "gzip"},
        "query_string": f"publicKey={PUBLIC_KEY}&nullifierHash={NULLIFIER}&page=2",
    }}
    result = main._before_send_filter(event, {})

    text = repr(result)
    assert SIGNATURE not in text and NULLIFIER not in text and PUBLIC_KEY not in text
    assert result["request"]["headers"]["content-type"] == "application/json"
    assert result["request"]["headers"]["accept-encoding"] == "gzip"
    assert "page=2" in result["request"]["query_string"]


def test_sqlalchemy_parameters_are_scrubbed_from_exception_text() -> None:
    message = (
        '(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) duplicate key value\n'
        '[SQL: INSERT INTO identity_records (nullifier_hash, public_key_hex) VALUES ($1, $2)]\n'
        f"[parameters: ('{NULLIFIER}', '{PUBLIC_KEY} [x]')]\n"
        '(Background on this error at: https://sqlalche.me/e/20/gkpj)'
    )
    event = {"exception": {"values": [{"type": "IntegrityError", "value": message}]}}
    result = main._before_send_filter(event, {})

    value = result["exception"]["values"][0]["value"]
    assert NULLIFIER not in value and PUBLIC_KEY not in value
    assert "[SQL: INSERT INTO identity_records" in value and "(Background on this error" in value


def test_database_engine_hides_bound_parameters() -> None:
    import database

    assert database.engine.sync_engine.hide_parameters is True


def test_sentry_options_disable_redis_and_info_breadcrumbs() -> None:
    import logging

    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    assert any(isinstance(i, RedisIntegration) for i in options["disabled_integrations"])
    logging_integration = next(i for i in options["integrations"] if isinstance(i, LoggingIntegration))
    assert logging_integration._breadcrumb_handler.level == logging.WARNING


def test_http_fragment_is_scrubbed() -> None:
    event = {"breadcrumbs": {"values": [{"data": {"url": "https://x.test/a", "http.fragment": f"n={NULLIFIER}"}}]}}

    assert NULLIFIER not in repr(main._before_send_filter(event, {}))

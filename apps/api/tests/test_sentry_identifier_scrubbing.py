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

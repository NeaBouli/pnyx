"""Newsletter provider identifiers must never reach Sentry telemetry."""
import copy
import json
from unittest.mock import Mock
from urllib.parse import quote, urlencode

import httpx
import pytest
import sentry_sdk

import main
from routers import newsletter
from services import newsletter_service
from tests.test_sentry_secret_scrubbing import _init_sdk, sdk_reset  # noqa: F401


EMAIL = "subscriber+telemetry@example.org"
ENCODED_EMAIL = quote(EMAIL, safe="")
CONTACT_ID = "729185603"
QUERY = f"lower(subscribers.email) = lower('{EMAIL}')"
BREVO_URL = f"https://api.brevo.com/v3/contacts/{ENCODED_EMAIL}/lists"
LISTMONK_URL = "http://listmonk.test/api/subscribers?" + urlencode({"query": QUERY, "page": 2})
STAGED_EMAILS = [
    "subscriber%25ab%40example.org",
    "subscriber%2525ab%2540example.org",
    "subscriber%252525ab%252540example.org",
    "subscriber%25Ab%40example.org",
    "subscriber%2525aB%2540example.org",
    "subscriber%2525252525ab%2525252540example.org",
]


def assert_private(value: object) -> None:
    text = repr(value).lower()
    for private in (EMAIL, ENCODED_EMAIL, quote(ENCODED_EMAIL, safe=""), "example.org", CONTACT_ID):
        assert private.lower() not in text


def breadcrumb() -> dict:
    return {
        "type": "http", "category": "httplib",
        "message": f"GET {BREVO_URL}",
        "data": {
            "url": BREVO_URL, "http.url": LISTMONK_URL,
            "http.query": urlencode({"query": QUERY, "page": 2}),
            "status_code": 200, "method": "GET",
            "nested": {"recipient": EMAIL, "aliases": [ENCODED_EMAIL, quote(ENCODED_EMAIL, safe="")]},
        },
    }


@pytest.mark.parametrize("hook", ["before_send", "before_send_transaction"])
def test_real_event_hooks_scrub_provider_and_generic_email_telemetry(hook: str) -> None:
    event = {
        "request": {"url": BREVO_URL, "query_string": urlencode({"lookup": EMAIL, "page": 2})},
        "transaction": f"GET /api/subscribers/{CONTACT_ID}",
        "breadcrumbs": {"values": [breadcrumb()]},
        "spans": [
            {"op": "http.client", "description": f"GET {BREVO_URL}", "data": {"url": LISTMONK_URL}},
            {"description": f"GET https://api.brevo.com/v3/contacts/{CONTACT_ID}/lists"},
            {"description": f"lookup {EMAIL}", "data": {"recipient": EMAIL}},
        ],
    }
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    result = options[hook](copy.deepcopy(event), {})

    assert_private(result)
    assert "page=2" in result["request"]["query_string"]
    assert result["breadcrumbs"]["values"][0]["data"]["status_code"] == 200
    assert result["spans"][0]["op"] == "http.client"
    assert "api.brevo.com" in result["spans"][0]["description"]


def test_before_breadcrumb_scrubs_before_scope_storage() -> None:
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    result = options["before_breadcrumb"](breadcrumb(), {})

    assert_private(result)
    assert result["data"]["method"] == "GET"
    assert result["data"]["status_code"] == 200


@pytest.mark.parametrize("hook", ["before_send", "before_send_transaction", "before_breadcrumb"])
@pytest.mark.parametrize("encoded_email", STAGED_EMAILS)
def test_each_decoding_stage_redacts_the_whole_email_value(hook: str, encoded_email: str) -> None:
    url = f"https://other.test/search?recipient={encoded_email}&page=2"
    crumb = {
        "type": "http", "category": "httplib", "message": f"GET {url}",
        "description": f"GET {url}",
        "data": {"url": url, "http.url": url, "recipient": encoded_email, "status_code": 200},
    }
    event = crumb if hook == "before_breadcrumb" else {
        "request": {"url": url, "query_string": urlencode({"lookup": encoded_email, "page": 2})},
        "extra": {"recipient": encoded_email},
        "breadcrumbs": {"values": [crumb]},
        "spans": [{"op": "http.client", "description": f"GET {url}", "data": crumb["data"]}],
    }
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    result = options[hook](copy.deepcopy(event), {})

    assert_private(result)
    assert "subscriber" not in repr(result).lower()
    assert encoded_email not in repr(result)
    filtered_crumb = result if hook == "before_breadcrumb" else result["breadcrumbs"]["values"][0]
    assert filtered_crumb["data"]["recipient"] == "[Filtered]"
    assert filtered_crumb["data"]["status_code"] == 200
    if hook != "before_breadcrumb":
        assert "page=2" in result["request"]["query_string"]
        assert result["spans"][0]["op"] == "http.client"


async def test_nested_encoded_emails_are_private_through_sdk_transport(sdk_reset) -> None:
    transport = _init_sdk()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        with sentry_sdk.start_transaction(name="generic-email-lookups", op="task"):
            for encoded_email in STAGED_EMAILS:
                await client.get(f"https://other.test/search?recipient={encoded_email}&page=2")
            assert_private(list(sentry_sdk.get_current_scope()._breadcrumbs))
            assert "subscriber" not in repr(list(sentry_sdk.get_current_scope()._breadcrumbs)).lower()
            with sentry_sdk.new_scope() as scope:
                scope.set_extra("recipients", STAGED_EMAILS)
                sentry_sdk.capture_message("generic lookups completed", level="error")
    sentry_sdk.flush()

    payloads = [(kind, json.loads(body)) for kind, body in transport.payloads]
    assert {"event", "transaction"} <= {kind for kind, _ in payloads}
    transaction = next(body for kind, body in payloads if kind == "transaction")
    assert len([span for span in transaction["spans"] if span["op"] == "http.client"]) == len(STAGED_EMAILS)
    event = next(body for kind, body in payloads if kind == "event")
    assert len([crumb for crumb in event["breadcrumbs"]["values"] if crumb.get("type") == "http"]) == len(STAGED_EMAILS)
    assert_private(payloads)
    assert "subscriber" not in repr(payloads).lower()


@pytest.mark.parametrize("url", [
    "https://other.test/search?q=ordinary%2520text&page=2",
    "https://other.test/search?q=" + "%" + "25" * 20 + "20",
])
def test_email_decoding_is_bounded_and_preserves_ordinary_url_escaping(monkeypatch, url: str) -> None:
    decode = Mock(wraps=main.unquote)
    monkeypatch.setattr(main, "unquote", decode)

    assert main._sentry_redact_text(url) == url
    assert 1 <= decode.call_count <= 5


@pytest.mark.parametrize("query", [
    f"lookup={EMAIL}&page=2",
    urlencode({"lookup": EMAIL, "page": 2}),
    {"lookup": EMAIL, "page": 2},
    {"lookup": "subscriber%ab@example.org", "page": 2},
    [["lookup", EMAIL], ["page", "2"]],
    [("lookup", ENCODED_EMAIL), ("page", "2")],
])
def test_query_values_are_private_regardless_of_key_or_representation(query: object) -> None:
    result = main._before_send_filter({"request": {"query_string": query}}, {})
    assert_private(result)
    assert "page" in repr(result) and "2" in repr(result)


@pytest.mark.parametrize("url", [
    f"https://api.brevo.com/v3/contacts/{CONTACT_ID}/lists",
    f"http://listmonk.test/api/subscribers/{CONTACT_ID}/blocklist",
    "http://listmonk.test/api/subscribers?" + urlencode({"query": f"subscribers.id = {CONTACT_ID}"}),
    f"https://other.test/search?recipient={ENCODED_EMAIL}&page=2",
    "https://other.test/search?recipient=subscriber%ab@example.org&page=2",
    f"https://other.test/{EMAIL}#recipient={ENCODED_EMAIL}",
])
def test_provider_ids_and_emails_in_arbitrary_urls_are_scrubbed(url: str) -> None:
    result = main._before_send_filter({"spans": [{"description": f"GET {url}"}]}, {})
    assert_private(result)


async def test_httpx_provider_lookups_ship_private_errors_and_sampled_spans(sdk_reset, monkeypatch) -> None:
    """Exercise HTTPX instrumentation and the app's production hooks through transport."""
    transport = _init_sdk()
    real_client = httpx.AsyncClient
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "api.brevo.com":
            return httpx.Response(404, json={})
        if request.method == "GET":
            return httpx.Response(200, json={"data": {"results": [{"email": EMAIL}]}})
        return httpx.Response(200, json={"data": True})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr(newsletter, "LISTMONK_URL", "http://listmonk.test")
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-provider-password")

    with sentry_sdk.start_transaction(name="newsletter-provider-lookups", op="task"):
        assert await newsletter_service.contact_status(EMAIL) == "to_add"
        assert await newsletter._remove_listmonk_contact(EMAIL, require_present=True) is True
        # The ingestion hook must protect breadcrumbs while they are still in scope.
        assert_private(list(sentry_sdk.get_current_scope()._breadcrumbs))
        sentry_sdk.capture_message("newsletter lookup failed", level="error")
    sentry_sdk.flush()

    assert len(requests) == 3
    payloads = [(kind, json.loads(body)) for kind, body in transport.payloads]
    assert {"event", "transaction"} <= {kind for kind, _ in payloads}
    transaction = next(body for kind, body in payloads if kind == "transaction")
    assert len([span for span in transaction["spans"] if span["op"] == "http.client"]) == 3
    event = next(body for kind, body in payloads if kind == "event")
    assert any(crumb.get("type") == "http" for crumb in event["breadcrumbs"]["values"])
    assert_private(payloads)

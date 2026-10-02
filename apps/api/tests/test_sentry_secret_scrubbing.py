"""T-471: Admin credential must not survive Sentry event filtering or the import contract."""

import copy
import json
from pathlib import Path
from urllib.parse import parse_qsl

import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

import main
from routers.scraper import BillImportRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "scraper.yml"
SECRET = "synthetic-admin-secret"


def _pre_fix_import_event() -> dict:
    """Shape of a sentry-sdk 2.x FastAPI event for a failed /scraper/import."""
    return {
        "event_id": "abc",
        "level": "error",
        "request": {
            "url": "https://api.ekklesia.gr/api/v1/scraper/import",
            "method": "POST",
            "query_string": f"dry=1&Admin_Key={SECRET}&api-key={SECRET}",
            "headers": {
                "authorization": "[Filtered]",
                "content-type": "application/json",
                "x-forwarded-for": "203.0.113.7",
                "cookie": "session=1",
                "X-Forwarded-For": "203.0.113.8",
                "Cookie": "session=2",
            },
            "cookies": {"session_token": SECRET},
            "env": {"REMOTE_ADDR": "203.0.113.7"},
            "data": {
                "ADMIN_KEY": SECRET,
                "bills": [{"bill_id": "GR-1", "title_el": "Τίτλος", "meta": {"adminKey": SECRET}}],
            },
        },
        "extra": {"context": {"admin_key": SECRET, "bill_id": "GR-1"}},
        "exception": {
            "values": [{
                "type": "RuntimeError",
                "stacktrace": {"frames": [{
                    "function": "import_parliament_bills",
                    "vars": {
                        "admin_key": f"'{SECRET}'",
                        "Authorization": f"'Bearer {SECRET}'",
                        "imported": "0",
                    },
                }]},
            }],
        },
    }


def _contains_secret(value) -> bool:
    return SECRET in repr(value)


def test_before_send_redacts_sensitive_keys_case_insensitive():
    event = _pre_fix_import_event()
    original = copy.deepcopy(event)

    result = main._before_send_filter(event, {})

    assert result is not None
    assert not _contains_secret(result)

    request = result["request"]
    assert request["data"]["ADMIN_KEY"] == "[Filtered]"
    assert request["data"]["bills"][0]["meta"]["adminKey"] == "[Filtered]"
    assert request["data"]["bills"][0]["bill_id"] == "GR-1"
    assert request["data"]["bills"][0]["title_el"] == "Τίτλος"
    assert dict(parse_qsl(request["query_string"])) == {
        "dry": "1", "Admin_Key": "[Filtered]", "api-key": "[Filtered]",
    }
    assert request["cookies"] == {"session_token": "[Filtered]"}
    assert request["url"] == original["request"]["url"]
    assert request["method"] == "POST"

    frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert frame_vars["admin_key"] == "[Filtered]"
    assert frame_vars["Authorization"] == "[Filtered]"
    assert frame_vars["imported"] == "0"
    assert result["extra"]["context"] == {"admin_key": "[Filtered]", "bill_id": "GR-1"}
    assert result["event_id"] == "abc" and result["level"] == "error"


def test_before_send_keeps_header_and_env_scrubbing():
    result = main._before_send_filter(_pre_fix_import_event(), {})
    request = result["request"]

    assert "env" not in request
    assert {k.lower() for k in request["headers"]} == {"authorization", "content-type"}
    assert request["headers"]["authorization"] == "[Filtered]"
    assert request["headers"]["content-type"] == "application/json"


def test_before_send_tolerates_events_without_request():
    event = {"event_id": "x", "message": "plain"}
    assert main._before_send_filter(event, {}) == {"event_id": "x", "message": "plain"}


def test_redact_header_pair_list_without_corrupting_outer_list():
    headers = [
        ["b'authorization'", f"b'Bearer {SECRET}'"],
        ["b'content-type'", "b'application/json'"],
    ]

    assert main._sentry_redact(headers) == [
        ["b'authorization'", "[Filtered]"],
        ["b'content-type'", "b'application/json'"],
    ]


def test_bill_import_request_has_no_body_credential():
    assert "admin_key" not in BillImportRequest.model_fields
    assert BillImportRequest(bills=[]).model_dump() == {"bills": []}


def test_bill_import_request_ignores_legacy_body_credential():
    request = BillImportRequest.model_validate({"admin_key": SECRET, "bills": []})

    assert "admin_key" not in request.model_dump()
    assert SECRET not in repr(request)


def test_scraper_workflow_sends_bearer_without_json_credential():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '-H "Authorization: Bearer ${{ secrets.EKKLESIA_ADMIN_KEY }}"' in workflow
    assert "'{bills: $bills[0][:20]}'" in workflow
    assert "admin_key" not in workflow
    payload_block = workflow[workflow.index("jq -n"):workflow.index("> /tmp/payload.json")]
    assert "secrets." not in payload_block


# ── SDK-Pipeline: echte sentry_sdk-Verarbeitung bis zum Transport ─────────────

class _CaptureTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.payloads: list[tuple[str, str]] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            self.payloads.append((item.headers.get("type"), item.get_bytes().decode("utf-8")))


def _init_sdk(**overrides) -> _CaptureTransport:
    transport = _CaptureTransport()
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    options["traces_sample_rate"] = 1.0
    options.update(overrides)
    sentry_sdk.init(**{k: v for k, v in options.items() if v is not None}, transport=transport)
    return transport


@pytest.fixture
def sdk_reset():
    yield
    sentry_sdk.flush()
    sentry_sdk.init()


def _post_import(client: TestClient, path: str) -> None:
    client.post(
        f"{path}?dry=1&Admin_Key={SECRET}",
        json={"Admin_Key": SECRET, "bills": []},
        headers={"Authorization": f"Bearer {SECRET}"},
    )


def test_sentry_init_wires_filter_for_errors_and_transactions():
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    assert options["before_send"] is main._before_send_filter
    assert options["before_send_transaction"] is main._before_send_filter
    assert options["send_default_pii"] is False


def test_sampled_import_transaction_does_not_ship_admin_key(sdk_reset):
    transport = _init_sdk()
    _post_import(TestClient(main.app, raise_server_exceptions=False), "/api/v1/scraper/import")
    sentry_sdk.flush()

    transactions = [body for kind, body in transport.payloads if kind == "transaction"]
    assert transactions, "sampled transaction must reach transport"
    assert '"query_string"' in transactions[0] and "Admin_Key" in transactions[0]
    assert all(SECRET not in body for _, body in transport.payloads)


def test_sampled_transaction_leaks_without_transaction_hook(sdk_reset):
    """Kontrolle: ohne before_send_transaction erreicht das Secret den Transport."""
    transport = _init_sdk(before_send_transaction=None)
    _post_import(TestClient(main.app, raise_server_exceptions=False), "/api/v1/scraper/import")
    sentry_sdk.flush()

    assert any(kind == "transaction" and SECRET in body for kind, body in transport.payloads)


def test_error_event_does_not_ship_admin_key(sdk_reset):
    transport = _init_sdk()
    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):
        await request.json()
        raise RuntimeError("synthetic import failure")

    _post_import(TestClient(app, raise_server_exceptions=False), "/boom")
    sentry_sdk.flush()

    kinds = {kind for kind, _ in transport.payloads}
    assert {"event", "transaction"} <= kinds
    assert all(SECRET not in body for _, body in transport.payloads)


# ── T-494: Capture-Grenze — keine Frame-Locals, keine Request-Bodies ──────────

LOCAL_SENTINEL = "synthetic-local-sentinel-t494"
BODY_SENTINEL = "synthetic-body-sentinel-t494"


def _events(transport: _CaptureTransport) -> list[dict]:
    return [json.loads(body) for kind, body in transport.payloads if kind == "event"]


def test_sentry_init_disables_local_variables_and_request_bodies():
    options = main._sentry_init_options("https://public@o0.ingest.sentry.io/1")
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"


def _raise_with_plain_local() -> None:
    plain_note = LOCAL_SENTINEL  # harmloser Name: vom Key-Filter nicht erkannt
    raise ValueError(f"synthetic failure ({len(plain_note)})")


def _capture_plain_local_failure(transport: _CaptureTransport) -> dict:
    try:
        _raise_with_plain_local()
    except ValueError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()
    events = _events(transport)
    assert len(events) == 1
    return events[0]


def test_error_event_omits_plain_frame_locals(sdk_reset):
    transport = _init_sdk()
    event = _capture_plain_local_failure(transport)

    assert all(LOCAL_SENTINEL not in body for _, body in transport.payloads)
    exc = event["exception"]["values"][-1]
    assert exc["type"] == "ValueError"
    frames = exc["stacktrace"]["frames"]
    assert any(f.get("function") == "_raise_with_plain_local" for f in frames)
    assert all("vars" not in f for f in frames)


def test_error_event_leaks_plain_frame_locals_without_option(sdk_reset):
    """Kontrolle: mit include_local_variables=True erreicht der Wert den Transport."""
    transport = _init_sdk(include_local_variables=True)
    _capture_plain_local_failure(transport)

    assert any(kind == "event" and LOCAL_SENTINEL in body for kind, body in transport.payloads)


def _post_plain_body(**overrides) -> _CaptureTransport:
    transport = _init_sdk(**overrides)
    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):
        await request.json()
        raise RuntimeError("synthetic body failure")

    TestClient(app, raise_server_exceptions=False).post(
        "/boom?dry=1", json={"plain_note": BODY_SENTINEL},
    )
    sentry_sdk.flush()
    return transport


def test_fastapi_events_omit_plain_request_body(sdk_reset):
    transport = _post_plain_body()

    kinds = {kind for kind, _ in transport.payloads}
    assert {"event", "transaction"} <= kinds
    assert all(BODY_SENTINEL not in body for _, body in transport.payloads)

    event = _events(transport)[0]
    assert event["exception"]["values"][-1]["type"] == "RuntimeError"
    assert event["exception"]["values"][-1]["stacktrace"]["frames"]
    request = event["request"]
    assert request["url"].endswith("/boom")
    assert request["method"] == "POST"
    assert not request.get("data")
    assert event["_meta"]["request"]["data"][""]["rem"][0][0] == "!config"


def test_fastapi_events_leak_plain_request_body_without_option(sdk_reset):
    """Kontrolle: mit max_request_body_size="always" erreicht der Body den Transport."""
    transport = _post_plain_body(max_request_body_size="always")

    assert any(kind == "event" and BODY_SENTINEL in body for kind, body in transport.payloads)

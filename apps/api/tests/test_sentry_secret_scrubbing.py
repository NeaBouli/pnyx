"""T-471: Admin credential must not survive Sentry event filtering or the import contract."""

import copy
from pathlib import Path
from urllib.parse import parse_qsl

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

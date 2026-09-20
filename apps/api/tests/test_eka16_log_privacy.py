"""EKA-16 regression tests: no personal data in contact/newsletter app logs.

Drives the audited contact and newsletter paths with sentinel PII and asserts
the sentinels — and provider response bodies echoing them — never reach
captured application logs, while safe references (ipref/emailref) and provider
status codes remain. Delivery payloads themselves are asserted unchanged.
Mock-only: no real Redis, email provider or network access.
"""
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from routers import contact, newsletter

SENTINELS = {
    "first_name": "SentinelFirst",
    "last_name": "SentinelLast",
    "email": "sentinel.person@example.org",
    "phone": "+306900001111",
    "org": "SentinelOrg",
    "position": "SentinelPosition",
    "region": "SentinelRegion",
    "subject": "SentinelSubject",
    "message": "SentinelMessage",
}

PROVIDER_ECHO = (
    '{"message":"rejected: '
    + " ".join(SENTINELS.values())
    + '"}'
)


def _request(ip: str = "203.0.113.10") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})


def _sentinel_contact_body() -> contact.NgoContactRequest:
    return contact.NgoContactRequest(
        first_name=SENTINELS["first_name"],
        last_name=SENTINELS["last_name"],
        email=SENTINELS["email"],
        phone=SENTINELS["phone"],
        org=SENTINELS["org"],
        position=SENTINELS["position"],
        region=SENTINELS["region"],
        subject=SENTINELS["subject"],
        message=SENTINELS["message"],
        consent=True,
    )


def _log_text(caplog: pytest.LogCaptureFixture, logger_name: str) -> str:
    return " ".join(
        record.getMessage() for record in caplog.records if record.name == logger_name
    )


def _assert_no_pii(log_text: str) -> None:
    for value in SENTINELS.values():
        assert value not in log_text
    assert PROVIDER_ECHO not in log_text


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return {}


def _client_class(response: _FakeResponse | None = None, error: Exception | None = None):
    """AsyncClient stand-in recording the outbound payload for assertions."""

    class _Client:
        posted: dict[str, Any] = {}

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            type(self).posted = {"method": method, "url": url, **kwargs}
            return response

        async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            type(self).posted = {"url": url, **kwargs}
            if error is not None:
                raise error
            return response

    _Client.posted = {}
    return _Client


class _ContactRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def eval(self, script: str, numkeys: int, key: str, seconds: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


@pytest.fixture
def contact_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setattr(contact, "_get_redis", lambda: _async(_ContactRedis()))


async def _async(value: Any) -> Any:
    return value


async def test_contact_success_logs_no_pii_and_keeps_ref(
    contact_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client_class(response=_FakeResponse(201))
    monkeypatch.setattr(contact.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.contact"):
        out = await contact.contact_ngo(_sentinel_contact_body(), _request())

    assert out["status"] == "ok"
    # Delivery behavior preserved: the provider payload still carries the PII.
    payload = client.posted["json"]
    assert payload["replyTo"] == {
        "email": SENTINELS["email"],
        "name": f"{SENTINELS['first_name']} {SENTINELS['last_name']}",
    }
    for value in SENTINELS.values():
        assert value in payload["htmlContent"] or value in payload["subject"]

    logs = _log_text(caplog, "routers.contact")
    _assert_no_pii(logs)
    assert "ipref:" in logs


async def test_contact_provider_error_body_never_logged(
    contact_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client_class(response=_FakeResponse(400, PROVIDER_ECHO))
    monkeypatch.setattr(contact.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.contact"):
        with pytest.raises(HTTPException) as exc:
            await contact.contact_ngo(_sentinel_contact_body(), _request())

    assert exc.value.status_code == 502
    logs = _log_text(caplog, "routers.contact")
    _assert_no_pii(logs)
    assert "Brevo error 400 ref=ipref:" in logs
    assert "ipref:" in logs


async def test_contact_http_error_logs_no_pii(
    contact_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client_class(error=contact.httpx.ConnectError("connection refused"))
    monkeypatch.setattr(contact.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.contact"):
        with pytest.raises(HTTPException) as exc:
            await contact.contact_ngo(_sentinel_contact_body(), _request())

    assert exc.value.status_code == 502
    _assert_no_pii(_log_text(caplog, "routers.contact"))


class _SubscribeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.pending: dict[str, str] = {}

    async def hget(self, key: str, field: str) -> None:
        return None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.pending[key] = value

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        key = args[0]
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


@pytest.fixture
def newsletter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "test-key")


async def test_newsletter_subscribe_success_logs_no_email(
    newsletter_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", lambda: _async(_SubscribeRedis()))
    client = _client_class(response=_FakeResponse(201))
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.newsletter"):
        out = await newsletter.subscribe(
            newsletter.SubscribeRequest(email=SENTINELS["email"], name=SENTINELS["first_name"]),
            _request(),
        )

    assert out["success"] is True
    # Delivery behavior preserved: the provider payload still carries the email.
    assert client.posted["json"]["to"] == [{"email": SENTINELS["email"]}]

    logs = _log_text(caplog, "routers.newsletter")
    assert SENTINELS["email"] not in logs
    assert SENTINELS["first_name"] not in logs
    assert "emailref:" in logs


async def test_newsletter_subscribe_provider_error_body_never_logged(
    newsletter_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", lambda: _async(_SubscribeRedis()))
    client = _client_class(response=_FakeResponse(400, PROVIDER_ECHO))
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.newsletter"):
        with pytest.raises(HTTPException) as exc:
            await newsletter.subscribe(
                newsletter.SubscribeRequest(email=SENTINELS["email"]), _request()
            )

    assert exc.value.status_code == 502
    logs = _log_text(caplog, "routers.newsletter")
    assert SENTINELS["email"] not in logs
    assert PROVIDER_ECHO not in logs
    assert "[MOD-19] Brevo send failed: 400" in logs


async def test_newsletter_subscribe_http_error_logs_no_pii(
    newsletter_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", lambda: _async(_SubscribeRedis()))
    client = _client_class(error=newsletter.httpx.ConnectError("connection refused"))
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.newsletter"):
        with pytest.raises(HTTPException) as exc:
            await newsletter.subscribe(
                newsletter.SubscribeRequest(email=SENTINELS["email"]), _request()
            )

    assert exc.value.status_code == 502
    logs = _log_text(caplog, "routers.newsletter")
    assert SENTINELS["email"] not in logs
    assert "[MOD-19] Brevo error: connection refused" in logs


class _ConfirmRedis:
    def __init__(self, pending_json: str) -> None:
        self._pending_json = pending_json

    async def get(self, key: str) -> str:
        return self._pending_json

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        return 1


async def test_newsletter_confirm_listmonk_error_body_never_logged(
    newsletter_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pending = json.dumps(
        {
            "email": SENTINELS["email"],
            "name": SENTINELS["first_name"],
            "subscriber_type": "citizens",
            "frequency": "weekly",
            "language": "el",
            "topics": {},
        }
    )
    monkeypatch.setattr(newsletter, "_get_redis", lambda: _async(_ConfirmRedis(pending)))
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "pw")
    client = _client_class(response=_FakeResponse(400, PROVIDER_ECHO))
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", client)
    with caplog.at_level(logging.DEBUG, logger="routers.newsletter"):
        out = await newsletter.confirm_subscription("token")

    assert out.status_code == 200
    logs = _log_text(caplog, "routers.newsletter")
    assert SENTINELS["email"] not in logs
    assert PROVIDER_ECHO not in logs
    assert "[MOD-19] Listmonk POST /api/subscribers: 400" in logs

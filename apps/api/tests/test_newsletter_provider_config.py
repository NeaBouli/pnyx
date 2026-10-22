"""List service configuration, private diagnostics and optional connection health."""
import asyncio
import base64
import json
import logging
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_consent import (
    CONFIRMED_KEY, LISTMONK_ADD_UNSETTLED_KEY, LISTMONK_REMOVE_RETRY_KEY, SUPPRESSED_KEY,
)
from tests.test_newsletter_delivery_sync import EMAIL, HTTP_CLIENT, MemoryRedis, consent


API_USER = "synthetic-api-user"
API_TOKEN = "synthetic-api-token"
AUTH_MESSAGE = "Newsletter list service rejected credentials; configure an API user"


@pytest.fixture(autouse=True)
def provider_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(newsletter, "LISTMONK_URL", "http://listmonk:9000")
    monkeypatch.setattr(newsletter, "LISTMONK_USER", API_USER)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    newsletter._warn_listmonk_ipv4_url.cache_clear()
    newsletter._warn_listmonk_auth_rejected.cache_clear()
    yield
    newsletter._warn_listmonk_ipv4_url.cache_clear()
    newsletter._warn_listmonk_auth_rejected.cache_clear()


def test_default_url_is_compose_service_name(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("LISTMONK_URL", raising=False)
    assert newsletter._listmonk_base_url() == "http://listmonk:9000"
    assert not caplog.records


@pytest.mark.parametrize("url", [
    "http://192.0.2.7:9000",
    f"https://{API_USER}:{API_TOKEN}@192.0.2.7:9000/private?token={API_TOKEN}#{EMAIL}",
])
def test_ipv4_host_warns_once_without_url_or_credentials(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str,
) -> None:
    monkeypatch.setenv("LISTMONK_URL", url)
    for _ in range(3):
        assert newsletter._listmonk_base_url() == url
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "stable service hostname" in caplog.text
    for private in ("192.0.2.7", API_USER, API_TOKEN, EMAIL, url):
        assert private not in caplog.text


@pytest.mark.parametrize("url", [
    "http://listmonk:9000", "https://lists.example.org", "http://[::1]:9000",
    "http://192.0.2.7.example.org:9000", "http://listmonk:9000/192.0.2.7",
])
def test_hostname_or_ipv6_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str,
) -> None:
    monkeypatch.setenv("LISTMONK_URL", url)
    assert newsletter._listmonk_base_url() == url
    assert not caplog.records


@pytest.mark.parametrize("statuses", [(401, 401), (403, 403), (401, 403)])
async def test_auth_rejection_logs_once_and_preserves_request_failure_types(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, statuses: tuple[int, int],
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", API_TOKEN)
    credentials = base64.b64encode(f"{API_USER}:{API_TOKEN}".encode()).decode()
    requests: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Basic {credentials}"
        requests.append(request)
        return httpx.Response(statuses[(len(requests) - 1) % 2], text=f"{EMAIL} {API_USER} {API_TOKEN}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: HTTP_CLIENT(
        transport=httpx.MockTransport(provider), **kw,
    ))
    for method in ("GET", "POST", "PUT", "GET"):
        if method == "GET":
            with pytest.raises(HTTPException) as error:
                await newsletter._listmonk_request(method, "/api/subscribers")
            assert error.value.status_code == 502
            assert error.value.detail == "Newsletter provider request failed"
        else:
            with pytest.raises(newsletter_service.ContactNotWritten):
                await newsletter._listmonk_request(method, "/api/subscribers", {"email": EMAIL})
    assert caplog.text.count(AUTH_MESSAGE) == 1
    for private in (EMAIL, API_USER, API_TOKEN, credentials):
        assert private not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_rejection_keeps_enrollment_retryable_and_withdrawal_marker(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int,
) -> None:
    monkeypatch.setattr(newsletter, "LISTMONK_PW", API_TOKEN)
    monkeypatch.setattr(newsletter_service, "remove_contact", AsyncMock(return_value=True))
    store = MemoryRedis()
    raw = json.dumps(consent())
    store.hashes[CONFIRMED_KEY][EMAIL] = raw
    rejected = True

    def provider(request: httpx.Request) -> httpx.Response:
        if rejected:
            return httpx.Response(status, text=f"{EMAIL} {API_TOKEN}")
        return httpx.Response(200, json={"data": True})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: HTTP_CLIENT(
        transport=httpx.MockTransport(provider), **kw,
    ))
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is False
    assert store.hashes[CONFIRMED_KEY][EMAIL] == raw
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    rejected = False
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is True

    rejected = True
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed") is False
    assert store.hashes[SUPPRESSED_KEY][EMAIL] == "unsubscribed"
    assert store.hashes[LISTMONK_REMOVE_RETRY_KEY] == {EMAIL: "1"}
    assert not store.hashes[CONFIRMED_KEY]
    rejected = False
    assert await newsletter._retry_withdrawal(store, EMAIL) is True
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert caplog.text.count(AUTH_MESSAGE) == 1
    for private in (EMAIL, API_USER, API_TOKEN):
        assert private not in caplog.text


@pytest.mark.parametrize("failure", [
    "success", "unconfigured", "401", "403", "503", "connect", "timeout", "invalid_json", "invalid_count", "redirect",
])
async def test_optional_readiness_health_is_bounded_private_and_get_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, failure: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "" if failure == "unconfigured" else API_TOKEN)
    monkeypatch.setattr(newsletter_admin, "LIST_SERVICE_READINESS_TIMEOUT_SECONDS", 0.01)
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[0])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    requests: list[httpx.Request] = []
    cancelled: list[bool] = []

    async def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "listmonk"
        assert request.url.path == "/api/subscribers"
        assert dict(request.url.params) == {"per_page": "1", "page": "1"}
        if failure == "connect":
            raise httpx.ConnectError(f"{EMAIL} {API_TOKEN}", request=request)
        if failure == "timeout":
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        if failure == "redirect":
            return httpx.Response(307, headers={"Location": f"https://outside.invalid/{EMAIL}?token={API_TOKEN}"})
        if failure == "invalid_json":
            return httpx.Response(200, text=f"{EMAIL} {API_TOKEN}")
        if failure.isdigit():
            return httpx.Response(int(failure), text=f"{EMAIL} {API_TOKEN}")
        return httpx.Response(200, json={"data": {
            "total": EMAIL if failure == "invalid_count" else 7, "results": [{"email": EMAIL}],
        }})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: HTTP_CLIENT(
        transport=httpx.MockTransport(provider), **kw,
    ))
    before = await newsletter_admin.newsletter_readiness(_auth=True)
    assert not requests
    result = await newsletter_admin.newsletter_readiness(_auth=True, check_list_service=True)
    for private in (EMAIL, API_USER, API_TOKEN, "outside.invalid"):
        assert private not in caplog.text
        assert private not in json.dumps(result)
    assert result.pop("list_service") == {
        "configured": int(failure != "unconfigured"), "reachable": int(failure == "success"),
        "failed": int(failure not in {"success", "unconfigured"}),
    }
    assert result == before
    assert len(requests) == int(failure != "unconfigured")
    assert cancelled == ([True] if failure == "timeout" else [])
    assert {call[0] for call in store.method_calls} == {"eval_ro"}
    assert caplog.text.count(AUTH_MESSAGE) == int(failure in {"401", "403"})


async def test_opt_in_health_uses_existing_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")
    health = AsyncMock(return_value={"configured": 0, "reachable": 0, "failed": 0})
    monkeypatch.setattr(newsletter_admin, "_listmonk_connection_health", health)
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[0])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    app = FastAPI()
    app.include_router(newsletter_admin.router)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/newsletter/readiness?check_list_service=true")
        assert response.status_code == 403
        health.assert_not_awaited()
        response = await client.get("/api/v1/admin/newsletter/readiness?check_list_service=true", headers={
            "Authorization": "Bearer synthetic-admin-key",
        })
    assert response.status_code == 200
    assert response.json()["list_service"] == {"configured": 0, "reachable": 0, "failed": 0}
    health.assert_awaited_once()

"""Consent-to-delivery boundary, using only in-memory stores and HTTP transports."""
import json
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_consent import (
    CONFIRMED_KEY, CONFIRM_ONCE, SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY,
    BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY, WITHDRAW_CONSENT,
)

EMAIL = "subscriber+fixture@example.org"
HTTP_CLIENT = httpx.AsyncClient


class MemoryRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self.pending: dict[str, str] = {}
        self.mutations: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.pending.get(key)

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes[key].get(field)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes[key])

    async def hkeys(self, key: str) -> list[str]:
        return list(self.hashes[key])

    async def hset(self, key: str, field: str, value: str) -> None:
        self.mutations.append(key)
        self.hashes[key][field] = value

    async def hdel(self, key: str, field: str) -> None:
        self.mutations.append(key)
        self.hashes[key].pop(field, None)

    async def hincrby(self, key: str, field: str, amount: int) -> None:
        self.hashes[key][field] = str(int(self.hashes[key].get(field, "0")) + amount)

    async def delete(self, key: str) -> None:
        self.mutations.append(key)

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        self.mutations.append("eval")
        if script == CONFIRM_ONCE:
            pending_key, confirmed_key, raw, email, confirmed = args
            if self.pending.get(pending_key) != raw:
                return 0
            self.pending.pop(pending_key)
            if email in self.hashes[confirmed_key]:
                return 2
            self.hashes[confirmed_key][email] = confirmed
            return 1
        assert script == WITHDRAW_CONSENT and numkeys == 5
        confirmed, suppressed, add_retry, brevo_retry, listmonk_retry, email, reason, configured, normalized = args
        self.hashes[suppressed][normalized] = reason
        self.hashes[confirmed].pop(email, None)
        self.hashes[add_retry].pop(email, None)
        self.hashes[brevo_retry][email] = "1"
        if configured == "1":
            self.hashes[listmonk_retry][email] = "1"
        return 1


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryRedis:
    redis = MemoryRedis()
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    monkeypatch.setattr(newsletter, "BREVO_WEBHOOK_TOKEN", "synthetic-webhook-token")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")
    monkeypatch.setattr(newsletter_service, "add_contact", AsyncMock(return_value=True))
    monkeypatch.setattr(newsletter_service, "remove_contact", AsyncMock(return_value=True))
    monkeypatch.setattr(newsletter_service, "contact_status", AsyncMock(return_value="to_add"))
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(side_effect=AssertionError("Network forbidden")))
    return redis


def application() -> FastAPI:
    app = FastAPI()
    app.include_router(newsletter.router)
    app.include_router(newsletter_admin.router)
    return app


async def test_confirm_calls_add_once_and_replay_does_not(store: MemoryRedis) -> None:
    store.pending["newsletter:pending:synthetic-token"] = json.dumps({"email": EMAIL, "name": "Fixture"})
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.get("/api/v1/newsletter/confirm/synthetic-token")
        assert response.status_code == 200
        assert "Εγγραφή Επιβεβαιώθηκε!" in response.text
        assert (await client.get("/api/v1/newsletter/confirm/synthetic-token")).status_code == 410
    newsletter_service.add_contact.assert_awaited_once_with(EMAIL, "Fixture")
    assert EMAIL in store.hashes[CONFIRMED_KEY]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]


@pytest.mark.parametrize("raises", [False, True])
async def test_brevo_failure_retains_consent_and_retry_then_backfill_repairs(
    store: MemoryRedis, raises: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    store.pending["newsletter:pending:synthetic-token"] = json.dumps({"email": EMAIL})
    add = newsletter_service.add_contact
    add.return_value = False
    if raises:
        add.side_effect = RuntimeError(f"{EMAIL} synthetic-private-key synthetic-token")
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        assert (await client.get("/api/v1/newsletter/confirm/synthetic-token")).status_code == 200
    assert EMAIL in store.hashes[CONFIRMED_KEY]
    assert store.hashes[BREVO_ADD_RETRY_KEY] == {EMAIL: "1"}
    assert "sync failed" in caplog.text
    for private in (EMAIL, "synthetic-private-key", "synthetic-token"):
        assert private not in caplog.text
    add.side_effect = None
    add.return_value = True
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 1, "already_present": 0, "failed": 0,
    }
    assert not store.hashes[BREVO_ADD_RETRY_KEY]


async def test_dry_run_default_counts_without_mutations(store: MemoryRedis) -> None:
    for index in range(4):
        email = f"fixture{index}@example.org"
        store.hashes[CONFIRMED_KEY][email] = json.dumps({"email": email})
    store.hashes[CONFIRMED_KEY]["invalid@example.org"] = "not-json"
    newsletter_service.contact_status.side_effect = ["to_add", "already_present", "failed", "suppressed"]
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/backfill", headers={
            "Authorization": "Bearer synthetic-admin-key",
        })
    assert response.status_code == 200
    assert response.json() == {"to_add": 1, "already_present": 1, "failed": 3}
    assert "@" not in response.text
    assert store.mutations == []
    newsletter_service.add_contact.assert_not_awaited()
    newsletter_service.remove_contact.assert_not_awaited()


async def test_backfill_idempotent_and_ignores_pending_and_list_only_contacts(store: MemoryRedis) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL, "name": "Fixture"})
    store.pending["newsletter:pending:other-token"] = json.dumps({"email": "pending@example.org"})
    members: set[str] = {"list-only@example.org"}

    async def status(email: str) -> str:
        return "already_present" if email in members else "to_add"

    async def add(email: str, name: str) -> bool:
        members.add(email)
        return True

    newsletter_service.contact_status.side_effect = status
    newsletter_service.add_contact.side_effect = add
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 1, "already_present": 0, "failed": 0,
    }
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 0, "already_present": 1, "failed": 0,
    }
    newsletter_service.add_contact.assert_awaited_once_with(EMAIL, "Fixture")
    assert members == {EMAIL, "list-only@example.org"}


@pytest.mark.parametrize("path", ["/api/v1/admin/newsletter/backfill?dry_run=false", "/api/v1/newsletter/unsubscribe"])
@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "Basic synthetic-admin-key"])
async def test_admin_auth_precedes_io(
    store: MemoryRedis, path: str, authorization: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = AsyncMock(side_effect=AssertionError("Unauthorized I/O"))
    monkeypatch.setattr(newsletter, "_get_redis", redis)
    headers = {"Authorization": authorization} if authorization else {}
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post(path, headers=headers, json={"email": EMAIL})
    assert response.status_code == 403
    redis.assert_not_awaited()


async def test_unsubscribe_propagates_to_both_providers_and_is_idempotent(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL})
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    remove_listmonk = AsyncMock(return_value=True)
    monkeypatch.setattr(newsletter, "_remove_listmonk_contact", remove_listmonk)
    for _ in range(2):
        assert await newsletter.unsubscribe(newsletter.UnsubscribeRequest(email=EMAIL), _auth=True) == {
            "success": True, "message": "Unsubscribed.",
        }
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert store.hashes[SUPPRESSED_KEY][EMAIL] == "unsubscribed"
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert newsletter_service.remove_contact.await_count == remove_listmonk.await_count == 2
    newsletter_service.remove_contact.assert_awaited_with(EMAIL)


async def test_failed_withdrawal_retries_without_readding(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL})
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    listmonk = AsyncMock(side_effect=RuntimeError(f"private {EMAIL}"))
    monkeypatch.setattr(newsletter, "_remove_listmonk_contact", listmonk)
    newsletter_service.remove_contact.return_value = False
    await newsletter.unsubscribe(newsletter.UnsubscribeRequest(email=EMAIL), _auth=True)
    assert store.hashes[BREVO_REMOVE_RETRY_KEY] == store.hashes[LISTMONK_REMOVE_RETRY_KEY] == {EMAIL: "1"}
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert EMAIL not in caplog.text
    # Dry-run never attempts pending removals.
    newsletter_service.remove_contact.reset_mock()
    await newsletter_admin.newsletter_backfill(_auth=True)
    newsletter_service.remove_contact.assert_not_awaited()
    newsletter_service.remove_contact.return_value = True
    listmonk.side_effect = None
    listmonk.return_value = True
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 0, "already_present": 0, "failed": 0,
    }
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    newsletter_service.add_contact.assert_not_awaited()


@pytest.mark.parametrize("event", ["unsubscribed", "unsubscribe", "hardBounce", "hard_bounce", "spam", "complaint"])
async def test_authenticated_webhook_withdraws_consent(store: MemoryRedis, event: str) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL})
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/newsletter/webhook/brevo", headers={
            "Authorization": "Bearer synthetic-webhook-token",
        }, json={"event": event, "email": EMAIL})
    assert response.json() == {"received": True, "events": 1}
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    newsletter_service.remove_contact.assert_awaited_once_with(EMAIL)
    if event in ("unsubscribe", "unsubscribed"):
        assert store.hashes["newsletter:events"]["unsubscribed"] == "1"


@pytest.mark.parametrize("timeout", [False, True])
async def test_withdrawal_during_add_is_compensated(store: MemoryRedis, timeout: bool) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL})

    async def add(email: str, name: str) -> bool:
        await newsletter._withdraw_subscription(store, email, "unsubscribed")
        if timeout:
            raise httpx.ReadTimeout("synthetic timeout after provider accepted add")
        return True

    newsletter_service.add_contact.side_effect = add
    assert await newsletter._sync_brevo_contact(store, EMAIL) is False
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert newsletter_service.remove_contact.await_count == 2


async def test_withdrawal_matches_provider_casing_and_blocks_old_pending_link(store: MemoryRedis) -> None:
    original = EMAIL.upper()
    store.hashes[CONFIRMED_KEY][original] = json.dumps({"email": original})
    await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
    assert not store.hashes[CONFIRMED_KEY]
    store.pending["newsletter:pending:old-token"] = json.dumps({"email": original})
    assert (await newsletter.confirm_subscription("old-token")).status_code == 200
    assert not store.hashes[CONFIRMED_KEY]
    newsletter_service.add_contact.assert_not_awaited()


async def test_pending_link_after_withdrawal_cannot_reactivate(store: MemoryRedis) -> None:
    store.hashes[SUPPRESSED_KEY][EMAIL] = "unsubscribed"
    store.pending["newsletter:pending:old-token"] = json.dumps({"email": EMAIL})
    assert (await newsletter.confirm_subscription("old-token")).status_code == 200
    newsletter_service.add_contact.assert_not_awaited()
    assert EMAIL not in store.hashes[CONFIRMED_KEY]


def mock_provider(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", "synthetic-private-key")
    monkeypatch.setattr(newsletter_service, "LIST_ID", 9)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: HTTP_CLIENT(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize("suppression", [{"emailBlacklisted": True}, {"listUnsubscribed": [9]}])
async def test_provider_suppression_never_reactivated(
    monkeypatch: pytest.MonkeyPatch, suppression: dict,
) -> None:
    def provider(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"email": EMAIL, "listIds": [9], "emailBlacklisted": False, **suppression})

    mock_provider(monkeypatch, provider)
    assert await newsletter_service.add_contact(EMAIL) is False


async def test_real_service_add_and_remove_payloads_and_removal_idempotence(monkeypatch: pytest.MonkeyPatch) -> None:
    members: set[str] = set()
    writes: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.raw_path.endswith(b"subscriber%2Bfixture%40example.org")
            return httpx.Response(200, json={"email": EMAIL, "listIds": [9] if EMAIL in members else [],
                                           "emailBlacklisted": False})
        writes.append(request)
        body = json.loads(request.content)
        if request.url.path == "/v3/contacts":
            assert body == {"email": EMAIL, "attributes": {"FIRSTNAME": "Fixture"}, "listIds": [9], "updateEnabled": True}
            members.add(EMAIL)
            return httpx.Response(201, json={"id": 123})
        assert request.url.path == "/v3/contacts/lists/9/contacts/remove"
        assert body == {"emails": [EMAIL]}
        members.remove(EMAIL)
        return httpx.Response(201, json={"contacts": {"success": [EMAIL], "failure": []}})

    mock_provider(monkeypatch, provider)
    assert await newsletter_service.add_contact(EMAIL, "Fixture") is True
    assert await newsletter_service.add_contact(EMAIL, "Fixture") is True
    assert await newsletter_service.remove_contact(EMAIL) is True
    assert await newsletter_service.remove_contact(EMAIL) is True
    assert len(writes) == 2


@pytest.mark.parametrize("failure", ["404", "500", "redirect", "timeout", "invalid_json"])
async def test_contact_lookup_failures_private_and_no_unsafe_write(
    monkeypatch: pytest.MonkeyPatch, failure: str, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    requests: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(500, text=f"private {EMAIL} synthetic-private-key")
        if failure == "timeout":
            raise httpx.ReadTimeout(f"private {EMAIL} synthetic-private-key", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text=f"private {EMAIL}")
        if failure == "redirect":
            return httpx.Response(307, headers={"Location": f"https://outside.invalid/{EMAIL}"})
        return httpx.Response(int(failure), text=f"private {EMAIL}")

    mock_provider(monkeypatch, provider)
    assert await newsletter_service.add_contact(EMAIL) is False
    assert len(requests) == (2 if failure == "404" else 1)
    for private in (EMAIL, "example.org", "synthetic-private-key", "outside.invalid"):
        assert private not in caplog.text


async def test_listmonk_blocklist_uses_exact_escaped_identity_in_body(monkeypatch: pytest.MonkeyPatch) -> None:
    request = AsyncMock(return_value={"data": True})
    monkeypatch.setattr(newsletter, "_listmonk_request", request)
    assert await newsletter._remove_listmonk_contact("o'hara@example.org") is True
    request.assert_awaited_once_with("PUT", "/api/subscribers/query/blocklist", {
        "query": "lower(subscribers.email) = lower('o''hara@example.org')",
    })

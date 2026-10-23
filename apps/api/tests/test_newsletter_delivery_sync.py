"""Consent-to-delivery boundary, using only in-memory stores and HTTP transports."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from redis.exceptions import ConnectionError as RedisConnectionError, ResponseError

from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_lock import RENEW_LOCK, RELEASE_LOCK, NewsletterLockUnavailable
from services.newsletter_claims import WRITE_CLAIM
from services.newsletter_consent import (
    CONFIRMED_KEY, CONFIRM_ONCE, SUPPRESSED_KEY, BREVO_ADD_RETRY_KEY,
    BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY, WITHDRAW_CONSENT,
    BREVO_ADD_UNSETTLED_KEY, QUEUE_BREVO_ADD, QUEUE_DELIVERY_REMOVAL, TOPICS,
    LISTMONK_ADD_UNSETTLED_KEY, QUEUE_LISTMONK_ADD, preference_attributes,
    UPDATE_PREFERENCES,
)

EMAIL = "subscriber+fixture@example.org"
HTTP_CLIENT = httpx.AsyncClient
REMOVE_CONTACT = newsletter_service.remove_contact
CONTACT_STATUS = newsletter_service.contact_status
ADD_CONTACT = newsletter_service.add_contact


def consent(email: str = EMAIL, **changes: Any) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "email": email, "name": "Fixture", "consent_schema": 2,
        "requested_at": (now - timedelta(minutes=5)).isoformat(),
        "confirmed_at": now.isoformat(), "confirmation_method": "double_opt_in",
        "frequency": "monthly", "language": "el", "subscriber_type": "citizens",
        "topics": {topic: topic == "active_votes" for topic in TOPICS}, **changes,
    }


class MemoryRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self.pending: dict[str, str] = {}
        self.mutations: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.pending.get(key)

    async def set(self, key: str, value: str, *, nx: bool = False, px: int = 0):
        if nx and key in self.pending:
            return None
        self.pending[key] = value
        return True

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
        if script in (RENEW_LOCK, RELEASE_LOCK):
            key, owner = args[:2]
            if self.pending.get(key) != owner:
                return 0
            if script == RELEASE_LOCK:
                self.pending.pop(key)
            return 1
        self.mutations.append("eval")
        if script == WRITE_CLAIM:
            lock, claims, owner, key, previous, updated = args
            if self.pending.get(lock) != owner or self.hashes[claims].get(key, "") != previous:
                return 0
            self.hashes[claims][key] = updated
            return 1
        if script == UPDATE_PREFERENCES:
            confirmed, suppressed, retry, email, normalized, raw, updated = args
            if normalized in self.hashes[suppressed] or self.hashes[confirmed].get(email) != raw:
                return 0
            self.hashes[confirmed][email] = updated
            self.hashes[retry][email] = "1"
            return 1
        if script == CONFIRM_ONCE:
            pending_key, confirmed_key, retry, raw, email, confirmed = args
            if self.pending.get(pending_key) != raw:
                return 0
            self.pending.pop(pending_key)
            if email in self.hashes[confirmed_key]:
                return 2
            self.hashes[retry][email] = "1"
            self.hashes[confirmed_key][email] = confirmed
            return 1
        if script == QUEUE_BREVO_ADD:
            confirmed, suppressed, retry, removal, unsettled, email, raw, normalized = args
            if (normalized in self.hashes[suppressed] or self.hashes[confirmed].get(email) != raw
                    or email in self.hashes[removal] or normalized in self.hashes[unsettled]):
                return 0
            self.hashes[retry][email] = "1"
            self.hashes[unsettled][normalized] = "pending"
            return 1
        if script == QUEUE_DELIVERY_REMOVAL:
            add_retry, brevo_retry, listmonk_retry, email, configured = args
            self.hashes[add_retry].pop(email, None)
            self.hashes[brevo_retry][email] = "1"
            if configured == "1":
                self.hashes[listmonk_retry][email] = "1"
            return 1
        if script == QUEUE_LISTMONK_ADD:
            assert numkeys == 4
            confirmed, suppressed, removal, unsettled, email, raw, normalized = args
            if (normalized in self.hashes[suppressed] or self.hashes[confirmed].get(email) != raw
                    or email in self.hashes[removal] or normalized in self.hashes[unsettled]):
                return 0
            self.hashes[unsettled][normalized] = "pending"
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


@pytest.mark.parametrize("dry_run,failure", [
    (True, "connect"), (False, "connect"), (True, "confirmed"), (False, "confirmed"),
    (False, "brevo_retry"), (False, "listmonk_retry"),
])
@pytest.mark.parametrize("error_type", [RedisConnectionError, ResponseError])
async def test_backfill_initial_redis_failure_returns_sanitized_503_without_provider_io(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    dry_run: bool, failure: str, error_type: type[Exception],
) -> None:
    private = f"redis://private-user:private-password@localhost/0 {EMAIL}"
    if failure == "connect":
        monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(side_effect=error_type(private)))
    elif failure == "confirmed":
        store.hgetall = AsyncMock(side_effect=error_type(private))
    else:
        failed_key = BREVO_REMOVE_RETRY_KEY if failure == "brevo_retry" else LISTMONK_REMOVE_RETRY_KEY

        async def scan(key: str) -> list[str]:
            if key == failed_key:
                raise error_type(private)
            return [EMAIL]

        store.hkeys = AsyncMock(side_effect=scan)
    store.hashes[BREVO_REMOVE_RETRY_KEY][EMAIL] = "1"
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    listmonk_remove = AsyncMock(return_value=True)
    monkeypatch.setattr(newsletter, "_remove_listmonk_contact", listmonk_remove)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/backfill", params={"dry_run": dry_run},
                                     headers={"Authorization": "Bearer synthetic-admin-key"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Newsletter store unavailable; retry"}
    for value in (EMAIL, "private-user", "private-password"):
        assert value not in response.text + caplog.text
    assert not store.mutations
    newsletter_service.contact_status.assert_not_awaited()
    newsletter_service.add_contact.assert_not_awaited()
    newsletter_service.remove_contact.assert_not_awaited()
    listmonk_remove.assert_not_awaited()


@pytest.mark.parametrize("failed_key", [BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY])
@pytest.mark.parametrize("completed_withdrawals", [0, 1])
@pytest.mark.parametrize("error_type", [RedisConnectionError, ResponseError])
async def test_backfill_withdrawal_redis_failure_returns_sanitized_503_and_retains_retries(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    failed_key: str, completed_withdrawals: int, error_type: type[Exception],
) -> None:
    private = f"redis://private-user:private-password@localhost/0 {EMAIL}"
    emails = {EMAIL, "another-subscriber@example.org"}
    store.hashes[failed_key].update({email: "1" for email in emails})
    original_hget = store.hget
    reads = 0

    async def failing_hget(key: str, field: str) -> str | None:
        nonlocal reads
        if key == failed_key:
            reads += 1
            if reads > completed_withdrawals:
                raise error_type(private)
        return await original_hget(key, field)

    monkeypatch.setattr(store, "hget", failing_hget)
    listmonk_remove = AsyncMock(return_value=True)
    monkeypatch.setattr(newsletter, "_remove_listmonk_contact", listmonk_remove)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/backfill", params={"dry_run": False},
                                     headers={"Authorization": "Bearer synthetic-admin-key"})

        assert response.status_code == 503
        assert response.json() == {"detail": "Newsletter store unavailable; retry"}
        for value in (*emails, "private-user", "private-password"):
            assert value not in response.text + caplog.text
        assert len(store.hashes[failed_key]) == len(emails) - completed_withdrawals
        assert set(store.hashes[failed_key]) <= emails
        assert newsletter_service.remove_contact.await_count + listmonk_remove.await_count == completed_withdrawals
        newsletter_service.contact_status.assert_not_awaited()
        newsletter_service.add_contact.assert_not_awaited()

        monkeypatch.setattr(store, "hget", original_hget)
        retried = await client.post("/api/v1/admin/newsletter/backfill", params={"dry_run": False},
                                    headers={"Authorization": "Bearer synthetic-admin-key"})

    assert retried.status_code == 200
    assert retried.json() == {"to_add": 0, "already_present": 0, "held": 0, "failed": 0}
    assert not store.hashes[failed_key]
    assert newsletter_service.remove_contact.await_count + listmonk_remove.await_count == len(emails)
    newsletter_service.add_contact.assert_not_awaited()


async def test_confirm_calls_add_once_and_replay_does_not(store: MemoryRedis) -> None:
    store.pending["newsletter:pending:synthetic-token"] = json.dumps(consent())
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.get("/api/v1/newsletter/confirm/synthetic-token")
        assert response.status_code == 200
        assert "Εγγραφή Επιβεβαιώθηκε!" in response.text
        assert (await client.get("/api/v1/newsletter/confirm/synthetic-token")).status_code == 410
    newsletter_service.add_contact.assert_awaited_once_with(EMAIL, "Fixture", preferences=json.loads(store.hashes[CONFIRMED_KEY][EMAIL]))
    assert EMAIL in store.hashes[CONFIRMED_KEY]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]


@pytest.mark.parametrize("raises", [False, True])
async def test_brevo_failure_retains_consent_and_retry_then_backfill_repairs(
    store: MemoryRedis, raises: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    store.pending["newsletter:pending:synthetic-token"] = json.dumps(consent())
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
    # Reconcile the uncertain original request through a positive provider read.
    newsletter_service.contact_status.return_value = "already_present"
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 0, "already_present": 1, "held": 0, "failed": 0,
    }
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]


async def test_dry_run_default_counts_without_mutations(store: MemoryRedis) -> None:
    for index in range(4):
        email = f"fixture{index}@example.org"
        store.hashes[CONFIRMED_KEY][email] = json.dumps(consent(email))
    store.hashes[CONFIRMED_KEY]["invalid@example.org"] = "not-json"
    newsletter_service.contact_status.side_effect = ["to_add", "already_present", "failed", "suppressed"]
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/backfill", headers={
            "Authorization": "Bearer synthetic-admin-key",
        })
    assert response.status_code == 200
    assert response.json() == {"to_add": 1, "already_present": 1, "held": 0, "failed": 3}
    assert "@" not in response.text
    assert store.mutations == []
    newsletter_service.add_contact.assert_not_awaited()
    newsletter_service.remove_contact.assert_not_awaited()


async def test_backfill_idempotent_and_ignores_pending_and_list_only_contacts(store: MemoryRedis) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    store.pending["newsletter:pending:other-token"] = json.dumps({"email": "pending@example.org"})
    members: set[str] = {"list-only@example.org"}

    async def status(email: str, **kwargs: Any) -> str:
        return "already_present" if email in members else "to_add"

    async def add(email: str, name: str, **kwargs: Any) -> bool:
        members.add(email)
        return True

    newsletter_service.contact_status.side_effect = status
    newsletter_service.add_contact.side_effect = add
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 1, "already_present": 0, "held": 0, "failed": 0,
    }
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 0, "already_present": 1, "held": 0, "failed": 0,
    }
    newsletter_service.add_contact.assert_awaited_once_with(EMAIL, "Fixture", preferences=json.loads(store.hashes[CONFIRMED_KEY][EMAIL]))
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
        "to_add": 0, "already_present": 0, "held": 0, "failed": 0,
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
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())

    async def add(email: str, name: str, **kwargs: Any) -> bool:
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


@pytest.mark.parametrize("source", ["sync", "backfill"])
@pytest.mark.parametrize("failure", [
    "lookup_503", "lookup_timeout", "unconfigured", "connect", "connect_timeout", "pool_timeout", "rejected",
])
async def test_brevo_prewrite_failure_can_retry_after_healthy_absent_lookup(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, source: str, failure: str,
) -> None:
    raw = json.dumps(consent())
    store.hashes[CONFIRMED_KEY][EMAIL] = raw
    monkeypatch.setattr(newsletter_service, "add_contact", ADD_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    requests: list[str] = []
    failed = failure == "unconfigured"

    def provider(request: httpx.Request) -> httpx.Response:
        nonlocal failed
        requests.append(request.method)
        if request.method == "GET":
            if not failed and failure.startswith("lookup") and (source == "sync" or len(requests) == 2):
                failed = True
                if failure == "lookup_timeout":
                    raise httpx.ReadTimeout("synthetic lookup timeout", request=request)
                return httpx.Response(503)
            return httpx.Response(404)
        assert request.method == "POST"
        if not failed:
            failed = True
            if failure == "rejected":
                return httpx.Response(401)
            error = {"connect": httpx.ConnectError, "connect_timeout": httpx.ConnectTimeout,
                     "pool_timeout": httpx.PoolTimeout}[failure]
            raise error("synthetic failure before send", request=request)
        return httpx.Response(201, json={"id": 123})

    mock_provider(monkeypatch, provider)
    if failure == "unconfigured":
        monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", "")
    if source == "sync":
        assert await newsletter._sync_brevo_contact(store, EMAIL) is False
    else:
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
    assert store.hashes[CONFIRMED_KEY][EMAIL] == raw
    # Backfill can fail its initial lookup before queueing an enrollment.
    assert store.hashes[BREVO_ADD_RETRY_KEY] == ({} if source == "backfill" and failure == "unconfigured"
                                               else {EMAIL: "1"})
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]
    assert requests.count("POST") == (0 if failure.startswith("lookup") or failure == "unconfigured" else 1)

    monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", "synthetic-private-key")
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 1, "already_present": 0, "held": 0, "failed": 0,
    }
    assert requests[-3:] == ["GET", "GET", "POST"]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]


@pytest.mark.parametrize("failure", ["read_timeout", "write_timeout", "503"])
async def test_brevo_indeterminate_post_stays_uncertain_until_positive_lookup(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    monkeypatch.setattr(newsletter_service, "add_contact", ADD_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    present = False
    writes = 0

    def provider(request: httpx.Request) -> httpx.Response:
        nonlocal writes
        if request.method == "GET":
            if present:
                return httpx.Response(200, json={"email": EMAIL, "listIds": [9], "emailBlacklisted": False,
                                                "attributes": preference_attributes(json.loads(store.hashes[CONFIRMED_KEY][EMAIL]))})
            return httpx.Response(404)
        writes += 1
        assert request.method == "POST"
        if failure == "503":
            return httpx.Response(503)
        error = httpx.ReadTimeout if failure == "read_timeout" else httpx.WriteTimeout
        raise error("synthetic timeout after send", request=request)

    mock_provider(monkeypatch, provider)
    assert await newsletter._sync_brevo_contact(store, EMAIL) is False
    for _ in range(2):
        assert store.hashes[BREVO_ADD_UNSETTLED_KEY] == {EMAIL: "uncertain"}
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
    assert writes == 1
    present = True
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["already_present"] == 1
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert writes == 1


@pytest.mark.parametrize("failure", ["unconfigured", "connect", "connect_timeout", "pool_timeout", "rejected"])
async def test_listmonk_prewrite_failure_leaves_enrollment_retryable(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    raw = json.dumps(consent())
    store.hashes[CONFIRMED_KEY][EMAIL] = raw
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "" if failure == "unconfigured" else "synthetic-password")
    writes = 0

    def provider(request: httpx.Request) -> httpx.Response:
        nonlocal writes
        assert request.method == "POST" and request.url.path == "/api/subscribers"
        writes += 1
        if writes == 1 and failure != "unconfigured":
            if failure == "rejected":
                return httpx.Response(401)
            error = {"connect": httpx.ConnectError, "connect_timeout": httpx.ConnectTimeout,
                     "pool_timeout": httpx.PoolTimeout}[failure]
            raise error("synthetic failure before send", request=request)
        return httpx.Response(200, json={"data": {"id": 123}})

    mock_provider(monkeypatch, provider)
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is False
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    assert store.hashes[CONFIRMED_KEY][EMAIL] == raw
    assert writes == (0 if failure == "unconfigured" else 1)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is True
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    assert writes == (1 if failure == "unconfigured" else 2)


@pytest.mark.parametrize("failure", ["read_timeout", "write_timeout", "503"])
async def test_listmonk_indeterminate_post_requires_positive_withdrawal_reconciliation(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    present = False
    writes: list[str] = []
    fail_lookup = True

    def provider(request: httpx.Request) -> httpx.Response:
        nonlocal present, fail_lookup
        if request.method == "GET":
            if fail_lookup:
                fail_lookup = False
                return httpx.Response(503)
            return httpx.Response(200, json={"data": {"results": [{"email": EMAIL}] if present else []}})
        writes.append(request.method)
        if request.method == "PUT":
            present = False
            return httpx.Response(200, json={"data": True})
        assert request.method == "POST"
        if failure == "503":
            return httpx.Response(503)
        error = httpx.ReadTimeout if failure == "read_timeout" else httpx.WriteTimeout
        raise error("synthetic timeout after send", request=request)

    mock_provider(monkeypatch, provider)
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is False
    assert await newsletter._sync_listmonk_contact(store, EMAIL) is False
    assert writes == ["POST"]
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed") is False
    for _ in range(2):
        assert store.hashes[LISTMONK_ADD_UNSETTLED_KEY] == {EMAIL: "uncertain"}
        assert store.hashes[LISTMONK_REMOVE_RETRY_KEY] == {EMAIL: "1"}
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
    present = True
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 0
    assert not present
    assert writes == ["POST", "PUT"]
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert not store.hashes[CONFIRMED_KEY]


@pytest.mark.parametrize("provider_name", ["brevo", "listmonk"])
async def test_withdrawal_during_prewrite_failure_clears_unsettled_work(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, provider_name: str,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    is_brevo = provider_name == "brevo"
    unsettled_key = BREVO_ADD_UNSETTLED_KEY if is_brevo else LISTMONK_ADD_UNSETTLED_KEY
    sync = newsletter._sync_brevo_contact if is_brevo else newsletter._sync_listmonk_contact
    monkeypatch.setattr(newsletter_service, "add_contact", ADD_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "" if is_brevo else "synthetic-password")

    async def provider(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(200, json={"data": True})
        assert request.method == ("GET" if is_brevo else "POST")
        await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
        assert store.hashes[unsettled_key] == {EMAIL: "pending"}
        if is_brevo:
            return httpx.Response(503)
        raise httpx.ConnectError("synthetic failure before send", request=request)

    mock_provider(monkeypatch, provider)
    assert await sync(store, EMAIL) is False
    assert not store.hashes[CONFIRMED_KEY]
    assert store.hashes[SUPPRESSED_KEY] == {EMAIL: "suppressed"}
    assert not store.hashes[unsettled_key]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 0


@pytest.mark.parametrize("suppression", [{"emailBlacklisted": True}, {"listUnsubscribed": [9]}])
async def test_provider_suppression_never_reactivated(
    monkeypatch: pytest.MonkeyPatch, suppression: dict,
) -> None:
    def provider(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"email": EMAIL, "listIds": [9], "emailBlacklisted": False, **suppression})

    mock_provider(monkeypatch, provider)
    with pytest.raises(newsletter_service.ContactSuppressed):
        await newsletter_service.add_contact(EMAIL)


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
            assert body == {"email": EMAIL, "attributes": {}, "listIds": [9], "updateEnabled": True}
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
    if failure == "404":
        assert await newsletter_service.add_contact(EMAIL) is False
    else:
        with pytest.raises(newsletter_service.ContactNotWritten):
            await newsletter_service.add_contact(EMAIL)
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


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("change", [
    {"consent_schema": 1}, {"consent_schema": "2"}, {"requested_at": None},
    {"confirmation_method": "import"}, {"confirmed_at": None},
    {"requested_at": "2026-01-01T00:00:00+00:00"},
    {"confirmed_at": "2099-01-01T00:00:00+00:00"},
    {"requested_at": "2026-01-01T00:00:00"},
])
async def test_backfill_holds_invalid_doi_without_enrollment_or_identity_disclosure(
    store: MemoryRedis, dry_run: bool, change: dict, caplog: pytest.LogCaptureFixture,
) -> None:
    raw = json.dumps(consent(**change))
    store.hashes[CONFIRMED_KEY][EMAIL] = raw
    result = await newsletter_admin.newsletter_backfill(dry_run=dry_run, _auth=True)
    assert result == {"to_add": 0, "already_present": 0, "held": 1, "failed": 0}
    assert store.hashes[CONFIRMED_KEY][EMAIL] == raw
    newsletter_service.add_contact.assert_not_awaited()
    newsletter_service.contact_status.assert_not_awaited()
    assert (newsletter_service.remove_contact.await_count == 1) is (not dry_run)
    if dry_run:
        assert store.mutations == []
    assert EMAIL not in json.dumps(result) + caplog.text


async def test_email_only_backfill_is_held_and_previous_enrollment_removed(store: MemoryRedis) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({"email": EMAIL})
    assert (await newsletter_admin.newsletter_backfill(_auth=True))["held"] == 1
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["held"] == 1
    newsletter_service.add_contact.assert_not_awaited()
    newsletter_service.remove_contact.assert_awaited_once_with(EMAIL)


@pytest.mark.parametrize("source", ["confirmation", "backfill", "sync"])
@pytest.mark.parametrize("topics", [{topic: False for topic in TOPICS}, {"active_votes": "yes"}, {}])
async def test_ineligible_topics_never_enable_either_provider_and_remove_existing_delivery(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, source: str, topics: dict,
) -> None:
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    listmonk = AsyncMock(return_value={})
    blocklist = AsyncMock(return_value=True)
    monkeypatch.setattr(newsletter, "_listmonk_request", listmonk)
    monkeypatch.setattr(newsletter, "_remove_listmonk_contact", blocklist)
    raw = json.dumps(consent(topics=topics))
    if source == "confirmation":
        store.pending["newsletter:pending:no-topics"] = raw
        assert (await newsletter.confirm_subscription("no-topics")).status_code == 200
    else:
        store.hashes[CONFIRMED_KEY][EMAIL] = raw
        if source == "backfill":
            assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["held"] == 1
        else:
            assert await newsletter._sync_brevo_contact(store, EMAIL) is False
    newsletter_service.add_contact.assert_not_awaited()
    listmonk.assert_not_awaited()
    newsletter_service.remove_contact.assert_awaited_once_with(EMAIL)
    blocklist.assert_awaited_once_with(EMAIL)
    assert EMAIL in store.hashes[CONFIRMED_KEY]


@pytest.mark.parametrize("listmonk", [False, True])
async def test_suppression_lookup_failure_after_confirmation_preserves_success_and_skips_delivery(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, listmonk: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    store.pending["newsletter:pending:redis-outage"] = json.dumps(consent())
    if listmonk:
        monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    optional = AsyncMock()
    monkeypatch.setattr(newsletter, "_listmonk_request", optional)
    original_hget = store.hget

    async def failed_suppression_lookup(key, field):
        if key == SUPPRESSED_KEY:
            raise RuntimeError(f"private redis error {EMAIL}")
        return await original_hget(key, field)

    store.hget = AsyncMock(side_effect=failed_suppression_lookup)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.get("/api/v1/newsletter/confirm/redis-outage")
    assert response.status_code == 200
    assert EMAIL in store.hashes[CONFIRMED_KEY]
    assert "newsletter:pending:redis-outage" not in store.pending
    newsletter_service.add_contact.assert_not_awaited()
    optional.assert_not_awaited()
    assert EMAIL not in response.text + caplog.text


@pytest.mark.parametrize("failure", ["connect", "identities", "persist"])
@pytest.mark.parametrize("path,status", [
    ("/api/v1/newsletter/webhook/brevo", 429), ("/api/v1/newsletter/unsubscribe", 503),
])
async def test_withdrawal_persistence_failure_returns_retryable_status_without_counter_writes(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, path: str, status: int,
    failure: str, caplog: pytest.LogCaptureFixture,
) -> None:
    private = f"private redis failure {EMAIL}"
    if failure == "connect":
        monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(side_effect=RuntimeError(private)))
    elif failure == "identities":
        store.hkeys = AsyncMock(side_effect=RuntimeError(private))
    else:
        store.eval = AsyncMock(side_effect=RuntimeError(private))
    store.hincrby = AsyncMock()
    token = "synthetic-webhook-token" if path.endswith("brevo") else "synthetic-admin-key"
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post(path, headers={"Authorization": f"Bearer {token}"},
                                     json={"event": "unsubscribed", "email": EMAIL})
    assert response.status_code == status
    if status == 429:
        assert response.headers["Retry-After"] == "600"
    store.hincrby.assert_not_awaited()
    assert EMAIL not in response.text + caplog.text
    newsletter_service.remove_contact.assert_not_awaited()


async def test_batch_withdrawals_persist_before_any_statistics_failure(store: MemoryRedis) -> None:
    other = "other@example.org"
    store.hincrby = AsyncMock(side_effect=RuntimeError("synthetic counter outage"))
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/newsletter/webhook/brevo", headers={
            "Authorization": "Bearer synthetic-webhook-token",
        }, json=[{"event": "delivered"}, {"event": "unsubscribe", "email": EMAIL},
                 {"event": "complaint", "email": other}])
    assert response.status_code == 200
    assert store.hashes[SUPPRESSED_KEY] == {EMAIL: "unsubscribed", other: "complaint"}
    assert newsletter_service.remove_contact.await_count == 2


@pytest.mark.parametrize("path", ["/api/v1/newsletter/unsubscribe", "/api/v1/newsletter/subscribe"])
@pytest.mark.parametrize("payload", [
    {"email": "private@example.org invalid"}, {"email": {"private@example.org": "value"}},
    {"email": [EMAIL]}, {"email": EMAIL, "name": {"private@example.org": "invalid"}},
])
async def test_validation_422_never_echoes_submitted_identities(
    store: MemoryRedis, path: str, payload: dict,
) -> None:
    if path.endswith("unsubscribe") and "name" in payload:
        payload = {"email": payload["name"]}
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post(path, headers={"Authorization": "Bearer synthetic-admin-key"}, json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid newsletter request"}
    assert store.mutations == []


async def test_delayed_timed_out_add_keeps_removal_work_until_positive_reconciliation(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    members: set[str] = set()
    # Exercise the real removal helper: "absent" must not settle an uncertain add.
    monkeypatch.setattr(newsletter_service, "remove_contact", REMOVE_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))

    def provider(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"email": EMAIL, "listIds": [9] if EMAIL in members else [],
                                           "emailBlacklisted": False})
        assert request.url.path.endswith("/contacts/remove")
        members.discard(EMAIL)
        return httpx.Response(201, json={"contacts": {"success": [EMAIL]}})

    mock_provider(monkeypatch, provider)

    async def delayed_add(email: str, name: str, **kwargs: Any) -> bool:
        await newsletter._withdraw_subscription(store, email.lower(), "unsubscribed")
        assert store.hashes[BREVO_REMOVE_RETRY_KEY]
        raise httpx.ReadTimeout("synthetic timeout while remote write continues")

    monkeypatch.setattr(newsletter_service, "add_contact", AsyncMock(side_effect=delayed_add))
    assert await newsletter._sync_brevo_contact(store, EMAIL) is False
    for _ in range(2):
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
        assert store.hashes[BREVO_REMOVE_RETRY_KEY] == {EMAIL: "1"}
        assert store.hashes[BREVO_ADD_UNSETTLED_KEY] == {EMAIL: "uncertain"}
    # The provider commits only after every earlier removal returned "absent".
    members.add(EMAIL)
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 0
    assert not members
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]
    assert store.hashes[SUPPRESSED_KEY]
    assert not store.hashes[CONFIRMED_KEY]
    newsletter_service.add_contact.assert_awaited_once()


async def test_concurrent_add_and_withdrawal_retry_after_delivery_lease(store: MemoryRedis) -> None:
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    started, finish = asyncio.Event(), asyncio.Event()

    async def add(email, name, **kwargs):
        started.set()
        await finish.wait()
        return True

    newsletter_service.add_contact.side_effect = add
    task = asyncio.create_task(newsletter._sync_brevo_contact(store, EMAIL))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        with pytest.raises(NewsletterLockUnavailable):
            await newsletter._sync_brevo_contact(store, EMAIL)
        with pytest.raises(NewsletterLockUnavailable):
            await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
        assert store.hashes[BREVO_ADD_UNSETTLED_KEY] == {EMAIL: "pending"}
        assert EMAIL in store.hashes[CONFIRMED_KEY]
        assert not store.hashes[SUPPRESSED_KEY]
    finally:
        finish.set()
        assert await asyncio.wait_for(task, timeout=1) is True
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    newsletter_service.add_contact.assert_awaited_once()
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]


async def test_held_contact_removal_failure_keeps_work_and_consent_for_backfill(store: MemoryRedis) -> None:
    raw = json.dumps(consent(topics={topic: False for topic in TOPICS}))
    store.hashes[CONFIRMED_KEY][EMAIL] = raw
    newsletter_service.remove_contact.return_value = False
    result = await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True)
    assert result["held"] == 1 and result["failed"] == 1
    assert store.hashes[BREVO_REMOVE_RETRY_KEY] == {EMAIL: "1"}
    assert store.hashes[CONFIRMED_KEY][EMAIL] == raw
    newsletter_service.add_contact.assert_not_awaited()


async def test_listmonk_timeout_after_withdrawal_retains_removal_until_late_creation_is_blocklisted(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    store.pending["newsletter:pending:listmonk-timeout"] = json.dumps(consent())
    contacts: dict[str, str] = {}
    calls = []

    async def listmonk(method, path, json_data=None):
        calls.append((method, path, json_data))
        if method == "POST":
            assert store.hashes[LISTMONK_ADD_UNSETTLED_KEY] == {EMAIL: "pending"}
            await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
            # Bulk success for an absent contact cannot settle the pending POST.
            assert store.hashes[LISTMONK_REMOVE_RETRY_KEY] == {EMAIL: "1"}
            raise httpx.ReadTimeout(f"private timeout {EMAIL}")
        if method == "GET":
            return {"data": {"results": [{"email": email, "status": status}
                                         for email, status in contacts.items()]}}
        assert method == "PUT" and path == "/api/subscribers/query/blocklist"
        if EMAIL in contacts:
            contacts[EMAIL] = "blocklisted"
        return {"data": True}

    monkeypatch.setattr(newsletter, "_listmonk_request", listmonk)
    assert (await newsletter.confirm_subscription("listmonk-timeout")).status_code == 200
    assert not store.hashes[CONFIRMED_KEY]
    for _ in range(2):
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
        assert store.hashes[LISTMONK_REMOVE_RETRY_KEY] == {EMAIL: "1"}
        assert store.hashes[LISTMONK_ADD_UNSETTLED_KEY] == {EMAIL: "uncertain"}
    contacts[EMAIL] = "enabled"  # The timed-out creation commits after earlier removals.
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 0
    assert contacts == {EMAIL: "blocklisted"}
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    assert store.hashes[SUPPRESSED_KEY]
    assert sum(method == "POST" for method, _, _ in calls) == 1
    assert EMAIL not in caplog.text


async def test_listmonk_add_and_withdrawal_retry_after_delivery_lease(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(consent())
    started, finish = asyncio.Event(), asyncio.Event()

    async def listmonk(method, path, json_data=None):
        if method == "POST":
            started.set()
            await finish.wait()
        return {"data": True}

    provider = AsyncMock(side_effect=listmonk)
    monkeypatch.setattr(newsletter, "_listmonk_request", provider)
    task = asyncio.create_task(newsletter._sync_listmonk_contact(store, EMAIL))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        with pytest.raises(NewsletterLockUnavailable):
            await newsletter._sync_listmonk_contact(store, EMAIL)
        with pytest.raises(NewsletterLockUnavailable):
            await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
        assert store.hashes[LISTMONK_ADD_UNSETTLED_KEY] == {EMAIL: "pending"}
        assert EMAIL in store.hashes[CONFIRMED_KEY]
        assert not store.hashes[SUPPRESSED_KEY]
    finally:
        finish.set()
        assert await asyncio.wait_for(task, timeout=1) is True
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert not store.hashes[LISTMONK_ADD_UNSETTLED_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert sum(call.args[0] == "POST" for call in provider.await_args_list) == 1


@pytest.mark.parametrize("source", ["confirmation", "backfill", "backfill_add"])
@pytest.mark.parametrize("suppression", [{"emailBlacklisted": True}, {"listUnsubscribed": [9]}])
async def test_detected_provider_suppression_is_persisted_and_withdraws_both_providers(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, source: str, suppression: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    monkeypatch.setattr(newsletter_service, "add_contact", ADD_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    monkeypatch.setattr(newsletter_service, "remove_contact", REMOVE_CONTACT)
    listmonk = AsyncMock(return_value={"data": True})
    monkeypatch.setattr(newsletter, "_listmonk_request", listmonk)
    reads = 0
    writes = []

    def provider(request):
        nonlocal reads
        if request.method == "GET":
            reads += 1
            # Also cover suppression detected by add_contact after backfill's initial read.
            if source == "backfill_add" and reads == 1:
                return httpx.Response(404)
            return httpx.Response(200, json={"email": EMAIL.upper(), "listIds": [9],
                                           "emailBlacklisted": False, **suppression})
        writes.append(request.url.path)
        assert request.url.path.endswith("/contacts/remove")
        return httpx.Response(201, json={"contacts": {"success": [EMAIL]}})

    mock_provider(monkeypatch, provider)
    raw = json.dumps(consent())
    if source == "confirmation":
        store.pending["newsletter:pending:provider-suppression"] = raw
        assert (await newsletter.confirm_subscription("provider-suppression")).status_code == 200
    else:
        store.hashes[CONFIRMED_KEY][EMAIL] = raw
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
    assert store.hashes[SUPPRESSED_KEY] == {EMAIL: "provider_suppressed"}
    assert not store.hashes[CONFIRMED_KEY]
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not store.hashes[BREVO_ADD_UNSETTLED_KEY]
    assert not store.hashes[BREVO_REMOVE_RETRY_KEY]
    assert not store.hashes[LISTMONK_REMOVE_RETRY_KEY]
    assert len(writes) == 1
    listmonk.assert_awaited_once_with("PUT", "/api/subscribers/query/blocklist", {
        "query": f"lower(subscribers.email) = lower('{EMAIL}')",
    })
    # An old pending link must obey the persisted suppression without provider lookup.
    store.pending["newsletter:pending:older-link"] = raw
    assert (await newsletter.confirm_subscription("older-link")).status_code == 200
    assert not store.hashes[CONFIRMED_KEY]
    assert all(call.args[0] == "PUT" for call in listmonk.await_args_list)
    for private in (EMAIL, "example.org", "synthetic-private-key"):
        assert private not in caplog.text


async def test_confirmation_skips_listmonk_if_detected_suppression_cannot_be_persisted(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    store.pending["newsletter:pending:persistence-failure"] = json.dumps(consent())
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    newsletter_service.add_contact.side_effect = newsletter_service.ContactSuppressed()
    monkeypatch.setattr(newsletter, "_withdraw_subscription",
                        AsyncMock(side_effect=RuntimeError(f"private Redis failure {EMAIL}")))
    listmonk = AsyncMock()
    monkeypatch.setattr(newsletter, "_listmonk_request", listmonk)
    assert (await newsletter.confirm_subscription("persistence-failure")).status_code == 200
    listmonk.assert_not_awaited()
    assert EMAIL not in caplog.text


@pytest.mark.parametrize("invalid", ["private@example.org", "synthetic-private-token", "{'email':'private@example.org'}"])
async def test_admin_backfill_invalid_dry_run_has_sanitized_422_without_io(
    store: MemoryRedis, monkeypatch: pytest.MonkeyPatch, invalid: str,
) -> None:
    redis = AsyncMock(side_effect=AssertionError("Invalid request must not access Redis"))
    monkeypatch.setattr(newsletter, "_get_redis", redis)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/backfill", params={"dry_run": invalid},
                                     headers={"Authorization": "Bearer synthetic-admin-key"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid newsletter request"}
    redis.assert_not_awaited()
    newsletter_service.contact_status.assert_not_awaited()
    newsletter_service.add_contact.assert_not_awaited()
    assert not store.mutations


async def test_listmonk_uncertain_removal_lookup_redacts_identity_in_transport_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    calls = []

    def provider(request):
        calls.append(request)
        if request.method == "GET":
            assert request.url.params["query"] == f"lower(subscribers.email) = lower('{EMAIL}')"
            return httpx.Response(200, json={"data": {"results": [{"email": EMAIL}]}})
        assert request.method == "PUT"
        return httpx.Response(200, json={"data": True})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: HTTP_CLIENT(transport=httpx.MockTransport(provider), **kw))
    assert await newsletter._remove_listmonk_contact(EMAIL, require_present=True) is True
    assert len(calls) == 2
    for private in (EMAIL, "example.org", "subscriber%2Bfixture%40example.org"):
        assert private not in caplog.text


async def test_provider_header_tracing_private_using_actual_http_transport(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    import httpcore

    caplog.set_level(logging.DEBUG)
    secret = "synthetic-private-header-key"
    location = f"https://outside.invalid/profile/{EMAIL}?key={secret}"
    traces = []
    written = bytearray()

    class Stream(httpcore.AsyncNetworkStream):
        response = (f"HTTP/1.1 307 Temporary Redirect\r\nLocation: {location}\r\n"
                    f"X-Private: {EMAIL}\r\nContent-Length: 0\r\n\r\n").encode()

        async def read(self, max_bytes, timeout=None):
            response, self.response = self.response, b""
            return response

        async def write(self, buffer, timeout=None):
            written.extend(buffer)

        async def aclose(self):
            pass

        def get_extra_info(self, info):
            return None

    class Backend(httpcore.AsyncNetworkBackend):
        async def connect_tcp(self, *args, **kwargs):
            return Stream()

    async def trace(event, info):
        traces.append((event, info))

    async def attach_trace(request):
        request.extensions["trace"] = trace

    def client(**kwargs):
        transport = httpx.AsyncHTTPTransport(trust_env=False)
        transport._pool._network_backend = Backend()
        return HTTP_CLIENT(transport=transport, event_hooks={"request": [attach_trace]}, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(newsletter_service, "BREVO_API", "http://provider.test/v3")
    monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", secret)
    assert await newsletter_service.contact_status(EMAIL) == "failed"
    assert secret.encode() in written
    headers = [info for event, info in traces if event == "http11.receive_response_headers.complete"]
    assert len(headers) == 1 and location in str(headers)
    for private in (EMAIL, "example.org", "subscriber%2Bfixture%40example.org", location, secret):
        assert private not in caplog.text

"""Real Redis Lua tests on unique local-only keys; no provider calls or flush."""
import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException
import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from routers import newsletter
from services import newsletter_lock
from services.newsletter_consent import (
    CONFIRM_ONCE, READ_CONSENT_SNAPSHOT, START_RECONFIRM, CLAIM_RECONFIRM_SEND,
    CONFIRM_RECONFIRM, EXPIRE_RECONFIRM, FINISH_RECONFIRM_EXPIRY,
)


@pytest.fixture
async def isolated_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[aioredis.Redis, str, str]]:
    url = os.getenv("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL is required for the local Redis integration test")
    if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Newsletter tests require a local Redis, never production")
    client = aioredis.from_url(url, decode_responses=True)
    token = f"synthetic-newsletter-{uuid4().hex}"
    confirmed = f"test:newsletter:confirmed:{uuid4().hex}"
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=client))
    monkeypatch.setattr(newsletter, "CONFIRMED_KEY", confirmed)
    monkeypatch.setattr(newsletter_lock, "LOCK_KEY", f"{confirmed}:campaign-lock")
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    monkeypatch.setattr(newsletter.newsletter_service, "remove_contact", AsyncMock(return_value=True))
    try:
        yield client, token, confirmed
    finally:
        await client.delete(f"newsletter:pending:{token}", f"newsletter:pending:{token}-other", confirmed, f"{confirmed}:campaign-lock")
        await client.aclose()


async def test_twenty_concurrent_clicks_have_one_winner(
    isolated_redis: tuple, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, confirmed = isolated_redis
    original = {"email": "consent@example.org", "frequency": "weekly", "language": "en"}
    await client.set(f"newsletter:pending:{token}", json.dumps(original), ex=60)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    optional_provider = AsyncMock(return_value={"data": True})
    monkeypatch.setattr(newsletter, "_listmonk_request", optional_provider)
    async def click():
        try:
            return await newsletter.confirm_subscription(token)
        except HTTPException as exc:
            assert exc.status_code == 503
            return None

    responses = await asyncio.gather(*[click() for _ in range(20)])
    # Contending workers retry after the winning consent write releases its lease.
    responses = [response if response is not None else await newsletter.confirm_subscription(token)
                 for response in responses]
    assert [response.status_code for response in responses].count(200) == 1
    assert [response.status_code for response in responses].count(410) == 19
    stored = json.loads(await client.hget(confirmed, original["email"]))
    assert all(stored[key] == value for key, value in original.items())
    assert stored["consent_schema"] == 1
    assert await client.exists(f"newsletter:pending:{token}") == 0
    # Legacy proof is preserved, but only a removal may reach the provider.
    optional_provider.assert_awaited_once_with("PUT", "/api/subscribers/query/blocklist", {
        "query": "lower(subscribers.email) = lower('consent@example.org')",
    })


async def test_second_pending_token_cannot_replace_existing_consent(isolated_redis: tuple) -> None:
    client, token, confirmed = isolated_redis
    old = json.dumps({"email": "consent@example.org", "frequency": "monthly", "topics": {"vote_results": False}})
    await client.hset(confirmed, "consent@example.org", old)
    await client.set(f"newsletter:pending:{token}", json.dumps({"email": "consent@example.org", "frequency": "weekly"}), ex=60)
    assert (await newsletter.confirm_subscription(token)).status_code == 200
    assert await client.hget(confirmed, "consent@example.org") == old
    assert await client.exists(f"newsletter:pending:{token}") == 0


async def test_write_failure_preserves_pending_proof(isolated_redis: tuple) -> None:
    client, token, confirmed = isolated_redis
    raw = json.dumps({"email": "consent@example.org"})
    await client.set(f"newsletter:pending:{token}", raw, ex=60)
    await client.set(confirmed, "wrong-type-synthetic-fixture")
    with pytest.raises(ResponseError, match="WRONGTYPE"):
        await newsletter.confirm_subscription(token)
    assert await client.get(f"newsletter:pending:{token}") == raw
    assert await client.ttl(f"newsletter:pending:{token}") > 0


async def test_changed_payload_cannot_confirm_stale_proof(isolated_redis: tuple) -> None:
    client, token, confirmed = isolated_redis
    await client.set(f"newsletter:pending:{token}", "new-payload", ex=60)
    assert await client.eval(CONFIRM_ONCE, 2, f"newsletter:pending:{token}", confirmed,
                             "stale-payload", "consent@example.org", "stale-confirmation") == 0
    assert await client.exists(confirmed) == 0
    assert await client.get(f"newsletter:pending:{token}") == "new-payload"


async def test_read_only_snapshot_is_bounded_and_unchanged(isolated_redis: tuple) -> None:
    client, token, confirmed = isolated_redis
    await client.set(f"newsletter:pending:{token}", "pending-must-not-be-included", ex=60)
    await client.hset(confirmed, mapping={"one@example.org": "one", "two@example.org": "two"})
    before = await client.hgetall(confirmed)
    assert await client.eval_ro(READ_CONSENT_SNAPSHOT, 1, confirmed, 1) == [2]
    snapshot = await client.eval_ro(READ_CONSENT_SNAPSHOT, 1, confirmed, 2)
    assert snapshot[0] == 2
    assert dict(zip(snapshot[1::2], snapshot[2::2])) == before
    assert await client.hgetall(confirmed) == before
    assert await client.get(f"newsletter:pending:{token}") == "pending-must-not-be-included"


@pytest.mark.parametrize("finish", ["confirm", "expire"])
async def test_reconfirmation_lua_has_one_winner_and_durable_cleanup(
    isolated_redis: tuple, finish: str,
) -> None:
    client, _, confirmed = isolated_redis
    registry, suppressed, token, old_token, addition, brevo_retry, listmonk_retry = [
        f"{confirmed}:{suffix}" for suffix in ("registry", "suppressed", "token", "old", "add", "brevo", "listmonk")
    ]
    email = "consent@example.org"
    legacy, invitation, attempted, evidence = "legacy", "invitation", "attempted", "fresh-doi"
    try:
        await client.hset(confirmed, email, legacy)
        args = (START_RECONFIRM, 5, confirmed, suppressed, registry, token, old_token,
                email, email, legacy, "", invitation, int(time.time() * 1000) + 2592000000)
        results = await asyncio.gather(*[client.eval(*args) for _ in range(20)])
        assert results.count(1) == 1 and results.count(0) == 19
        assert await client.ttl(token) > 2591900
        assert await client.eval(CLAIM_RECONFIRM_SEND, 4, confirmed, registry, suppressed, token,
                                 email, email, invitation, attempted) == 1
        assert await client.eval(CLAIM_RECONFIRM_SEND, 4, confirmed, registry, suppressed, token,
                                 email, email, invitation, attempted) == 0
        if finish == "confirm":
            args = (CONFIRM_RECONFIRM, 4, token, confirmed, registry, suppressed,
                    invitation, email, email, attempted, evidence)
            results = await asyncio.gather(*[client.eval(*args) for _ in range(20)])
            assert results.count(1) == 1 and results.count(0) == 19
            assert await client.hget(confirmed, email) == evidence
            assert not await client.hexists(registry, email)
        else:
            args = (EXPIRE_RECONFIRM, 6, confirmed, registry, token, addition, brevo_retry, listmonk_retry,
                    email, email, attempted, "cleanup", "1")
            results = await asyncio.gather(*[client.eval(*args) for _ in range(20)])
            assert results.count(1) == 1 and results.count(0) == 19
            assert not await client.hexists(confirmed, email)
            assert await client.hget(registry, email) == "cleanup"
            assert await client.hget(brevo_retry, email) == await client.hget(listmonk_retry, email) == "1"
            assert await client.eval(FINISH_RECONFIRM_EXPIRY, 1, registry, email, "stale") == 0
            assert await client.eval(FINISH_RECONFIRM_EXPIRY, 1, registry, email, "cleanup") == 1
        assert not await client.exists(token)
    finally:
        await client.delete(registry, suppressed, token, old_token, addition, brevo_retry, listmonk_retry)


async def test_campaign_lease_is_shared_renewed_and_owner_checked(isolated_redis, monkeypatch):
    from services import newsletter_lock
    client, _, confirmed = isolated_redis
    key = f"{confirmed}:campaign-lock"
    monkeypatch.setattr(newsletter_lock, "LOCK_KEY", key)
    monkeypatch.setattr(newsletter_lock, "LOCK_MS", 120)
    other_worker = aioredis.Redis(connection_pool=client.connection_pool)
    try:
        async with newsletter_lock.newsletter_lock(client) as lease:
            with pytest.raises(newsletter_lock.NewsletterLockUnavailable):
                async with newsletter_lock.newsletter_lock(other_worker):
                    pytest.fail("A second worker acquired the campaign lease")
            await asyncio.sleep(.18)
            assert await client.get(key) == lease.owner
            assert await client.pttl(key) > 0
            await client.set(key, "replacement-owner", px=1000)
            with pytest.raises(newsletter_lock.NewsletterLockUnavailable):
                await lease.check()
        assert await client.get(key) == "replacement-owner"
    finally:
        await client.delete(key)
        await other_worker.aclose()


async def test_alias_pruning_cannot_delete_concurrent_fresh_evidence(isolated_redis):
    from services.newsletter_consent import RECONCILE_CONSENT_ALIASES
    client, _, confirmed = isolated_redis
    email, alias = "consent@example.org", "CONSENT@example.org"
    records = {email: "pending", alias: "legacy"}
    await client.hset(confirmed, mapping=records)
    await client.hset(confirmed, alias, "fresh-doi")
    assert await client.eval(RECONCILE_CONSENT_ALIASES, 1, confirmed, json.dumps(records), email) == 0
    assert await client.hget(confirmed, alias) == "fresh-doi"
    records[alias] = "fresh-doi"
    assert await client.eval(RECONCILE_CONSENT_ALIASES, 1, confirmed, json.dumps(records), alias) == 1
    assert await client.hgetall(confirmed) == {alias: "fresh-doi"}


async def test_send_claim_rejects_token_at_absolute_deadline(isolated_redis):
    client, _, confirmed = isolated_redis
    registry, suppressed, token = [f"{confirmed}:{suffix}" for suffix in ("registry", "suppressed", "token")]
    email = "consent@example.org"
    try:
        await client.hset(confirmed, email, "legacy")
        deadline = int(time.time() * 1000) + 2000
        assert await client.eval(START_RECONFIRM, 5, confirmed, suppressed, registry, token, token,
                                 email, email, "legacy", "", "invitation", deadline) == 1
        assert await client.pexpiretime(token) == deadline
        await client.pexpireat(token, int(time.time() * 1000) - 1)
        assert await client.eval(CLAIM_RECONFIRM_SEND, 4, confirmed, registry, suppressed, token,
                                 email, email, "invitation", "attempted") == 0
        assert await client.hget(confirmed, email) == "invitation"
    finally:
        await client.delete(registry, suppressed, token)

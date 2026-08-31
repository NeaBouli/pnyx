"""Real Redis Lua tests on unique local-only keys; no provider calls or flush."""
import asyncio
import json
import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from urllib.parse import urlparse
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from routers import newsletter
from services.newsletter_consent import CONFIRM_ONCE, READ_CONSENT_SNAPSHOT


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
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    try:
        yield client, token, confirmed
    finally:
        await client.delete(f"newsletter:pending:{token}", f"newsletter:pending:{token}-other", confirmed)
        await client.aclose()


async def test_twenty_concurrent_clicks_have_one_winner(
    isolated_redis: tuple, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, confirmed = isolated_redis
    original = {"email": "consent@example.org", "frequency": "weekly", "language": "en"}
    await client.set(f"newsletter:pending:{token}", json.dumps(original), ex=60)
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    optional_provider = AsyncMock(return_value={})
    monkeypatch.setattr(newsletter, "_listmonk_request", optional_provider)
    responses = await asyncio.gather(*[newsletter.confirm_subscription(token) for _ in range(20)])
    assert [response.status_code for response in responses].count(200) == 1
    assert [response.status_code for response in responses].count(410) == 19
    stored = json.loads(await client.hget(confirmed, original["email"]))
    assert all(stored[key] == value for key, value in original.items())
    assert stored["consent_schema"] == 1
    assert await client.exists(f"newsletter:pending:{token}") == 0
    optional_provider.assert_awaited_once()


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

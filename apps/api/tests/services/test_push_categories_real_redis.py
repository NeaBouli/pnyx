"""Data-only push claim against a real Redis: SET NX + owner-checked Lua (T-657)."""
import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import redis.asyncio as aioredis

from services import push_categories as pc

NOW = datetime(2099, 1, 5, 7, 0, tzinfo=timezone.utc)
CAP_KEY = f"push:data_only:count:{NOW.strftime('%Y%m%d%H')}"


@pytest.fixture
async def real_redis(monkeypatch):
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the real Redis claim test")
    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "HOURLY_CAP", 10_000)
    client = aioredis.from_url(redis_url, decode_responses=True)
    keys: list[str] = [CAP_KEY]
    try:
        yield client, keys
    finally:
        await client.delete(*keys)
        await client.aclose()


def _bill(keys):
    bill = SimpleNamespace(id=f"T657-{uuid4().hex}", title_el="t")
    keys.append(f"notified:vote_24h:{bill.id}")
    return bill


@pytest.mark.asyncio
async def test_real_redis_parallel_claims_send_once(real_redis):
    client, keys = real_redis
    bill, sent = _bill(keys), []

    async def send(template_id, payload):
        await asyncio.sleep(0.05)
        sent.append(template_id)
        return {"attempted": 1, "accepted": 1, "failed": 0}

    results = await asyncio.gather(*[pc.push_vote_24h(client, bill, sender=send, now=NOW) for _ in range(10)])
    assert results.count(True) == 1 and len(sent) == 1
    key = f"notified:vote_24h:{bill.id}"
    assert await client.get(key) == "1"
    assert 0 < await client.ttl(key) <= pc.DEDUP_TTL["vote_24h"]


@pytest.mark.asyncio
async def test_real_redis_release_then_retry(real_redis):
    client, keys = real_redis
    bill = _bill(keys)

    async def refused(template_id, payload):
        return {"attempted": 2, "accepted": 0, "failed": 2}

    async def ok(template_id, payload):
        return {"attempted": 2, "accepted": 2, "failed": 0}

    assert await pc.push_vote_24h(client, bill, sender=refused, now=NOW) is False
    assert await client.exists(f"notified:vote_24h:{bill.id}") == 0
    assert await pc.push_vote_24h(client, bill, sender=ok, now=NOW) is True


@pytest.mark.asyncio
async def test_real_redis_settle_keeps_a_foreign_claim(real_redis):
    client, keys = real_redis
    key = f"notified:vote_24h:T657-{uuid4().hex}"
    keys.append(key)
    await client.set(key, "claim:other", ex=60)
    for mode in ("final", "release"):
        assert await client.eval(pc._SETTLE_CLAIM, 1, key, "claim:mine", mode, 60) == 0
    assert await client.get(key) == "claim:other"

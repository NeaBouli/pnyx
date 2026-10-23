"""Run the production Lua scripts against Redis when REDIS_URL is configured."""
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from services import scraper_http
from services.scraper_http import HostCooldown, HostRateLimiter


@pytest.fixture
async def live_host(monkeypatch):
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the scraper Lua integration tests")
    url = f"https://{uuid4().hex}.scraper-test.invalid/"
    async with aioredis.from_url(redis_url, decode_responses=True) as client:
        @asynccontextmanager
        async def connection():
            yield client

        monkeypatch.setattr(scraper_http, "_redis", connection)
        try:
            yield url, client
        finally:
            keys = [key async for key in client.scan_iter(f"scraper:host:{HostRateLimiter._host(url)}:*")]
            if keys:
                await client.delete(*keys)


async def test_lua_backoff_uses_redis_clock_and_survives_worker_restart(live_host, monkeypatch):
    url, client = live_host

    def worker_clock():
        raise AssertionError("Worker wall clock must not control cooldown")

    monkeypatch.setattr(scraper_http, "time", SimpleNamespace(
        time=worker_clock, monotonic=scraper_http.time.monotonic,
    ))
    for count, hours in enumerate((6, 12, 24, 48, 48), start=1):
        limiter = HostRateLimiter()
        await limiter.record(url, 403, {})
        ttl = await client.pttl(limiter._keys(url)[0])
        assert hours * 3600 * 1000 - 2000 <= ttl <= hours * 3600 * 1000
        assert (await HostRateLimiter().status(url))["consecutive_403"] == count
        with pytest.raises(HostCooldown):
            await HostRateLimiter().reserve(url)
        # Model server-side expiry without sleeping through a six-hour block.
        await client.delete(limiter._keys(url)[0])


async def test_lua_lost_commit_ack_and_event_replay_are_idempotent(live_host, monkeypatch):
    url, client = live_host
    original_eval = client.eval
    lost = False

    async def lose_ack(script, *args):
        nonlocal lost
        result = await original_eval(script, *args)
        if script == scraper_http._OUTCOME and not lost:
            lost = True
            raise RedisConnectionError("Acknowledgement lost after commit")
        return result

    monkeypatch.setattr(client, "eval", lose_ack)
    limiter = HostRateLimiter()
    leases = await limiter.reserve(url)
    await limiter.record(url, 403, {}, lease=leases[0])
    await limiter.release(leases)
    before = await limiter.status(url)
    await limiter.record(url, 403, {}, lease=leases[0])
    assert lost and before["consecutive_403"] == 1
    assert await limiter.status(url) == before


async def test_lua_reset_fences_stale_responses_and_release(live_host):
    url, client = live_host
    first, second = HostRateLimiter(), HostRateLimiter()
    await client.set(first._keys(url)[1], "3")
    await first.check_persisted(url)
    await second.check_persisted(url)
    stale = await first.reserve(url)
    with pytest.raises(HostCooldown, match="lease busy"):
        await second.reserve(url)
    # Simulate expiry of an abandoned owner's lease, then a successful reset.
    await client.delete(first._lease_key(url))
    current = await second.reserve(url)
    await first.release(stale)
    assert await client.get(first._lease_key(url)) == current[0].token
    await second.record(url, 200, {}, lease=current[0])
    await second.release(current)
    with pytest.raises(HostCooldown):
        await first.record(url, 403, {}, lease=stale[0])
    await first.record(url, 403, {})
    assert (await second.status(url))["consecutive_403"] == 1
    assert await client.pttl(first._keys(url)[0]) > 6 * 3600 * 1000 - 2000

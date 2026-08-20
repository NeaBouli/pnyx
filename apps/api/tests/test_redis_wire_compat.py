"""Real Redis compatibility coverage for production command shapes."""

import os
from uuid import uuid4

import pytest
import redis
import redis.asyncio as aioredis

from ip_utils import redis_fixed_window_limit


def test_real_redis_monitor_command_shapes() -> None:
    """Cover the synchronous command forms used by the monitor service."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the wire compatibility test")

    prefix = f"test:redis-monitor-wire:{uuid4().hex}"
    lock_key = f"{prefix}:lock"
    state_key = f"{prefix}:state"
    active_key = f"{prefix}:active"
    counter_key = f"{prefix}:counter"
    delete_key = f"{prefix}:delete"
    client = redis.from_url(redis_url, decode_responses=True)

    try:
        assert client.ping() is True
        assert client.set(lock_key, "1", ex=30, nx=True) is True
        assert client.set(lock_key, "2", ex=30, nx=True) is None
        assert client.set(state_key, '{"status":"active"}', ex=30) is True
        assert client.get(state_key) == '{"status":"active"}'
        assert client.sadd(active_key, "one", "two") == 2
        assert client.smembers(active_key) == {"one", "two"}
        assert client.srem(active_key, "one") == 1
        assert client.incr(counter_key) == 1
        assert client.expire(counter_key, 30) is True
        assert client.ttl(counter_key) > 0
        assert client.set(delete_key, "remove", ex=30) is True
        assert client.delete(delete_key) == 1
        assert client.get(delete_key) is None
    finally:
        client.delete(lock_key, state_key, active_key, counter_key, delete_key)
        client.close()


@pytest.mark.asyncio
async def test_real_redis_production_command_shapes() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the wire compatibility test")

    prefix = f"test:redis-wire:{uuid4().hex}"
    keys = {
        "lock": f"{prefix}:lock",
        "value": f"{prefix}:value",
        "counter": f"{prefix}:counter",
        "fixed_window": f"{prefix}:fixed-window",
        "hash": f"{prefix}:hash",
        "list": f"{prefix}:list",
        "quarantine": f"{prefix}:quarantine",
        "pipeline": f"{prefix}:pipeline",
        "scan": f"{prefix}:scan",
    }
    client = aioredis.from_url(redis_url, decode_responses=True)

    try:
        assert await client.ping() is True

        assert await client.set(keys["lock"], "token", nx=True, ex=30) is True
        assert await client.set(keys["lock"], "other", nx=True, ex=30) is None
        release_script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """
        assert int(await client.eval(release_script, 1, keys["lock"], "token")) == 1

        assert await client.setex(keys["value"], 30, "stored") is True
        assert await client.get(keys["value"]) == "stored"
        assert await client.ttl(keys["value"]) > 0
        assert await client.incr(keys["counter"]) == 1
        assert await client.incrby(keys["counter"], 2) == 3
        assert await client.incrbyfloat(keys["counter"], "0.25") == 3.25

        assert await redis_fixed_window_limit(
            client,
            keys["fixed_window"],
            limit=2,
            window_seconds=30,
        ) == 1
        assert await client.ttl(keys["fixed_window"]) > 0

        assert await client.hset(keys["hash"], "field", "value") == 1
        assert await client.hset(keys["hash"], mapping={"other": "two"}) == 1
        assert await client.hgetall(keys["hash"]) == {
            "field": "value",
            "other": "two",
        }
        assert await client.hexists(keys["hash"], "field") is True

        assert await client.rpush(keys["list"], "a", "b") == 2
        quarantine_script = """
        local value = redis.call('lindex', KEYS[1], 0)
        if value then
            redis.call('lrem', KEYS[1], 1, value)
            redis.call('rpush', KEYS[2], value)
            return 1
        end
        return 0
        """
        assert int(
            await client.eval(
                quarantine_script,
                2,
                keys["list"],
                keys["quarantine"],
            )
        ) == 1
        assert await client.lrange(keys["list"], 0, -1) == ["b"]
        assert await client.llen(keys["quarantine"]) == 1

        pipeline = client.pipeline()
        pipeline.set(keys["pipeline"], "one", nx=True)
        pipeline.incrbyfloat(keys["counter"], "0.75")
        assert await pipeline.execute() == [True, 4.0]

        assert await client.set(keys["scan"], "x") is True
        assert [key async for key in client.scan_iter(f"{prefix}:scan*")] == [
            keys["scan"]
        ]
    finally:
        await client.delete(*keys.values())
        await client.aclose()

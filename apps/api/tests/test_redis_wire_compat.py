"""Real Redis compatibility coverage for production command shapes."""

import os
from uuid import uuid4

import pytest
import redis.asyncio as aioredis


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

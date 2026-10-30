"""Cross-worker fences for cached public responses containing bill data."""
import asyncio
from contextlib import asynccontextmanager
import logging

import redis.asyncio as aioredis
from fastapi import HTTPException

from config import settings

logger = logging.getLogger(__name__)
PUBLIC_VISIBILITY_GENERATION_KEY = "public:bill-visibility:generation:v1"


@asynccontextmanager
async def _connection():
    async with aioredis.from_url(
        settings.redis_url, decode_responses=True,
        socket_connect_timeout=0.05, socket_timeout=0.05,
    ) as cache:
        yield cache


async def public_visibility_generation(cache=None):
    """None means unverified: callers must calculate rather than reuse a body."""
    try:
        async with asyncio.timeout(0.1):
            if cache is None:
                async with _connection() as connection:
                    return await public_visibility_generation(connection)
            value = await cache.get(PUBLIC_VISIBILITY_GENERATION_KEY)
            return int(value) if value is not None else 0
    except Exception:
        return None


async def bump_public_visibility_generation(cache):
    """Best effort, after commit; keep the counter persistent across body expiry."""
    try:
        async with asyncio.timeout(0.1):
            await cache.incr(PUBLIC_VISIBILITY_GENERATION_KEY)
    except Exception:
        logger.warning("Public visibility generation invalidation unavailable")


async def with_public_visibility_generation(factory, *, wait_timeout=10):
    """Fence hits and racing fills; None must select an uncached calculation.

    Recheck after work so a fill begun before another worker's commit cannot be
    served as a current generation. Continuous writes have a bounded deadline.
    """
    try:
        async with asyncio.timeout(wait_timeout):
            while True:
                generation = await public_visibility_generation()
                result = await factory(generation)
                current = await public_visibility_generation()
                if generation == current:
                    return result
                await asyncio.sleep(0)
    except TimeoutError as exc:
        raise HTTPException(504, "Fresh public data is temporarily unavailable") from exc

"""Shared commit boundary for writes affecting the representation aggregate."""
import asyncio
import logging

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)
REPRESENTATION_CACHE_PREFIX = "analytics:representation:v1:k"


async def commit_and_invalidate_representation(db) -> None:
    """Preserve commit errors; a cache failure must never fail a committed write."""
    await db.commit()
    await invalidate_representation_cache()


async def invalidate_representation_cache() -> None:
    # Remove every policy variant so switching policy cannot revive stale data.
    try:
        async with aioredis.from_url(
            settings.redis_url, decode_responses=True,
            socket_connect_timeout=0.05, socket_timeout=0.05,
        ) as cache:
            async with asyncio.timeout(0.1):
                async for key in cache.scan_iter(match=f"{REPRESENTATION_CACHE_PREFIX}*"):
                    await cache.delete(key)
    except Exception:
        # The anchored TTL still bounds staleness during outages or racing fills.
        logger.warning("Representation cache invalidation unavailable")

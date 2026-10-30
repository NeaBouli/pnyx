"""Request-time cache policy for bodies governed by small-cell suppression."""
import asyncio
import logging
from time import monotonic
from uuid import uuid4
from weakref import WeakSet

from fastapi import HTTPException

from services.small_cell import small_cell_k


logger = logging.getLogger(__name__)


class ResultCachePolicy:
    def __init__(self):
        self.k = 0
        self.epoch = ""
        self.caches = WeakSet()
        self.purged = {}

    def current(self):
        k = small_cell_k()
        if k != self.k:
            self.k = k
            # Retire Redis namespaces immediately, even if deletion fails or an
            # older fill completes after the purge. Never revive a k=0 body.
            self.epoch = uuid4().hex
            for cache in self.caches:
                cache.clear()
        return self.k, self.epoch

    async def prepare_redis(self, cache, *prefixes):
        policy = self.current()
        if policy[1] and self.purged.get(prefixes) != policy:
            try:
                async with asyncio.timeout(0.1):
                    for prefix in prefixes:
                        async for key in cache.scan_iter(match=f"{prefix}*"):
                            await cache.delete(key)
                if policy == self.current():
                    self.purged[prefixes] = policy
            except Exception:
                # Namespace retirement is the safety fence; retry physical
                # deletion on the next access to this Redis cache family.
                logger.warning("Public result cache policy purge unavailable")
        return policy

    @staticmethod
    def key(base, policy):
        return f"{base}:policy:{policy[1]}" if policy[1] else base


result_cache_policy = ResultCachePolicy()


async def with_result_cache_policy(factory):
    """A policy change during work also requires a fresh response calculation."""
    deadline = monotonic() + 10
    while True:
        policy = result_cache_policy.current()
        result = await factory(policy)
        if policy == result_cache_policy.current():
            return result
        if monotonic() >= deadline:
            raise HTTPException(504, "Fresh public data is temporarily unavailable")
        await asyncio.sleep(0)

"""Small, short-lived caches for released clients sharing public reads."""
from collections import OrderedDict
from time import monotonic

from services.request_work import SingleFlight


class ClientFlowCache:
    """Bound memory and coalesce fills; hits never extend the five-second TTL."""

    def __init__(self, capacity=128, ttl=5):
        self.capacity = capacity
        self.ttl = ttl
        self.entries = OrderedDict()
        self.flights = SingleFlight(capacity=capacity)
        self.generation = 0

    def clear(self):
        self.generation += 1
        self.entries.clear()

    async def get_or_fill(self, key, factory):
        async def fill():
            now = monotonic()
            cached = self.entries.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]
            self.entries.pop(key, None)
            generation = self.generation
            value = await factory()
            # Anchor expiry before work: a slow query cannot prolong staleness.
            if generation == self.generation and now + self.ttl > monotonic():
                self.entries[key] = (now + self.ttl, value)
                self.entries.move_to_end(key)
                while len(self.entries) > self.capacity:
                    self.entries.popitem(last=False)
            return value

        return await self.flights.run(key, fill)


scope_status_cache = ClientFlowCache()
results_cache = ClientFlowCache()


def invalidate_client_flow_caches():
    scope_status_cache.clear()
    results_cache.clear()

"""Small, short-lived caches for released clients sharing public reads."""
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from inspect import signature
from time import monotonic

from fastapi.params import Param
from services.request_work import SingleFlight, WorkSlots, cache_fill_quota, register_public_fill_budget


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
public_caches = {}
_fill_slots = WorkSlots(4)


def public_policy_key():
    """Versioned visibility rules and the live small-cell policy, never identity."""
    from services.bill_visibility import DIAVGEIA_SENSITIVE_PUBLIC_TERMS
    from services.small_cell import small_cell_k
    return ("public-visibility-v1", tuple(DIAVGEIA_SENSITIVE_PUBLIC_TERMS), small_cell_k())


def public_client_cache(*, quota="60/minute"):
    """Cache only explicitly decorated public responses, never signed reads.

    All declared path/query arguments participate, including defaults. Undeclared
    query fields do not affect the handler and are never retained (they may
    contain identity material). Headers, Request and DB sessions are not keys.
    The fill budget is shared across workers and charged only to leaders.
    """
    def decorate(function):
        name = f"{function.__module__}.{function.__name__}"
        cache = public_caches.setdefault(name, ClientFlowCache())
        register_public_fill_budget(name, quota)
        parameters = signature(function)

        @wraps(function)
        async def wrapped(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs)
            bound.apply_defaults()
            values = {}
            for key, value in bound.arguments.items():
                if key in {"db", "request"}:
                    continue
                values[key] = value.default if isinstance(value, Param) else value
            thresholds = tuple((key, function.__globals__[key]) for key in
                               ("K_MIN", "K_ANONYMITY_MIN", "EVALUATION_K_ANONYMITY_MIN")
                               if key in function.__globals__)
            key = (tuple(sorted(values.items())), public_policy_key(), thresholds)

            async def fill():
                async with _fill_slots.slot():
                    await cache_fill_quota(name)
                    return await function(*args, **kwargs)

            # Callers may modify Pydantic models/lists without changing a hit.
            return deepcopy(await cache.get_or_fill(key, fill))

        wrapped.public_cache = cache
        wrapped.public_cache_parameters = frozenset(parameters.parameters) - {"db", "request"}
        return wrapped
    return decorate


def invalidate_client_flow_caches():
    scope_status_cache.clear()
    results_cache.clear()
    for cache in public_caches.values():
        cache.clear()

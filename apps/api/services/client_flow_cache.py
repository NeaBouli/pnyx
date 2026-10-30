"""Small, short-lived caches for released clients sharing public reads."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from inspect import signature
import logging
from time import monotonic

from fastapi import HTTPException
from fastapi.params import Param
from limits import parse
from services.request_work import SingleFlight, WaitingWorkSlots


logger = logging.getLogger(__name__)
_read_slots = WaitingWorkSlots(capacity=32)
_aggregate_slots = WaitingWorkSlots(capacity=8)
SENSITIVE_MAX_STALE = 30
PUBLIC_MAX_STALE = 600


async def with_cache_db(factory):
    """Refreshes own their session; the response may already have closed its DB."""
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        return await factory(db)


class SoftFillBudget:
    """Per-route, per-process telemetry only; never gates a public read."""

    def __init__(self, name, quota):
        self.name = name
        self.quota = parse(quota)
        self.started = monotonic()
        self.count = 0

    def observe(self):
        now = monotonic()
        if now < self.started or now >= self.started + self.quota.get_expiry():
            self.started, self.count = now, 0
        self.count += 1
        if self.count == self.quota.amount + 1:
            logger.info("public_cache event=soft_budget_exceeded route=%s", self.name)


class ClientFlowCache:
    """Bound memory and stale age, and coalesce queued refreshes."""

    def __init__(self, capacity=128, ttl=5, *, max_stale=PUBLIC_MAX_STALE,
                 workers=None, wait_timeout=10):
        self.capacity = capacity
        self.ttl = ttl
        self.max_stale = max_stale
        self.wait_timeout = wait_timeout
        self.entries = OrderedDict()
        self.flights = SingleFlight(capacity=capacity, reject_on_capacity=False, wait_timeout=wait_timeout)
        self.workers = workers or _read_slots
        self.generation = 0

    def clear(self):
        self.generation += 1
        self.entries.clear()

    def invalidate(self, key):
        self.generation += 1
        self.entries.pop(key, None)

    async def check_eligibility(self, validate, *, key=None):
        """Run current request policy even on hits; fence off older fills on denial."""
        try:
            return await validate()
        except HTTPException as exc:
            if exc.status_code in {403, 404, 410}:
                if key is None:
                    self.clear()
                else:
                    self.invalidate(key)
            raise

    async def get_or_fill(self, key, factory, *, background_factory=None, validate=None):
        if validate is not None:
            await self.check_eligibility(validate, key=key)
        generation = self.generation

        async def fill(background=False):
            now = monotonic()
            cached = self.entries.get(key)
            if cached is not None and cached[0] > now:
                return cached

            async def compute():
                started = monotonic()
                try:
                    calculate = (background_factory or factory) if background else factory
                    value = await calculate()
                except Exception as exc:
                    if isinstance(exc, HTTPException) and exc.status_code in {403, 404, 410}:
                        self.invalidate(key)
                    if background:
                        # Do not log exceptions containing SQL parameters or identities.
                        logger.warning("public_cache event=refresh_failed count=1")
                    raise
                # Freshness is anchored before work, never renewed by failures.
                entry = (started + self.ttl, value)
                if generation == self.generation:
                    self.entries[key] = entry
                    self.entries.move_to_end(key)
                    while len(self.entries) > self.capacity:
                        self.entries.popitem(last=False)
                return entry

            return await self.workers.run(compute, background=background)

        cached = self.entries.get(key)
        if cached is not None and monotonic() < cached[0] + self.max_stale:
            if cached[0] <= monotonic():
                self.flights.start((generation, key), lambda: fill(background=True))
            return cached[1]

        async def fresh():
            entry = await self.flights.run((generation, key), fill)
            if entry is WaitingWorkSlots.DEFERRED or monotonic() >= entry[0] + self.max_stale:
                # A deferred background fill never satisfies a foreground read.
                # Nor does a refresh begun before the maximum age window.
                entry = await fill()
            if monotonic() >= entry[0] + self.max_stale:
                raise HTTPException(504, "Fresh public data is temporarily unavailable")
            return entry[1]

        if cached is None:
            return await fresh()
        try:
            return await asyncio.wait_for(fresh(), self.wait_timeout)
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "Fresh public data is temporarily unavailable") from exc


scope_status_cache = ClientFlowCache(max_stale=SENSITIVE_MAX_STALE)
results_cache = ClientFlowCache(max_stale=SENSITIVE_MAX_STALE, workers=_aggregate_slots)
public_caches = {}


def public_policy_key():
    """Versioned visibility rules and the live small-cell policy, never identity."""
    from services.bill_visibility import DIAVGEIA_SENSITIVE_PUBLIC_TERMS
    from services.small_cell import small_cell_k
    return ("public-visibility-v1", tuple(DIAVGEIA_SENSITIVE_PUBLIC_TERMS), small_cell_k())


def public_client_cache(*, quota="600/minute", aggregate=False, validate=None, sensitive=False):
    """Cache only explicitly decorated public responses, never signed reads.

    All declared path/query arguments participate, including defaults. Undeclared
    query fields do not affect the handler and are never retained (they may
    contain identity material). Headers, Request and DB sessions are not keys.
    Validation precedes all cache accounting. Soft budgets only log leaders.
    """
    def decorate(function):
        name = f"{function.__module__}.{function.__name__}"
        cache = public_caches.setdefault(name, ClientFlowCache(
            workers=_aggregate_slots if aggregate else _read_slots,
            max_stale=SENSITIVE_MAX_STALE if sensitive else PUBLIC_MAX_STALE,
        ))
        budget = SoftFillBudget(name, quota)
        parameters = signature(function)

        @wraps(function)
        async def wrapped(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs)
            bound.apply_defaults()
            for key, value in bound.arguments.items():
                if isinstance(value, Param):
                    bound.arguments[key] = value.default
            values = {}
            for key, value in bound.arguments.items():
                if key in {"db", "request"}:
                    continue
                values[key] = value
            thresholds = tuple((key, function.__globals__[key]) for key in
                               ("K_MIN", "K_ANONYMITY_MIN", "EVALUATION_K_ANONYMITY_MIN")
                               if key in function.__globals__)
            key = (tuple(sorted(values.items())), public_policy_key(), thresholds)
            if validate is not None:
                await cache.check_eligibility(lambda: validate(**bound.arguments), key=key)

            async def fill():
                budget.observe()
                return await function(*bound.args, **bound.kwargs)

            async def refresh():
                async def using_db(db):
                    arguments = dict(bound.arguments, db=db)
                    if validate is not None:
                        await cache.check_eligibility(lambda: validate(**arguments), key=key)
                    budget.observe()
                    return await function(**arguments)
                return await with_cache_db(using_db)

            # Callers may modify Pydantic models/lists without changing a hit.
            return deepcopy(await cache.get_or_fill(key, fill, background_factory=refresh))

        wrapped.public_cache = cache
        wrapped.public_fill_budget = budget
        wrapped.public_cache_parameters = frozenset(parameters.parameters) - {"db", "request"}
        return wrapped
    return decorate


def invalidate_client_flow_caches():
    scope_status_cache.clear()
    results_cache.clear()
    for cache in public_caches.values():
        cache.clear()

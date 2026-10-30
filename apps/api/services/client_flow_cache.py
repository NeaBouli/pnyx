"""Small, short-lived caches for released clients sharing public reads."""
import asyncio
from collections import OrderedDict
from functools import wraps
from inspect import signature
import logging
from time import monotonic

from fastapi import HTTPException
from fastapi.params import Param
from limits import parse
from services.request_work import SingleFlight, WaitingWorkSlots
from services.public_visibility_cache import with_public_visibility_generation
from services.public_bill_response import CONTRIBUTOR_KEYS, BILL_SCHEMAS, capture_public_bill_body, serve_public_bill_body
from services import result_cache_policy as result_policy


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
                 workers=None, wait_timeout=10, visibility_sensitive=False, suppression_sensitive=False):
        self.capacity = capacity
        self.ttl = ttl
        self.max_stale = max_stale
        self.wait_timeout = wait_timeout
        self.entries = OrderedDict()
        self.flights = SingleFlight(capacity=capacity, reject_on_capacity=False, wait_timeout=wait_timeout)
        self.workers = workers or _read_slots
        self.generation = 0
        self.visibility_sensitive = visibility_sensitive
        self.public_generation = None
        self.suppression_sensitive = suppression_sensitive
        if suppression_sensitive:
            result_policy.result_cache_policy.caches.add(self)

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
        if self.suppression_sensitive:
            async def under_policy(policy):
                if policy[0] > 0:
                    # Only concurrent requests share work; completed results
                    # never enter entries or stale/background refresh paths.
                    return await self.flights.run(
                        ("uncached", policy, self.generation, key), lambda: self.workers.run(factory),
                    )
                return await self._get_visible_or_fill(key, factory, background_factory=background_factory)
            return await result_policy.with_result_cache_policy(under_policy)
        return await self._get_visible_or_fill(key, factory, background_factory=background_factory)

    async def _get_visible_or_fill(self, key, factory, *, background_factory=None):
        if self.visibility_sensitive:
            async def current(public_generation):
                if public_generation != self.public_generation:
                    self.clear()
                    self.public_generation = public_generation
                return await self._get_or_fill(
                    key, factory, background_factory=background_factory,
                    public_generation=public_generation,
                )
            return await with_public_visibility_generation(current, wait_timeout=self.wait_timeout)
        return await self._get_or_fill(key, factory, background_factory=background_factory)

    async def _get_or_fill(self, key, factory, *, background_factory=None, public_generation=None):
        generation = self.generation
        policy = result_policy.result_cache_policy.current() if self.suppression_sensitive else None

        def lookup():
            entry = self.entries.get(key)
            if entry is not None and self.visibility_sensitive:
                if public_generation is None or entry[2] != public_generation:
                    return None
            return entry

        async def fill(background=False):
            now = monotonic()
            cached = lookup()
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
                if self.visibility_sensitive:
                    entry += (public_generation,)
                policy_current = (not self.suppression_sensitive or (
                    policy == result_policy.result_cache_policy.current() and policy[0] == 0
                ))
                if policy_current and generation == self.generation and (not self.visibility_sensitive or public_generation is not None):
                    self.entries[key] = entry
                    self.entries.move_to_end(key)
                    while len(self.entries) > self.capacity:
                        self.entries.popitem(last=False)
                return entry

            return await self.workers.run(compute, background=background)

        cached = lookup()
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


scope_status_cache = ClientFlowCache(max_stale=SENSITIVE_MAX_STALE, visibility_sensitive=True)
results_cache = ClientFlowCache(max_stale=SENSITIVE_MAX_STALE, workers=_aggregate_slots, visibility_sensitive=True,
                                suppression_sensitive=True)
public_caches = {}


def public_policy_key():
    """Versioned visibility rules and the live small-cell policy, never identity."""
    from services.bill_visibility import DIAVGEIA_SENSITIVE_PUBLIC_TERMS
    from services.small_cell import small_cell_k
    return ("public-visibility-v1", tuple(DIAVGEIA_SENSITIVE_PUBLIC_TERMS), small_cell_k())


def public_client_cache(*, bill_schema, quota="600/minute", aggregate=False, validate=None, sensitive=False,
                        bill_candidates=None):
    """Cache only explicitly decorated public responses, never signed reads.

    All declared path/query arguments participate, including defaults. Undeclared
    query fields do not affect the handler and are never retained (they may
    contain identity material). Headers, Request and DB sessions are not keys.
    Validation precedes all cache accounting. Soft budgets only log leaders.
    """
    if bill_schema not in BILL_SCHEMAS - {"point", "history"}:
        raise ValueError(f"Unknown public bill schema: {bill_schema}")
    def decorate(function):
        name = f"{function.__module__}.{function.__name__}"
        cache = public_caches.setdefault(name, ClientFlowCache(
            workers=_aggregate_slots if aggregate else _read_slots,
            max_stale=SENSITIVE_MAX_STALE if sensitive else PUBLIC_MAX_STALE,
            visibility_sensitive=True,
            suppression_sensitive=bill_schema != "independent",
        ))
        budget = SoftFillBudget(name, quota)
        cache.public_bill_contributor_keys = CONTRIBUTOR_KEYS if bill_schema in {"aggregate", "representation"} else frozenset()
        cache.public_bill_schema = bill_schema
        cache.public_visibility_filter = serve_public_bill_body
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
                async def calculate():
                    return await function(*bound.args, **bound.kwargs)
                if bill_schema in {"aggregate", "representation"}:
                    return await capture_public_bill_body(
                        calculate, db=bound.arguments["db"],
                        candidates=bill_candidates(bound.arguments) if bill_candidates else None,
                    )
                return await calculate()

            async def refresh():
                async def using_db(db):
                    arguments = dict(bound.arguments, db=db)
                    if validate is not None:
                        await cache.check_eligibility(lambda: validate(**arguments), key=key)
                    budget.observe()
                    async def calculate():
                        return await function(**arguments)
                    if bill_schema in {"aggregate", "representation"}:
                        return await capture_public_bill_body(
                            calculate, db=db, candidates=bill_candidates(arguments) if bill_candidates else None,
                        )
                    return await calculate()
                return await with_cache_db(using_db)

            async def respond(_policy):
                # Callers may modify Pydantic models/lists without changing a hit.
                body = await cache.get_or_fill(key, fill, background_factory=refresh)

                async def refresh_visible():
                    nonlocal body
                    entry = cache.entries.get(key)
                    if entry is not None and entry[1] is body:
                        cache.invalidate(key)
                    body = await cache.get_or_fill(key, fill, background_factory=refresh)
                    return body

                return await serve_public_bill_body(
                    body, db=bound.arguments.get("db"), schema=bill_schema, refresh=refresh_visible,
                )

            if cache.suppression_sensitive:
                return await result_policy.with_result_cache_policy(respond)
            return await respond(None)

        wrapped.public_cache = cache
        wrapped.public_fill_budget = budget
        wrapped.public_cache_parameters = frozenset(parameters.parameters) - {"db", "request"}
        wrapped.public_bill_contributor_keys = cache.public_bill_contributor_keys
        wrapped.public_bill_schema = bill_schema
        wrapped.public_bill_candidates = bill_candidates
        wrapped.public_visibility_filter = serve_public_bill_body
        return wrapped
    return decorate


def invalidate_client_flow_caches():
    scope_status_cache.clear()
    results_cache.clear()
    for cache in public_caches.values():
        cache.clear()

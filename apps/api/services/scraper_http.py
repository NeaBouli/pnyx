"""Shared scraper pacing and Redis-owned host admission, including redirects.

A host lease spans admission, HTTP dispatch and atomic outcome persistence.
Redis TTL/TIME are the only cooldown clock. Local state is pacing/display only;
responses carry idempotency tokens, never pending increments or reset counts.
"""
import asyncio
import logging
import math
import os
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from uuid import uuid4
from urllib.parse import urlsplit

import httpx
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

MAX_RETRY_AFTER = 15 * 60
MAX_FORBIDDEN_COOLDOWN = 48 * 3600
# Scraper attempts have deadlines of at most 90 seconds. Orphaned leases after
# transport errors/process death expire without a scheduler polling loop.
HOST_LEASE_MS = 5 * 60 * 1000
EVENT_TTL_MS = 10 * 60 * 1000

# Also accept the previous JSON streak format until the next outcome migrates it.
_READ_STATE = """
local raw = redis.call('GET', KEYS[2])
local count = 0
if raw then
    if string.match(raw, '^%d+$') then
        count = tonumber(raw)
    else
        local old = cjson.decode(raw)
        if old.reason ~= 'http_403' or type(old.started_at) ~= 'number'
            or type(old.cooldown_until) ~= 'number'
            or old.started_at <= 0 or old.cooldown_until <= old.started_at then
            error('Invalid host streak')
        end
        count = old.consecutive_403
    end
    if type(count) ~= 'number' or count < 1 or count ~= math.floor(count) then
        error('Invalid host streak')
    end
end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then error('Host cooldown has no expiry') end
local clock = redis.call('TIME')
local now = clock[1] * 1000 + math.floor(clock[2] / 1000)
local until_ms = 0
if ttl >= 0 then until_ms = now + ttl end
"""
_ADMISSION = _READ_STATE + """
if ARGV[1] ~= '' and redis.call('GET', KEYS[3]) ~= ARGV[1] then
    return {-1, until_ms, count}
end
return {ttl == -2 and 1 or 0, until_ms, count}
"""
_OUTCOME = """
-- Check the event before ownership: a committed result can be acknowledged
-- again even after release, but can never mutate the next lease's generation.
local replay = redis.call('EXISTS', KEYS[4]) == 1
if not replay and redis.call('GET', KEYS[3]) ~= ARGV[1] then
    return {-1, 0, 0}
end
""" + _READ_STATE + """
if replay then return {1, until_ms, count} end
local status = tonumber(ARGV[2])
if status == 403 then
    -- INCR only authoritative state, including after a successful reset.
    if raw then redis.call('SET', KEYS[2], count) end
    count = redis.call('INCR', KEYS[2])
    local duration = math.min(tonumber(ARGV[3]) * 2 ^ math.min(count - 1, 3),
                              tonumber(ARGV[4]))
    until_ms = now + duration
    local record = cjson.encode({started_at=now / 1000,
        cooldown_until=until_ms / 1000, reason='http_403', consecutive_403=count})
    redis.call('SET', KEYS[1], record, 'PX', duration)
elseif (status >= 200 and status < 300) or status == 304 then
    redis.call('DEL', KEYS[1], KEYS[2])
    until_ms = 0
    count = 0
end
redis.call('SET', KEYS[4], '1', 'PX', ARGV[5])
return {1, until_ms, count}
"""
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


@asynccontextmanager
async def _redis() -> AsyncIterator[aioredis.Redis]:
    async with aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True,
        socket_connect_timeout=1, socket_timeout=1,
    ) as client:
        yield client


class HostCooldown(Exception):
    """The host must be deferred to a later run. Contains no request data."""


@dataclass
class _HostState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_request: float = 0.0
    cooldown_until: float | None = None
    consecutive_403: int | None = None
    robots_interval: float = 0.0
    last_request: float = 0.0


@dataclass(frozen=True)
class _HostLease:
    url: str
    token: str


class HostRateLimiter:
    def __init__(self, min_interval: float = 5.0, forbidden_cooldown: float = 6 * 3600) -> None:
        self.min_interval = min_interval
        self.forbidden_cooldown = forbidden_cooldown
        self._hosts: dict[str, _HostState] = {}

    @staticmethod
    def _host(url: str) -> str:
        host = (urlsplit(url).hostname or "").lower()
        if host == "hellenicparliament.gr" or host.endswith(".hellenicparliament.gr"):
            host = "hellenicparliament.gr"
        return host

    def _state(self, url: str) -> _HostState:
        return self._hosts.setdefault(self._host(url), _HostState())

    def _keys(self, url: str) -> tuple[str, str]:
        prefix = f"scraper:host:{self._host(url)}"
        return f"{prefix}:cooldown", f"{prefix}:streak"

    def _lease_key(self, url: str) -> str:
        return f"scraper:host:{self._host(url)}:lease"

    def _snapshot(self, url: str, result) -> int:
        admitted, until_ms, count = map(int, result)
        state = self._state(url)
        state.cooldown_until = until_ms / 1000 if until_ms else None
        state.consecutive_403 = count
        return admitted

    async def _admission(self, url: str, token: str = "") -> None:
        try:
            async with _redis() as client:
                result = await client.eval(_ADMISSION, 3, *self._keys(url), self._lease_key(url), token)
            admitted = self._snapshot(url, result)
        except Exception:
            raise HostCooldown("Scraper host cooldown state unavailable") from None
        if admitted != 1:
            raise HostCooldown("Scraper host cooldown active or lease lost")

    async def check_persisted(self, url: str) -> None:
        await self._admission(url)

    async def reserve(self, *urls: str) -> list[_HostLease]:
        """Try each host once; acquire all leases before final admission."""
        leases = []
        hosts = {self._host(url): url for url in urls}
        try:
            for host in sorted(hosts):
                lease = _HostLease(hosts[host], uuid4().hex)
                try:
                    async with _redis() as client:
                        acquired = await client.set(self._lease_key(lease.url), lease.token,
                                                    nx=True, px=HOST_LEASE_MS)
                except Exception:
                    raise HostCooldown("Scraper host cooldown state unavailable") from None
                if not acquired:
                    raise HostCooldown("Scraper host lease busy")
                leases.append(lease)
            for lease in leases:
                await self._admission(lease.url, lease.token)
            return leases
        except BaseException:
            await self.release(leases)
            raise

    async def release(self, leases: list[_HostLease]) -> None:
        for lease in reversed(leases):
            try:
                async with _redis() as client:
                    await client.eval(_RELEASE, 1, self._lease_key(lease.url), lease.token)
            except Exception:
                # The lease TTL recovers abandoned ownership; never delete a
                # newer owner's token, or log URLs/Redis exception payloads.
                logging.getLogger(__name__).info("[SCRAPER-HTTP] deferred=1")

    async def record(self, url: str, status: int, headers: Mapping[str, str],
                     *, lease: _HostLease | None = None) -> None:
        """Persist one response; retry an ambiguous acknowledgement identically."""
        owned = await self.reserve(url) if lease is None else []
        lease = lease or owned[0]
        self.observe(url, status, headers)
        try:
            # A bounded retry is safe even when the first EVAL committed.
            for attempt in range(2):
                try:
                    async with _redis() as client:
                        result = await client.eval(
                            _OUTCOME, 4, *self._keys(url), self._lease_key(url),
                            f"scraper:host:{self._host(url)}:event:{lease.token}",
                            lease.token, status, max(1, math.ceil(self.forbidden_cooldown * 1000)),
                            MAX_FORBIDDEN_COOLDOWN * 1000, EVENT_TTL_MS,
                        )
                    if int(result[0]) != 1:
                        raise HostCooldown("Scraper host lease lost")
                    self._snapshot(url, result)
                    break
                except (RedisConnectionError, RedisTimeoutError, ConnectionError, TimeoutError):
                    if attempt:
                        raise
        except Exception:
            # No local increments to replay. Retain the lease until expiry if
            # persistence is unavailable; all further admission fails closed.
            logging.getLogger(__name__).info("[SCRAPER-HTTP] deferred=1")
            raise HostCooldown("Scraper host cooldown state unavailable") from None
        else:
            await self.release(owned)

    async def status(self, url: str) -> dict[str, float | int | None]:
        try:
            async with _redis() as client:
                result = await client.eval(_ADMISSION, 3, *self._keys(url), self._lease_key(url), "")
            self._snapshot(url, result)
        except Exception:
            pass
        state = self._state(url)
        return {"cooldown_until": state.cooldown_until, "consecutive_403": state.consecutive_403}

    async def acquire(self, url: str) -> None:
        """Local pacing precedes the shared lease, so queued work holds no lease."""
        state = self._state(url)
        async with state.lock:
            while True:
                await self.check_persisted(url)
                delay = state.next_request - time.monotonic()
                if delay <= 0:
                    break
                await asyncio.sleep(delay)
            from services.parliament_access import is_parliament
            interval = max(10.0, self.min_interval, state.robots_interval) if is_parliament(url) else self.min_interval
            state.last_request = time.monotonic()
            state.next_request = state.last_request + interval

    def observe(self, url: str, status: int, headers: Mapping[str, str]) -> None:
        # Retry-After affects local pacing only, never persisted cooldowns.
        state = self._state(url)
        now = time.monotonic()
        if status in (429, 503):
            raw = headers.get("retry-after", "")
            try:
                delay = float(raw)
            except (TypeError, ValueError):
                try:
                    date = parsedate_to_datetime(raw)
                    if date.tzinfo is None:
                        return
                    delay = date.timestamp() - time.time()
                    if delay > MAX_RETRY_AFTER:
                        return
                except (TypeError, ValueError, OverflowError, OSError):
                    return
            if math.isfinite(delay) and delay > 0:
                state.next_request = max(state.next_request, now + min(delay, MAX_RETRY_AFTER))


host_limiter = HostRateLimiter()


class _ScraperRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX logs full URLs itself before response hooks run. Redact requests
        # to hosts used by these scrapers, including paths and reason phrases.
        args = record.args
        if record.msg == 'HTTP Request: %s %s "%s %d %s"' and isinstance(args, tuple) and len(args) == 5:
            from services.parliament_access import is_parliament
            if isinstance(args[1], httpx.URL) and (args[1].host in host_limiter._hosts or (
                is_parliament(str(args[1])) and "hellenicparliament.gr" in host_limiter._hosts
            )):
                record.msg = "Scraper HTTP response status=%d"
                record.args = (args[3],)
        return True


logging.getLogger("httpx").addFilter(_ScraperRequestLogFilter())


async def pace_request(request: httpx.Request, *, limiter: HostRateLimiter | None = None) -> None:
    limiter = limiter or host_limiter
    from services.parliament_access import prepare
    url = str(request.url)
    source = request.extensions.get("scraper_source_url", url)
    if source.startswith("https://r.jina.ai/"):
        source = source[len("https://r.jina.ai/"):]
    request.extensions["scraper_source_url"] = source
    try:
        await limiter.check_persisted(source)
        # Robots preparation may issue its own request, before content leases.
        await prepare(request)
        await limiter.acquire(url)
        # Keep both source and dispatch hosts leased until response persistence.
        # Redirects inherit extensions, so always replace the previous leases.
        request.extensions["scraper_host_leases"] = await limiter.reserve(source, url)
    except HostCooldown:
        logging.getLogger(__name__).info("[SCRAPER-HTTP] deferred=1")
        raise


async def record_response(response: httpx.Response, *, limiter: HostRateLimiter | None = None) -> None:
    limiter = limiter or host_limiter
    from services.parliament_access import observe
    url = str(response.url)
    leases = response.request.extensions.get("scraper_host_leases", [])
    lease = next((item for item in leases if limiter._host(item.url) == limiter._host(url)), None)
    if lease is None:
        raise HostCooldown("Scraper host lease unavailable")
    try:
        # Policy can recognize an access-denied body or fail while recording
        # source metadata. Persist its HTTP outcome even if that happens.
        await observe(response)
    finally:
        forbidden = response.request.extensions.get("scraper_forbidden", False)
        status = 403 if forbidden else response.status_code
        if response.request.extensions.get("parliament_robots") and (200 <= status < 300 or status == 304):
            status = 0  # robots success must not reset a content 403 streak
        await limiter.record(url, status, response.headers, lease=lease)
        await limiter.release(leases)


SCRAPER_HTTP_HOOKS = {"request": [pace_request], "response": [record_response]}

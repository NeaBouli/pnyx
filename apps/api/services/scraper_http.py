"""Shared scraper pacing and Redis-backed host cooldowns, including redirects.

Cooldown timestamps are UTC Unix seconds; pacing alone uses monotonic time.
Redis read failures fail closed, including for hosts unknown to this worker.
The local record remains available for status and failed writes are retried
before another request. A streak survives cooldown expiry until a successful
fetch resets it; the separate active cooldown key has only the remaining TTL.
"""
import asyncio
import json
import logging
import math
import os
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
import redis.asyncio as aioredis
from redis.exceptions import WatchError

MAX_RETRY_AFTER = 15 * 60
MAX_FORBIDDEN_COOLDOWN = 48 * 3600


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
    cooldown_until: float = 0.0
    cooldown_started: float = 0.0
    consecutive_403: int = 0
    pending_403: int = 0
    dirty: bool = False
    revision: int = 0
    robots_interval: float = 0.0
    last_request: float = 0.0


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

    def _duration(self, count: int) -> float:
        return min(MAX_FORBIDDEN_COOLDOWN, self.forbidden_cooldown * 2 ** min(count - 1, 3))

    @staticmethod
    def _decode(raw: str | None) -> tuple[float, float, int]:
        if raw is None:
            return 0.0, 0.0, 0
        record = json.loads(raw)
        started, until, count = record["started_at"], record["cooldown_until"], record["consecutive_403"]
        if (record["reason"] != "http_403" or type(count) is not int or count <= 0
                or type(started) not in (int, float) or type(until) not in (int, float)
                or not math.isfinite(started) or not math.isfinite(until) or not 0 < started < until):
            raise ValueError("Invalid host cooldown state")
        return started, until, count

    async def _refresh(self, url: str) -> None:
        state = self._state(url)
        if state.dirty:
            await self._persist(url)
        try:
            async with _redis() as client:
                record = self._decode(await client.get(self._keys(url)[1]))
        except Exception:
            raise HostCooldown("Scraper host cooldown state unavailable") from None
        if state.dirty:
            # A response may have recorded a 403 while the Redis read awaited IO.
            await self._persist(url)
            return
        state.cooldown_started, state.cooldown_until, state.consecutive_403 = record

    async def check_persisted(self, url: str) -> None:
        async with self._state(url).lock:
            await self._refresh(url)
            self.check(url)

    async def _persist(self, url: str) -> None:
        state = self._state(url)
        cooldown_key, streak_key = self._keys(url)
        try:
            async with _redis() as client:
                # WATCH prevents simultaneous workers losing a 403 increment or
                # a successful response clearing another worker's active block.
                for _ in range(3):
                    async with client.pipeline() as pipe:
                        try:
                            await pipe.watch(streak_key)
                            started, until, count = self._decode(await pipe.get(streak_key))
                            revision = state.revision
                            pending = state.pending_403
                            if state.consecutive_403:
                                count = max(count + pending, state.consecutive_403)
                                started = state.cooldown_started
                                until = max(until, state.cooldown_until, started + self._duration(count))
                                raw = json.dumps({"started_at": started, "cooldown_until": until,
                                                  "reason": "http_403", "consecutive_403": count})
                                pipe.multi()
                                pipe.set(streak_key, raw)
                                remaining = math.ceil(until - time.time())
                                if remaining > 0:
                                    pipe.set(cooldown_key, raw, ex=remaining)
                                else:
                                    pipe.delete(cooldown_key)
                            elif until > time.time():
                                state.cooldown_started, state.cooldown_until, state.consecutive_403 = started, until, count
                                state.dirty = False
                                return
                            else:
                                pipe.multi()
                                pipe.delete(cooldown_key, streak_key)
                            await pipe.execute()
                            state.pending_403 = max(0, state.pending_403 - pending)
                            if state.revision != revision:
                                # Preserve a response observed during the write.
                                continue
                            if state.consecutive_403:
                                state.cooldown_started, state.cooldown_until, state.consecutive_403 = started, until, count
                            state.dirty = False
                            return
                        except WatchError:
                            continue
        except Exception:
            pass
        # Keep local state, including an unpersisted 403, and defer all requests.
        raise HostCooldown("Scraper host cooldown state unavailable") from None

    async def persist(self, url: str) -> None:
        async with self._state(url).lock:
            if self._state(url).dirty:
                await self._persist(url)

    async def status(self, url: str) -> dict[str, float | int | None]:
        state = self._state(url)
        async with state.lock:
            try:
                # Status is read-only; it must not retry writes or fetch content.
                async with _redis() as client:
                    record = self._decode(await client.get(self._keys(url)[1]))
                if not state.dirty:
                    state.cooldown_started, state.cooldown_until, state.consecutive_403 = record
            except Exception:
                if not state.consecutive_403:
                    return {"cooldown_until": None, "consecutive_403": None}
            return {"cooldown_until": state.cooldown_until or None,
                    "consecutive_403": state.consecutive_403}

    def check(self, url: str) -> None:
        if self._state(url).cooldown_until > time.time():
            raise HostCooldown("Scraper host cooldown active")

    async def acquire(self, url: str) -> None:
        state = self._state(url)
        async with state.lock:
            while True:
                await self._refresh(url)
                self.check(url)
                delay = state.next_request - time.monotonic()
                if delay <= 0:
                    from services.parliament_access import is_parliament
                    interval = max(10.0, self.min_interval, state.robots_interval) if is_parliament(url) else self.min_interval
                    state.last_request = time.monotonic()
                    state.next_request = time.monotonic() + interval
                    return
                await asyncio.sleep(delay)

    def observe(self, url: str, status: int, headers: Mapping[str, str]) -> None:
        state = self._state(url)
        now = time.monotonic()
        if status == 403:
            state.revision += 1
            state.pending_403 += 1
            state.consecutive_403 += 1
            state.cooldown_started = time.time()
            state.cooldown_until = max(state.cooldown_until, state.cooldown_started + self._duration(state.consecutive_403))
            state.dirty = True
        elif (200 <= status < 300 or status == 304) and state.consecutive_403 and state.cooldown_until <= time.time():
            state.revision += 1
            state.cooldown_started = state.cooldown_until = 0.0
            state.consecutive_403 = 0
            state.pending_403 = 0
            state.dirty = True
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
                    # Far-future dates usually indicate a bad upstream clock.
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


async def pace_request(request: httpx.Request) -> None:
    from services.parliament_access import prepare
    # A source cooldown also applies when a caller tries Jina for that source.
    url = str(request.url)
    source = request.extensions.get("scraper_source_url", url)
    if source.startswith("https://r.jina.ai/"):
        source = source[len("https://r.jina.ai/"):]
    request.extensions["scraper_source_url"] = source
    await host_limiter.check_persisted(source)
    await prepare(request)
    await host_limiter.acquire(url)
    # A concurrent response may have forbidden the source while we queued.
    await host_limiter.check_persisted(source)
    if host_limiter._host(source) != host_limiter._host(url):
        await host_limiter.check_persisted(url)


async def record_response(response: httpx.Response) -> None:
    url = str(response.url)
    from services.parliament_access import observe
    try:
        # Parliament's policy observes both HTTP 403 and access-denied bodies.
        # It raises after recording the block; do not count that response twice.
        await observe(response)
    except HostCooldown:
        await host_limiter.persist(url)
        raise
    if response.request.extensions.get("parliament_robots") and (200 <= response.status_code < 300 or response.status_code == 304):
        # A robots revalidation must not reset a content-fetch 403 streak.
        return
    # Observe before waiting on the pacing lock, so queued requests see a block.
    host_limiter.observe(url, response.status_code, response.headers)
    await host_limiter.persist(url)


SCRAPER_HTTP_HOOKS = {"request": [pace_request], "response": [record_response]}

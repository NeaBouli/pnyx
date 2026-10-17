"""Shared, process-local pacing for scraper requests, including redirects."""
import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx


class HostCooldown(Exception):
    """The host must be deferred to a later run. Contains no request data."""


@dataclass
class _HostState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_request: float = 0.0
    cooldown_until: float = 0.0


class HostRateLimiter:
    def __init__(self, min_interval: float = 5.0, forbidden_cooldown: float = 6 * 3600):
        self.min_interval = min_interval
        self.forbidden_cooldown = forbidden_cooldown
        self._hosts: dict[str, _HostState] = {}

    def _state(self, url: str) -> _HostState:
        host = (urlsplit(url).hostname or "").lower()
        return self._hosts.setdefault(host, _HostState())

    def check(self, url: str) -> None:
        if self._state(url).cooldown_until > time.monotonic():
            raise HostCooldown("Scraper host cooldown active")

    async def acquire(self, url: str) -> None:
        state = self._state(url)
        async with state.lock:
            while True:
                self.check(url)
                delay = state.next_request - time.monotonic()
                if delay <= 0:
                    state.next_request = time.monotonic() + self.min_interval
                    return
                await asyncio.sleep(delay)

    def observe(self, url: str, status: int, headers) -> None:
        state = self._state(url)
        now = time.monotonic()
        if status == 403:
            state.cooldown_until = max(state.cooldown_until, now + self.forbidden_cooldown)
        if status in (429, 503):
            raw = headers.get("retry-after", "")
            try:
                delay = float(raw)
            except (TypeError, ValueError):
                try:
                    delay = parsedate_to_datetime(raw).timestamp() - time.time()
                except (TypeError, ValueError, OverflowError):
                    return
            if math.isfinite(delay) and delay > 0:
                state.next_request = max(state.next_request, now + delay)


host_limiter = HostRateLimiter()


class _ScraperRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX logs full URLs itself before response hooks run. Redact requests
        # to hosts used by these scrapers, including paths and reason phrases.
        args = record.args
        if record.msg == 'HTTP Request: %s %s "%s %d %s"' and isinstance(args, tuple) and len(args) == 5:
            if isinstance(args[1], httpx.URL) and args[1].host in host_limiter._hosts:
                record.msg = "Scraper HTTP response status=%d"
                record.args = (args[3],)
        return True


logging.getLogger("httpx").addFilter(_ScraperRequestLogFilter())


async def pace_request(request: httpx.Request) -> None:
    # A source cooldown also applies when a caller tries Jina for that source.
    url = str(request.url)
    if url.startswith("https://r.jina.ai/"):
        host_limiter.check(url[len("https://r.jina.ai/"):])
    await host_limiter.acquire(url)


async def record_response(response: httpx.Response) -> None:
    host_limiter.observe(str(response.url), response.status_code, response.headers)


SCRAPER_HTTP_HOOKS = {"request": [pace_request], "response": [record_response]}

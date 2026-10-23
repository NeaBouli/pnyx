"""Parliament access policy: identified, robots-aware, conditional direct HTTP only.

Robots and bounded response bodies are cached per worker. A worker restart
revalidates robots before fetching any content; unavailable robots fail closed.
"""
import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ekklesia.gr-bot/1.0 (+https://ekklesia.gr/bot.html; contact: kaspartisan@proton.me)"
DAY = 24 * 3600
MAX_BODY = 2 * 1024 * 1024
MAX_ENTRIES = 128


def is_parliament(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "hellenicparliament.gr" or host.endswith(".hellenicparliament.gr")


def access_denied(text: str) -> bool:
    text = text.lower()
    return ("you don't have permission to access" in text or "errors.edgesuite.net" in text
            or ("access denied" in text and "reference #" in text))


class RobotsDisallowed(Exception):
    """No content request is permitted by the current robots policy."""


@dataclass
class CachedResponse:
    body: bytes
    headers: httpx.Headers
    checked: float


responses: dict[str, CachedResponse] = {}
robots: dict[str, tuple[float, RobotFileParser]] = {}
_robots_lock = asyncio.Lock()


def validators(url: str) -> dict[str, str]:
    cached = responses.get(url)
    if cached is None:
        return {}
    return {target: cached.headers[source] for source, target in (
        ("etag", "If-None-Match"), ("last-modified", "If-Modified-Since"),
    ) if source in cached.headers}


async def check_robots(url: str) -> None:
    from services.scraper_http import HostCooldown, SCRAPER_HTTP_HOOKS, host_limiter
    origin = str(httpx.URL(url).copy_with(path="/robots.txt", query=None, fragment=None))
    async with _robots_lock:
        cached = robots.get(origin)
        if cached is None or cached[0] <= time.monotonic():
            parser = RobotFileParser(origin)
            # Deny until a usable robots response is available.
            parser.disallow_all = True
            ttl = DAY
            try:
                async with httpx.AsyncClient(timeout=30, trust_env=False, event_hooks=SCRAPER_HTTP_HOOKS) as client:
                    response = await client.get(origin, extensions={"parliament_robots": True})
                if response.status_code == 200:
                    parser.disallow_all = False
                    parser.parse(response.text.splitlines())
                elif response.status_code in (404, 410):
                    parser.disallow_all = False
                    parser.parse(["User-agent: *", "Disallow:"])
                else:
                    ttl = 3600
            except HostCooldown:
                robots[origin] = (time.monotonic() + 3600, parser)
                raise
            except Exception:
                # A denied/failed robots fetch never authorizes content access.
                ttl = 3600
            robots[origin] = (time.monotonic() + ttl, parser)
        parser = robots[origin][1]
    if not parser.can_fetch(USER_AGENT, url):
        raise RobotsDisallowed("Parliament robots policy disallows request")
    state = host_limiter._state(url)
    rate = parser.request_rate(USER_AGENT)
    state.robots_interval = max(10, parser.crawl_delay(USER_AGENT) or 0,
                                rate.seconds / rate.requests if rate and rate.requests else 0)
    state.next_request = max(state.next_request, state.last_request + state.robots_interval)


async def prepare(request: httpx.Request) -> None:
    from services.scraper_http import HostCooldown
    url = str(request.url)
    source = request.extensions.get("scraper_source_url", url)
    if url.startswith("https://r.jina.ai/"):
        source = url[len("https://r.jina.ai/"):]
    if is_parliament(source) and not is_parliament(url):
        raise HostCooldown("Third-party Parliament fetching is disabled")
    if not is_parliament(url):
        return
    request.headers["User-Agent"] = USER_AGENT
    # Only the internal robots request may skip the robots check.
    if not (request.extensions.get("parliament_robots") and request.url.path == "/robots.txt"):
        await check_robots(url)
    request.headers.update(validators(url))


async def observe(response: httpx.Response) -> None:
    from services.scraper_http import HostCooldown
    from services.source_freshness import record_source_blocked
    url = str(response.url)
    if not is_parliament(url):
        return
    await response.aread()
    if response.status_code == 403 or (response.status_code == 200 and access_denied(response.text)):
        response.request.extensions["scraper_forbidden"] = True
        await record_source_blocked()
        raise HostCooldown("Parliament source_blocked")
    cached = responses.get(url)
    if response.status_code == 304 and cached is not None:
        headers = cached.headers.copy()
        headers.update(response.headers)
        response.status_code = 200
        response.headers = headers
        response._content = cached.body
    if response.status_code == 200 and len(response.content) <= MAX_BODY:
        if len(responses) >= MAX_ENTRIES and url not in responses:
            responses.pop(next(iter(responses)))
        responses[url] = CachedResponse(response.content, response.headers.copy(), time.monotonic())

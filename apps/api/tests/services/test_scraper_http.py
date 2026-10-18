import asyncio
from email.utils import formatdate

import httpx
import pytest
import respx

from services.scraper_http import HostCooldown, MAX_RETRY_AFTER, SCRAPER_HTTP_HOOKS

pytestmark = pytest.mark.usefixtures("scraper_clock")


async def test_concurrent_requests_share_host_spacing(scraper_clock):
    times = []

    async def attempt(path):
        await scraper_clock.limiter.acquire(f"https://example.org/{path}")
        times.append(scraper_clock.now)

    await asyncio.gather(*(attempt(path) for path in ("a", "b", "c")))
    assert times == [1000, 1005, 1010]
    await scraper_clock.limiter.acquire("https://other.org/")
    assert scraper_clock.sleeps == [5, 5]


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("http_date", [False, True])
async def test_retry_after_seconds_and_http_date(scraper_clock, status, http_date):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/a")
    value = formatdate(scraper_clock.time() + 30, usegmt=True) if http_date else "30"
    limiter.observe("https://example.org/a", status, {"retry-after": value})
    await limiter.acquire("https://example.org/b")
    assert scraper_clock.now == 1030


@pytest.mark.parametrize("value", ["", "nonsense", "-10", "inf", "nan", "1e999", "Wed, 99 Jan 2026", "Tue, 14 Nov 2023 22:30:00", None])
async def test_invalid_retry_after_keeps_minimum_spacing(scraper_clock, value):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/")
    limiter.observe("https://example.org/", 503, {"retry-after": value})
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1005


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("value", ["901", "86400", "1e100"])
async def test_retry_after_seconds_are_capped(scraper_clock, status, value):
    limiter = scraper_clock.limiter
    limiter.observe("https://example.org/", status, {"retry-after": value})
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1000 + MAX_RETRY_AFTER


@pytest.mark.parametrize("offset,expected_delay", [(-60, 5), (900, 900), (901, 5), (10 * 365 * 86400, 5)])
async def test_retry_after_dates_ignore_past_and_far_future(scraper_clock, offset, expected_delay):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/")
    limiter.observe("https://example.org/", 503, {
        "retry-after": formatdate(scraper_clock.time() + offset, usegmt=True),
    })
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1000 + expected_delay


async def test_forbidden_cooldown_expires_and_does_not_block_other_hosts(scraper_clock):
    limiter = scraper_clock.limiter
    limiter.observe("https://example.org/a", 403, {})
    for url in ("https://example.org/b", "http://EXAMPLE.org/a"):
        with pytest.raises(HostCooldown):
            await limiter.acquire(url)
    assert scraper_clock.sleeps == []
    await limiter.acquire("https://other.org/")
    scraper_clock.now += 6 * 3600
    await limiter.acquire("https://example.org/b")


@respx.mock
async def test_http_redirect_attempts_are_paced(scraper_clock):
    times = []

    def respond(request):
        times.append(scraper_clock.now)
        return httpx.Response(302, headers={"location": "/final"}) if request.url.path == "/start" else httpx.Response(200)

    respx.get("https://example.org/start").mock(side_effect=respond)
    respx.get("https://example.org/final").mock(side_effect=respond)
    async with httpx.AsyncClient(follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS) as client:
        await client.get("https://example.org/start")
    assert times == [1000, 1005]


@respx.mock
async def test_source_cooldown_cannot_be_bypassed_via_jina(scraper_clock):
    scraper_clock.limiter.observe("https://www.hellenicparliament.gr/", 403, {})
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get("https://r.jina.ai/https://www.hellenicparliament.gr/law?private=value")
    assert len(respx.calls) == 0


@pytest.mark.parametrize("target", [
    "https://www.hellenicparliament.gr/law",
    "https://r.jina.ai/https://www.hellenicparliament.gr/law",
    "http://ollama:11434/api/generate",
    "https://redirect.example.org/final",
])
@respx.mock
async def test_source_cooldown_is_rechecked_after_queue(scraper_clock, monkeypatch, target):
    from services import scraper_http, parliament_access
    from unittest.mock import AsyncMock
    # This test isolates cooldown ordering; robots behavior has dedicated coverage.
    monkeypatch.setattr(parliament_access, "check_robots", AsyncMock())

    source = "https://www.hellenicparliament.gr/law"
    limiter = scraper_clock.limiter
    await limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        limiter.observe(source, 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(target, extensions={"scraper_source_url": source})
    assert len(respx.calls) == 0


@respx.mock
async def test_jina_source_is_rechecked_after_queue_without_extensions(scraper_clock, monkeypatch):
    from services import scraper_http

    target = "https://r.jina.ai/https://www.hellenicparliament.gr/law"
    await scraper_clock.limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        scraper_clock.limiter.observe("https://www.hellenicparliament.gr/", 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(target)
    assert len(respx.calls) == 0


@respx.mock
async def test_cross_host_redirect_retains_source_cooldown(scraper_clock, monkeypatch):
    from services import scraper_http

    source = "https://source.example.org/start"
    target = "https://target.example.org/final"
    redirect = respx.get(source).respond(302, headers={"location": target})
    final = respx.get(target).respond(200)
    await scraper_clock.limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        scraper_clock.limiter.observe(source, 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(source)
    assert redirect.call_count == 1 and final.call_count == 0

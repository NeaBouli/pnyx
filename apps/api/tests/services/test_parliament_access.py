"""T-9147: exercise the actual HTTP hooks with an offline transport and clock."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from routers import scraper
from services import parliament_access as policy, parliament_fetcher as fetcher, source_freshness
from services.scraper_http import HostCooldown, SCRAPER_HTTP_HOOKS

BASE = "https://www.hellenicparliament.gr"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, scraper_clock):
    monkeypatch.setattr(policy, "robots", {})
    monkeypatch.setattr(policy, "responses", {})
    monkeypatch.setattr(policy, "_robots_lock", asyncio.Lock())
    monkeypatch.setattr(policy, "time", scraper_clock)
    monkeypatch.setattr(source_freshness, "record_source_blocked", AsyncMock())


@respx.mock
async def test_robots_disallow_daily_cache_and_honest_ua(scraper_clock):
    robots = respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow: /private")
    allowed = respx.get(BASE + "/public").respond(200, text="public")
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(policy.RobotsDisallowed):
            await client.get(BASE + "/private/law")
        await client.get(BASE + "/public", headers={"User-Agent": "Mozilla/5.0"})
        with pytest.raises(policy.RobotsDisallowed):
            await client.get(BASE + "/private/other")
    assert robots.call_count == allowed.call_count == 1
    assert len(respx.calls) == 2
    assert all(call.request.headers["user-agent"] == policy.USER_AGENT for call in respx.calls)
    assert policy.USER_AGENT == "ekklesia.gr-bot/1.0 (+https://ekklesia.gr/bot.html; contact: kaspartisan@proton.me)"
    assert scraper_clock.sleeps == [10]


@respx.mock
async def test_robots_revalidated_daily_with_validators_and_cached_body(scraper_clock):
    robots = respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow: /private", headers={"ETag": '"robots-v1"'})
    for _ in range(2):
        with pytest.raises(policy.RobotsDisallowed):
            await policy.check_robots(BASE + "/private")
    assert robots.call_count == 1
    scraper_clock.now += policy.DAY + 1
    robots.respond(304)
    with pytest.raises(policy.RobotsDisallowed):
        await policy.check_robots(BASE + "/private")
    assert robots.call_count == 2
    assert robots.calls[-1].request.headers["if-none-match"] == '"robots-v1"'


@pytest.mark.parametrize("status", [403, 503, 302])
@respx.mock
async def test_unavailable_robots_never_allows_content(status):
    robots = respx.get(BASE + "/robots.txt").respond(status, headers={"location": "/elsewhere"})
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises((policy.RobotsDisallowed, HostCooldown)):
            await client.get(BASE + "/law")
    assert robots.call_count == 1 and len(respx.calls) == 1


@pytest.mark.parametrize("blocked_body", [False, True])
@respx.mock
async def test_discovery_stops_on_block_without_any_alternate_route(monkeypatch, blocked_body):
    respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    route = respx.get(scraper.PARLIAMENT_API).respond(
        200 if blocked_body else 403,
        text="Access Denied Reference #123 errors.edgesuite.net" if blocked_body else "Forbidden",
    )
    jina = AsyncMock(side_effect=AssertionError("No third-party source requests"))
    monkeypatch.setattr(scraper, "_fetch_jina_markdown", jina)
    errors = []
    assert await scraper.scrape_parliament_bills(probe_errors=errors) == []
    assert await scraper.scrape_parliament_bills() == []
    assert "source_blocked" in errors
    assert route.call_count == 1 and len(respx.calls) == 2
    jina.assert_not_awaited()
    source_freshness.record_source_blocked.assert_awaited_once()


@respx.mock
async def test_enrichment_and_old_channels_cannot_use_jina_after_403(monkeypatch):
    respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    route = respx.get(BASE + "/law").respond(403)
    assert await fetcher._fetch_bill_text_result("bill", BASE + "/law") == ("", "skipped")
    for channel in (fetcher._channel_jina_markdown, fetcher._channel_jina_html,
                    fetcher._channel_ollama_extract, fetcher._channel_playwright):
        assert await channel(BASE + "/law") == ""
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        for url in ("https://r.jina.ai/" + BASE + "/law", "https://proxy.example.org/"):
            with pytest.raises(HostCooldown):
                await client.get(url, extensions={"scraper_source_url": BASE + "/law"})
    assert route.call_count == 1 and len(respx.calls) == 2


@respx.mock
async def test_conditional_content_request_reuses_cached_body():
    respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    headers = {"ETag": '"law-v1"', "Last-Modified": "Sat, 17 Oct 2026 09:00:00 GMT"}
    route = respx.get(BASE + "/law").respond(200, text="official content", headers=headers)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        assert (await client.get(BASE + "/law")).text == "official content"
        route.respond(304)
        response = await client.get(BASE + "/law")
    assert response.status_code == 200 and response.text == "official content"
    assert route.calls[-1].request.headers["if-none-match"] == headers["ETag"]
    assert route.calls[-1].request.headers["if-modified-since"] == headers["Last-Modified"]


async def test_parliament_aliases_share_ten_second_pacing_and_cooldown(scraper_clock):
    limiter = scraper_clock.limiter
    await limiter.acquire(BASE + "/one")
    await limiter.acquire("https://hellenicparliament.gr/two")
    assert scraper_clock.sleeps == [10]
    await limiter.record(BASE, 403, {})
    with pytest.raises(HostCooldown):
        await limiter.acquire("https://hellenicparliament.gr/three")


@respx.mock
async def test_robots_crawl_delay_can_increase_host_spacing(scraper_clock):
    respx.get(BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:\nCrawl-delay: 30")
    respx.get(BASE + "/law").respond(200, text="official content")
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        await client.get(BASE + "/law")
    assert scraper_clock.sleeps == [30]


def test_offline_backfill_refuses_direct_and_third_party_parliament_fetches(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("t9147_backfill", Path(__file__).resolve().parents[4] / "scripts/backfill_analysis_claude.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def unexpected(*args, **kwargs):
        raise AssertionError("No Parliament fetching from backfill scripts")

    monkeypatch.setattr(module.urllib.request, "urlopen", unexpected)
    assert module._http_text(BASE + "/law") == ""
    assert module._http_text(module.JINA_BASE + BASE + "/law") == ""

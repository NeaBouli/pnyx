import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
import respx

from routers import scraper
from services import parliament_access, source_freshness


@pytest.fixture(autouse=True)
def parliament_policy(monkeypatch):
    monkeypatch.setattr(parliament_access, "robots", {})
    monkeypatch.setattr(parliament_access, "responses", {})
    monkeypatch.setattr(source_freshness, "record_source_blocked", AsyncMock())


@respx.mock
async def test_discovery_403_prevents_jina_and_direct_retries(scraper_clock, caplog):
    caplog.set_level(logging.INFO)
    respx.get(scraper.PARLIAMENT_BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    route = respx.get(scraper.PARLIAMENT_API).respond(403)
    errors = []
    assert await scraper.scrape_parliament_bills(probe_errors=errors) == []
    assert await scraper.scrape_parliament_bills() == []
    assert "source_blocked" in errors
    assert route.call_count == 1 and len(respx.calls) == 2
    assert scraper_clock.sleeps == [10]
    assert caplog.text.count("fetched=0 skipped=1 failed=0") == 2
    assert "https://" not in caplog.text


@respx.mock
async def test_discovery_success_logs_fetched_count(scraper_clock, caplog):
    caplog.set_level(logging.INFO)
    respx.get(scraper.PARLIAMENT_BASE + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    respx.get(scraper.PARLIAMENT_API).respond(200, json={"Data": [{
        "Title": "Τίτλος νομοσχεδίου για τη λειτουργία των θεσμών", "ID": "id",
    }]})
    assert len(await scraper.scrape_parliament_bills(limit=1)) == 1
    assert "fetched=1 skipped=0 failed=0" in caplog.text


@pytest.mark.parametrize("fetch", [scraper.fetch_with_fallback, scraper._fetch_jina_markdown, scraper.scrape_parliament_bills])
@respx.mock
async def test_discovery_deadlines_include_limiter_wait(scraper_clock, monkeypatch, offline_http_client, fetch):
    attempts = []

    async def queued(url):
        attempts.append(url)
        await asyncio.Event().wait()

    monkeypatch.setattr(scraper_clock.limiter, "acquire", queued)
    monkeypatch.setattr(scraper, "attempt_timeout", lambda budget: asyncio.timeout(0.03))
    result = await asyncio.wait_for(
        fetch() if fetch is scraper.scrape_parliament_bills else fetch(scraper.PARLIAMENT_BASE),
        timeout=5,
    )
    assert result == ([] if fetch is scraper.scrape_parliament_bills else None)
    assert len(attempts) == (2 if fetch is scraper.scrape_parliament_bills else 1 if fetch is scraper.fetch_with_fallback else 0)
    assert len(respx.calls) == 0

import logging
import respx

from routers import scraper


@respx.mock
async def test_discovery_403_prevents_jina_and_direct_retries(scraper_clock, caplog):
    caplog.set_level(logging.INFO)
    route = respx.get(scraper.PARLIAMENT_API).respond(403)
    errors = []
    assert await scraper.scrape_parliament_bills(probe_errors=errors) == []
    assert await scraper.scrape_parliament_bills() == []
    assert "api_http_403" in errors
    assert route.call_count == 1 and len(respx.calls) == 1
    assert scraper_clock.sleeps == []
    assert caplog.text.count("fetched=0 skipped=1 failed=0") == 2
    assert "https://" not in caplog.text


@respx.mock
async def test_discovery_success_logs_fetched_count(scraper_clock, caplog):
    caplog.set_level(logging.INFO)
    respx.get(scraper.PARLIAMENT_API).respond(200, json={"Data": [{
        "Title": "Τίτλος νομοσχεδίου για τη λειτουργία των θεσμών", "ID": "id",
    }]})
    assert len(await scraper.scrape_parliament_bills(limit=1)) == 1
    assert "fetched=1 skipped=0 failed=0" in caplog.text

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
import respx

from routers import scraper
from services import parliament_access, source_freshness


@pytest.fixture(autouse=True)
def parliament_policy(monkeypatch):
    monkeypatch.setattr(scraper, "SCRAPE_DELAY_SECONDS", 0)
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


@pytest.mark.parametrize("missing_id", [None, "", "   "])
@respx.mock
async def test_api_rows_without_ids_use_dated_official_html(scraper_clock, missing_id):
    """The live Open Data response has dates/documents but no law IDs."""
    base = scraper.PARLIAMENT_BASE
    law_id = "726dad50-ab77-453c-9590-b4e4012a069e"
    path = f"/Nomothetiko-Ergo/Psifisthenta-Nomoschedia?law_id={law_id}"
    respx.get(base + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    api = respx.get(scraper.PARLIAMENT_API).respond(200, json={"Data": [{
        "Title": "Κύρωση συμφωνίας για τη λειτουργία των θεσμών",
        "LawPhaseDate": "/Date(1792702800000+0300)/",
        **({"ID": missing_id} if missing_id is not None else {}),
    }]})
    html = respx.get(base + "/Nomothetiko-Ergo/Psifisthenta-Nomoschedia").respond(
        200, text=f"""<table><tr>
        <td><span>22/10/2026</span></td>
        <td><a href="{path}">Κύρωση συμφωνίας για τη λειτουργία των θεσμών</a></td>
        <td></td></tr></table>""",
    )
    errors = []

    bills = await scraper.scrape_parliament_bills(limit=1, require_dates=True, probe_errors=errors)

    assert len(bills) == 1
    assert bills[0]["url"] == base + path
    assert bills[0]["date"] == "2026-10-22T00:00:00+00:00"
    assert "api_missing_law_id" in errors
    assert api.call_count == 2 and html.call_count == 1
    assert len(respx.calls) == 4  # robots, two API categories, the direct HTML page


@respx.mock
async def test_direct_html_rejects_undated_and_foreign_law_links(scraper_clock):
    base = scraper.PARLIAMENT_BASE
    law_id = "726dad50-ab77-453c-9590-b4e4012a069e"
    respx.get(base + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    respx.get(scraper.PARLIAMENT_API).respond(200, json={"Data": []})
    respx.get(base + "/Nomothetiko-Ergo/Psifisthenta-Nomoschedia").respond(
        200, text=f"""<table>
        <tr><td>22/10/2026</td><td><a href="https://example.org/?law_id={law_id}">
        Κύρωση συμφωνίας από μη επίσημη πηγή</a></td></tr>
        <tr><td>31/02/2026</td><td><a href="?law_id={law_id}">
        Κύρωση συμφωνίας με μη έγκυρη ημερομηνία</a></td></tr>
        <tr><td></td><td><a href="?law_id={law_id}">
        Κύρωση συμφωνίας χωρίς ημερομηνία</a></td></tr>
        </table>""",
    )

    assert await scraper.scrape_parliament_bills(limit=10, require_dates=True) == []


@pytest.mark.parametrize("require_dates", [False, True])
@respx.mock
async def test_html_filters_dates_before_limit_and_keeps_loose_results(scraper_clock, require_dates):
    base = scraper.PARLIAMENT_BASE
    first = "726dad50-ab77-453c-9590-b4e4012a069e"
    second = "97e0885f-30fe-45f3-bbe9-b4de0151a84f"
    respx.get(base + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    respx.get(scraper.PARLIAMENT_API).respond(200, json={"Data": []})
    respx.get(base + "/Nomothetiko-Ergo/Psifisthenta-Nomoschedia").respond(
        200, text=f"""<table>
        <tr><td></td><td><a href="?law_id={first}">Νομοσχέδιο χωρίς ημερομηνία</a></td></tr>
        <tr><td>23/10/2026</td><td><a href="?law_id={second}">Κύρωση συμφωνίας</a></td></tr>
        </table>""",
    )

    bills = await scraper.scrape_parliament_bills(limit=1, require_dates=require_dates)

    assert len(bills) == 1
    expected_id = second if require_dates else first
    assert bills[0]["url"] == base + f"/Nomothetiko-Ergo/Psifisthenta-Nomoschedia?law_id={expected_id}"
    assert bills[0]["date"] == ("2026-10-23T00:00:00+00:00" if require_dates else None)


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

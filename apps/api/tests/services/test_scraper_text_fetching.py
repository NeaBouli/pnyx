import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from services import parliament_fetcher as fetcher

pytestmark = pytest.mark.usefixtures("scraper_clock")

DOCUMENT = "https://diavgeia.gov.gr/doc/private-ada?person=private-name"
LAW = "https://www.hellenicparliament.gr/law?person=private-name"
TEXT = "Οι αρμοδιότητες και οι προϋποθέσεις εφαρμογής της απόφασης περιγράφονται αναλυτικά. " * 10


@pytest.mark.parametrize("content_type,body", [
    ("application/pdf; charset=binary", b"%PDF-1.4 private-person"),
    ("application/octet-stream", b"%PDF-1.4 private-person"),
    ("text/plain", b"%PDF-1.4 private-person"),
])
@respx.mock
async def test_diavgeia_pdf_is_fetched_directly_and_skipped(content_type, body, caplog):
    caplog.set_level(logging.INFO)
    route = respx.get(DOCUMENT).respond(200, content=body, headers={"content-type": content_type})
    bill = SimpleNamespace(id="private-id", source="DIAVGEIA", parliament_url=DOCUMENT, summary_long_el=None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: bill)), commit=AsyncMock())

    result = await fetcher.enrich_bill_with_text(bill.id, db)

    assert result["success"] is False and result["skipped"] is True
    assert bill.parliament_url == DOCUMENT and bill.summary_long_el is None
    db.commit.assert_not_awaited()
    assert route.call_count == 1 and len(respx.calls) == 1
    assert route.calls[0].request.headers["user-agent"] == fetcher.USER_AGENT
    assert "fetched=0 skipped=1 failed=0" in caplog.text
    for private in ("private-ada", "private-person", "private-name", "private-id", "https://"):
        assert private not in caplog.text


@respx.mock
async def test_pdf_skip_does_not_download_the_body():
    closed = []

    class UnreadBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("PDF body must not be downloaded")
            yield b""

        async def aclose(self):
            closed.append(True)

    respx.get(DOCUMENT).mock(return_value=httpx.Response(
        200, headers={"content-type": "application/pdf"}, stream=UnreadBody(),
    ))
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert closed == [True]


@respx.mock
async def test_legacy_text_entrypoint_detects_diavgeia_without_source():
    respx.get(DOCUMENT).respond(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})
    assert await fetcher.fetch_bill_text("id", DOCUMENT) == ""
    assert len(respx.calls) == 1


@pytest.mark.parametrize("content_type,body", [
    ("text/plain; charset=utf-8", TEXT),
    ("text/html", f"<main><p>{TEXT}</p></main>"),
])
@respx.mock
async def test_diavgeia_text_can_be_enriched_directly(content_type, body, caplog):
    caplog.set_level(logging.INFO)
    respx.get(DOCUMENT).respond(200, text=body, headers={"content-type": content_type})
    text = await fetcher.fetch_bill_text("id", DOCUMENT, source="DIAVGEIA")
    assert len(text) >= fetcher.MIN_TEXT_LENGTH and "<main>" not in text
    assert len(respx.calls) == 1
    assert "fetched=1 skipped=0 failed=0" in caplog.text


@respx.mock
async def test_unknown_document_type_is_skipped():
    respx.get(DOCUMENT).respond(200, content=b"binary data", headers={"content-type": "image/png"})
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert len(respx.calls) == 1


@pytest.mark.parametrize("channel", [fetcher._channel_jina_markdown, fetcher._channel_jina_html])
@pytest.mark.parametrize("status,expected_time", [(422, 1005), (429, 1030), (503, 1030)])
@respx.mock
async def test_jina_non_200_retries_are_delayed(channel, status, expected_time, scraper_clock):
    times = []

    def respond(request):
        times.append(scraper_clock.now)
        return httpx.Response(status, headers={"Retry-After": "30"} if status in (429, 503) else {})

    route = respx.get(f"{fetcher.JINA_URL}{LAW}").mock(side_effect=respond)
    assert await channel(LAW) == ""
    assert route.call_count == 2
    assert times == [1000, expected_time]
    assert 3 in scraper_clock.sleeps  # regression: continue used to bypass this sleep


@respx.mock
async def test_jina_403_is_one_attempt_across_channels(scraper_clock):
    from services.scraper_http import HostCooldown

    route = respx.get(f"{fetcher.JINA_URL}{LAW}").respond(403)
    for channel in (fetcher._channel_jina_markdown, fetcher._channel_jina_html):
        with pytest.raises(HostCooldown):
            await channel(LAW)
    assert route.call_count == 1 and scraper_clock.sleeps == []


@respx.mock
async def test_direct_diavgeia_retries_are_paced(scraper_clock):
    times = []

    def respond(request):
        times.append(scraper_clock.now)
        return httpx.Response(503, headers={"Retry-After": "30"}) if len(times) == 1 else httpx.Response(200, text=TEXT)

    respx.get(DOCUMENT).mock(side_effect=respond)
    assert await fetcher.fetch_bill_text("id", DOCUMENT) == TEXT.strip()
    assert times == [1000, 1030]


@respx.mock
async def test_exceptions_and_failed_run_counts_do_not_leak(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    respx.get(f"{fetcher.JINA_URL}{LAW}").mock(side_effect=httpx.ConnectError("private-name " + LAW))
    respx.get(LAW).mock(side_effect=httpx.ConnectError("private-name " + LAW))
    monkeypatch.setattr(fetcher, "_channel_playwright", AsyncMock(return_value=""))
    assert await fetcher.fetch_bill_text("private-id", LAW) == ""
    assert "fetched=0 skipped=0 failed=1" in caplog.text
    for private in ("private-name", "private-id", "https://"):
        assert private not in caplog.text


@respx.mock
async def test_ollama_attempts_use_the_host_limiter(scraper_clock):
    times = []
    respx.get(f"{fetcher.JINA_URL}{LAW}").respond(200, text=f"<main>{TEXT}</main>")

    def respond(request):
        times.append(scraper_clock.now)
        return httpx.Response(503, headers={"Retry-After": "30"}) if len(times) == 1 else httpx.Response(200, json={"response": TEXT})

    respx.post(f"{fetcher.OLLAMA_URL}/api/generate").mock(side_effect=respond)
    assert await fetcher._channel_ollama_extract(LAW) == TEXT.strip()
    assert times == [1000, 1030]


@respx.mock
async def test_browser_requests_and_redirects_use_shared_http_pacing(scraper_clock, monkeypatch):
    import sys

    times = []

    def respond(request):
        times.append(scraper_clock.now)
        if request.url.path == "/law":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, text=TEXT)

    respx.get(LAW).mock(side_effect=respond)
    respx.get("https://www.hellenicparliament.gr/final").mock(side_effect=respond)
    respx.get("https://www.hellenicparliament.gr/script.js").mock(side_effect=respond)

    class Page:
        async def route(self, pattern, callback):
            self.callback = callback

        async def goto(self, url, **kwargs):
            for request_url in (url, "https://www.hellenicparliament.gr/script.js"):
                route = SimpleNamespace(
                    request=SimpleNamespace(
                        url=request_url, method="GET", post_data_buffer=None,
                        all_headers=AsyncMock(return_value={"user-agent": fetcher.USER_AGENT}),
                    ),
                    abort=AsyncMock(), fulfill=AsyncMock(),
                )
                await self.callback(route)
                route.fulfill.assert_awaited_once()
            return SimpleNamespace(status=200, url=url)

        async def inner_text(self, selector):
            return TEXT

    browser = SimpleNamespace(new_page=AsyncMock(return_value=Page()), close=AsyncMock())

    class Playwright:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

        async def __aexit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=Playwright))
    assert await fetcher._channel_playwright(LAW) == TEXT.strip()
    assert times == [1000, 1005, 1010]
    browser.new_page.assert_awaited_once_with(user_agent=fetcher.USER_AGENT, service_workers="block")
    browser.close.assert_awaited_once()

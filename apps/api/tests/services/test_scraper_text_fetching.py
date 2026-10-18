import asyncio
import gzip
import logging
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import respx

from services import parliament_fetcher as fetcher

pytestmark = pytest.mark.usefixtures("scraper_clock")

DOCUMENT = "https://diavgeia.gov.gr/doc/private-ada?person=private-name"
# Generic fallback channels remain available for non-Parliament sources (T-9147).
LAW = "https://source.example.org/law?person=private-name"
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


@pytest.mark.parametrize("content_type", ["text/plain", "text/html"])
@pytest.mark.parametrize("chunks", [[b"%PDF-1.4"], [b"%", b"P", b"D", b"F", b"-"], [b"%PD", b"F-1.4"]])
@respx.mock
async def test_mislabeled_pdf_stops_at_signature(content_type, chunks):
    closed = []

    class PDFBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            for chunk in chunks:
                yield chunk
            raise AssertionError("Must stop before reading the rest of the PDF")

        async def aclose(self):
            closed.append(True)

    route = respx.get(DOCUMENT).mock(return_value=httpx.Response(
        200, headers={"content-type": content_type}, stream=PDFBody(),
    ))
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert closed == [True] and route.call_count == 1


@pytest.mark.parametrize("compressed", [False, True])
@respx.mock
async def test_document_body_limit_stops_stream_and_closes(monkeypatch, compressed):
    monkeypatch.setattr(fetcher, "MAX_DOCUMENT_BYTES", 32)
    closed = []

    class LargeBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            if compressed:
                yield gzip.compress(b"x" * 33)
            else:
                yield b"x" * 16
                yield b"x" * 17
            raise AssertionError("Must stop when decoded body exceeds the limit")

        async def aclose(self):
            closed.append(True)

    headers = {"content-type": "text/plain", "content-length": "1"}
    if compressed:
        headers["content-encoding"] = "gzip"
    route = respx.get(DOCUMENT).mock(return_value=httpx.Response(200, headers=headers, stream=LargeBody()))
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert closed == [True] and route.call_count == 1


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "br", "gzip, br", "unknown"])
@respx.mock
async def test_encoded_document_is_skipped_before_reading_or_decoding(monkeypatch, encoding):
    closed = []

    class EncodedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("An encoded body must never be read")
            yield b""

        async def aclose(self):
            closed.append(True)

    def decoded_body(*args, **kwargs):
        raise AssertionError("Document downloads must not use HTTPX decompression")

    monkeypatch.setattr(httpx.Response, "aiter_bytes", decoded_body)
    route = respx.get(DOCUMENT).mock(return_value=httpx.Response(
        200, headers={"content-type": "text/plain", "content-encoding": encoding}, stream=EncodedBody(),
    ))
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert route.call_count == 1 and closed == [True]
    assert route.calls[0].request.headers["accept-encoding"] == "identity"


@pytest.mark.parametrize("encoding", [None, "identity", " Identity "])
@respx.mock
async def test_document_at_body_limit_preserves_split_utf8(monkeypatch, encoding):
    body = TEXT.encode()
    monkeypatch.setattr(fetcher, "MAX_DOCUMENT_BYTES", len(body))

    class TextBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield body[:1]
            yield body[1:3]
            yield body[3:]

    headers = {"content-type": "text/plain; charset=utf-8"}
    if encoding is not None:
        headers["content-encoding"] = encoding
    respx.get(DOCUMENT).mock(return_value=httpx.Response(200, headers=headers, stream=TextBody()))
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == (TEXT.strip(), "fetched")


@pytest.mark.parametrize("terminal_kind", ["text", "oversized", "encoded"])
@respx.mock
async def test_document_redirect_chain_preserves_body_caps(monkeypatch, scraper_clock, terminal_kind):
    body = TEXT.encode()
    monkeypatch.setattr(fetcher, "MAX_DOCUMENT_BYTES", len(body))
    times = []
    closed = []

    class FinalBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            assert terminal_kind != "encoded", "Encoded terminal body must remain unread"
            yield body
            if terminal_kind == "oversized":
                yield b"x"
                raise AssertionError("Must stop at the terminal body cap")

        async def aclose(self):
            closed.append(True)

    def respond(request):
        times.append(scraper_clock.now)
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["scraper_source_url"] == DOCUMENT
        if len(times) <= 3:
            return httpx.Response(302, headers={"location": f"/doc/hop-{len(times)}"})
        headers = {"content-type": "text/plain", "content-length": "1"}
        if terminal_kind == "encoded":
            headers["content-encoding"] = "gzip"
        return httpx.Response(200, headers=headers, stream=FinalBody())

    respx.route(method="GET", host="diavgeia.gov.gr").mock(side_effect=respond)
    expected = (TEXT.strip(), "fetched") if terminal_kind == "text" else ("", "skipped")
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == expected
    assert times == [1000, 1005, 1010, 1015]
    assert closed == [True]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("compressed", [False, True])
@respx.mock
async def test_oversized_redirect_body_is_closed_unread(monkeypatch, status, compressed):
    body = b"x" * (2 * fetcher.MAX_DOCUMENT_BYTES)
    if compressed:
        body = gzip.compress(body)
    read = []
    closed = []

    class RedirectBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            read.append(True)
            yield body

        async def aclose(self):
            closed.append(True)

    class FinalBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield TEXT.encode()

    def decoded_body(*args, **kwargs):
        raise AssertionError("Redirects must not invoke HTTPX decompression")

    monkeypatch.setattr(httpx.Response, "aiter_bytes", decoded_body)
    headers = {"location": "/doc/final", "content-type": "text/plain", "content-length": str(len(body))}
    if compressed:
        headers["content-encoding"] = "gzip"
    respx.get(DOCUMENT).mock(return_value=httpx.Response(status, headers=headers, stream=RedirectBody()))
    respx.get("https://diavgeia.gov.gr/doc/final").mock(return_value=httpx.Response(
        200, headers={"content-type": "text/plain; charset=utf-8"}, stream=FinalBody(),
    ))

    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == (TEXT.strip(), "fetched")
    assert read == [] and closed == [True]
    assert len(respx.calls) == 2


@pytest.mark.parametrize("target", [
    "https://example.org/doc/private",
    "//example.org/doc/private",
    "https://diavgeia.gov.gr.example.org/doc/private",
    "https://diavgeia.gov.gr@example.org/doc/private",
    "https://unknown.diavgeia.gov.gr/doc/private",
    "http://diavgeia.gov.gr/doc/private",
])
@respx.mock
async def test_document_redirect_rejects_untrusted_target(target, caplog):
    caplog.set_level(logging.INFO)
    respx.get(DOCUMENT).respond(302, headers={"location": target})

    assert await fetcher._fetch_bill_text_result("private-id", DOCUMENT) == ("", "skipped")
    assert len(respx.calls) == 1
    assert "https://" not in caplog.text and "private" not in caplog.text


@pytest.mark.parametrize("url", ["http://diavgeia.gov.gr/doc/private", "https://example.org/doc/private"])
@respx.mock
async def test_document_rejects_untrusted_initial_url(url):
    assert await fetcher._fetch_diavgeia_document(url) == ("", "skipped")
    assert len(respx.calls) == 0


@pytest.mark.parametrize("redirect_kind", ["chain", "self", "cycle"])
@respx.mock
async def test_document_redirect_limit_closes_last_body_without_retry(scraper_clock, redirect_kind):
    times = []
    closed = []

    class RedirectBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("Redirect bodies must remain unread even at the hop limit")
            yield b""

        async def aclose(self):
            closed.append(True)

    def respond(request):
        times.append(scraper_clock.now)
        if redirect_kind == "chain":
            target = f"/doc/hop-{len(times)}"
        elif redirect_kind == "self" or request.url.path == "/doc/loop":
            target = DOCUMENT
        else:
            target = "/doc/loop"
        return httpx.Response(302, headers={"location": target}, stream=RedirectBody())

    respx.route(method="GET", host="diavgeia.gov.gr").mock(side_effect=respond)
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == ("", "skipped")
    assert times == [1000, 1005, 1010, 1015]
    assert closed == [True] * 4


@pytest.mark.parametrize("status", [403, 429, 503])
@respx.mock
async def test_document_redirect_target_uses_cooldown_and_retry_after(scraper_clock, status):
    times = []
    respx.get(DOCUMENT).respond(302, headers={"location": "/doc/final"})

    def respond(request):
        times.append(scraper_clock.now)
        if len(times) == 1:
            return httpx.Response(status, headers={"retry-after": "30"})
        return httpx.Response(200, text=TEXT)

    respx.get("https://diavgeia.gov.gr/doc/final").mock(side_effect=respond)
    expected = ("", "skipped") if status == 403 else (TEXT.strip(), "fetched")
    assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == expected
    if status == 403:
        assert await fetcher._fetch_bill_text_result("id", DOCUMENT) == expected
        assert times == [1005] and len(respx.calls) == 2
    else:
        assert times == [1005, 1040] and len(respx.calls) == 4


@pytest.mark.parametrize("channel", [
    fetcher._channel_jina_markdown, fetcher._channel_jina_html,
    fetcher._channel_ollama_extract, fetcher._fetch_diavgeia_document,
])
@respx.mock
async def test_attempt_deadline_includes_limiter_wait(monkeypatch, scraper_clock, offline_http_client, channel):
    monkeypatch.setattr(fetcher, "TIMEOUT", 0.03)
    monkeypatch.setattr(fetcher, "MAX_RETRIES", 1)
    entered = asyncio.Event()

    async def queued(url):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(scraper_clock.limiter, "acquire", queued)
    result = await asyncio.wait_for(channel(DOCUMENT), timeout=5)
    assert entered.is_set()
    assert result == (("", "failed") if channel is fetcher._fetch_diavgeia_document else "")
    assert len(respx.calls) == 0


@respx.mock
async def test_attempt_deadline_bounds_trickling_body_and_retries(monkeypatch, scraper_clock, offline_http_client):
    monkeypatch.setattr(fetcher, "TIMEOUT", 0.06)
    consumed = []
    closed = []

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.01)
                consumed.append(True)
                yield b"ordinary document text "

        async def aclose(self):
            closed.append(True)

    route = respx.get(DOCUMENT).mock(side_effect=lambda request: httpx.Response(
        200, headers={"content-type": "text/plain"}, stream=SlowBody(),
    ))
    assert await asyncio.wait_for(fetcher._fetch_bill_text_result("id", DOCUMENT), timeout=5) == ("", "failed")
    assert route.call_count == fetcher.MAX_RETRIES == len(closed)
    assert 0 < len(consumed) < 100


@pytest.mark.parametrize("blocked_stage", ["launch", "new_page", "goto", "inner_text", "close", "goto_and_close"])
async def test_browser_attempt_has_overall_deadline(monkeypatch, offline_http_client, blocked_stage):
    monkeypatch.setattr(fetcher, "TIMEOUT", 0.03)
    monkeypatch.setattr(fetcher, "PLAYWRIGHT_TEARDOWN_TIMEOUT", 0.02)
    monkeypatch.setattr(fetcher, "MAX_RETRIES", 1)
    reached = []

    async def block(*args, **kwargs):
        reached.append(blocked_stage)
        await asyncio.Event().wait()

    page = SimpleNamespace(
        route=AsyncMock(), goto=AsyncMock(return_value=SimpleNamespace(status=200)),
        inner_text=AsyncMock(return_value=TEXT),
    )
    browser = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))
    if blocked_stage == "goto_and_close":
        page.goto.side_effect = block
        browser.close.side_effect = block
    else:
        target = chromium if blocked_stage == "launch" else browser if blocked_stage in ("new_page", "close") else page
        getattr(target, blocked_stage).side_effect = block

    class Playwright:
        async def __aenter__(self):
            return SimpleNamespace(chromium=chromium)

        async def __aexit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=Playwright))
    assert await asyncio.wait_for(fetcher._channel_playwright(LAW), timeout=5) == ""
    assert reached
    if blocked_stage != "launch":
        browser.close.assert_awaited_once()


@pytest.mark.parametrize("blocked_stage", [None, "enter", "launch", "goto", "close", "goto_and_close"])
@pytest.mark.parametrize("slow_cancellation", [False, True])
async def test_browser_context_teardown_is_bounded_and_kills_driver(
    monkeypatch, offline_http_client, blocked_stage, slow_cancellation,
):
    monkeypatch.setattr(fetcher, "TIMEOUT", 0.05)
    monkeypatch.setattr(fetcher, "PLAYWRIGHT_TEARDOWN_TIMEOUT", 0.02)
    monkeypatch.setattr(fetcher, "MAX_RETRIES", 1)
    killed = asyncio.Event()
    exited = asyncio.Event()
    stopped = asyncio.Event()

    async def block(*args, **kwargs):
        await asyncio.Event().wait()

    page = SimpleNamespace(
        route=AsyncMock(), goto=AsyncMock(return_value=SimpleNamespace(status=200)),
        inner_text=AsyncMock(return_value=TEXT),
    )
    browser = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))
    if blocked_stage == "launch":
        chromium.launch.side_effect = block
    if blocked_stage in ("goto", "goto_and_close"):
        page.goto.side_effect = block
    if blocked_stage in ("close", "goto_and_close"):
        browser.close.side_effect = block

    def kill():
        process.returncode = -9
        killed.set()

    process = SimpleNamespace(returncode=None, kill=Mock(side_effect=kill))

    class Playwright:
        _connection = SimpleNamespace(_transport=SimpleNamespace(_proc=process))

        async def __aenter__(self):
            if blocked_stage == "enter":
                await block()
            return SimpleNamespace(chromium=chromium)

        async def __aexit__(self, *args):
            exited.set()
            try:
                await block()
            except asyncio.CancelledError:
                if slow_cancellation:
                    await killed.wait()
                else:
                    raise
            finally:
                stopped.set()

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=Playwright))
    assert await asyncio.wait_for(fetcher._channel_playwright(LAW), timeout=4 * fetcher.TIMEOUT) == ""
    assert exited.is_set()
    process.kill.assert_called_once_with()
    await asyncio.wait_for(stopped.wait(), timeout=0.1)
    if blocked_stage not in ("enter", "launch"):
        browser.close.assert_awaited_once()


@respx.mock
async def test_browser_background_routes_share_attempt_deadline(monkeypatch, scraper_clock, offline_http_client):
    monkeypatch.setattr(fetcher, "TIMEOUT", 0.06)
    monkeypatch.setattr(fetcher, "MAX_RETRIES", 1)
    entered_queue = asyncio.Event()
    tasks = []
    route = SimpleNamespace(
        request=SimpleNamespace(
            url=LAW, method="GET", post_data_buffer=None,
            all_headers=AsyncMock(return_value={}),
        ),
        abort=AsyncMock(), fulfill=AsyncMock(),
    )

    async def queued(url):
        entered_queue.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(scraper_clock.limiter, "acquire", queued)

    class Page:
        async def route(self, pattern, callback):
            self.callback = callback

        async def goto(self, *args, **kwargs):
            tasks.append(asyncio.create_task(self.callback(route)))
            await entered_queue.wait()
            await asyncio.Event().wait()

    browser = SimpleNamespace(new_page=AsyncMock(return_value=Page()), close=AsyncMock())

    class Playwright:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

        async def __aexit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=Playwright))
    assert await asyncio.wait_for(fetcher._channel_playwright(LAW), timeout=5) == ""
    assert entered_queue.is_set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
    route.abort.assert_awaited_once()
    route.fulfill.assert_not_awaited()
    browser.close.assert_awaited_once()
    assert len(respx.calls) == 0


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
    respx.get("https://source.example.org/final").mock(side_effect=respond)
    respx.get("https://source.example.org/script.js").mock(side_effect=respond)

    class Page:
        async def route(self, pattern, callback):
            self.callback = callback

        async def goto(self, url, **kwargs):
            for request_url in (url, "https://source.example.org/script.js"):
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

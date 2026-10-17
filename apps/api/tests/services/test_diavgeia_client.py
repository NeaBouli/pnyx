"""
Tests for Diavgeia API Client — uses respx to mock all HTTP calls.
NEVER hits live Diavgeia API.
"""
import asyncio
import json
import os

import pytest
import respx
import httpx

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.diavgeia_client import DiavgeiaClient, parse_timestamp, BASE_URL


pytestmark = pytest.mark.usefixtures("scraper_clock")

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "diavgeia_response_fixture.json")

with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
    FIXTURE_DATA = json.load(f)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Timestamp Parsing ───────────────────────────────────────────────────────

def test_parse_iso_timestamp():
    ts = parse_timestamp("2026-04-20T10:30:00Z")
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 4
    assert ts.day == 20
    assert ts.hour == 10
    assert ts.minute == 30


def test_parse_legacy_timestamp():
    ts = parse_timestamp("24/04/2026 09:15:00")
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 4
    assert ts.day == 24
    assert ts.hour == 9


def test_parse_iso_without_z():
    ts = parse_timestamp("2026-04-20T10:30:00")
    assert ts is not None
    assert ts.hour == 10


def test_parse_date_only():
    ts = parse_timestamp("24/04/2026")
    assert ts is not None
    assert ts.year == 2026


def test_parse_empty():
    assert parse_timestamp("") is None
    assert parse_timestamp(None) is None


def test_parse_garbage():
    assert parse_timestamp("not-a-date") is None


# ── Client: Pagination ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_pagination():
    """Client should paginate until empty page."""
    page0 = {"decisions": FIXTURE_DATA["decisions"]}
    page1 = {"decisions": []}

    respx.get(f"{BASE_URL}/search.json").mock(
        side_effect=[
            httpx.Response(200, json=page0),
            httpx.Response(200, json=page1),
        ]
    )

    client = DiavgeiaClient()
    decisions = []
    async for d in client.iter_decisions(max_pages=5):
        decisions.append(d)

    assert len(decisions) == 3
    assert decisions[0]["ada"] == "Ε7ΞΥ46ΜΨΦΖ-ΔΝΖ"
    await client.close()


# ── Client: Rate Limit ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_enforcement(scraper_clock):
    """Separate clients share one host limit without real-time sleeps."""
    respx.get(f"{BASE_URL}/organizations.json").mock(
        return_value=httpx.Response(200, json={"organizations": []})
    )
    async with DiavgeiaClient() as first, DiavgeiaClient() as second:
        await first.list_organizations()
        await second.list_organizations()
    assert scraper_clock.now == 1005


# ── Client: Retry on 5xx ────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_retry_on_5xx():
    """Should retry on 500 and eventually succeed."""
    respx.get(f"{BASE_URL}/organizations.json").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"organizations": [{"uid": "1", "label": "Test"}]}),
        ]
    )

    client = DiavgeiaClient()
    result = await client.list_organizations()
    assert "organizations" in result
    assert len(result["organizations"]) == 1
    await client.close()


# ── Client: No Retry on 4xx ─────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_no_retry_on_4xx():
    """Should NOT retry on 400/404 — raise immediately."""
    respx.get(f"{BASE_URL}/organizations.json").mock(
        return_value=httpx.Response(404)
    )

    client = DiavgeiaClient()
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.list_organizations()
    assert exc_info.value.response.status_code == 404
    await client.close()


# ── Client: Retry on 429 ────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_retry_on_429():
    """Should retry on 429 (rate limited)."""
    respx.get(f"{BASE_URL}/search.json").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"decisions": []}),
        ]
    )

    client = DiavgeiaClient()
    result = await client.search_decisions()
    assert result == {"decisions": []}
    await client.close()


# ── Client: Organizations ───────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_organizations():
    respx.get(f"{BASE_URL}/organizations.json").mock(
        return_value=httpx.Response(200, json={
            "organizations": [
                {"uid": "6183", "label": "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ", "category": "MUNICIPALITY"},
            ]
        })
    )

    client = DiavgeiaClient()
    result = await client.list_organizations()
    assert len(result["organizations"]) == 1
    assert result["organizations"][0]["uid"] == "6183"
    await client.close()


@pytest.mark.parametrize("status", [429, 503])
@respx.mock
async def test_every_retry_honours_retry_after(scraper_clock, status):
    times = []

    def respond(request):
        times.append(scraper_clock.now)
        if len(times) == 1:
            return httpx.Response(status, headers={"Retry-After": "30"})
        return httpx.Response(200, json={"organizations": []})

    respx.get(f"{BASE_URL}/organizations.json").mock(side_effect=respond)
    async with DiavgeiaClient() as client:
        await client.list_organizations()
    assert times == [1000, 1030]


@respx.mock
async def test_forbidden_cools_down_other_clients_and_documents(scraper_clock):
    from services.parliament_fetcher import fetch_bill_text
    from services.scraper_http import HostCooldown

    route = respx.get(f"{BASE_URL}/organizations.json").respond(403)
    async with DiavgeiaClient() as first, DiavgeiaClient() as second:
        with pytest.raises(httpx.HTTPStatusError):
            await first.list_organizations()
        with pytest.raises(HostCooldown):
            await second.search_decisions()
        assert await fetch_bill_text("private-id", "https://diavgeia.gov.gr/doc/private") == ""
    assert route.call_count == 1
    assert len(respx.calls) == 1
    assert scraper_clock.sleeps == []


@respx.mock
async def test_logs_omit_request_data_and_timestamps(scraper_clock, caplog):
    import logging

    caplog.set_level(logging.INFO)
    secret = "private-person@example.org"
    respx.get(f"{BASE_URL}/search.json").respond(200, json={"decisions": []})
    async with DiavgeiaClient() as client:
        await client.search_decisions(organization_uid=secret)
    parse_timestamp(secret)
    assert secret not in caplog.text
    assert "https://" not in caplog.text
    assert "response status=200" in caplog.text


@respx.mock
async def test_overall_attempt_deadline_includes_queue_and_retries(scraper_clock, monkeypatch, offline_http_client):
    from services import diavgeia_client

    attempts = []

    async def queued(url):
        attempts.append(url)
        await asyncio.Event().wait()

    monkeypatch.setattr(scraper_clock.limiter, "acquire", queued)
    async with DiavgeiaClient(timeout=0.03) as client:
        async with asyncio.timeout(5):
            with pytest.raises(TimeoutError):
                await client.list_organizations()
    assert len(attempts) == diavgeia_client.MAX_RETRIES
    assert len(respx.calls) == 0


@respx.mock
async def test_overall_attempt_deadline_bounds_trickling_json(monkeypatch, offline_http_client):
    from services import diavgeia_client

    monkeypatch.setattr(diavgeia_client, "MAX_RETRIES", 1)
    consumed = []
    closed = []

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"organizations": ['
            for _ in range(100):
                await asyncio.sleep(0.01)
                consumed.append(True)
                yield b" "
            yield b"]}"

        async def aclose(self):
            closed.append(True)

    respx.get(f"{BASE_URL}/organizations.json").mock(return_value=httpx.Response(200, stream=SlowBody()))
    async with DiavgeiaClient(timeout=0.06) as client:
        async with asyncio.timeout(5):
            with pytest.raises(TimeoutError):
                await client.list_organizations()
    assert 0 < len(consumed) < 100
    assert closed == [True]

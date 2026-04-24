"""
Tests for Diavgeia API Client — uses respx to mock all HTTP calls.
NEVER hits live Diavgeia API.
"""
import json
import os
import time

import pytest
import respx
import httpx

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.diavgeia_client import DiavgeiaClient, parse_timestamp, BASE_URL


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
    client._last_request_at = None  # skip throttle for tests
    decisions = []
    async for d in client.iter_decisions(max_pages=5):
        decisions.append(d)
        client._last_request_at = None  # skip throttle between pages

    assert len(decisions) == 3
    assert decisions[0]["ada"] == "Ε7ΞΥ46ΜΨΦΖ-ΔΝΖ"
    await client.close()


# ── Client: Rate Limit ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_enforcement():
    """_throttle should enforce minimum delay."""
    respx.get(f"{BASE_URL}/organizations.json").mock(
        return_value=httpx.Response(200, json={"organizations": []})
    )

    client = DiavgeiaClient()
    # Set last request to now
    client._last_request_at = time.monotonic()
    start = time.monotonic()
    await client._throttle()
    elapsed = time.monotonic() - start
    # Should have waited ~5 seconds (allow tolerance since test env)
    assert elapsed >= 4.5
    await client.close()


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
    client._last_request_at = None
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
    client._last_request_at = None
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
    client._last_request_at = None
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
    client._last_request_at = None
    result = await client.list_organizations()
    assert len(result["organizations"]) == 1
    assert result["organizations"][0]["uid"] == "6183"
    await client.close()

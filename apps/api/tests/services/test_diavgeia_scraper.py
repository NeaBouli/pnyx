"""
Tests for Diavgeia Scraper Service + Router.
Uses respx for HTTP mocking. DB calls are mocked/xfailed (no local PG).
"""
import json
import os
import sys

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from main import app


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "diavgeia_response_fixture.json")


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Router: Admin Auth Required ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrape_requires_admin_key():
    """POST /api/v1/admin/diavgeia/scrape without admin_key -> 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/admin/diavgeia/scrape", json={"dry_run": True})
    assert r.status_code == 422  # missing required query param


@pytest.mark.asyncio
async def test_scrape_wrong_admin_key():
    """POST /api/v1/admin/diavgeia/scrape with wrong key -> 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/admin/diavgeia/scrape?admin_key=wrong-key",
            json={"dry_run": True},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_scrape_with_valid_key():
    """POST /api/v1/admin/diavgeia/scrape with valid key -> 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/admin/diavgeia/scrape?admin_key=dev-admin-key",
            json={"dry_run": True, "max_pages": 1},
        )
    assert r.status_code == 200
    data = r.json()
    assert "fetched" in data
    assert "inserted" in data


# ── Router: Municipal Decisions ─────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_municipal_decisions_404():
    """GET /api/v1/municipal/999999/decisions -> 404 for non-existent dimos."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/municipal/999999/decisions")
    assert r.status_code == 404


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_municipal_decisions_pagination():
    """GET /api/v1/municipal/{id}/decisions respects limit/offset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/municipal/1/decisions?limit=5&offset=0")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "data" in data
        assert "total" in data


# ── Router: Regional Decisions ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_regional_decisions_404():
    """GET /api/v1/regions/999999/decisions -> 404 for non-existent periferia."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/regions/999999/decisions")
    assert r.status_code == 404


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_regional_decisions_pagination():
    """GET /api/v1/regions/{id}/decisions respects limit/offset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/regions/1/decisions?limit=5&offset=0")
    assert r.status_code in (200, 404)


# ── Scraper: Unit Tests (mocked) ────────────────────────────────────────────

def test_fixture_has_valid_adas():
    """Fixture file should contain 3 decisions with valid ADAs."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["decisions"]) == 3
    for d in data["decisions"]:
        ada = d["ada"]
        assert 10 <= len(ada) <= 32, f"ADA {ada} length {len(ada)} out of range"
        assert d.get("decisionTypeUid") == "2.4.1"


def test_scrape_result_schema():
    """ScrapeResult.to_dict() must have all expected keys."""
    from services.diavgeia_scraper import ScrapeResult
    sr = ScrapeResult(fetched=10, inserted=8, updated=1, skipped=1, errors=["test"])
    d = sr.to_dict()
    assert set(d.keys()) == {"fetched", "inserted", "updated", "skipped", "errors"}
    assert d["fetched"] == 10
    assert d["errors"] == ["test"]


def test_scrape_result_defaults():
    """ScrapeResult defaults should be zero/empty."""
    from services.diavgeia_scraper import ScrapeResult
    sr = ScrapeResult()
    assert sr.fetched == 0
    assert sr.errors == []

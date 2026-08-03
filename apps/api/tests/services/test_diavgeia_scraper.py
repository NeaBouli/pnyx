"""
Tests for Diavgeia Scraper Service + Router.
Uses respx for HTTP mocking. DB calls are mocked/xfailed (no local PG).
"""
import json
import os
import sys
from types import SimpleNamespace

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
    """POST /api/v1/admin/diavgeia/scrape without Bearer token -> 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/admin/diavgeia/scrape", json={"dry_run": True})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_scrape_wrong_admin_key():
    """POST /api/v1/admin/diavgeia/scrape with wrong Bearer -> 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/admin/diavgeia/scrape",
            json={"dry_run": True},
            headers={"Authorization": "Bearer wrong-key"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline — no local PostgreSQL")
async def test_scrape_with_valid_key():
    """POST /api/v1/admin/diavgeia/scrape with valid Bearer -> 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/admin/diavgeia/scrape",
            json={"dry_run": True, "max_pages": 1},
            headers={"Authorization": "Bearer dev-admin-key"},
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


@pytest.mark.asyncio
async def test_manual_scrape_runs_scope_sync_via_conversion(monkeypatch):
    from routers import diavgeia
    from services.diavgeia_scraper import ScrapeResult

    calls = []

    async def scrape_decisions(**kwargs):
        calls.append(("scrape", kwargs["dry_run"]))
        return ScrapeResult(fetched=1, inserted=1)

    async def convert_decisions_to_bills(session):
        calls.append(("convert", session))
        return {"created": 0, "skipped": 0, "scope_synced": 1, "total_checked": 0}

    monkeypatch.setattr("services.diavgeia_scraper.scrape_decisions", scrape_decisions)
    monkeypatch.setattr(
        "services.diavgeia_scraper.convert_decisions_to_bills",
        convert_decisions_to_bills,
    )
    db = object()
    result = await diavgeia.admin_scrape_diavgeia(
        diavgeia.ScrapeRequest(max_pages=1),
        _key="admin",
        db=db,
    )

    assert calls == [("scrape", False), ("convert", db)]
    assert result["conversion"]["scope_synced"] == 1


@pytest.mark.asyncio
async def test_manual_scrape_dry_run_never_converts_or_mutates(monkeypatch):
    from routers import diavgeia
    from services.diavgeia_scraper import ScrapeResult

    async def scrape_decisions(**kwargs):
        assert kwargs["dry_run"] is True
        return ScrapeResult(fetched=1, inserted=1)

    async def convert_decisions_to_bills(_session):
        raise AssertionError("dry-run must not convert")

    monkeypatch.setattr("services.diavgeia_scraper.scrape_decisions", scrape_decisions)
    monkeypatch.setattr(
        "services.diavgeia_scraper.convert_decisions_to_bills",
        convert_decisions_to_bills,
    )
    result = await diavgeia.admin_scrape_diavgeia(
        diavgeia.ScrapeRequest(max_pages=1, dry_run=True),
        _key="admin",
        db=object(),
    )

    assert "conversion" not in result


def test_upsert_refreshes_geographic_scope_fields():
    from services.diavgeia_scraper import _upsert_update_values

    excluded = SimpleNamespace(**{
        name: object()
        for name in (
            "subject",
            "decision_type_label",
            "organization_label",
            "document_url",
            "raw_payload",
            "dimos_id",
            "periferia_id",
            "governance_level",
            "fetched_at",
        )
    })
    values = _upsert_update_values(SimpleNamespace(excluded=excluded))

    assert set(values) == {
        "subject",
        "decision_type_label",
        "organization_label",
        "document_url",
        "raw_payload",
        "dimos_id",
        "periferia_id",
        "governance_level",
        "fetched_at",
    }


def test_unknown_raw_scope_never_defaults_to_national():
    from models import GovernanceLevel
    from services.diavgeia_scraper import _canonical_bill_scope

    assert _canonical_bill_scope("UNKNOWN", None, None) == (
        GovernanceLevel.INSTITUTIONAL,
        None,
        None,
    )
    assert _canonical_bill_scope("REGION", None, 6) == (
        GovernanceLevel.REGIONAL,
        None,
        6,
    )
    assert _canonical_bill_scope("MUNICIPAL", 22, 6) == (
        GovernanceLevel.MUNICIPAL,
        22,
        6,
    )


@pytest.mark.asyncio
async def test_scope_sync_repairs_only_geographic_metadata():
    from services.diavgeia_scraper import _sync_existing_decision_bill_scopes

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{
                "bill_id": "DIAV-TEST",
                "bill_governance_level": "NATIONAL",
                "bill_dimos_id": None,
                "bill_periferia_id": None,
                "raw_governance_level": "MUNICIPAL",
                "raw_dimos_id": 22,
                "raw_periferia_id": 6,
            }]

    class Session:
        def __init__(self):
            self.calls = []

        async def execute(self, statement, params=None):
            self.calls.append((str(statement), params))
            return Result()

    session = Session()
    updated = await _sync_existing_decision_bill_scopes(session)

    assert updated == 1
    update_sql, params = session.calls[1]
    assert "UPDATE parliament_bills" in update_sql
    assert "title_el" not in update_sql
    assert "status" not in update_sql
    assert params == {
        "bill_id": "DIAV-TEST",
        "governance_level": "MUNICIPAL",
        "dimos_id": 22,
        "periferia_id": 6,
    }

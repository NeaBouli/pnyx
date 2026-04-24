"""
Tests for seed_diavgeia_orgs (snapshot mode) and backfill_diavgeia_decisions.
"""
import gzip
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


SAMPLE_SNAPSHOT = {
    "metadata": {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_count": 3,
        "source_url": "https://diavgeia.gov.gr/luminapi/opendata/organizations.json",
        "api_version_hint": "luminapi-v1",
        "script_version": "1.0",
    },
    "organizations": [
        {"uid": "6013", "label": "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ", "category": "MUNICIPALITY", "parent_uid": None, "status": "active"},
        {"uid": "6219", "label": "ΔΗΜΟΣ ΘΕΣΣΑΛΟΝΙΚΗΣ", "category": "MUNICIPALITY", "parent_uid": None, "status": "active"},
        {"uid": "99999", "label": "ΥΠΟΥΡΓΕΙΟ ΕΣΩΤΕΡΙΚΩΝ", "category": "MINISTRY", "parent_uid": None, "status": "active"},
    ],
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Seed: snapshot loading ──────────────────────────────────────────────────

def test_seed_load_snapshot_valid():
    """load_snapshot should parse a valid JSON file."""
    from scripts.seed_diavgeia_orgs import load_snapshot
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(SAMPLE_SNAPSHOT, f, ensure_ascii=False)
        f.flush()
        path = Path(f.name)
    try:
        data = load_snapshot(path)
        assert data["metadata"]["total_count"] == 3
        assert len(data["organizations"]) == 3
    finally:
        path.unlink()


def test_seed_load_snapshot_gzip():
    """load_snapshot should handle gzipped files."""
    from scripts.seed_diavgeia_orgs import load_snapshot
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
        path = Path(f.name)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(SAMPLE_SNAPSHOT, f, ensure_ascii=False)
    try:
        data = load_snapshot(path)
        assert len(data["organizations"]) == 3
    finally:
        path.unlink()


def test_seed_missing_snapshot_error():
    """load_snapshot should raise FileNotFoundError with clear message."""
    from scripts.seed_diavgeia_orgs import load_snapshot, DEFAULT_SNAPSHOT, DEFAULT_SNAPSHOT_GZ
    from unittest.mock import patch
    # Patch default paths to non-existent locations so fallback fails too
    with patch.object(
        __import__("scripts.seed_diavgeia_orgs", fromlist=["DEFAULT_SNAPSHOT"]),
        "DEFAULT_SNAPSHOT", Path("/nonexistent/a.json"),
    ), patch.object(
        __import__("scripts.seed_diavgeia_orgs", fromlist=["DEFAULT_SNAPSHOT_GZ"]),
        "DEFAULT_SNAPSHOT_GZ", Path("/nonexistent/a.json.gz"),
    ):
        with pytest.raises(FileNotFoundError, match="Snapshot not found"):
            load_snapshot(None)


def test_seed_malformed_snapshot_error():
    """load_snapshot should raise ValueError for bad structure."""
    from scripts.seed_diavgeia_orgs import load_snapshot
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"bad": "data"}, f)
        path = Path(f.name)
    try:
        with pytest.raises(ValueError, match="Malformed snapshot"):
            load_snapshot(path)
    finally:
        Path(path).unlink()


def test_seed_stale_snapshot_warns(caplog):
    """check_staleness should warn if snapshot is old."""
    from scripts.seed_diavgeia_orgs import check_staleness
    old_meta = {"fetched_at": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()}
    with caplog.at_level("WARNING"):
        check_staleness(old_meta, stale_days=180)
    assert "200 days old" in caplog.text


def test_seed_fresh_snapshot_no_warn(caplog):
    """check_staleness should not warn for fresh snapshots."""
    from scripts.seed_diavgeia_orgs import check_staleness
    fresh_meta = {"fetched_at": datetime.now(timezone.utc).isoformat()}
    with caplog.at_level("WARNING"):
        check_staleness(fresh_meta, stale_days=180)
    assert "days old" not in caplog.text or "OK" in caplog.text


# ── Seed: normalize_greek ───────────────────────────────────────────────────

def test_normalize_strips_accents():
    from scripts.seed_diavgeia_orgs import normalize_greek
    assert normalize_greek("ΔΗΜΟΣ Αθηναίων") == "ΑΘΗΝΑΙΩΝ"
    assert normalize_greek("ΔΗΜΟΣ ΘΕΣΣΑΛΟΝΙΚΗΣ") == "ΘΕΣΣΑΛΟΝΙΚΗΣ"


def test_normalize_removes_prefix():
    from scripts.seed_diavgeia_orgs import normalize_greek
    assert normalize_greek("ΔΗΜΟΣ ΠΑΤΡΕΩΝ") == "ΠΑΤΡΕΩΝ"
    assert normalize_greek("ΔΗΜΟΥ ΑΘΗΝΑΙΩΝ") == "ΑΘΗΝΑΙΩΝ"


# ── Backfill: cursor handling ───────────────────────────────────────────────

def test_backfill_cursor_roundtrip():
    """save_cursor + load_cursor should round-trip correctly."""
    from scripts.backfill_diavgeia_decisions import save_cursor, load_cursor, DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    test_uid = "_test_cursor_"
    ts = datetime(2026, 4, 20, 12, 0, 0)
    try:
        save_cursor(test_uid, ts, page=42, total_committed=1000)
        loaded = load_cursor(test_uid)
        assert loaded is not None
        assert loaded.year == 2026
        assert loaded.month == 4
        assert loaded.day == 20
    finally:
        from scripts.backfill_diavgeia_decisions import cursor_path
        p = cursor_path(test_uid)
        if p.exists():
            p.unlink()


def test_backfill_no_cursor_returns_none():
    """load_cursor should return None if no cursor file."""
    from scripts.backfill_diavgeia_decisions import load_cursor
    assert load_cursor("_nonexistent_type_") is None


# ── Router: refresh-orgs-cache ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_orgs_cache_requires_admin():
    """POST /refresh-orgs-cache without key -> 422."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/admin/diavgeia/refresh-orgs-cache")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_refresh_orgs_cache_wrong_key():
    """POST /refresh-orgs-cache with wrong key -> 403."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/admin/diavgeia/refresh-orgs-cache?admin_key=wrong")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_refresh_orgs_cache_status_not_found():
    """GET /refresh-orgs-cache/badid -> 404."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/admin/diavgeia/refresh-orgs-cache/nonexistent?admin_key=dev-admin-key")
    assert r.status_code == 404


# ── ScrapeResult schema ────────────────────────────────────────────────────

def test_scrape_result_to_dict():
    from services.diavgeia_scraper import ScrapeResult
    sr = ScrapeResult(fetched=5, inserted=3, updated=1, skipped=1, errors=["x"])
    d = sr.to_dict()
    assert d["fetched"] == 5
    assert d["errors"] == ["x"]

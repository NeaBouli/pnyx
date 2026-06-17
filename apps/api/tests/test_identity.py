"""
Tests für MOD-01 Identity Router
Läuft ohne PostgreSQL — DB wird gemockt.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from routers import identity


@pytest.mark.asyncio
async def test_verify_invalid_number(monkeypatch):
    """Festnetznummer wird abgelehnt"""
    async def fake_increment_hlr_usage() -> int:
        return 1

    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment_hlr_usage)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/identity/verify", json={
            "phone_number": "+302101234567"
        })
    assert r.status_code == 400
    assert "Μη έγκυρος" in r.json()["detail"] or "Ungültige" in r.json()["detail"]


@pytest.mark.asyncio
async def test_health_includes_mod01():
    """Health Check zeigt MOD-01 als aktiv"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert any("MOD-01" in m for m in r.json()["modules"])


@pytest.mark.asyncio
async def test_verify_missing_phone():
    """Fehlende Telefonnummer gibt 422"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/identity/verify", json={})
    assert r.status_code == 422

import importlib.util

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import main
from main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert any("MOD-01" in m for m in data["modules"])

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == 200


def test_health_lifespan_starts_with_identity_kdf_v2(monkeypatch):
    if importlib.util.find_spec("argon2") is None:
        pytest.skip("argon2-cffi not installed in this local Python environment")

    class NoopScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SERVER_SALT", "a" * 64)
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")
    monkeypatch.setattr(main, "scheduler", NoopScheduler())
    monkeypatch.setattr(main.sso, "validate_forum_sso_config", lambda: None)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

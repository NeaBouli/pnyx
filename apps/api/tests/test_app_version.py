import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_app_version_direct_apk_url_points_to_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")

    assert response.status_code == 200
    data = response.json()
    assert data["direct_apk_url"] == "https://ekklesia.gr/download/ekklesia-latest.apk"
    assert not data["direct_apk_url"].endswith("/download/")


@pytest.mark.asyncio
async def test_legacy_version_download_url_matches_direct_apk_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/version")

    assert response.status_code == 200
    data = response.json()
    assert data["downloadUrl"] == "https://ekklesia.gr/download/ekklesia-latest.apk"
    assert not data["downloadUrl"].endswith("/download/")

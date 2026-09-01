import json
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers import app_version


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_mobile_release_metadata_is_consistent() -> None:
    app_config = json.loads((REPO_ROOT / "apps/mobile/app.json").read_text())
    expo = app_config["expo"]
    gradle = (REPO_ROOT / "apps/mobile/android/app/build.gradle").read_text()
    gradle_name = re.search(r'versionName\s+"([^"]+)"', gradle)
    gradle_code = re.search(r"versionCode\s+(\d+)", gradle)

    assert gradle_name is not None
    assert gradle_code is not None
    assert expo["version"] == app_version.LATEST_VERSION == gradle_name.group(1)
    assert expo["android"]["versionCode"] == app_version.LATEST_VERSION_CODE == int(gradle_code.group(1))
    assert app_version.RELEASE_NOTES_EL.startswith(f"v{app_version.LATEST_VERSION}")
    assert app_version.RELEASE_NOTES_EN.startswith(f"v{app_version.LATEST_VERSION}")


@pytest.mark.asyncio
async def test_app_version_direct_apk_url_points_to_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")

    assert response.status_code == 200
    data = response.json()
    assert data["direct_apk_url"] == (
        "https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/"
        "ekklesia-v1.0.30-vC59-DIRECT.apk"
    )
    assert not data["direct_apk_url"].endswith("/download/")
    assert data["playstore_url"] == "https://play.google.com/apps/testing/ekklesia.gr"


@pytest.mark.asyncio
async def test_legacy_version_download_url_matches_direct_apk_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/version")

    assert response.status_code == 200
    data = response.json()
    assert data["downloadUrl"] == (
        "https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/"
        "ekklesia-v1.0.30-vC59-DIRECT.apk"
    )
    assert not data["downloadUrl"].endswith("/download/")
    assert data["playStoreUrl"] == "https://play.google.com/apps/testing/ekklesia.gr"


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["direct", "play"])
async def test_v34_profile_uses_current_download_without_legacy_fallback(channel: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")

    assert response.status_code == 200
    data = response.json()
    assert data["latest_version_code"] > 34
    # v34 requests this endpoint but reads camelCase fields in its profile button.
    download_url = (
        data.get("playStoreUrl")
        if channel == "play"
        else data.get("downloadUrl") or "https://ekklesia.gr/download"
    )
    expected_url = data["playstore_url"] if channel == "play" else data["direct_apk_url"]
    assert download_url == expected_url
    assert data["version"] == data["latest_version"]


@pytest.mark.asyncio
async def test_profile_compatibility_aliases_match_legacy_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        canonical = await client.get("/api/v1/app/version")
        legacy = await client.get("/api/v1/version")

    assert canonical.status_code == legacy.status_code == 200
    for field in ("version", "downloadUrl", "playStoreUrl"):
        assert canonical.json()[field] == legacy.json()[field]

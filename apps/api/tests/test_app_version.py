import json
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers import app_version


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_mobile_build_metadata_is_consistent() -> None:
    app_config = json.loads((REPO_ROOT / "apps/mobile/app.json").read_text())
    expo = app_config["expo"]
    gradle = (REPO_ROOT / "apps/mobile/android/app/build.gradle").read_text()
    gradle_name = re.search(r'versionName\s+"([^"]+)"', gradle)
    gradle_code = re.search(r"versionCode\s+(\d+)", gradle)

    assert gradle_name is not None
    assert gradle_code is not None
    assert expo["version"] == gradle_name.group(1)
    assert expo["android"]["versionCode"] == int(gradle_code.group(1))


def test_api_announces_only_the_published_release() -> None:
    assert app_version.LATEST_VERSION == "1.0.36"
    assert app_version.LATEST_VERSION_CODE == 65
    assert app_version.RELEASE_NOTES_EL == (
        "v1.0.36 — Σαφέστερη διατύπωση «χωρίς όνομα», ασφαλέστερος χειρισμός κλειδιών, μία διόρθωση ψήφου στο 24ωρο."
    )
    assert app_version.RELEASE_NOTES_EN == (
        "v1.0.36 — Clearer no-name wording, safer key handling, one vote correction in the 24-hour window."
    )


@pytest.mark.asyncio
async def test_app_version_direct_apk_url_points_to_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")

    assert response.status_code == 200
    data = response.json()
    assert data["direct_apk_url"] == (
        "https://github.com/NeaBouli/pnyx/releases/download/v1.0.36/"
        "ekklesia-v1.0.36-vC65-DIRECT.apk"
    )
    assert not data["direct_apk_url"].endswith("/download/")
    assert data["playstore_url"] == "https://play.google.com/apps/testing/ekklesia.gr"
    assert data["fdroid_url"] == "https://f-droid.org/packages/ekklesia.gr/"


@pytest.mark.asyncio
async def test_minimum_version_contract_preserves_legacy_and_fdroid_code_schemes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")

    assert response.status_code == 200
    data = response.json()
    assert data["min_required_version_code"] == 62
    assert data["min_required_version_code_by_channel"] == {
        "direct": 62, "play": 62, "fdroid": 621,
    }
    # Do not force all supported clients (including F-Droid 621-624) to update.
    assert data["force_update"] is False
    assert data["latest_version_code"] == 65
    for channel in ("direct", "play"):
        minimum = data["min_required_version_code_by_channel"][channel]
        assert 61 < minimum <= 62 <= 65
    minimum = data["min_required_version_code_by_channel"]["fdroid"]
    assert all(code < minimum for code in range(611, 615))
    assert all(code >= minimum for code in (*range(621, 625), *range(651, 655)))


@pytest.mark.asyncio
async def test_legacy_version_download_url_matches_direct_apk_file() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/version")

    assert response.status_code == 200
    data = response.json()
    assert data["downloadUrl"] == (
        "https://github.com/NeaBouli/pnyx/releases/download/v1.0.36/"
        "ekklesia-v1.0.36-vC65-DIRECT.apk"
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


@pytest.mark.asyncio
@pytest.mark.parametrize("env,expected", [(None, False), ("false", False), ("true", True)])
async def test_identity_rotate_feature_follows_the_server_flag(monkeypatch, env, expected) -> None:
    # EVA-001 PR4: the app rotates legacy keys only when this is advertised.
    if env is None:
        monkeypatch.delenv("IDENTITY_ROTATE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("IDENTITY_ROTATE_ENABLED", env)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")
    assert response.status_code == 200
    assert response.json()["features"]["identity_rotate"] is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("env,expected", [(None, False), ("true", True)])
async def test_identity_key_check_feature_follows_the_server_flag(monkeypatch, env, expected) -> None:
    # EVA-003 PR5: browsers migrate their legacy key only when advertised.
    if env is None:
        monkeypatch.delenv("IDENTITY_KEY_CHECK_ENABLED", raising=False)
    else:
        monkeypatch.setenv("IDENTITY_KEY_CHECK_ENABLED", env)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/app/version")
    assert response.json()["features"]["identity_key_check"] is expected

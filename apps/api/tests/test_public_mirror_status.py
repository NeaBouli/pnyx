import pytest

from routers import public_api


def _reset_mirror_cache(monkeypatch):
    monkeypatch.setattr(public_api, "_mirror_status_cache", None)
    monkeypatch.setattr(public_api, "_mirror_status_cache_until", 0.0)


def test_mirror_status_classification():
    assert public_api._classify_mirror_status(
        {"health": True, "status": True, "api": True}
    ) == "online"
    assert public_api._classify_mirror_status(
        {"health": True, "status": False, "api": True}
    ) == "degraded"
    assert public_api._classify_mirror_status(
        {"health": False, "status": True, "api": True}
    ) == "offline"


@pytest.mark.asyncio
async def test_public_mirror_status_online(monkeypatch):
    _reset_mirror_cache(monkeypatch)

    async def fake_get_ok(_client, _url):
        return True

    monkeypatch.setattr(public_api, "_mirror_get_ok", fake_get_ok)

    data = await public_api._build_mirror_status()

    mirror = data["mirrors"][0]
    assert mirror["name"] == "1.ekklesia.gr"
    assert mirror["status"] == "online"
    assert mirror["checks"] == {"health": True, "status": True, "api": True}


@pytest.mark.asyncio
async def test_public_mirror_status_degraded_when_api_proxy_fails(monkeypatch):
    _reset_mirror_cache(monkeypatch)

    async def fake_get_ok(_client, url):
        return not url.endswith("/api/v1/bills?limit=1")

    monkeypatch.setattr(public_api, "_mirror_get_ok", fake_get_ok)

    data = await public_api._build_mirror_status()

    mirror = data["mirrors"][0]
    assert mirror["status"] == "degraded"
    assert mirror["checks"] == {"health": True, "status": True, "api": False}


@pytest.mark.asyncio
async def test_public_mirror_status_offline_when_health_fails(monkeypatch):
    _reset_mirror_cache(monkeypatch)
    calls = []

    async def fake_get_ok(_client, url):
        calls.append(url)
        return False

    monkeypatch.setattr(public_api, "_mirror_get_ok", fake_get_ok)

    data = await public_api._build_mirror_status()

    mirror = data["mirrors"][0]
    assert mirror["status"] == "offline"
    assert mirror["checks"] == {"health": False, "status": False, "api": False}
    assert calls == [f"{public_api.MIRROR_SANDBOX_URL}/health"]

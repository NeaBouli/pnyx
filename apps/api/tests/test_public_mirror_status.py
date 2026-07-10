import pytest

from routers import public_api


def _reset_mirror_cache(monkeypatch):
    monkeypatch.setattr(public_api, "_mirror_status_cache", None)
    monkeypatch.setattr(public_api, "_mirror_status_cache_until", 0.0)
    monkeypatch.delenv("MIRROR_SANDBOX_URL", raising=False)
    monkeypatch.delenv("MIRROR_READONLY_URLS", raising=False)


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

    assert [mirror["name"] for mirror in data["mirrors"]] == [
        "1.ekklesia.gr",
        "2.ekklesia.gr",
        "3.ekklesia.gr",
    ]
    assert {mirror["status"] for mirror in data["mirrors"]} == {"online"}
    assert all(
        mirror["checks"] == {"health": True, "status": True, "api": True}
        for mirror in data["mirrors"]
    )


@pytest.mark.asyncio
async def test_public_mirror_status_degraded_when_api_proxy_fails(monkeypatch):
    _reset_mirror_cache(monkeypatch)

    async def fake_get_ok(_client, url):
        return not url.endswith("/api/v1/bills?limit=1")

    monkeypatch.setattr(public_api, "_mirror_get_ok", fake_get_ok)

    data = await public_api._build_mirror_status()

    assert {mirror["status"] for mirror in data["mirrors"]} == {"degraded"}
    assert all(
        mirror["checks"] == {"health": True, "status": True, "api": False}
        for mirror in data["mirrors"]
    )


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
    assert calls == [
        "https://1.ekklesia.gr/health",
        "https://2.ekklesia.gr/health",
        "https://3.ekklesia.gr/health",
    ]


@pytest.mark.asyncio
async def test_public_mirror_status_supports_env_url_list(monkeypatch):
    _reset_mirror_cache(monkeypatch)
    monkeypatch.setenv("MIRROR_READONLY_URLS", "https://a.example, https://b.example/")

    async def fake_get_ok(_client, _url):
        return True

    monkeypatch.setattr(public_api, "_mirror_get_ok", fake_get_ok)

    data = await public_api._build_mirror_status()

    assert [(mirror["name"], mirror["url"]) for mirror in data["mirrors"]] == [
        ("a.example", "https://a.example"),
        ("b.example", "https://b.example"),
    ]

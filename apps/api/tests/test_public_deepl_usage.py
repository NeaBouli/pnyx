"""EKA-53: anonymous DeepL aggregate usage lives under /api/v1/public, not /admin."""
import types
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers import public_api


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PATH = "/api/v1/public/deepl/usage"
OLD_ADMIN_PATH = "/api/v1/admin/deepl/usage"
SYNTHETIC_KEY = "synthetic-test-key-not-real:fx"
RESPONSE_FIELDS = {"available", "character_count", "character_limit"}
UNAVAILABLE = {"available": False, "character_count": 0, "character_limit": 0}

FIRST_PARTY_CONSUMERS = [
    "docs/community.html",
    "apps/dashboard/src/lib/api.ts",
    "apps/dashboard/src/app/(dashboard)/page.tsx",
    "apps/dashboard/src/app/(dashboard)/settings/page.tsx",
    "apps/dashboard/src/app/(dashboard)/ai/page.tsx",
    "apps/dashboard/src/app/(dashboard)/system/page.tsx",
    "docs/INTEGRATION-ANSWERS.md",
    "docs/ekklesia_project_handover.md",
]


def _mock_provider(monkeypatch, handler):
    """Route the handler's httpx.AsyncClient through a MockTransport; no network."""
    seen: dict = {"requests": [], "timeouts": []}

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen["requests"].append(request)
        return handler(request)

    def fake_async_client(*, timeout):
        seen["timeouts"].append(timeout)
        return httpx.AsyncClient(transport=httpx.MockTransport(recording_handler), timeout=timeout)

    monkeypatch.setattr(public_api, "httpx", types.SimpleNamespace(AsyncClient=fake_async_client))
    return seen


async def _get(path: str) -> httpx.Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_public_deepl_usage_projects_configured_provider_aggregate(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", SYNTHETIC_KEY)
    seen = _mock_provider(
        monkeypatch,
        lambda _req: httpx.Response(
            200,
            json={"character_count": 7000, "character_limit": 500000, "extra": "must-not-leak"},
        ),
    )

    response = await _get(PUBLIC_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body == {"available": True, "character_count": 7000, "character_limit": 500000}
    assert set(body) == RESPONSE_FIELDS
    assert SYNTHETIC_KEY not in response.text
    assert seen["timeouts"] == [5]
    [request] = seen["requests"]
    assert request.method == "GET"
    assert str(request.url) == "https://api-free.deepl.com/v2/usage"
    assert request.headers["Authorization"] == f"DeepL-Auth-Key {SYNTHETIC_KEY}"


@pytest.mark.asyncio
async def test_public_deepl_usage_without_key_skips_provider(monkeypatch):
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    seen = _mock_provider(monkeypatch, lambda _req: pytest.fail("provider must not be called"))

    response = await _get(PUBLIC_PATH)

    assert response.status_code == 200
    assert response.json() == UNAVAILABLE
    assert seen["requests"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler",
    [
        lambda _req: httpx.Response(403, text="Forbidden: synthetic provider body"),
        lambda _req: httpx.Response(200, text="not json"),
        lambda req: (_ for _ in ()).throw(httpx.ConnectTimeout("synthetic timeout", request=req)),
    ],
    ids=["http-error", "invalid-json", "transport-error"],
)
async def test_public_deepl_usage_provider_failure_is_unavailable(monkeypatch, handler):
    monkeypatch.setenv("DEEPL_API_KEY", SYNTHETIC_KEY)
    _mock_provider(monkeypatch, handler)

    response = await _get(PUBLIC_PATH)

    assert response.status_code == 200
    assert response.json() == UNAVAILABLE
    assert "synthetic" not in response.text


@pytest.mark.asyncio
async def test_old_anonymous_admin_deepl_usage_path_is_gone(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", SYNTHETIC_KEY)
    seen = _mock_provider(monkeypatch, lambda _req: pytest.fail("provider must not be called"))

    response = await _get(OLD_ADMIN_PATH)

    assert response.status_code == 404
    assert seen["requests"] == []
    paths = app.openapi()["paths"]
    assert PUBLIC_PATH in paths
    assert OLD_ADMIN_PATH not in paths


def test_first_party_consumers_use_public_deepl_usage_path():
    for rel in FIRST_PARTY_CONSUMERS:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "admin/deepl/usage" not in text, rel
        assert "public/deepl/usage" in text, rel

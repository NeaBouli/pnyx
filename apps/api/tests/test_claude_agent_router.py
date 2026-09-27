"""Regression guards for EKA-61: public POST /api/v1/claude/ask removed fail-closed.

The endpoint bypassed every guardrail and only tracked the token budget
post-hoc. These tests prove the route is no longer registered, cannot reach a
provider or Redis even with a configured API key, and that the read-only
GET /api/v1/claude/budget status surface keeps its field contract.
"""

from collections.abc import Generator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from routers import claude_agent

ASK_PATH = "/api/v1/claude/ask"
BUDGET_PATH = "/api/v1/claude/budget"

EXPECTED_BUDGET_FIELDS = {
    "model",
    "tokens_today",
    "tokens_month",
    "chat_tokens_today",
    "chat_tokens_month",
    "analysis_tokens_today",
    "analysis_tokens_month",
    "estimated_cost_usd_today",
    "estimated_cost_usd_month",
    "estimated_analysis_cost_usd_month",
    "daily_token_limit",
    "monthly_budget_eur",
    "balance_available",
    "is_active",
    "error",
}


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    test_client = TestClient(main.app)
    yield test_client
    test_client.close()


def test_post_ask_route_not_registered(client: TestClient) -> None:
    registered = {
        (route.path, method)
        for route in main.app.routes
        for method in getattr(route, "methods", None) or set()
    }
    assert not any(path == ASK_PATH for path, _ in registered), (
        f"POST {ASK_PATH} must stay removed (EKA-61)"
    )

    response = client.post(ASK_PATH, json={"question": "Is this route gone?", "lang": "en"})
    assert response.status_code in (404, 405)


def test_openapi_schema_excludes_ask_keeps_budget() -> None:
    paths = main.app.openapi()["paths"]
    assert ASK_PATH not in paths
    assert BUDGET_PATH in paths
    assert "get" in paths[BUDGET_PATH]


def test_post_ask_with_dummy_key_triggers_no_provider_or_redis(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_http_client(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("httpx.AsyncClient must not be instantiated for removed /ask")

    async def fail_redis() -> None:
        raise AssertionError("Redis must not be touched for removed /ask")

    monkeypatch.setattr(claude_agent, "ANTHROPIC_API_KEY", "sk-ant-dummy-test-key")
    monkeypatch.setattr(httpx, "AsyncClient", fail_http_client)
    monkeypatch.setattr(claude_agent, "_redis", fail_redis)

    response = client.post(ASK_PATH, json={"question": "trigger provider?", "lang": "en"})
    assert response.status_code in (404, 405)


def test_get_budget_keeps_field_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis()

    async def fake_redis() -> FakeRedis:
        return fake

    monkeypatch.setattr(claude_agent, "_redis", fake_redis)
    monkeypatch.setattr(claude_agent, "ANTHROPIC_API_KEY", "sk-ant-dummy-test-key")

    response = client.get(BUDGET_PATH)

    assert response.status_code == 200
    body = response.json()
    assert EXPECTED_BUDGET_FIELDS <= set(body), (
        f"budget fields drifted: missing {EXPECTED_BUDGET_FIELDS - set(body)}"
    )
    assert body["is_active"] is True
    assert body["balance_available"] is False


def test_get_budget_reports_inactive_without_api_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis()

    async def fake_redis() -> FakeRedis:
        return fake

    monkeypatch.setattr(claude_agent, "_redis", fake_redis)
    monkeypatch.setattr(claude_agent, "ANTHROPIC_API_KEY", "")

    response = client.get(BUDGET_PATH)

    assert response.status_code == 200
    assert response.json()["is_active"] is False

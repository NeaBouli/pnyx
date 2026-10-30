"""EKA-32 HTTP acceptance using the production singleton and included routes."""

from collections.abc import Iterator
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import Response
from limits import parse
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

import ip_utils
import main
from database import get_db
from rate_limit import create_limiter, limiter, rate_limit_http_exception_handler
from security_headers import API_CSP
from routers import public_api


BODY = {"nullifier_hash": "a" * 64}
PATH = "/api/v1/identity/status"
ORIGINS = ["https://ekklesia.gr", "https://www.ekklesia.gr", "https://api.ekklesia.gr",
           "https://dashboard.ekklesia.gr", "https://test.ekklesia.gr"]


@pytest.fixture
def acceptance_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    instance = create_limiter(storage_uri="memory://", enabled=True)
    for name in (
        "enabled", "_storage", "_limiter", "_fallback_storage", "_fallback_limiter", "_storage_dead",
        "_Limiter__last_check_backend", "_Limiter__check_backend_count",
    ):
        monkeypatch.setattr(limiter, name, getattr(instance, name))
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)))
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: session)
    client = TestClient(main.app, client=("198.51.100.8", 1234))
    yield client
    client.close()
    instance._storage.reset()
    instance._fallback_storage.reset()


def assert_quota_response(response: Response) -> None:
    assert response.status_code == 429
    assert set(response.json()) == {"error", "detail", "retry_after"}
    assert response.json()["error"] == "Rate limit exceeded"
    assert int(response.headers["retry-after"]) == response.json()["retry_after"] > 0
    assert len(response.headers.get_list("retry-after")) == 1
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers.get_list("content-security-policy") == [API_CSP]


@pytest.mark.parametrize("origin", ORIGINS)
def test_included_route_429_contract_and_browser_headers(acceptance_client: TestClient, origin: str) -> None:
    for _ in range(1200):
        assert acceptance_client.post(PATH, json=BODY).status_code == 404
    response = acceptance_client.post(PATH, json=BODY, headers={"Origin": origin})
    assert_quota_response(response)
    assert response.json()["detail"] == "Rate limit exceeded"
    assert response.headers["access-control-allow-origin"] == origin
    assert "Retry-After" in response.headers["access-control-expose-headers"]
    assert "Origin" in response.headers["vary"]


def test_untrusted_forwarding_cannot_reset_route_bucket(acceptance_client: TestClient) -> None:
    for index in range(1200):
        assert acceptance_client.post(PATH, json=BODY, headers={"X-Forwarded-For": f"203.0.113.{index}"}).status_code == 404
    response = acceptance_client.post(PATH, json=BODY, headers={"X-Forwarded-For": "203.0.113.99", "Origin": "https://untrusted.example"})
    assert_quota_response(response)
    assert "access-control-allow-origin" not in response.headers


def test_outage_is_stricter_and_logs_only_event_counts(
    acceptance_client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise RedisConnectionError("198.51.100.8 secret-client-identifier")

    monkeypatch.setattr(limiter._storage, "incr", unavailable)
    monkeypatch.setattr(limiter._storage, "check", lambda: False)
    with caplog.at_level(logging.WARNING, logger="slowapi"):
        for _ in range(600):
            assert acceptance_client.post(PATH, json=BODY).status_code == 404
        response = acceptance_client.post(PATH, json=BODY, headers={"Origin": ORIGINS[0]})
    assert_quota_response(response)
    assert limiter._storage_dead is True
    assert response.headers["access-control-allow-origin"] == ORIGINS[0]
    records = [record for record in caplog.records if record.name == "slowapi"]
    assert {record.getMessage() for record in records} == {
        "rate_limit event=fallback count=1", "rate_limit event=exceeded count=1",
    }
    assert all(record.exc_info is None for record in records)


def test_unreachable_redis_uses_production_factory_fallback(
    acceptance_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = create_limiter(storage_uri="redis://127.0.0.1:1", enabled=True)
    monkeypatch.setattr(limiter, "_storage", instance._storage)
    monkeypatch.setattr(limiter, "_limiter", instance._limiter)
    for _ in range(600):
        assert acceptance_client.post(PATH, json=BODY).status_code == 404
    response = acceptance_client.post(PATH, json=BODY, headers={"Origin": ORIGINS[0]})
    assert_quota_response(response)
    assert limiter._storage_dead is True
    assert response.headers["access-control-allow-origin"] == ORIGINS[0]


def test_fallback_retains_route_scope_and_is_per_process() -> None:
    first = create_limiter(storage_uri="memory://", enabled=True)
    second = create_limiter(storage_uri="memory://", enabled=True)
    quota = parse("10/minute")
    for _ in range(5):
        assert first._fallback_limiter.hit(quota, "hashed-client", "signed-read")
    assert not first._fallback_limiter.hit(quota, "hashed-client", "signed-read")
    assert first._fallback_limiter.hit(quota, "hashed-client", "vote")
    assert second._fallback_limiter.hit(quota, "hashed-client", "signed-read")
    first._fallback_storage.reset()
    second._fallback_storage.reset()


def test_storage_recovery_restores_shared_backend(
    acceptance_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limiter, "_storage_dead", True)
    monkeypatch.setattr(limiter, "_Limiter__should_check_backend", lambda: True)
    assert acceptance_client.post(PATH, json=BODY).status_code == 404
    assert limiter._storage_dead is False
    assert list(limiter._storage.storage.values()) == [1]
    assert not limiter._fallback_storage.storage


def test_public_shared_counter_outage_keeps_http_contract(
    acceptance_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ip_utils, "_fallback_counts", {})
    redis = SimpleNamespace(eval=AsyncMock(side_effect=RedisConnectionError("client-identifier")))
    monkeypatch.setattr(public_api, "get_redis", AsyncMock(return_value=redis))
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: session)
    for _ in range(50):
        assert acceptance_client.get("/api/v1/public/vaa/parties").status_code == 200
    response = acceptance_client.get("/api/v1/public/vaa/parties", headers={"Origin": ORIGINS[0]})
    assert_quota_response(response)
    assert response.json()["detail"]["limit"] == 100  # Normal quota metadata is compatible.
    assert response.headers["access-control-allow-origin"] == ORIGINS[0]
    assert response.headers["retry-after"] == "60"
    assert session.execute.await_count == 50


def test_429_expiry_lookup_failure_preserves_response(
    acceptance_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(1200):
        assert acceptance_client.post(PATH, json=BODY).status_code == 404

    def unavailable(*args: object) -> None:
        raise RedisConnectionError()

    monkeypatch.setattr(limiter.limiter, "get_window_stats", unavailable)
    response = acceptance_client.post(PATH, json=BODY)
    assert_quota_response(response)
    assert response.headers["retry-after"] == "60"


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["Retry-After", "retry-after", "RETRY-AFTER"])
async def test_translated_dedicated_quota_preserves_retry_window(header: str) -> None:
    from starlette.requests import Request

    try:
        try:
            raise HTTPException(429, "Rate limit exceeded", headers={header: "3600"})
        except HTTPException:
            raise HTTPException(429, {"error": "Rate limit exceeded", "limit": 3})
    except HTTPException as error:
        response = await rate_limit_http_exception_handler(Request({"type": "http"}), error)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "3600"


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after,expected", [("600", 600), ("invalid", 60), ("0", 1)])
async def test_handler_retry_header_is_normalized_once(retry_after: str, expected: int) -> None:
    from starlette.requests import Request

    response = await rate_limit_http_exception_handler(
        Request({"type": "http"}),
        HTTPException(429, "Provider deferred", headers={"retry-after": retry_after, "X-Quota": "provider"}),
    )
    assert response.headers.getlist("retry-after") == [str(expected)]
    assert response.headers["x-quota"] == "provider"


@pytest.mark.asyncio
async def test_other_http_exceptions_keep_their_existing_response() -> None:
    from starlette.requests import Request

    response = await rate_limit_http_exception_handler(
        Request({"type": "http"}),
        HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"}),
    )
    assert response.status_code == 401
    assert response.body == b'{"detail":"Unauthorized"}'
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_dedicated_redis_counter_falls_back_and_expires(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(ip_utils, "_fallback_counts", {})
    now = [100.0]
    monkeypatch.setattr(ip_utils.time, "monotonic", lambda: now[0])
    redis = SimpleNamespace(eval=AsyncMock(side_effect=RedisConnectionError("raw-identifier")))
    key = "ratelimit:test:hashed-subject"
    assert await ip_utils.redis_fixed_window_limit(redis, key, 4, 60) == 1
    assert await ip_utils.redis_fixed_window_limit(redis, key, 4, 60) == 2
    with pytest.raises(HTTPException) as error:
        await ip_utils.redis_fixed_window_limit(redis, key, 4, 60)
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "60"}
    assert "raw-identifier" not in caplog.text
    now[0] += 60
    assert await ip_utils.redis_fixed_window_limit(redis, key, 4, 60) == 1


@pytest.mark.asyncio
async def test_fallback_capacity_rejects_new_buckets_without_evicting_live_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ip_utils, "_fallback_counts", {})
    monkeypatch.setattr(ip_utils, "_MAX_FALLBACK_BUCKETS", 1)
    redis = SimpleNamespace(eval=AsyncMock(side_effect=RedisConnectionError()))
    assert await ip_utils.redis_fixed_window_limit(redis, "first", 4, 60) == 1
    with pytest.raises(HTTPException) as error:
        await ip_utils.redis_fixed_window_limit(redis, "second", 4, 60)
    assert error.value.status_code == 429
    assert await ip_utils.redis_fixed_window_limit(redis, "first", 4, 60) == 2

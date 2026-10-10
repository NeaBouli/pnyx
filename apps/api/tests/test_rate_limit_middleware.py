"""Regression guards for EKA-32's default 60/min/IP endpoint limit."""

from collections.abc import AsyncIterator, Callable, Generator
from dataclasses import dataclass
import os
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from limits import parse
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware

import main
from database import get_db
from ip_utils import rate_limit_key_for_ip
from rate_limit import get_rate_limit_storage_uri, limiter
from routers import agent, public_api
from services import cplm


@pytest.fixture
def install_test_limiter() -> Generator[Callable[..., Limiter], None, None]:
    original = main.app.state.limiter

    def install(
        limit: str = "60/minute",
        *,
        enabled: bool = True,
        storage_uri: str = "memory://",
        fallback: bool = False,
    ) -> Limiter:
        test_limiter = Limiter(
            key_func=lambda request: rate_limit_key_for_ip(request, "slowapi-test"),
            default_limits=[limit],
            storage_uri=storage_uri,
            in_memory_fallback_enabled=fallback,
            enabled=enabled,
        )
        main.app.state.limiter = test_limiter
        return test_limiter

    yield install
    main.app.state.limiter = original


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    test_client = TestClient(main.app)
    yield test_client
    test_client.close()


def test_slowapi_middleware_registered() -> None:
    middleware_classes = [m.cls for m in main.app.user_middleware]
    assert SlowAPIMiddleware in middleware_classes, (
        "SlowAPIMiddleware missing — default_limits are dead config without it"
    )


def test_default_endpoint_limit_matches_documented_value() -> None:
    rendered = [str(item.limit) for group in main.limiter._default_limits for item in group]
    assert "60 per 1 minute" in rendered, (
        f"global default limit drifted from the documented 60/minute: {rendered}"
    )


def test_limiter_wired_into_app_state() -> None:
    assert main.app.state.limiter is main.limiter


def test_all_slowapi_routes_share_one_limiter() -> None:
    assert main.limiter is limiter
    assert agent.limiter is limiter


def test_runtime_storage_uses_configured_shared_backend() -> None:
    expected = (
        os.getenv("RATE_LIMIT_STORAGE_URI")
        or os.getenv("REDIS_URL")
        or "memory://"
    )
    assert get_rate_limit_storage_uri() == expected
    assert main.limiter._storage_uri == expected
    assert main.limiter._in_memory_fallback_enabled is True


@pytest.mark.skipif(not os.getenv("REDIS_URL"), reason="Redis integration unavailable")
def test_redis_backend_coordinates_independent_limiter_instances() -> None:
    storage_uri = os.environ["REDIS_URL"]
    bucket = f"eka32-test-{uuid4()}"
    first = Limiter(
        key_func=lambda: "subject",
        storage_uri=storage_uri,
    )
    second = Limiter(
        key_func=lambda: "subject",
        storage_uri=storage_uri,
    )
    limit = parse("2/second")

    assert first.limiter.hit(limit, bucket, "/shared") is True
    assert second.limiter.hit(limit, bucket, "/shared") is True
    assert first.limiter.hit(limit, bucket, "/shared") is False


def test_sixty_first_request_is_rejected(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter()
    headers = {"X-Forwarded-For": "203.0.113.60"}

    for _ in range(60):
        assert client.get("/health", headers=headers).status_code == 200

    assert client.get("/health", headers=headers).status_code == 429


def test_default_limit_is_per_endpoint(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter("1/minute")
    headers = {"X-Forwarded-For": "203.0.113.61"}

    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/", headers=headers).status_code == 200
    assert client.get("/health", headers=headers).status_code == 429
    assert client.get("/", headers=headers).status_code == 429


def test_rate_limit_response_keeps_cors_and_noindex_headers(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter("1/minute")
    headers = {
        "Origin": "https://ekklesia.gr",
        "X-Forwarded-For": "203.0.113.62",
    }

    assert client.get("/health", headers=headers).status_code == 200
    response = client.get("/health", headers=headers)

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "https://ekklesia.gr"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_cors_preflight_does_not_consume_rate_limit(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter("1/minute")
    preflight_headers = {
        "Origin": "https://ekklesia.gr",
        "Access-Control-Request-Method": "GET",
        "X-Forwarded-For": "203.0.113.63",
    }

    for _ in range(3):
        assert client.options("/health", headers=preflight_headers).status_code == 200

    get_headers = {
        "Origin": "https://ekklesia.gr",
        "X-Forwarded-For": "203.0.113.63",
    }
    assert client.get("/health", headers=get_headers).status_code == 200
    assert client.get("/health", headers=get_headers).status_code == 429


def test_disabled_limiter_does_not_reject_requests(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter("1/minute", enabled=False)
    headers = {"X-Forwarded-For": "203.0.113.64"}

    for _ in range(3):
        assert client.get("/health", headers=headers).status_code == 200


def test_unavailable_backend_falls_back_to_bounded_memory_limit(
    client: TestClient,
    install_test_limiter: Callable[..., Limiter],
) -> None:
    install_test_limiter(
        "1/minute",
        storage_uri="redis://127.0.0.1:1",
        fallback=True,
    )
    headers = {"X-Forwarded-For": "203.0.113.65"}

    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/health", headers=headers).status_code == 429


# T-9050 characterizes current quotas; it does not approve or change policy.
PARTIES_ROUTE = "/api/v1/public/vaa/parties"
CPLM_ROUTE = "/api/v1/public/cplm"
VALID_QUOTA_KEY = "qkey"


class PublicQuotaRedis:
    """Only the actual key verifier and fixed-window Lua helper use this fake."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.acquisitions = 0
        self.key_checks = 0
        self.evaluations = 0

    async def hexists(self, name: str, key: str) -> bool:
        assert name == public_api.REDIS_KEY_HASH
        self.key_checks += 1
        return key == public_api.hash_key(VALID_QUOTA_KEY)

    async def eval(self, script: str, numkeys: int, key: str, seconds: int) -> int:
        assert numkeys == 1 and seconds == 60
        assert "redis.call('INCR', KEYS[1])" in script
        assert "redis.call('EXPIRE', KEYS[1], ARGV[1])" in script
        self.evaluations += 1
        self.counts[key] = self.counts.get(key, 0) + 1
        if self.counts[key] == 1:
            self.expirations[key] = seconds
        return self.counts[key]


class EmptyPartyResult:
    def scalars(self) -> "EmptyPartyResult":
        return self

    def all(self) -> list[Any]:
        return []


class PublicQuotaDB:
    def __init__(self) -> None:
        self.executions = 0
        self.aggregates = 0

    async def execute(self, statement: Any) -> EmptyPartyResult:
        self.executions += 1
        return EmptyPartyResult()


@dataclass
class PublicQuotaBackend:
    redis: PublicQuotaRedis
    db: PublicQuotaDB
    helper: AsyncMock

    def effects(self) -> tuple[int, int, int, int, int, int]:
        return (
            self.redis.acquisitions, self.redis.key_checks,
            self.redis.evaluations, self.db.executions, self.db.aggregates,
            self.helper.await_count,
        )

    def assert_helper_quota(self, quota: int) -> None:
        assert self.helper.await_count > 0
        for call in self.helper.await_args_list:
            assert call.args[0] is self.redis
            assert call.args[2:] == (quota, 60)


@pytest.fixture
def public_quota_backend(
    monkeypatch: pytest.MonkeyPatch,
    install_test_limiter: Callable[..., Limiter],
) -> Generator[PublicQuotaBackend, None, None]:
    installed = install_test_limiter(enabled=True, storage_uri="memory://")
    assert installed.enabled is True
    redis = PublicQuotaRedis()
    db = PublicQuotaDB()
    helper = AsyncMock(wraps=public_api.redis_fixed_window_limit)

    async def fake_redis() -> PublicQuotaRedis:
        redis.acquisitions += 1
        return redis

    async def fake_db() -> AsyncIterator[PublicQuotaDB]:
        yield db

    async def fake_cplm(session: PublicQuotaDB) -> dict[str, int]:
        assert session is db
        db.aggregates += 1
        return {"x": 0, "y": 0, "total_voters": 0}

    monkeypatch.setattr(public_api, "get_redis", fake_redis)
    monkeypatch.setattr(public_api, "redis_fixed_window_limit", helper)
    monkeypatch.setattr(cplm, "get_cplm_cached", fake_cplm)
    previous_overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[get_db] = fake_db
    try:
        yield PublicQuotaBackend(redis, db, helper)
    finally:
        if get_db in previous_overrides:
            main.app.dependency_overrides[get_db] = previous_overrides[get_db]
        else:
            main.app.dependency_overrides.pop(get_db, None)


def test_public_valid_key_sixty_first_read_reaches_shared_quota(
    client: TestClient, public_quota_backend: PublicQuotaBackend,
) -> None:
    headers = {"X-API-Key": VALID_QUOTA_KEY, "Origin": "https://ekklesia.gr"}
    for _ in range(60):
        response = client.get(PARTIES_ROUTE, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"data": [], "data_license": "CC BY 4.0"}
    response = client.get(PARTIES_ROUTE, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": [], "data_license": "CC BY 4.0"}
    assert response.headers["access-control-allow-origin"] == "https://ekklesia.gr"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert list(public_quota_backend.redis.counts.values()) == [61]
    assert public_quota_backend.redis.evaluations == 61
    assert public_quota_backend.db.executions == 61
    assert public_quota_backend.db.aggregates == 0
    assert public_quota_backend.helper.await_count == 61
    public_quota_backend.assert_helper_quota(1000)


def test_public_valid_key_sixty_first_reads_share_cross_endpoint_budget(
    client: TestClient, public_quota_backend: PublicQuotaBackend,
) -> None:
    headers = {"X-API-Key": VALID_QUOTA_KEY}
    for route in (PARTIES_ROUTE, CPLM_ROUTE):
        for _ in range(60):
            assert client.get(route, headers=headers).status_code == 200
    assert list(public_quota_backend.redis.counts.values()) == [120]
    assert public_quota_backend.db.executions == 60
    assert public_quota_backend.db.aggregates == 60
    for route in (PARTIES_ROUTE, CPLM_ROUTE):
        response = client.get(route, headers=headers)
        assert response.status_code == 200
    assert list(public_quota_backend.redis.counts.values()) == [122]
    assert public_quota_backend.redis.evaluations == 122
    assert public_quota_backend.db.executions == 61
    assert public_quota_backend.db.aggregates == 61
    assert public_quota_backend.helper.await_count == 122
    public_quota_backend.assert_helper_quota(1000)


def test_public_valid_key_shared_backend_thousand_boundary(
    client: TestClient, public_quota_backend: PublicQuotaBackend,
) -> None:
    headers = {"X-API-Key": VALID_QUOTA_KEY}
    key = f"ratelimit:public_api:key:{public_api.hash_key(VALID_QUOTA_KEY)}"
    public_quota_backend.redis.counts[key] = 999
    public_quota_backend.redis.expirations[key] = 60
    assert client.get(PARTIES_ROUTE, headers=headers).status_code == 200
    assert public_quota_backend.redis.counts[key] == 1000
    before_db = (public_quota_backend.db.executions, public_quota_backend.db.aggregates)
    response = client.get(CPLM_ROUTE, headers=headers)
    assert response.status_code == 429
    assert response.json()["detail"]["limit"] == 1000
    assert response.json()["detail"]["window"] == "60s"
    assert (public_quota_backend.db.executions, public_quota_backend.db.aggregates) == before_db
    assert public_quota_backend.redis.counts == {key: 1001}
    public_quota_backend.assert_helper_quota(1000)


def test_public_anonymous_quota_is_shared_across_endpoints(
    client: TestClient, public_quota_backend: PublicQuotaBackend,
) -> None:
    for route, attempts in ((PARTIES_ROUTE, 60), (CPLM_ROUTE, 40)):
        for _ in range(attempts):
            assert client.get(route).status_code == 200
    before_db = (public_quota_backend.db.executions, public_quota_backend.db.aggregates)
    response = client.get(CPLM_ROUTE)
    assert response.status_code == 429
    assert response.json()["detail"]["limit"] == 100
    assert response.json()["detail"]["window"] == "60s"
    assert (public_quota_backend.db.executions, public_quota_backend.db.aggregates) == before_db
    assert list(public_quota_backend.redis.counts.values()) == [101]
    assert next(iter(public_quota_backend.redis.counts)).startswith("ratelimit:public_api:anon:")
    public_quota_backend.assert_helper_quota(100)


def test_public_invalid_keys_cannot_create_fresh_quota_buckets(
    client: TestClient, public_quota_backend: PublicQuotaBackend,
) -> None:
    for route, attempts in ((PARTIES_ROUTE, 60), (CPLM_ROUTE, 40)):
        for index in range(attempts):
            assert client.get(route, headers={"X-API-Key": f"junk{index}"}).status_code == 200
    before_db = (public_quota_backend.db.executions, public_quota_backend.db.aggregates)
    response = client.get(CPLM_ROUTE, headers={"X-API-Key": "fresh"})
    assert response.status_code == 429 and response.json()["detail"]["limit"] == 100
    assert (public_quota_backend.db.executions, public_quota_backend.db.aggregates) == before_db
    assert len(public_quota_backend.redis.counts) == 1
    key = next(iter(public_quota_backend.redis.counts))
    assert key.startswith("ratelimit:public_api:anon:")
    assert "junk" not in key and "fresh" not in key
    assert public_quota_backend.redis.key_checks == 101
    public_quota_backend.assert_helper_quota(100)

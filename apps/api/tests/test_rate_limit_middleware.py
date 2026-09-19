"""Regression guards for EKA-32's default 60/min/IP endpoint limit."""

from collections.abc import Callable, Generator
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from limits import parse
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware

import main
from ip_utils import rate_limit_key_for_ip
from rate_limit import get_rate_limit_storage_uri, limiter
from routers import agent, claude_agent


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
    assert claude_agent.limiter is limiter


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

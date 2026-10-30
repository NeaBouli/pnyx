"""Shared, privacy-preserving API rate limiter configuration."""

from __future__ import annotations

import logging
import math
import os
import time

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from limits import RateLimitItem
from limits.strategies import FixedWindowRateLimiter
from limits.util import WindowStats
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException

from ip_utils import rate_limit_key_for_ip


class CountsOnlyFilter(logging.Filter):
    """SlowAPI's default warning includes the bucket and endpoint identifiers."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = str(record.msg)
        event = "exceeded"
        if "unreachable" in message:
            event = "fallback"
        elif "recovered" in message:
            event = "recovered"
        elif "exceeded" not in message:
            event = "error"
        record.msg = "rate_limit event=%s count=1"
        record.args = (event,)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


_logger = logging.getLogger("slowapi")
if not any(isinstance(item, CountsOnlyFilter) for item in _logger.filters):
    _logger.addFilter(CountsOnlyFilter())


class ConservativeMemoryLimiter(FixedWindowRateLimiter):
    """Per-process outage counters allow half the normal quota, rounded down."""

    @staticmethod
    def reduced(item: RateLimitItem) -> RateLimitItem:
        return type(item)(max(1, item.amount // 2), item.multiples, item.namespace)

    def hit(self, item: RateLimitItem, *identifiers: str, cost: int = 1) -> bool:
        return super().hit(self.reduced(item), *identifiers, cost=cost)

    def test(self, item: RateLimitItem, *identifiers: str, cost: int = 1) -> bool:
        return super().test(self.reduced(item), *identifiers, cost=cost)

    def get_window_stats(self, item: RateLimitItem, *identifiers: str) -> WindowStats:
        return super().get_window_stats(self.reduced(item), *identifiers)


def get_rate_limit_storage_uri() -> str:
    """Use the shared Redis service in runtime and memory for local development."""
    return (
        os.getenv("RATE_LIMIT_STORAGE_URI")
        or os.getenv("REDIS_URL")
        or "memory://"
    )


def get_rate_limit_key(request: Request) -> str:
    """Return a daily rotating HMAC key instead of persisting a raw client IP."""
    return rate_limit_key_for_ip(request, "slowapi")


# FastAPI includes lazy routers via _IncludedRouter (no top-level endpoint).
# SlowAPI skips default_limits for those routes. The 60/min default is
# NOT an API-wide guarantee: router writes need an explicit decorator or a
# handler-level Redis guard. tests/test_rate_limit_coverage.py audits the
# registered app, with reasoned exceptions for Redis guards/provider callbacks.
def create_limiter(*, storage_uri: str | None = None, enabled: bool | None = None) -> Limiter:
    """Create the same shared-store and conservative-fallback policy in every worker."""
    uri = storage_uri or get_rate_limit_storage_uri()
    instance = Limiter(
        key_func=get_rate_limit_key,
        default_limits=["60/minute"],
        strategy="fixed-window",
        storage_uri=uri,
        storage_options={"socket_connect_timeout": 0.2, "socket_timeout": 0.2}
        if uri.startswith(("redis://", "rediss://")) else {},
        in_memory_fallback_enabled=True,
        key_prefix="ekklesia-api",
        enabled=enabled if enabled is not None else os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
    )
    instance._fallback_limiter = ConservativeMemoryLimiter(instance._fallback_storage)
    return instance


limiter = create_limiter()


def rate_limit_response(
    detail: object, retry_after: int, headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Keep legacy detail values while providing one machine-readable 429 envelope."""
    seconds = max(1, retry_after)
    response_headers = {
        key: value for key, value in (headers or {}).items()
        if key.lower() != "retry-after"
    }
    response_headers["Retry-After"] = str(seconds)
    return JSONResponse(
        {"error": "Rate limit exceeded", "detail": detail, "retry_after": seconds},
        status_code=429,
        headers=response_headers,
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Work both in SlowAPI's synchronous middleware and in route wrappers."""
    retry_after = exc.limit.limit.get_expiry()
    window = getattr(request.state, "view_rate_limit", None)
    if window:
        try:
            stats = request.app.state.limiter.limiter.get_window_stats(window[0], *window[1])
            retry_after = math.ceil(stats.reset_time - time.time())
        except Exception:
            # A backend can disappear between rejecting a request and reading
            # its expiry. Never turn the original 429 into a storage 5xx.
            pass
    return rate_limit_response("Rate limit exceeded", retry_after)


async def rate_limit_http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Normalize handler-level quotas; preserve other HTTP responses as before."""
    if exc.status_code != 429:
        return await http_exception_handler(request, exc)
    retry_after = 60
    current: BaseException | None = exc
    # Some established routers translate a guard's detail and retain its
    # exception as context. Preserve the original window's retry guidance.
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HTTPException) and current.headers:
            value = Headers(current.headers).get("Retry-After")
            if value is not None:
                try:
                    retry_after = max(1, int(value))
                except ValueError:
                    pass
                break
        current = current.__context__
    return rate_limit_response(exc.detail, retry_after, exc.headers)


async def enforce_route_limit(request: Request) -> None:
    """Run the endpoint's registered policy before expensive dependencies.

    Install as a route dependency before authentication. Reuse SlowAPI's
    storage/fallback and completion flag so the endpoint wrapper does not
    consume a second request from the same bucket.
    """
    if limiter.enabled and not getattr(request.state, "_rate_limiting_complete", False):
        limiter._check_request_limit(request, request.scope["endpoint"], False)
        request.state._rate_limiting_complete = True

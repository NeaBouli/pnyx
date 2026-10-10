"""Shared, privacy-preserving API rate limiter configuration."""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter

from ip_utils import rate_limit_key_for_ip


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


# FastAPI 0.142.2 includes routers via _IncludedRouter (no top-level endpoint).
# SlowAPI 0.1.10 skips default_limits for those routes. The 60/min default is
# NOT an API-wide guarantee: router writes need an explicit decorator or a
# handler-level Redis guard. Keep the existing default policy unchanged.
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60/minute"],
    storage_uri=get_rate_limit_storage_uri(),
    in_memory_fallback_enabled=True,
    key_prefix="ekklesia-api",
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
)

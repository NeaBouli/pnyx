"""Privacy-preserving client IP helpers.

Centralizes proxy-aware IP extraction and rate-limit identifiers so routers do
not log or persist raw client IP addresses.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import date
from ipaddress import ip_address
from typing import Iterable

import redis.asyncio as aioredis
from fastapi import HTTPException, Request


def _valid_ip(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        ip_address(value)
    except ValueError:
        return None
    return value


def _split_forwarded_for(header: str) -> list[str]:
    return [part.strip() for part in header.split(",") if part.strip()]


def _candidate_from_forwarded_for(parts: Iterable[str]) -> str | None:
    valid = [_valid_ip(part) for part in parts]
    valid = [part for part in valid if part]
    if not valid:
        return None

    # Traefik appends the actual peer IP to X-Forwarded-For. Taking the
    # rightmost trusted entry avoids client-supplied spoofed leftmost values.
    trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))
    if trusted_proxy_count < 1:
        trusted_proxy_count = 1
    index = max(len(valid) - trusted_proxy_count, 0)
    return valid[index]


def get_client_ip(request: Request) -> str:
    """Return a proxy-aware client IP for local rate limiting only."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        candidate = _candidate_from_forwarded_for(_split_forwarded_for(forwarded))
        if candidate:
            return candidate

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_salt() -> str:
    salt = os.getenv("RATE_LIMIT_SALT") or os.getenv("SERVER_SALT") or ""
    if not salt:
        # Production startup validates SERVER_SALT. This fallback keeps local
        # tests deterministic without weakening production behavior.
        salt = "local-development-rate-limit-salt"
    return salt


def hashed_rate_subject(subject: str, namespace: str, today: date | None = None) -> str:
    """Return a non-reversible daily HMAC identifier for rate-limit buckets."""
    day = (today or date.today()).isoformat()
    msg = f"{namespace}:{day}:{subject}".encode()
    digest = hmac.new(_rate_limit_salt().encode(), msg, hashlib.sha256).hexdigest()
    return digest[:32]


def rate_limit_key_for_ip(request: Request, namespace: str, today: date | None = None) -> str:
    subject = get_client_ip(request)
    day = (today or date.today()).isoformat()
    hashed = hashed_rate_subject(subject, namespace, today=today)
    return f"ratelimit:{namespace}:{day}:{hashed}"


def ip_reference(request: Request, namespace: str = "request") -> str:
    """Stable-for-the-day IP reference for logs/emails without exposing raw IP."""
    return f"ipref:{hashed_rate_subject(get_client_ip(request), namespace)[:12]}"


async def redis_fixed_window_limit(
    redis: aioredis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> int:
    """Increment a Redis fixed-window counter and raise 429 on overflow."""
    count = int(
        await redis.eval(
            """
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then
              redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return count
            """,
            1,
            key,
            window_seconds,
        )
    )
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
        )
    return count

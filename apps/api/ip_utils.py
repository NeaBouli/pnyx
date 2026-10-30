"""Privacy-preserving client IP helpers.

Centralizes proxy-aware IP extraction and rate-limit identifiers so routers do
not log or persist raw client IP addresses.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import math
import os
import threading
import time
from datetime import date
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import Iterable

import redis.asyncio as aioredis
from fastapi import HTTPException, Request
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)
_fallback_lock = threading.Lock()
_fallback_counts: dict[tuple[str, int], tuple[int, float]] = {}
_MAX_FALLBACK_BUCKETS = 10_000


def _valid_ip(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        address = ip_address(value)
    except ValueError:
        return None
    return str(address)


def _split_forwarded_for(header: str) -> list[str]:
    return [part.strip() for part in header.split(",")]


def _trusted_proxy_networks() -> tuple[IPv4Network | IPv6Network, ...]:
    """Return the immediate proxy networks allowed to assert forwarding headers."""
    configured = os.getenv(
        "TRUSTED_PROXY_CIDRS",
        "127.0.0.1/32,::1/128",
    )
    networks: list[IPv4Network | IPv6Network] = []
    for value in configured.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ip_network(value, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _is_trusted_proxy(value: str | None) -> bool:
    peer = _valid_ip(value or "")
    if not peer:
        return False
    address = ip_address(peer)
    return any(
        address.version == network.version and address in network
        for network in _trusted_proxy_networks()
    )


def _candidate_from_forwarded_for(parts: Iterable[str]) -> str | None:
    chain = list(parts)
    if not chain:
        return None

    # Traefik appends the actual peer IP to X-Forwarded-For. Walk only the
    # configured trusted hops from the right; stop at an untrusted client.
    try:
        trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))
    except ValueError:
        trusted_proxy_count = 1
    if trusted_proxy_count < 1:
        trusted_proxy_count = 1
    if trusted_proxy_count > len(chain):
        # A count larger than the observed chain is a deployment mismatch.
        # Prefer the nearest asserted hop instead of a spoofable leftmost value.
        return _valid_ip(chain[-1])
    for index, value in enumerate(reversed(chain)):
        candidate = _valid_ip(value)
        if candidate is None:
            # Do not discard malformed hops and shift an attacker-controlled
            # address into the configured position.
            return None
        if index == trusted_proxy_count - 1 or not _is_trusted_proxy(candidate):
            return candidate
    return None


def get_client_ip(request: Request) -> str:
    """Return the peer IP, honoring forwarding data only from trusted proxies."""
    peer = request.client.host if request.client and request.client.host else None
    if _is_trusted_proxy(peer):
        # Repeated fields form one ordered chain; a client-supplied first field
        # must not hide the peer appended by a trusted proxy in a later field.
        forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
        candidate = _candidate_from_forwarded_for(_split_forwarded_for(forwarded))
        if candidate:
            return candidate

    return peer or "unknown"


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


def log_reference(value: str, namespace: str) -> str:
    """Return a short stable HMAC reference for logs instead of a secret or identifier.

    EVA-004: invite codes and representative ADAs must not appear in logs. The
    reference is stable (no daily rotation) so an invite's creation and its use
    can still be correlated by an operator, but the value cannot be recovered
    from the log line.
    """
    msg = f"log:{namespace}:{value}".encode()
    return hmac.new(_rate_limit_salt().encode(), msg, hashlib.sha256).hexdigest()[:12]


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
    """Use atomic shared counters, or half-quota local counters during outage.

    Only counters fall back. Callers' separate Redis data, locks and paid
    provider cost guards retain their own availability requirements.
    """
    try:
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
    except (RedisError, ConnectionError, TimeoutError):
        logger.warning("rate_limit event=fallback count=1")
        return _local_fixed_window_limit(key, limit, window_seconds)
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window_seconds)},
        )
    return count


def _local_fixed_window_limit(key: str, limit: int, window_seconds: int) -> int:
    """Bound memory without evicting live buckets (which would reset quotas)."""
    now = time.monotonic()
    bucket = (key, window_seconds)
    with _fallback_lock:
        for expired in [item for item, (_, end) in _fallback_counts.items() if end <= now]:
            del _fallback_counts[expired]
        count, end = _fallback_counts.get(bucket, (0, now + window_seconds))
        if bucket not in _fallback_counts and len(_fallback_counts) >= _MAX_FALLBACK_BUCKETS:
            raise HTTPException(
                429, "Rate limit exceeded", headers={"Retry-After": str(window_seconds)},
            )
        count += 1
        _fallback_counts[bucket] = (count, end)
    if count > max(1, limit // 2):
        raise HTTPException(
            429, "Rate limit exceeded",
            headers={"Retry-After": str(max(1, math.ceil(end - now)))},
        )
    return count

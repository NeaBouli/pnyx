"""EKA-05: signed Expo push registration — canonical payload, storage key
derivation and privacy-preserving fixed-window limits.

Raw tokens, device IDs, nullifiers and IPs must never appear in Redis keys or
log lines; all limit/storage identifiers are HMAC digests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Request

from ip_utils import (
    get_client_ip,
    hashed_rate_subject,
    redis_fixed_window_limit,
)

PUSH_TOKEN_TTL_SECONDS = 90 * 24 * 3600  # 90 days

# NAT-tolerant pre-auth ceiling: shared carrier/office IPs legitimately carry
# many installs, so the hourly per-IP bucket stays far above plausible real
# usage while still bounding unauthenticated Redis key filling.
PUSH_REGISTER_IP_LIMIT = 600
PUSH_REGISTER_IP_WINDOW_SECONDS = 3600

# Verified identities may rotate a bounded number of new/changed devices per
# day; same-value re-registrations never consume this quota.
PUSH_REGISTER_IDENTITY_LIMIT = 20
PUSH_REGISTER_IDENTITY_WINDOW_SECONDS = 86400

# Real Expo forms with a bounded permissive printable-ASCII inner charset;
# inner brackets are rejected separately by the request validator.
EXPO_TOKEN_RE = re.compile(
    r"^(?:ExpoPushToken|ExponentPushToken)\[([ -~]{1,256})\]$"
)
DEVICE_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def build_push_register_payload(
    device_id: str,
    token: str,
    platform: str,
    nullifier_hash: str,
    timestamp_ms: int,
) -> str:
    """Cross-client canonical payload; mirrors buildPushRegisterPayload (TS)."""
    body = json.dumps(
        [device_id, token, platform, nullifier_hash, int(timestamp_ms)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"push-register:v1:{body}"


def _push_key_salt() -> str:
    # Registration keys must remain stable even when an operator rotates the
    # dedicated rate-limit salt, so prefer the production SERVER_SALT here.
    salt = os.getenv("SERVER_SALT") or os.getenv("RATE_LIMIT_SALT") or ""
    if not salt:
        # Production startup validates SERVER_SALT; this fallback only keeps
        # local tests deterministic.
        salt = "local-development-rate-limit-salt"
    return salt


def push_token_storage_key(nullifier_hash: str, device_id: str) -> str:
    """Stable HMAC storage key; raw nullifier/device_id never reach Redis.

    Keeps the push_tokens: prefix so existing send scans keep working.
    """
    msg = f"push-register:v1:{nullifier_hash}:{device_id}".encode()
    digest = hmac.new(_push_key_salt().encode(), msg, hashlib.sha256).hexdigest()
    return f"push_tokens:{digest}"


async def enforce_push_register_ip_limit(
    redis: aioredis.Redis, request: Request,
) -> None:
    """Per-IP hourly ceiling, enforced before any identity database work."""
    subject = get_client_ip(request)
    now = datetime.now(timezone.utc)
    hour = now.strftime("%Y-%m-%dT%H")
    hashed = hashed_rate_subject(
        subject, "push_register_ip", today=now.date(),
    )
    key = f"ratelimit:push_register:ip:{hour}:{hashed}"
    await redis_fixed_window_limit(
        redis, key, PUSH_REGISTER_IP_LIMIT, PUSH_REGISTER_IP_WINDOW_SECONDS,
    )


async def enforce_push_register_identity_limit(
    redis: aioredis.Redis, nullifier_hash: str,
) -> None:
    """Daily quota for new/changed registrations of one verified identity."""
    today = datetime.now(timezone.utc).date()
    day = today.isoformat()
    hashed = hashed_rate_subject(
        nullifier_hash, "push_register_identity", today=today,
    )
    key = f"ratelimit:push_register:id:{day}:{hashed}"
    await redis_fixed_window_limit(
        redis, key,
        PUSH_REGISTER_IDENTITY_LIMIT, PUSH_REGISTER_IDENTITY_WINDOW_SECONDS,
    )

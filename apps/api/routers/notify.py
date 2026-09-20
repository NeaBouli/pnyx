"""
MOD-20: Push Notifications (Expo Push API)
POST /api/v1/notify/register — register device push token (signed, EKA-05)
POST /api/v1/notify/send     — admin: send push to all (ADMIN_KEY required)
"""
import os
import json
import logging
import sys
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from dependencies import verify_admin_key
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional
import redis.asyncio as aioredis
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import IdentityRecord, KeyStatus
from services.citizen_action_integrity import citizen_action_timestamp_is_fresh
from services.push_registration import (
    DEVICE_ID_RE,
    EXPO_TOKEN_RE,
    PUSH_TOKEN_TTL_SECONDS,
    build_push_register_payload,
    enforce_push_register_identity_limit,
    enforce_push_register_ip_limit,
    push_token_storage_key,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notify", tags=["MOD-20 Push"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "")
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

_redis = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return _redis


async def _registered_push_tokens(r: aioredis.Redis) -> list[str]:
    """Return unique valid tokens across legacy and signed registration keys."""
    tokens: list[str] = []
    seen: set[str] = set()
    async for key in r.scan_iter("push_tokens:*"):
        raw = await r.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        token = data.get("token") if isinstance(data, dict) else None
        if isinstance(token, str) and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


class RegisterRequest(BaseModel):
    """Strict signed registration schema (EKA-05); extra fields forbidden."""

    model_config = ConfigDict(extra="forbid")

    token: str
    device_id: str = Field(..., pattern=DEVICE_ID_RE.pattern)
    platform: Literal["android", "ios"]
    nullifier_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    timestamp_ms: int = Field(..., ge=0, le=9_007_199_254_740_991)
    signature_hex: str = Field(..., pattern=r"^[0-9a-fA-F]{128}$")

    @field_validator("token")
    @classmethod
    def _real_expo_token(cls, value: str) -> str:
        match = EXPO_TOKEN_RE.match(value)
        if match is None or "[" in match.group(1) or "]" in match.group(1):
            raise ValueError("invalid Expo push token")
        return value


class SendRequest(BaseModel):
    template_id: str
    data: dict = {}
    target: str = "all"


@router.post("/register")
async def register_push(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Signed push registration bound to an ACTIVE identity (EKA-05).

    Never log token, device_id, nullifier or IP on this path.
    """
    r = await _get_redis()

    # Privacy-preserving per-IP ceiling before any identity database work.
    await enforce_push_register_ip_limit(r, request)

    if not citizen_action_timestamp_is_fresh(req.timestamp_ms):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.")

    # Missing and revoked identities share the invalid-signature response.
    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    payload = build_push_register_payload(
        req.device_id,
        req.token,
        req.platform,
        req.nullifier_hash,
        req.timestamp_ms,
    )
    if identity is None or not verify_signature(
        identity.public_key_hex, payload, req.signature_hex,
    ):
        raise HTTPException(401, "Μη έγκυρη υπογραφή.")

    key = push_token_storage_key(req.nullifier_hash, req.device_id)
    value = json.dumps({"token": req.token, "platform": req.platform})

    # Same-value re-registration is idempotent: refresh the TTL without
    # consuming the per-identity new-key quota.
    existing = await r.get(key)
    if existing is not None:
        try:
            current = json.loads(existing)
        except ValueError:
            current = None
        if (
            isinstance(current, dict)
            and current.get("token") == req.token
            and current.get("platform") == req.platform
        ):
            await r.setex(key, PUSH_TOKEN_TTL_SECONDS, value)
            return {"registered": True, "integrity": "signed-v1"}

    # Only new or changed registrations consume the daily identity quota.
    await enforce_push_register_identity_limit(r, req.nullifier_hash)
    await r.setex(key, PUSH_TOKEN_TTL_SECONDS, value)
    return {"registered": True, "integrity": "signed-v1"}


@router.post("/send")
async def send_push(
    req: SendRequest,
    _auth: bool = Depends(verify_admin_key),
) -> dict:

    r = await _get_redis()
    tokens = await _registered_push_tokens(r)

    if not tokens:
        return {"sent": 0, "failed": 0, "message": "No registered devices"}

    # Build messages
    messages = [
        {
            "to": t,
            "title": req.data.get("title", "ekklesia"),
            "body": req.data.get("body", ""),
            "data": {"template_id": req.template_id, **req.data},
        }
        for t in tokens
    ]

    # Send in batches of 100
    sent = 0
    failed = 0
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(0, len(messages), 100):
            batch = messages[i : i + 100]
            try:
                resp = await client.post(EXPO_PUSH_URL, json=batch)
                if resp.status_code == 200:
                    sent += len(batch)
                else:
                    failed += len(batch)
                    logger.warning(
                        "[MOD-20] Expo push batch failed: %s", resp.status_code
                    )
            except Exception as exc:
                failed += len(batch)
                logger.error("[MOD-20] Expo push error: %s", exc)

    return {"sent": sent, "failed": failed}


# ---------------------------------------------------------------------------
# Helper functions for other routers to call
# ---------------------------------------------------------------------------


async def notify_all(template_id: str, data: dict) -> None:
    """Send push to all registered devices. Call from other routers."""
    try:
        r = await _get_redis()
        tokens = await _registered_push_tokens(r)
        if not tokens:
            return
        messages = [
            {
                "to": t,
                "title": data.get("title", "ekklesia"),
                "body": data.get("body", ""),
                "data": {"template_id": template_id, **data},
            }
            for t in tokens
        ]
        async with httpx.AsyncClient(timeout=15.0) as client:
            for i in range(0, len(messages), 100):
                await client.post(EXPO_PUSH_URL, json=messages[i : i + 100])
    except Exception:
        pass  # Push is best-effort

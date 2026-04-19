"""
MOD-20: Push Notifications (Expo Push API)
POST /api/v1/notify/register — register device push token
POST /api/v1/notify/send     — admin: send push to all (ADMIN_KEY required)
"""
import os
import json
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import redis.asyncio as aioredis
import httpx

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


class RegisterRequest(BaseModel):
    token: str
    device_id: str
    platform: str = "android"


class SendRequest(BaseModel):
    template_id: str
    data: dict = {}
    target: str = "all"


@router.post("/register")
async def register_push(req: RegisterRequest) -> dict:
    r = await _get_redis()
    await r.setex(
        f"push_tokens:{req.device_id}",
        7776000,  # 90 day TTL
        json.dumps({"token": req.token, "platform": req.platform}),
    )
    return {"registered": True}


@router.post("/send")
async def send_push(
    req: SendRequest,
    x_admin_key: Optional[str] = Header(None),
) -> dict:
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Admin key required")

    r = await _get_redis()
    keys = [k async for k in r.scan_iter("push_tokens:*")]
    tokens: list[str] = []
    for k in keys:
        raw = await r.get(k)
        if raw:
            data = json.loads(raw)
            tokens.append(data["token"])

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
        keys = [k async for k in r.scan_iter("push_tokens:*")]
        tokens: list[str] = []
        for k in keys:
            raw = await r.get(k)
            if raw:
                tokens.append(json.loads(raw)["token"])
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

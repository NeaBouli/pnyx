"""Data-only pushes for the categories vote_24h, bill_announced, weekly_digest
and system_update (T-652).

The server keeps no per-category preferences. These pushes therefore carry no
OS-visible title/body: the app shows a local notification only when the user
enabled the category (apps/mobile notifications.ts, local_display="1"), so the
opt-in stays strictly on the device. Older app versions only add the event to
their unread list (if enabled) without a tray notification.

Sending is OFF unless PUSH_DATA_ONLY_CATEGORIES=1 (enable only after the
v1.0.34 rollout). Every event is deduplicated in Redis, the weekly digest is
sent at most once per ISO week, and a global hourly cap bounds the volume.
No new personal data is collected.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

FLAG = "PUSH_DATA_ONLY_CATEGORIES"
CATEGORIES = ("vote_24h", "bill_announced", "weekly_digest", "system_update")
HOURLY_CAP = int(os.getenv("PUSH_DATA_ONLY_HOURLY_CAP", "20"))
DEDUP_TTL = {
    "vote_24h": 7 * 86400,
    "bill_announced": 30 * 86400,
    "weekly_digest": 8 * 86400,
    "system_update": 180 * 86400,
}
ANNOUNCED_MAX_AGE = timedelta(hours=48)
SYSTEM_UPDATE_SEEN_KEY = "push:system_update:last_version"


def data_only_enabled() -> bool:
    return os.getenv(FLAG, "") == "1"


async def send_category_push(
    redis_client: Any,
    template_id: str,
    event_key: str,
    payload: dict[str, Any],
    *,
    sender: Any = None,
    now: datetime | None = None,
) -> bool:
    """Send one data-only push once per event. Returns True only when sent."""
    if template_id not in CATEGORIES or not data_only_enabled():
        return False
    dedup_key = f"notified:{template_id}:{event_key}"
    if await redis_client.exists(dedup_key):
        return False
    hour = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H")
    cap_key = f"push:data_only:count:{hour}"
    count = await redis_client.incr(cap_key)
    await redis_client.expire(cap_key, 7200)
    if int(count) > HOURLY_CAP:
        logger.warning("[MOD-20] data-only push cap reached; %s deferred", template_id)
        return False
    if sender is None:
        from routers.notify import notify_all_data_only as sender
    await sender(template_id, payload)
    await redis_client.setex(dedup_key, DEDUP_TTL[template_id], "1")
    return True


def iso_week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


async def push_vote_24h(redis_client: Any, bill: Any, **kw: Any) -> bool:
    return await send_category_push(redis_client, "vote_24h", bill.id, {
        "title": "⏳ Τελευταίες 24 ώρες",
        "body": (bill.title_el or bill.id)[:100],
        "bill_id": bill.id,
    }, **kw)


async def push_bill_announced(redis_client: Any, bill: Any, **kw: Any) -> bool:
    return await send_category_push(redis_client, "bill_announced", bill.id, {
        "title": "📢 Νέο νομοσχέδιο",
        "body": (bill.title_el or bill.id)[:100],
        "bill_id": bill.id,
    }, **kw)


async def push_weekly_digest(
    redis_client: Any, active: int, results: int, *, now: datetime | None = None, **kw: Any,
) -> bool:
    now = now or datetime.now(timezone.utc)
    week = iso_week_key(now)
    return await send_category_push(redis_client, "weekly_digest", week, {
        "title": "📅 Εβδομαδιαία ενημέρωση",
        "body": f"{active} ανοιχτές ψηφοφορίες · {results} νέα αποτελέσματα",
        "date": week,
    }, now=now, **kw)


async def push_system_update(redis_client: Any, version: str, **kw: Any) -> bool:
    """Announce a new app version once; the first run only records the version."""
    if not data_only_enabled():
        return False
    seen = await redis_client.get(SYSTEM_UPDATE_SEEN_KEY)
    if seen is None:
        await redis_client.set(SYSTEM_UPDATE_SEEN_KEY, version)
        return False
    if seen == version:
        return False
    sent = await send_category_push(redis_client, "system_update", version, {
        "title": "🆕 Νέα έκδοση εφαρμογής",
        "body": f"Διαθέσιμη η έκδοση {version}",
        "version": version,
    }, **kw)
    if sent:
        await redis_client.set(SYSTEM_UPDATE_SEEN_KEY, version)
    return sent


def announced_recently(bill: Any, now: datetime) -> bool:
    created = getattr(bill, "created_at", None)
    if created is None:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return now - created <= ANNOUNCED_MAX_AGE

"""Data-only pushes for the categories vote_24h, bill_announced, weekly_digest
and system_update (T-652).

The server keeps no per-category preferences. These pushes therefore carry no
OS-visible title/body: the app shows a local notification only when the user
enabled the category (apps/mobile notifications.ts, local_display="1"), so the
opt-in stays strictly on the device. Older app versions only add the event to
their unread list (if enabled) without a tray notification.

Sending is OFF unless PUSH_DATA_ONLY_CATEGORIES=1 (enable only after the
v1.0.34 rollout). Every event is sent at most once: an atomic Redis claim
(SET NX) is taken before sending, so parallel schedulers cannot send the same
event twice; it becomes the final dedup marker only when the provider accepted
at least one message, and is released (for a later retry) when nothing was
accepted. Provider acceptance is not a delivery receipt. The weekly digest is
sent at most once per ISO week, and a global hourly cap bounds the volume.
No new personal data is collected.
"""
from __future__ import annotations

import logging
import os
import uuid
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
# Longer than a full send (15 s timeout per batch of 100), short enough for a retry.
CLAIM_TTL = int(os.getenv("PUSH_DATA_ONLY_CLAIM_TTL", "900"))
WEEKLY_DIGEST_CATCHUP_LAST_WEEKDAY = 2  # Monday 07:00 UTC .. Wednesday

# Finalize (ARGV[2] == "final") or release the claim, only while we still own it.
_SETTLE_CLAIM = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if ARGV[2] == 'final' then
  redis.call('SET', KEYS[1], '1', 'EX', tonumber(ARGV[3]))
else
  redis.call('DEL', KEYS[1])
end
return 1
"""


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
    """Send one data-only push once per event. Returns True only when sent.

    `sender(template_id, payload)` returns a dict with `attempted`, `accepted`
    and `failed` message counts and raises when the send could not be made.
    """
    if template_id not in CATEGORIES or not data_only_enabled():
        return False
    dedup_key = f"notified:{template_id}:{event_key}"
    claim = f"claim:{uuid.uuid4().hex}"
    if not await redis_client.set(dedup_key, claim, nx=True, ex=CLAIM_TTL):
        return False  # already sent, or another worker is sending it
    hour = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H")
    cap_key = f"push:data_only:count:{hour}"
    try:
        count = await redis_client.incr(cap_key)
        await redis_client.expire(cap_key, 7200)
        if int(count) > HOURLY_CAP:
            logger.warning("[MOD-20] data-only push cap reached; %s deferred", template_id)
            await _settle(redis_client, dedup_key, claim, final=False)
            return False
        if sender is None:
            from routers.notify import notify_all_data_only as sender
        result = await sender(template_id, payload)
    except Exception as exc:
        logger.error("[MOD-20] data-only push %s failed: %s", template_id, exc)
        await _settle(redis_client, dedup_key, claim, final=False)
        return False
    attempted = int(result.get("attempted", 0))
    accepted = int(result.get("accepted", 0))
    failed = int(result.get("failed", 0))
    if attempted > 0 and accepted == 0:
        # Nothing reached the provider: release the claim so a later run retries.
        logger.warning("[MOD-20] data-only push %s not accepted (%d failed)", template_id, failed)
        await _settle(redis_client, dedup_key, claim, final=False)
        return False
    if failed:
        # Partial batch: no resend, it would duplicate for the accepted devices.
        logger.warning("[MOD-20] data-only push %s: %d accepted, %d failed", template_id, accepted, failed)
    await _settle(redis_client, dedup_key, claim, final=True, ttl=DEDUP_TTL[template_id])
    return accepted > 0


async def _settle(redis_client: Any, key: str, claim: str, *, final: bool, ttl: int = 0) -> None:
    try:
        await redis_client.eval(_SETTLE_CLAIM, 1, key, claim, "final" if final else "release", ttl)
    except Exception as exc:
        # The claim then expires after CLAIM_TTL; no second send happens before that.
        logger.error("[MOD-20] data-only push claim %s not settled: %s", key, exc)


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


def weekly_digest_due(now: datetime) -> bool:
    """Catch-up window for a missed Monday 07:00 UTC digest run."""
    weekday = now.weekday()
    if weekday == 0:
        return now.hour >= 7
    return weekday <= WEEKLY_DIGEST_CATCHUP_LAST_WEEKDAY


def announced_recently(bill: Any, now: datetime) -> bool:
    created = getattr(bill, "created_at", None)
    if created is None:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return now - created <= ANNOUNCED_MAX_AGE

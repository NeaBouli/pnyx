"""Shared consent gate for planned campaigns; identities stay inside the service."""
import json
import logging
import os
from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from services import newsletter_service
from services.newsletter_consent import (
    CONFIRMED_KEY, SUPPRESSED_KEY, BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY,
    BREVO_ADD_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY, LISTMONK_ADD_UNSETTLED_KEY, TOPICS,
    delivery_eligible, matches_campaign, parse_consent, preference_attributes,
)

logger = logging.getLogger(__name__)


class CampaignPlan(BaseModel):
    language: Literal["el", "en"] = "el"
    frequency: Literal["monthly", "weekly"] = "monthly"
    topic: Literal["new_proposals", "active_votes", "vote_results", "system_news", "breaking_news"] | None = None

    @property
    def key(self) -> str:
        return f"{self.language}:{self.frequency}:{self.topic or 'all'}"

    @property
    def tag(self) -> str:
        return f"newsletter:v1:{self.key}"


class AudienceUnavailable(Exception):
    """No provider dispatch is authorized when consent or segment state is unknown."""

    def __init__(self, reason: str = "audience_unavailable", counts: dict[str, int] | None = None):
        self.reason = reason
        self.counts = {"selected": 0, "excluded": 0, "failed": 0, "provider": 0, **(counts or {})}
        super().__init__(reason)

    @property
    def detail(self) -> dict[str, str | int]:
        return {"reason": self.reason, **self.counts}


def log_audience(reason: str, counts: dict[str, int]) -> None:
    log = logger.info if reason in {"ready", "sent"} else logger.warning
    log(
        "[NEWSLETTER] reason=%s selected=%d excluded=%d failed=%d provider=%d",
        reason, counts.get("selected", 0), counts.get("excluded", 0),
        counts.get("failed", 0), counts.get("provider", 0),
    )


def campaign_plan(tag: object) -> CampaignPlan:
    if not isinstance(tag, str) or not tag.startswith("newsletter:v1:"):
        raise AudienceUnavailable()
    try:
        language, frequency, topic = tag.removeprefix("newsletter:v1:").split(":")
        return CampaignPlan(language=language, frequency=frequency, topic=None if topic == "all" else topic)
    except ValueError:
        raise AudienceUnavailable() from None


def campaign_recipients(plan: CampaignPlan) -> dict[str, list[int]]:
    """Never combine listIds with segmentIds: that would broaden the audience."""
    raw = os.getenv("BREVO_NEWSLETTER_SEGMENTS", "")
    if not raw.strip():
        raise AudienceUnavailable("segments_not_configured")
    try:
        segments = json.loads(raw)
        if segments == {}:
            raise AudienceUnavailable("segments_not_configured")
        allowed = {f"{language}:{frequency}:{topic}" for language in ("el", "en")
                   for frequency in ("monthly", "weekly") for topic in ("all", *TOPICS)}
        if (not isinstance(segments, dict) or not set(segments) <= allowed
                or any(type(value) is not int or value <= 0 for value in segments.values())
                or plan.key not in segments):
            raise ValueError()
        return {"segmentIds": [segments[plan.key]]}
    except (TypeError, ValueError):
        raise AudienceUnavailable("segments_invalid") from None


@dataclass
class Audience:
    records: dict[str, str]
    suppressed: dict[str, str]
    selected: set[str]
    counts: dict[str, int]

    async def check(self, store: Redis) -> None:
        # Compare the entire snapshot, including aliases and new withdrawals.
        if (await store.hgetall(CONFIRMED_KEY) != self.records
                or await store.hgetall(SUPPRESSED_KEY) != self.suppressed):
            raise AudienceUnavailable("audience_mismatch", self.counts)
        await check_provider_writes(store, self.counts)


async def check_provider_writes(store: Redis, counts: dict[str, int]) -> None:
    for key in (BREVO_ADD_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY, LISTMONK_ADD_UNSETTLED_KEY,
                BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY):
        if await store.hgetall(key):
            raise AudienceUnavailable("unsettled_provider_writes", counts)


async def select_audience(store: Redis, plan: CampaignPlan) -> Audience:
    records = await store.hgetall(CONFIRMED_KEY)
    suppressed = await store.hgetall(SUPPRESSED_KEY)
    counts = {"selected": 0, "excluded": 0, "failed": 0}
    selected: set[str] = set()
    aliases = Counter(email.casefold() for email in records)
    now = datetime.now(timezone.utc)
    for email, raw in records.items():
        if aliases[email.casefold()] > 1:
            counts["failed"] += 1
            continue
        data = parse_consent(email, raw, now)
        if (email.casefold() in suppressed or data is None or not delivery_eligible(data, now)
                or not matches_campaign(data, plan.language, plan.frequency, plan.topic)):
            counts["excluded"] += 1
            continue
        status = await newsletter_service.contact_status(email, attributes=preference_attributes(data))
        if status == "already_present":
            selected.add(email.casefold())
        elif status == "suppressed":
            counts["excluded"] += 1
        else:
            counts["failed"] += 1
    counts["selected"] = len(selected)
    return Audience(records, suppressed, selected, counts)


async def _segment_members(segment: int) -> set[str]:
    """Read every page, bounded to 10,000 members; never log provider responses."""
    if not newsletter_service.BREVO_API_KEY:
        raise AudienceUnavailable()
    members: set[str] = set()
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        for offset in range(0, 10_000, 500):
            response = await client.get(
                f"{newsletter_service.BREVO_API}/contacts",
                headers={"api-key": newsletter_service.BREVO_API_KEY},
                params={"segmentId": segment, "limit": 500, "offset": offset, "sort": "asc"},
            )
            if response.status_code != 200:
                raise AudienceUnavailable()
            payload = response.json()
            contacts, count = payload["contacts"], payload["count"]
            if not isinstance(contacts, list) or type(count) is not int or not 0 <= count <= 10_000:
                raise AudienceUnavailable()
            for contact in contacts:
                if contact.get("emailBlacklisted") is True:
                    continue
                email = contact.get("email")
                lists, unsubscribed = contact.get("listIds"), contact.get("listUnsubscribed", [])
                if (not isinstance(email, str) or contact.get("emailBlacklisted") is not False
                        or not isinstance(lists, list) or not isinstance(unsubscribed, list)
                        or any(type(value) is not int for value in lists + unsubscribed)):
                    raise AudienceUnavailable()
                if newsletter_service.LIST_ID in unsubscribed:
                    continue
                if newsletter_service.LIST_ID not in lists:
                    raise AudienceUnavailable()
                members.add(email.casefold())
            if offset + len(contacts) >= count:
                return members
            if len(contacts) != 500:
                raise AudienceUnavailable()
    raise AudienceUnavailable()


async def audit_audience(store: Redis, plan: CampaignPlan) -> Audience:
    """Read-only diagnosis, also used by the final dispatch authorization."""
    audience = None
    try:
        audience = await select_audience(store, plan)
        recipients = campaign_recipients(plan)
        await check_provider_writes(store, audience.counts)
        members = await _segment_members(recipients["segmentIds"][0])
        audience.counts["provider"] = len(members)
        if audience.counts["failed"] or members != audience.selected:
            raise AudienceUnavailable("audience_mismatch", audience.counts)
        await audience.check(store)
        return audience
    except AudienceUnavailable as exc:
        if audience is not None:
            exc.counts.update(audience.counts)
        raise
    except Exception:
        raise AudienceUnavailable(counts=audience.counts if audience else None) from None


async def prepare_audience(store: Redis, plan: CampaignPlan) -> Audience:
    """Caller holds the campaign lease through preparation and dispatch."""
    if not await newsletter_service.ensure_reconfirmations_paused():
        raise AudienceUnavailable("unsettled_provider_writes")
    return await audit_audience(store, plan)


async def authorize_dispatch(lease, plan: CampaignPlan, previous: Audience) -> Audience:
    """Renew first, then reread consent and provider membership under that lease.

    The caller must invoke sendNow next, before releasing the lease. Every
    withdrawal and delivery write uses this same lock, including child tasks.
    """
    await lease.check()
    audience = await audit_audience(lease.store, plan)
    if audience.selected != previous.selected:
        raise AudienceUnavailable("audience_mismatch", audience.counts)
    return audience

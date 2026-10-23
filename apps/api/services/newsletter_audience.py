"""Shared consent gate for planned campaigns; identities stay inside the service."""
import json
import logging
import os
from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel
from redis.asyncio import Redis

from services import newsletter_service
from services.newsletter_consent import (
    CONFIRMED_KEY, SUPPRESSED_KEY, WITHDRAWAL_PENDING_KEY, RECONFIRM_KEY, TOPICS,
    delivery_eligible, matches_campaign, parse_consent,
    BREVO_ADD_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY,
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
    """No provider dispatch is authorized when consent or isolated list state is unknown."""

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
    """Legacy display configuration only. Dispatch never calls this parser."""
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
        if self.selected.intersection(email.casefold() for email in await store.hgetall(RECONFIRM_KEY)):
            raise AudienceUnavailable("audience_mismatch", self.counts)
        for key in (BREVO_ADD_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY):
            if self.selected.intersection(email.casefold() for email in await store.hgetall(key)):
                raise AudienceUnavailable("audience_mismatch", self.counts)
        # Keep withdrawal intent as the last store read before handing off to sendNow.
        pending = await store.hgetall(WITHDRAWAL_PENDING_KEY)
        if self.selected.intersection(email.casefold() for email in pending):
            raise AudienceUnavailable("withdrawal_pending", self.counts)


async def select_audience(store: Redis, plan: CampaignPlan) -> Audience:
    records = await store.hgetall(CONFIRMED_KEY)
    suppressed = await store.hgetall(SUPPRESSED_KEY)
    blocked = {email.casefold() for email in suppressed}
    blocked.update(email.casefold() for email in await store.hgetall(WITHDRAWAL_PENDING_KEY))
    blocked.update(email.casefold() for email in await store.hgetall(RECONFIRM_KEY))
    for key in (BREVO_ADD_RETRY_KEY, BREVO_ADD_UNSETTLED_KEY):
        blocked.update(email.casefold() for email in await store.hgetall(key))
    if len(records) > 10_000:
        raise AudienceUnavailable("audience_limit_exceeded")
    counts = {"selected": 0, "excluded": 0, "failed": 0}
    selected: set[str] = set()
    aliases = Counter(email.casefold() for email in records)
    now = datetime.now(timezone.utc)
    for email, raw in records.items():
        if aliases[email.casefold()] > 1:
            counts["failed"] += 1
            continue
        data = parse_consent(email, raw, now)
        if (email.casefold() in blocked or data is None or not delivery_eligible(data, now)
                or not matches_campaign(data, plan.language, plan.frequency, plan.topic)):
            counts["excluded"] += 1
            continue
        status = await newsletter_service.contact_status(email)
        if status in {"already_present", "to_add", "to_update"}:
            selected.add(email.casefold())
        elif status == "suppressed":
            counts["excluded"] += 1
        else:
            counts["failed"] += 1
    counts["selected"] = len(selected)
    return Audience(records, suppressed, selected, counts)


async def audit_audience(store: Redis, plan: CampaignPlan) -> Audience:
    """Read-only diagnosis, also used by the final dispatch authorization."""
    audience = None
    try:
        audience = await select_audience(store, plan)
        audience.counts["provider"] = len(audience.selected)
        if audience.counts["failed"]:
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
    return await audit_audience(store, plan)


async def authorize_dispatch(lease, plan: CampaignPlan, previous: Audience, target) -> Audience:
    """Verify the isolated target and current consent immediately before sendNow."""
    await lease.check()
    audience = await audit_audience(lease.store, plan)
    if audience.selected != previous.selected:
        raise AudienceUnavailable("audience_mismatch", audience.counts)
    await target.verify(audience)
    await lease.check()
    await audience.check(lease.store)
    return audience

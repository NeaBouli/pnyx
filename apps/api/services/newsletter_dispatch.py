"""Isolated campaign lists. No preference/enrollment writer knows these list IDs."""
import logging
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from services import newsletter_service
from services.newsletter_audience import AudienceUnavailable, log_audience
from services.newsletter_lock import newsletter_lock

logger = logging.getLogger(__name__)

MAX_CONTACTS = 10_000
ADD_BATCH_SIZE = 150
PAGE_SIZE = 500
LIST_PAGE_SIZE = 50
TEMP_PREFIX = "newsletter-tmp-v1-"
TEMP_NAME = re.compile(r"newsletter-tmp-v1-(\d{10})-[0-9a-f]{32}\Z")


async def provider_request(method: str, endpoint: str, data=None, *, params=None) -> dict:
    """Strict, bounded requests; never expose provider payloads or exceptions."""
    try:
        if not newsletter_service.BREVO_API_KEY:
            raise ValueError()
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(
                method, f"{newsletter_service.BREVO_API}/{endpoint}",
                headers={"api-key": newsletter_service.BREVO_API_KEY}, json=data, params=params,
            )
        if method == "DELETE" and response.status_code == 404:
            return {}  # Idempotent cleanup, without deleting contact history.
        if not 200 <= response.status_code < 300:
            raise ValueError()
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise ValueError()
        return payload
    except Exception:
        raise AudienceUnavailable("provider_unavailable") from None


async def list_members(list_id: int) -> set[str]:
    """Verify the raw population, including blacklisted members; never hide extras."""
    members = set()
    expected_count = None
    for offset in range(0, MAX_CONTACTS, PAGE_SIZE):
        payload = await provider_request("GET", f"contacts/lists/{list_id}/contacts", params={
            "limit": PAGE_SIZE, "offset": offset, "sort": "asc",
        })
        contacts, count = payload.get("contacts"), payload.get("count")
        if (not isinstance(contacts, list) or type(count) is not int or not 0 <= count <= MAX_CONTACTS
                or len(contacts) > PAGE_SIZE or (expected_count is not None and count != expected_count)):
            raise AudienceUnavailable("audience_mismatch")
        expected_count = count
        for contact in contacts:
            email = contact.get("email") if isinstance(contact, dict) else None
            if not isinstance(email, str) or not email or email.casefold() in members:
                raise AudienceUnavailable("audience_mismatch")
            members.add(email.casefold())
        if offset + len(contacts) == count:
            return members
        if len(contacts) != PAGE_SIZE or offset + len(contacts) > count:
            raise AudienceUnavailable("audience_mismatch")
    raise AudienceUnavailable("audience_limit_exceeded")


@dataclass
class CampaignTarget:
    list_id: int

    @property
    def recipients(self) -> dict[str, list[int]]:
        return {"listIds": [self.list_id]}

    async def verify_campaign(self, campaign_id: int) -> None:
        campaign = await provider_request("GET", f"emailCampaigns/{campaign_id}")
        recipients = campaign.get("recipients")
        # Brevo's GET schema uses `lists`, unlike the write schema's `listIds`.
        if (not isinstance(recipients, dict) or recipients.get("lists") != [self.list_id]
                or any(value for key, value in recipients.items() if key != "lists")):
            raise AudienceUnavailable("audience_mismatch")

    async def verify(self, audience) -> None:
        members = await list_members(self.list_id)
        audience.counts["provider"] = len(members)
        if members != audience.selected:
            raise AudienceUnavailable("audience_mismatch", audience.counts)


@asynccontextmanager
async def temporary_campaign_list(lease, audience):
    """Caller retains the shared lease until send acceptance and list cleanup."""
    target = None
    try:
        if not 0 < len(audience.selected) <= MAX_CONTACTS:
            raise AudienceUnavailable("audience_limit_exceeded", audience.counts)
        await lease.check()
        await audience.check(lease.store)
        # Reuse the enrollment list's folder, without a new required setting.
        parent = await provider_request("GET", f"contacts/lists/{newsletter_service.LIST_ID}")
        folder = parent.get("folderId")
        if type(folder) is not int or folder <= 0:
            raise AudienceUnavailable("provider_unavailable", audience.counts)
        name = f"{TEMP_PREFIX}{int(datetime.now(timezone.utc).timestamp())}-{uuid4().hex}"
        created = await provider_request("POST", "contacts/lists", {"name": name, "folderId": folder})
        list_id = created.get("id")
        if type(list_id) is not int or list_id <= 0 or list_id == newsletter_service.LIST_ID:
            raise AudienceUnavailable("provider_unavailable", audience.counts)
        target = CampaignTarget(list_id)
        if await list_members(list_id):
            raise AudienceUnavailable("audience_mismatch", audience.counts)
        emails = sorted(audience.selected)
        for offset in range(0, len(emails), ADD_BATCH_SIZE):
            await lease.check()
            await audience.check(lease.store)
            # Adding an existing member is idempotent; never retry an uncertain send.
            result = await provider_request("POST", f"contacts/lists/{list_id}/contacts/add", {
                "emails": emails[offset:offset + ADD_BATCH_SIZE],
            })
            contacts = result.get("contacts", {})
            if not isinstance(contacts, dict) or result.get("failure") or contacts.get("failure"):
                raise AudienceUnavailable("provider_unavailable", audience.counts)
        await target.verify(audience)
        yield target
    except AudienceUnavailable as exc:
        exc.counts.update(audience.counts)
        raise
    finally:
        if target is not None:
            try:
                await provider_request("DELETE", f"contacts/lists/{target.list_id}")
            except Exception:
                log_audience("temporary_list_cleanup_failed", {"failed": 1})


async def cleanup_temporary_campaign_lists() -> dict[str, int]:
    """Discover even lists left by create timeouts/crashes; preserve lists under 24h."""
    counts = {"selected": 0, "deleted": 0, "failed": 0}
    async with newsletter_lock() as lease:
        cutoff = datetime.now(timezone.utc).timestamp() - 86400
        stale = []
        seen = set()
        expected_count = None
        # Collect before deletion so pagination cannot skip a shifted entry.
        for offset in range(0, MAX_CONTACTS, LIST_PAGE_SIZE):
            await lease.check()
            payload = await provider_request("GET", "contacts/lists", params={
                "limit": LIST_PAGE_SIZE, "offset": offset, "sort": "asc",
            })
            lists, count = payload.get("lists"), payload.get("count")
            if (not isinstance(lists, list) or type(count) is not int or not 0 <= count <= MAX_CONTACTS
                    or len(lists) > LIST_PAGE_SIZE or (expected_count is not None and count != expected_count)):
                raise AudienceUnavailable("provider_unavailable")
            expected_count = count
            for item in lists:
                if not isinstance(item, dict):
                    raise AudienceUnavailable("provider_unavailable")
                list_id, name = item.get("id"), item.get("name")
                if type(list_id) is not int or list_id <= 0 or list_id in seen or not isinstance(name, str):
                    raise AudienceUnavailable("provider_unavailable")
                seen.add(list_id)
                match = TEMP_NAME.fullmatch(name)
                if (match and int(match[1]) < cutoff and type(list_id) is int and list_id > 0
                        and list_id != newsletter_service.LIST_ID):
                    stale.append(list_id)
            if offset + len(lists) == count:
                break
            if len(lists) != LIST_PAGE_SIZE or offset + len(lists) > count:
                raise AudienceUnavailable("provider_unavailable")
        else:
            raise AudienceUnavailable("audience_limit_exceeded")
        counts["selected"] = len(stale)
        for list_id in stale:
            await lease.check()
            try:
                await provider_request("DELETE", f"contacts/lists/{list_id}")
                counts["deleted"] += 1
            except AudienceUnavailable:
                counts["failed"] += 1
    logger.info("[NEWSLETTER] Temporary list cleanup selected=%d deleted=%d failed=%d",
                counts["selected"], counts["deleted"], counts["failed"])
    return counts

"""Durable dispatch ledger; all writes are fenced by the shared campaign lease."""
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass

from services.newsletter_audience import AudienceUnavailable
from services import newsletter_lock
from services.newsletter_service import CampaignNotSent

CLAIMS_KEY = "newsletter:dispatch:v1"
STATES = ("claimed", "sent", "failed", "uncertain")
WRITE_CLAIM = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if (redis.call('HGET', KEYS[2], ARGV[2]) or '') ~= ARGV[3] then return 0 end
redis.call('HSET', KEYS[2], ARGV[2], ARGV[4])
return 1
"""


@dataclass
class DispatchClaim:
    lease: object
    key: str
    raw: str = ""
    state: str = "claimed"
    campaign_id: int | None = None

    @asynccontextmanager
    async def attempt(self):
        try:
            yield
        except BaseException:
            if self.state == "claimed":
                await self.write("failed")
            raise

    async def write(self, state: str, campaign_id: int | None = None) -> None:
        campaign_id = self.campaign_id if campaign_id is None else campaign_id
        raw = json.dumps({"state": state, "campaign_id": campaign_id})
        if await self.lease.store.eval(
            WRITE_CLAIM, 2, newsletter_lock.LOCK_KEY, CLAIMS_KEY,
            self.lease.owner, self.key, self.raw, raw,
        ) != 1:
            raise AudienceUnavailable("lock_unavailable")
        self.raw, self.state, self.campaign_id = raw, state, campaign_id

    @classmethod
    async def acquire(cls, lease, key: str, campaign_id: int | None = None):
        from services.newsletter_dispatch import provider_request

        claim = cls(lease, key, campaign_id=campaign_id)
        claim.raw = await lease.store.hget(CLAIMS_KEY, key) or ""
        if claim.raw:
            try:
                saved = json.loads(claim.raw)
                claim.state, claim.campaign_id = saved["state"], saved["campaign_id"]
                if (claim.state not in STATES or (claim.campaign_id is not None
                        and (type(claim.campaign_id) is not int or claim.campaign_id <= 0))):
                    raise ValueError()
                if campaign_id is not None and campaign_id != claim.campaign_id:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise AudienceUnavailable("dispatch_unavailable") from None
        if claim.state == "sent":
            return claim
        if claim.state == "uncertain":
            # A stale draft status cannot prove that an earlier send will not commit.
            # Only positive provider evidence settles uncertainty; never resend it.
            try:
                campaign = await provider_request("GET", f"emailCampaigns/{claim.campaign_id}")
            except AudienceUnavailable:
                campaign = {}
            if campaign.get("status") == "sent":
                await claim.write("sent")
            return claim
        await claim.write("claimed")
        return claim

    async def send(self, operation, counts: dict[str, int], reason: str) -> None:
        if self.campaign_id is None:
            raise AudienceUnavailable("dispatch_unavailable", counts)
        # Write ahead of sendNow, including cancellation/process death and a lost ACK.
        await self.write("uncertain")
        try:
            result = await operation()
        except CampaignNotSent:
            await self.write("failed")
            raise AudienceUnavailable(reason, counts) from None
        except Exception:
            raise AudienceUnavailable(reason, {**counts, "uncertain": 1}) from None
        if result is None:
            raise AudienceUnavailable(reason, {**counts, "uncertain": 1})
        await self.write("sent")


async def dispatch_status(store) -> dict[str, int]:
    """Operator diagnosis without identities, campaign IDs, or provider payloads."""
    counts = dict.fromkeys(STATES, 0)
    for raw in (await store.hgetall(CLAIMS_KEY)).values():
        try:
            state = json.loads(raw)["state"]
            counts[state] += 1
        except (KeyError, TypeError, ValueError):
            raise AudienceUnavailable("dispatch_unavailable") from None
    return counts

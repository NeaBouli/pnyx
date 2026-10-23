"""One durable ledger for logical dispatches and provider campaign identities."""
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass

from services.newsletter_audience import AudienceUnavailable
from services import newsletter_lock
from services.newsletter_service import CampaignNotSent

CLAIMS_KEY = "newsletter:dispatch:v1"
FENCE_FIELD = "_fence"
CAMPAIGN_PREFIX = "campaign:"
STATES = ("claimed", "sent", "failed", "uncertain")
BLOCKING_STATES = {"claimed", "uncertain", "sent"}
STATE_PRIORITY = {"failed": 0, "claimed": 1, "sent": 2, "uncertain": 3}
ACQUIRE_CLAIM = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {0, ''} end
if (redis.call('HGET', KEYS[2], ARGV[2]) or '') ~= ARGV[3] then return {0, ''} end
if ARGV[4] ~= '' and (redis.call('HGET', KEYS[2], ARGV[4]) or '') ~= ARGV[5] then
    return {0, ''}
end
local claim = cjson.decode(ARGV[6])
claim.fence = redis.call('HINCRBY', KEYS[2], '_fence', 1)
local raw = cjson.encode(claim)
redis.call('HSET', KEYS[2], ARGV[2], raw)
if ARGV[4] ~= '' then redis.call('HSET', KEYS[2], ARGV[4], raw) end
return {1, raw}
"""
WRITE_CLAIM = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if (redis.call('HGET', KEYS[2], ARGV[2]) or '') ~= ARGV[3] then return 0 end
if tostring(cjson.decode(ARGV[3]).fence) ~= ARGV[6] then return 0 end
if ARGV[4] ~= '' then
    if (redis.call('HGET', KEYS[2], ARGV[4]) or '') ~= ARGV[5] then return 0 end
    if ARGV[5] ~= '' and tostring(cjson.decode(ARGV[5]).fence) ~= ARGV[6] then return 0 end
end
redis.call('HSET', KEYS[2], ARGV[2], ARGV[7])
if ARGV[4] ~= '' then redis.call('HSET', KEYS[2], ARGV[4], ARGV[7]) end
return 1
"""


async def _records(store) -> tuple[dict[str, str], dict[str, dict]]:
    raw = await store.hgetall(CLAIMS_KEY)
    records = {}
    for key, value in raw.items():
        if key == FENCE_FIELD:
            continue
        try:
            record = json.loads(value)
            campaign_id = record["campaign_id"]
            if (record["state"] not in STATES or (campaign_id is not None
                    and (type(campaign_id) is not int or campaign_id <= 0))
                    or ("fence" in record and (type(record["fence"]) is not int or record["fence"] <= 0))):
                raise ValueError()
            records[key] = record
        except (KeyError, TypeError, ValueError):
            raise AudienceUnavailable("dispatch_unavailable") from None
    return raw, records


@dataclass
class DispatchClaim:
    lease: object
    key: str
    raw: str = ""
    state: str = "claimed"
    campaign_id: int | None = None
    fence: int = 0
    acquired: bool = False
    campaign_raw: str = ""

    @asynccontextmanager
    async def attempt(self):
        try:
            yield
        except BaseException:
            if self.acquired and self.state == "claimed":
                await self.write("failed")
            raise

    async def write(self, state: str, campaign_id: int | None = None) -> None:
        if not self.acquired:
            raise AudienceUnavailable("dispatch_unavailable")
        campaign_id = self.campaign_id if campaign_id is None else campaign_id
        if campaign_id != self.campaign_id:
            # Binding a newly created provider campaign must not overwrite any
            # existing identity, including claims written before the shared index.
            _, records = await _records(self.lease.store)
            if self.campaign_id is not None or any(
                record["campaign_id"] == campaign_id for record in records.values()
            ):
                raise AudienceUnavailable("dispatch_unavailable")
        raw = json.dumps({"state": state, "campaign_id": campaign_id, "fence": self.fence})
        campaign_key = f"{CAMPAIGN_PREFIX}{campaign_id}" if campaign_id is not None else ""
        if await self.lease.store.eval(
            WRITE_CLAIM, 2, newsletter_lock.LOCK_KEY, CLAIMS_KEY,
            self.lease.owner, self.key, self.raw, campaign_key, self.campaign_raw, str(self.fence), raw,
        ) != 1:
            raise AudienceUnavailable("lock_unavailable")
        self.raw, self.state, self.campaign_id = raw, state, campaign_id
        self.campaign_raw = raw if campaign_key else ""

    @classmethod
    async def acquire(cls, lease, key: str, campaign_id: int | None = None):
        if campaign_id is not None and (isinstance(campaign_id, bool) or not isinstance(campaign_id, int) or campaign_id <= 0):
            raise AudienceUnavailable("invalid_campaign_id")
        raw, records = await _records(lease.store)
        claim = cls(lease, key, campaign_id=campaign_id)
        claim.raw = raw.get(key, "")
        saved = records.get(key)
        if saved is not None:
            claim.state, claim.campaign_id = saved["state"], saved["campaign_id"]
            if campaign_id is not None and campaign_id != claim.campaign_id:
                raise AudienceUnavailable("dispatch_unavailable")
        # Include legacy logical records with no campaign index. A deployment
        # must never make an earlier uncertain send eligible again.
        blockers = [record for name, record in records.items()
                    if (name == key or claim.campaign_id is not None
                        and record["campaign_id"] == claim.campaign_id)
                    and record["state"] in BLOCKING_STATES]
        if blockers:
            claim.state = max(blockers, key=lambda record: STATE_PRIORITY[record["state"]])["state"]
            return claim  # Claimed and uncertain both require manual resolution.
        campaign_key = f"{CAMPAIGN_PREFIX}{claim.campaign_id}" if claim.campaign_id is not None else ""
        claim.campaign_raw = raw.get(campaign_key, "")
        result = await lease.store.eval(
            ACQUIRE_CLAIM, 2, newsletter_lock.LOCK_KEY, CLAIMS_KEY,
            lease.owner, key, claim.raw, campaign_key, claim.campaign_raw,
            json.dumps({"state": "claimed", "campaign_id": claim.campaign_id}),
        )
        if not result or result[0] != 1:
            raise AudienceUnavailable("lock_unavailable")
        claim.raw = result[1]
        claim.fence = json.loads(claim.raw)["fence"]
        claim.state, claim.acquired = "claimed", True
        claim.campaign_raw = claim.raw if campaign_key else ""
        return claim

    async def send(self, operation, counts: dict[str, int], reason: str) -> None:
        if not self.acquired or self.state != "claimed" or self.campaign_id is None:
            raise AudienceUnavailable("dispatch_unavailable", counts)
        # Atomically check the lease, logical claim and shared campaign fence
        # immediately before sendNow; persist uncertainty before any network I/O.
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
    _, records = await _records(store)
    campaigns = {}
    for record in records.values():
        campaign_id = record["campaign_id"]
        if campaign_id is None:
            counts[record["state"]] += 1
        elif (campaign_id not in campaigns
              or STATE_PRIORITY[record["state"]] > STATE_PRIORITY[campaigns[campaign_id]]):
            campaigns[campaign_id] = record["state"]
    for state in campaigns.values():
        counts[state] += 1
    return counts

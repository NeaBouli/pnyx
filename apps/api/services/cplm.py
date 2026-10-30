"""
CPLM — Citizens Political Liquid Mirror
Aggregates all citizen votes into a societal X/Y political position.
Mirrors compass/engine.ts Liquid Update formula (±0.05 per vote per axis).
Includes OPEN_END votes for continuous calibration.
Redis-cached, recalculated every 6 hours.
"""
import logging
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from redis.exceptions import RedisError
import os

from models import CitizenVote, VoteChoice, ParliamentBill, BillStatus
from services.bill_visibility import public_bill_filter, results_visible_filter
from services.small_cell import small_cell_k
from services import result_cache_policy as result_policy
from services.public_bill_snapshot import snapshot_bill_filter, record_result_contributors
from services.request_work import SingleFlight, cache_fill_quota
from services.public_bill_response import (
    BODY_KEY, IDS_KEY, RESULTS_IDS_KEY, capture_public_bill_body, public_bill_response, serve_public_bill_body,
)

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
# v2 (T-599): aggregates computed before the visible-results filter must not be served after
# the rollout; the old v1 key simply expires with its TTL.
CACHE_KEY = "cplm:aggregate:v2"
CACHE_TTL = 3600  # 1 hour
# v2 (T-599): snapshots taken before the visible-results filter stay out of the public history.
HISTORY_KEY = "cplm:history:v2"

# Liquid Update strength — identical to compass/engine.ts
STRENGTH = 0.05


def publish_cplm(snapshot: dict, *, verified: bool = False) -> dict:
    """Guard new results as well as snapshots cached before flag activation."""
    k = small_cell_k()
    if not k:
        return snapshot
    result = dict(snapshot)
    hidden = not verified or (snapshot.get("total_voters") or 0) < k
    if hidden:
        for key in ("x", "y", "quadrant", "total_voters", "total_votes",
                    "open_end_votes", "consensus_adjustments", "trend"):
            result[key] = None
    result.update(suppressed=hidden, suppression_k=k)
    return result


# Bill category → axis mapping
# Bills default to "economic" axis; categories with social keywords → "social"
SOCIAL_KEYWORDS = [
    "κοινωνικ", "παιδεί", "υγεί", "δικαιωμάτ", "μεταναστ", "ασφάλει",
    "αστυνομ", "δικαιοσύν", "θρησκε", "social", "health", "education",
    "rights", "migration", "security", "justice",
]


def _classify_axis(bill: ParliamentBill) -> str:
    """Classify bill into economic or social axis based on title/categories."""
    text = f"{bill.title_el or ''} {bill.title_en or ''} {','.join(bill.categories or [])}".lower()
    for kw in SOCIAL_KEYWORDS:
        if kw in text:
            return "social"
    return "economic"


def _vote_direction(vote: VoteChoice) -> float:
    """Map vote to direction: YES=+1, NO=-1, ABSTAIN/UNKNOWN=0."""
    if vote == VoteChoice.YES:
        return 1.0
    elif vote == VoteChoice.NO:
        return -1.0
    return 0.0


async def compute_cplm(db: AsyncSession) -> dict:
    """
    Compute the aggregate CPLM position from citizen votes on bills whose results are visible.
    Votes of a running vote (ACTIVE with hidden results) are left out: with few active bills,
    changes of the aggregate could reveal how that vote is going (T-599).
    Each voter's position starts at (0, 0) and shifts ±0.05 per vote.
    The societal position is the average of all voter positions.
    """
    from sqlalchemy import text

    allowed = None
    if small_cell_k():
        from services.public_result_windows import load_publishable_bill_ids
        allowed = await load_publishable_bill_ids(db)

    # Load all votes with their bills
    result = await db.execute(
        select(CitizenVote, ParliamentBill)
        .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
        .where(public_bill_filter())
        .where(results_visible_filter(), snapshot_bill_filter(results=True))
    )
    rows = result.all()
    if allowed is not None:
        rows = [(vote, bill) for vote, bill in rows if bill.id in allowed]

    record_result_contributors(bill.id for _, bill in rows)

    if not rows:
        return publish_cplm({
            "x": 0.0, "y": 0.0, "quadrant": "center",
            "total_voters": 0, "total_votes": 0, "open_end_votes": 0,
            "consensus_adjustments": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "trend": {"x_delta": 0.0, "y_delta": 0.0, "direction": "stable"},
        }, verified=True)

    # Load consensus votes for weighting
    consensus_result = await db.execute(text(
        "SELECT nullifier_hash, bill_id, score FROM consensus_votes"
    ))
    consensus_map: dict[tuple, int] = {}
    for nh, bid, score in consensus_result:
        consensus_map[(nh, bid)] = score

    # Group votes by voter (nullifier_hash)
    voter_positions: dict[str, dict] = {}
    open_end_count = 0
    consensus_adjustments = 0

    for vote, bill in rows:
        nh = vote.nullifier_hash
        if nh not in voter_positions:
            voter_positions[nh] = {"x": 0.0, "y": 0.0}

        axis = _classify_axis(bill)
        direction = _vote_direction(vote.vote)

        # Apply consensus weighting if available
        consensus_score = consensus_map.get((nh, bill.id))
        if consensus_score is not None and bill.status == BillStatus.OPEN_END:
            # consensus_weight: -5→-1.0, 0→0.0, +5→+1.0
            weight = consensus_score / 5.0
            effective_direction = direction * weight
            consensus_adjustments += 1
        else:
            effective_direction = direction

        if axis == "economic":
            voter_positions[nh]["x"] = max(-10, min(10,
                voter_positions[nh]["x"] + effective_direction * STRENGTH))
        else:
            voter_positions[nh]["y"] = max(-10, min(10,
                voter_positions[nh]["y"] + effective_direction * STRENGTH))

        if bill.status == BillStatus.OPEN_END:
            open_end_count += 1

    # Aggregate: average of all voter positions
    n = len(voter_positions)
    avg_x = sum(v["x"] for v in voter_positions.values()) / n
    avg_y = sum(v["y"] for v in voter_positions.values()) / n

    # Quadrant
    if abs(avg_x) < 0.5 and abs(avg_y) < 0.5:
        quadrant = "center"
    elif avg_x < 0 and avg_y < 0:
        quadrant = "libertarian_left"
    elif avg_x > 0 and avg_y < 0:
        quadrant = "libertarian_right"
    elif avg_x < 0 and avg_y > 0:
        quadrant = "authoritarian_left"
    else:
        quadrant = "authoritarian_right"

    return publish_cplm({
        "x": round(avg_x, 4),
        "y": round(avg_y, 4),
        "quadrant": quadrant,
        "total_voters": n,
        "total_votes": len(rows),
        "open_end_votes": open_end_count,
        "consensus_adjustments": consensus_adjustments,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "trend": {"x_delta": 0.0, "y_delta": 0.0, "direction": "stable"},
    }, verified=True)


def _store_snapshot(snapshot: dict, k: int) -> str:
    return json.dumps({"policy": "publishable-v1", "snapshot": snapshot} if k else snapshot)


def _read_snapshot(raw: str, k: int) -> dict:
    stored = json.loads(raw)
    verified = bool(k and stored.get("policy") == "publishable-v1")
    snapshot = stored["snapshot"] if verified else stored
    if BODY_KEY in snapshot:
        return dict(snapshot, **{BODY_KEY: publish_cplm(snapshot[BODY_KEY], verified=verified)})
    return publish_cplm(snapshot, verified=verified)


async def _fresh_cplm(db):
    return await _get_cplm_cached(db, force=True)


@public_bill_response("aggregate", refresh=_fresh_cplm)
async def get_cplm_cached(db: AsyncSession) -> dict:
    return await _get_cplm_cached(db)


_cplm_flights = SingleFlight()


async def _get_cplm_cached(db: AsyncSession, *, force=False) -> dict:
    async def under_policy(policy):
        return await _cplm_flights.run((policy, force), lambda: _load_cplm(db, force=force, policy=policy))
    return await result_policy.with_result_cache_policy(under_policy)


async def _load_cplm(db, *, force=False, policy):
    """Get CPLM aggregate, using Redis cache if available."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.05, socket_timeout=0.05)
    try:
        await result_policy.result_cache_policy.prepare_redis(r, CACHE_KEY, HISTORY_KEY)
        if policy[0] > 0:
            return await capture_public_bill_body(lambda: compute_cplm(db), db=db)
        k = 0
        cache_key = result_policy.result_cache_policy.key(CACHE_KEY, policy)
        history_key = result_policy.result_cache_policy.key(HISTORY_KEY, policy)
        try:
            cached = await r.get(cache_key)
        except (RedisError, OSError):
            await cache_fill_quota("cplm")
            return await capture_public_bill_body(lambda: compute_cplm(db), db=db)
        if cached and not force:
            return _read_snapshot(cached, k)

        await cache_fill_quota("cplm")
        snapshot = await capture_public_bill_body(lambda: compute_cplm(db), db=db)
        result = snapshot[BODY_KEY]

        # Compute trend from previous snapshot
        try:
            prev = await r.lindex(history_key, 0)
        except (RedisError, OSError):
            return snapshot
        if prev:
            previous = _read_snapshot(prev, k)
            prev_data = await serve_public_bill_body(previous, db=db, schema="aggregate")
        if prev and prev_data and result["x"] is not None and prev_data["x"] is not None:
            # The delta is derived from both populations, including contributors
            # absent from today's votes. Keep their provenance until this body expires.
            for key in (IDS_KEY, RESULTS_IDS_KEY):
                snapshot[key] = sorted(set(snapshot[key]) | set(previous[key]))
            x_delta = result["x"] - prev_data.get("x", 0)
            y_delta = result["y"] - prev_data.get("y", 0)
            if abs(x_delta) > abs(y_delta):
                direction = "right" if x_delta > 0 else "left"
            elif abs(y_delta) > abs(x_delta):
                direction = "up" if y_delta > 0 else "down"
            else:
                direction = "stable"
            result["trend"] = {"x_delta": round(x_delta, 4), "y_delta": round(y_delta, 4), "direction": direction}

        # Push to history (keep last 365 entries)
        try:
            if policy == result_policy.result_cache_policy.current():
                await r.setex(cache_key, CACHE_TTL, _store_snapshot(snapshot, k))
                if policy == result_policy.result_cache_policy.current():
                    await r.lpush(history_key, _store_snapshot(snapshot, k))
                    await r.ltrim(history_key, 0, 364)
                if policy != result_policy.result_cache_policy.current():
                    await r.delete(cache_key)
                    await r.delete(history_key)
        except (RedisError, OSError):
            logger.warning("CPLM cache write unavailable")

        return snapshot

    finally:
        await r.aclose()


@public_bill_response("history")
async def get_cplm_history(days: int = 30, *, db: AsyncSession) -> list[dict]:
    """Get historical CPLM snapshots from Redis."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.05, socket_timeout=0.05)
    try:
        async def under_policy(policy):
            await result_policy.result_cache_policy.prepare_redis(r, CACHE_KEY, HISTORY_KEY)
            # Historical suppression inputs cannot be reconstructed safely.
            if policy[0] > 0:
                return []
            key = result_policy.result_cache_policy.key(HISTORY_KEY, policy)
            try:
                entries = await r.lrange(key, 0, min(days * 4, 364))
            except (RedisError, OSError):
                entries = []
            return [_read_snapshot(e, 0) for e in entries]
        return await result_policy.with_result_cache_policy(under_policy)
    finally:
        await r.aclose()


async def refresh_cplm_cache(db: AsyncSession) -> dict:
    """Force refresh the CPLM cache (called by scheduler)."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.05, socket_timeout=0.05)
    policy = await result_policy.result_cache_policy.prepare_redis(r, CACHE_KEY, HISTORY_KEY)
    await r.delete(result_policy.result_cache_policy.key(CACHE_KEY, policy))
    await r.aclose()
    return await get_cplm_cached(db)

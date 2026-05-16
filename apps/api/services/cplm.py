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
import os

from models import CitizenVote, VoteChoice, ParliamentBill, BillStatus

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CACHE_KEY = "cplm:aggregate:v1"
CACHE_TTL = 3600  # 1 hour
HISTORY_KEY = "cplm:history"

# Liquid Update strength — identical to compass/engine.ts
STRENGTH = 0.05

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
    Compute the aggregate CPLM position from all citizen votes.
    Each voter's position starts at (0, 0) and shifts ±0.05 per vote.
    The societal position is the average of all voter positions.
    """
    from sqlalchemy import text

    # Load all votes with their bills
    result = await db.execute(
        select(CitizenVote, ParliamentBill)
        .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
    )
    rows = result.all()

    if not rows:
        return {
            "x": 0.0, "y": 0.0, "quadrant": "center",
            "total_voters": 0, "total_votes": 0, "open_end_votes": 0,
            "consensus_adjustments": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "trend": {"x_delta": 0.0, "y_delta": 0.0, "direction": "stable"},
        }

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

    return {
        "x": round(avg_x, 4),
        "y": round(avg_y, 4),
        "quadrant": quadrant,
        "total_voters": n,
        "total_votes": len(rows),
        "open_end_votes": open_end_count,
        "consensus_adjustments": consensus_adjustments,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "trend": {"x_delta": 0.0, "y_delta": 0.0, "direction": "stable"},
    }


async def get_cplm_cached(db: AsyncSession) -> dict:
    """Get CPLM aggregate, using Redis cache if available."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    cached = await r.get(CACHE_KEY)
    if cached:
        await r.aclose()
        return json.loads(cached)

    result = await compute_cplm(db)

    # Cache + store history snapshot
    await r.setex(CACHE_KEY, CACHE_TTL, json.dumps(result))

    # Compute trend from previous snapshot
    prev = await r.lindex(HISTORY_KEY, 0)
    if prev:
        prev_data = json.loads(prev)
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
    await r.lpush(HISTORY_KEY, json.dumps(result))
    await r.ltrim(HISTORY_KEY, 0, 364)

    await r.aclose()
    return result


async def get_cplm_history(days: int = 30) -> list[dict]:
    """Get historical CPLM snapshots from Redis."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    entries = await r.lrange(HISTORY_KEY, 0, min(days * 4, 364))  # ~4 snapshots/day
    await r.aclose()
    return [json.loads(e) for e in entries]


async def refresh_cplm_cache(db: AsyncSession) -> dict:
    """Force refresh the CPLM cache (called by scheduler)."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await r.delete(CACHE_KEY)
    await r.aclose()
    return await get_cplm_cached(db)

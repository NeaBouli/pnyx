"""Canonical citizen-action signatures (bill flags and vote-status reads)."""
from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

CITIZEN_ACTION_MAX_SKEW_MS_ENV = "CITIZEN_ACTION_MAX_SKEW_MS"
VOTE_STATUS_REQUIRE_SIGNED_ENV = "VOTE_STATUS_REQUIRE_SIGNED"
DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS = 15 * 60 * 1000
MIN_CITIZEN_ACTION_MAX_SKEW_MS = 60_000
MAX_CITIZEN_ACTION_MAX_SKEW_MS = 3_600_000


def build_flag_payload(bill_id: str, nullifier_hash: str, timestamp_ms: int) -> str:
    """Build the cross-client canonical payload for a signed bill flag."""
    body = json.dumps(
        [bill_id, nullifier_hash, int(timestamp_ms)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"flag:v1:{body}"


def build_vote_status_read_payload(
    bill_id: str,
    nullifier_hash: str,
    timestamp_ms: int,
) -> str:
    """Build the cross-client canonical payload for a signed vote-status read."""
    body = json.dumps(
        [bill_id, nullifier_hash, int(timestamp_ms)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"vote-status-read:v1:{body}"


def citizen_action_max_skew_ms() -> int:
    """Return a bounded freshness window; invalid config falls back safely."""
    raw = os.getenv(
        CITIZEN_ACTION_MAX_SKEW_MS_ENV,
        str(DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS),
    )
    try:
        value = int(raw)
    except ValueError:
        logger.error(
            "Invalid %s=%r; using %dms",
            CITIZEN_ACTION_MAX_SKEW_MS_ENV,
            raw,
            DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS,
        )
        return DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS
    if not MIN_CITIZEN_ACTION_MAX_SKEW_MS <= value <= MAX_CITIZEN_ACTION_MAX_SKEW_MS:
        logger.error(
            "Out-of-range %s=%d; using %dms",
            CITIZEN_ACTION_MAX_SKEW_MS_ENV,
            value,
            DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS,
        )
        return DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS
    return value


def citizen_action_timestamp_is_fresh(
    timestamp_ms: int,
    *,
    now_ms: int | None = None,
) -> bool:
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return abs(current_ms - timestamp_ms) <= citizen_action_max_skew_ms()


def vote_status_require_signed() -> bool:
    """Allow a reversible compatibility window for already released clients."""
    return os.getenv(VOTE_STATUS_REQUIRE_SIGNED_ENV, "").strip().lower() in {
        "1", "true", "yes", "on",
    }

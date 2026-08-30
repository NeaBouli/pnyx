"""Canonical politician-evaluation signatures and aggregate privacy guards."""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Sequence
from typing import Protocol

logger = logging.getLogger(__name__)

EVALUATION_K_ANONYMITY_MIN = 10
EVALUATION_REQUIRE_V2_ENV = "EVALUATION_REQUIRE_V2"
EVALUATION_V2_MAX_SKEW_MS_ENV = "EVALUATION_V2_MAX_SKEW_MS"
DEFAULT_EVALUATION_V2_MAX_SKEW_MS = 15 * 60 * 1000


class EvaluationScore(Protocol):
    question_id: int
    score: int


def canonicalize_evaluation_scores(
    scores: Sequence[EvaluationScore],
) -> list[tuple[int, int]]:
    """Return a stable score order and reject ambiguous duplicate questions."""
    pairs = [(int(item.question_id), int(item.score)) for item in scores]
    question_ids = [question_id for question_id, _ in pairs]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("duplicate question_id")
    return sorted(pairs)


def build_evaluation_v2_payload(
    ada_number: str,
    nullifier_hash: str,
    timestamp_ms: int,
    scores: Sequence[EvaluationScore],
) -> str:
    """Build the cross-client canonical v2 payload bound to every submitted score."""
    pairs = [list(pair) for pair in canonicalize_evaluation_scores(scores)]
    body = json.dumps(
        [ada_number, nullifier_hash, int(timestamp_ms), pairs],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"evaluate:v2:{body}"


def evaluation_v2_required() -> bool:
    """Allow a reversible compatibility window for already released v1 clients."""
    return os.getenv(EVALUATION_REQUIRE_V2_ENV, "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def build_evaluation_read_payload(
    ada_number: str | None,
    nullifier_hash: str,
    timestamp_ms: int,
) -> str:
    """Bind a personal read to its owner, time and target (null means bulk)."""
    body = json.dumps(
        [ada_number, nullifier_hash, timestamp_ms],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"evaluation-read:v1:{body}"


def evaluation_v2_max_skew_ms() -> int:
    """Return a bounded freshness window; invalid config falls back safely."""
    raw = os.getenv(
        EVALUATION_V2_MAX_SKEW_MS_ENV,
        str(DEFAULT_EVALUATION_V2_MAX_SKEW_MS),
    )
    try:
        value = int(raw)
    except ValueError:
        logger.error(
            "Invalid %s=%r; using %dms",
            EVALUATION_V2_MAX_SKEW_MS_ENV,
            raw,
            DEFAULT_EVALUATION_V2_MAX_SKEW_MS,
        )
        return DEFAULT_EVALUATION_V2_MAX_SKEW_MS
    if not 60_000 <= value <= 3_600_000:
        logger.error(
            "Out-of-range %s=%d; using %dms",
            EVALUATION_V2_MAX_SKEW_MS_ENV,
            value,
            DEFAULT_EVALUATION_V2_MAX_SKEW_MS,
        )
        return DEFAULT_EVALUATION_V2_MAX_SKEW_MS
    return value


def evaluation_timestamp_is_fresh(timestamp_ms: int, *, now_ms: int | None = None) -> bool:
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return abs(current_ms - timestamp_ms) <= evaluation_v2_max_skew_ms()


def public_evaluation_average(value: object, evaluator_count: int) -> float | None:
    """Suppress score values until the project-wide k-anonymity threshold is met."""
    if value is None or evaluator_count < EVALUATION_K_ANONYMITY_MIN:
        return None
    return float(value)

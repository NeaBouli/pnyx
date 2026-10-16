"""Public individual-vote cells (ADR-007 S2); never apply to private reads.

Zero is a small cell too. Secondary suppression hides the entire choice or
source partition, so a published total cannot recover one hidden member.
"""
import logging
import os
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def small_cell_k() -> int:
    """Unset/zero disables suppression; malformed/negative values warn safely."""
    raw = os.getenv("PUBLIC_RESULTS_MIN_COUNT")
    if raw is None:
        return 0
    try:
        value = int(raw)
        if value >= 0:
            return value
    except ValueError:
        pass
    logger.warning("Invalid PUBLIC_RESULTS_MIN_COUNT; public results suppression disabled")
    return 0


def suppress_cell(count: int, *, k: int | None = None) -> dict:
    """Publish an isolated count as null plus a flag when below the threshold."""
    threshold = small_cell_k() if k is None else k
    suppressed = threshold > 0 and count < threshold
    return {"count": None if suppressed else count, "suppressed": suppressed}


def choices_suppressed(counts: Iterable[int], *, k: int | None = None) -> bool:
    threshold = small_cell_k() if k is None else k
    return threshold > 0 and any(count < threshold for count in counts)


def suppress_public_cells(
    payload: dict,
    *,
    choices: tuple[str, ...],
    total: str,
    percentages: tuple[str, ...] = (),
    partitions: tuple[str, ...] = (),
    derived: tuple[str, ...] = (),
    k: int | None = None,
) -> dict:
    """Preserve keys; suppress choices, derived shares and source partitions.

    With the flag off return the legacy payload unchanged. With it on add
    ``suppressed`` and ``suppression_k``. A null may be secondary suppression,
    so it does not necessarily mean that particular cell has fewer than k.
    """
    threshold = small_cell_k() if k is None else k
    if threshold == 0:
        return payload
    result = dict(payload)
    hide_choices = choices_suppressed((payload[key] for key in choices), k=threshold)
    hide_partitions = choices_suppressed((payload[key] for key in partitions), k=threshold)
    hide_total = payload[total] < threshold
    if hide_choices:
        for key in (*choices, *percentages, *derived):
            result[key] = None
    if hide_partitions:
        for key in partitions:
            result[key] = None
    if hide_total:
        result[total] = None
    result.update(suppressed=hide_choices or hide_partitions or hide_total,
                  suppression_k=threshold)
    return result


def suppress_public_series(rows: list[dict], *, choices: tuple[str, ...], total: str) -> list[dict]:
    """Suppress complementary buckets as well as cells within each bucket.

    If any bucket has hidden choices/totals, hide that partition throughout
    the series: bill totals minus other days must not reveal a small day.
    """
    threshold = small_cell_k()
    if threshold == 0 or not rows:
        return rows
    hide_choices = any(choices_suppressed((r[c] for c in choices), k=threshold) for r in rows)
    hide_totals = any(r[total] < threshold for r in rows)
    published = []
    for row in rows:
        result = suppress_public_cells(row, choices=choices, total=total, k=threshold)
        if hide_choices:
            result.update({key: None for key in choices})
        if hide_totals:
            result[total] = None
        result["suppressed"] = hide_choices or hide_totals
        published.append(result)
    return published

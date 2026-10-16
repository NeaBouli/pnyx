"""Public individual-vote cells (ADR-007 S2); never apply to private reads.

Zero is a small cell too. One publishable set governs all public bill results
and their derivatives; suppression withholds the entire bill population.
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


def publishable_set(bills: dict, *, k: int | None = None) -> set:
    """One release decision for every consumer.

    Values contain (combined choices, separately observable source choices).
    Absent sources are omitted; every choice (including zero) in a present
    source must reach k. Callers must supply complete source partitions.
    """
    threshold = small_cell_k() if k is None else k
    return {bill_id for bill_id, (combined, sources) in bills.items()
            if not threshold or all(count >= threshold
                                    for cells in (combined, *sources) for count in cells)}


def suppress_public_cells(
    payload: dict,
    *,
    choices: tuple[str, ...],
    total: str,
    percentages: tuple[str, ...] = (),
    partitions: tuple[str, ...] = (),
    derived: tuple[str, ...] = (),
    public_source_total: int = 0,
    publishable: bool | None = None,
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
    if publishable is None:
        cells = tuple(payload[key] for key in choices) or (payload[total],)
        sources = tuple((payload[key],) for key in partitions if payload[key])
        # A mixed source total cannot establish per-choice safety. Real bill
        # callers pass the decision made with the complete source counts.
        source_total = public_source_total or payload.get("zk_total", payload.get("zk_vote_count", 0)) or 0
        if source_total and source_total != payload[total]:
            sources += ((0,),)
        publishable = bool(publishable_set({0: (cells, sources)}, k=threshold))
    if not publishable:
        for key in (*choices, *percentages, *partitions, *derived, total):
            result[key] = None
    result.update(suppressed=not publishable, suppression_k=threshold)
    return result


def suppress_public_series(rows: list[dict], *, choices: tuple[str, ...], total: str,
                           all_time_rows: list[dict] | None = None) -> list[dict]:
    """Suppress complementary buckets as well as cells within each bucket.

    If any bucket has hidden choices/totals, hide that partition throughout
    the series: bill totals minus other days must not reveal a small day.
    """
    threshold = small_cell_k()
    if threshold == 0 or not rows:
        return rows
    # Use the same all-time daily partition for every requested window. This
    # also protects differences between successive/overlapping window queries.
    partition = rows if all_time_rows is None else all_time_rows
    hide_choices = any(choices_suppressed((r[c] for c in choices), k=threshold) for r in partition)
    hide_totals = hide_choices or any(r[total] < threshold for r in partition)
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

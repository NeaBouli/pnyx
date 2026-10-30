"""One DB visibility/results snapshot and private cache decision inputs."""
from contextvars import ContextVar
from dataclasses import dataclass, field

from sqlalchemy import case, func, select, true

from models import CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from services.bill_visibility import public_bill_filter, results_visible_filter
from services.small_cell import publishable_set, small_cell_k


@dataclass
class BillVisibilitySnapshot:
    listed: frozenset[str]
    results: frozenset[str]
    contributors: set[str] = field(default_factory=set)
    result_inputs: dict[str, "BillResultInputs"] = field(default_factory=dict)


@dataclass(frozen=True)
class BillResultInputs:
    """Counts include four choices, both source totals and the release decision."""
    k: int
    status: str
    results_visibility: str | None
    counts: tuple[int, int, int, int, int, int, bool]


building_snapshot = ContextVar("public_bill_snapshot", default=None)


async def read_visibility_snapshot(db):
    """A single statement, scalar columns only; Redis and ORM state cannot authorize.

    With suppression disabled this is just an ID/visibility scan. With it enabled,
    group each source once to make the same complete-choice release decision as
    the public vote helpers. Always read from DB (visibility TTL is zero).
    """
    k = small_cell_k()
    query = select(ParliamentBill.id, results_visible_filter().label("results_visible")).where(public_bill_filter())
    if k:
        sources = []
        for model, key, choice in (
            (CitizenVote, CitizenVote.bill_id, CitizenVote.vote),
            (ZkVoteReceipt, ZkVoteReceipt.vote_scope_id, ZkVoteReceipt.vote_commitment),
        ):
            counts = select(key.label("bill_key"), *(
                func.count().filter(choice == value).label(value.value.lower()) for value in VoteChoice
            )).group_by(key).subquery()
            join_key = ParliamentBill.id if model is CitizenVote else "bill:" + ParliamentBill.id
            query = query.outerjoin(counts, counts.c.bill_key == join_key)
            sources.append(counts)
        for index, counts in enumerate(sources):
            for value in VoteChoice:
                count = func.coalesce(counts.c[value.value.lower()], 0)
                if index:
                    count = case((func.coalesce(ParliamentBill.source, "PARLIAMENT") == "PARLIAMENT", count), else_=0)
                query = query.add_columns(count)
        query = query.add_columns(ParliamentBill.status, ParliamentBill.results_visibility)
    listed, results, result_inputs = set(), set(), {}
    for row in (await db.execute(query)).all():
        bill_id, visible, *counts = row
        listed.add(bill_id)
        if k:
            tier, zk = tuple(counts[:4]), tuple(counts[4:8])
            combined = tuple(a + b for a, b in zip(tier, zk))
            publishable = bool(publishable_set({bill_id: (combined, tuple(c for c in (tier, zk) if sum(c)))}, k=k))
            status, visibility = counts[8:]
            result_inputs[bill_id] = BillResultInputs(
                k, status.value, visibility, (*combined, sum(tier), sum(zk), publishable),
            )
        if visible and (not k or publishable):
            results.add(bill_id)
    return BillVisibilitySnapshot(frozenset(listed), frozenset(results), result_inputs=result_inputs)


def snapshot_bill_filter(column=ParliamentBill.id, *, results=False):
    snapshot = building_snapshot.get()
    return column.in_(snapshot.results if results else snapshot.listed) if snapshot is not None else true()


def snapshot_raw_filter(alias, *, results=False):
    if not alias.replace("_", "").isalnum():
        raise ValueError("SQL alias must be an identifier")
    snapshot = building_snapshot.get()
    if snapshot is None:
        return "1 = 1", {}
    ids = sorted(snapshot.results if results else snapshot.listed)
    params = {f"snapshot_{alias}_{i}": bill_id for i, bill_id in enumerate(ids)}
    return (f"{alias}.id IN (" + ", ".join(f":{key}" for key in params) + ")" if params else "1 = 0", params)


def record_result_contributors(ids):
    snapshot = building_snapshot.get()
    if snapshot is not None:
        ids = set(ids)
        if ids - snapshot.results:
            raise ValueError("Vote contributor outside the captured visibility snapshot")
        snapshot.contributors.update(ids)

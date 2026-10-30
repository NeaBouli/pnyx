"""One DB visibility/results snapshot and private cache decision inputs."""
from contextvars import ContextVar
from dataclasses import dataclass, field

from sqlalchemy import case, func, select, true, union_all

from models import CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from services.bill_visibility import public_bill_filter, results_visible_filter
from services.small_cell import publishable_set, small_cell_k
from services.bill_id_set import bill_ids_filter, raw_bill_ids_filter


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


def vote_bearing_bill_ids():
    return union_all(
        select(CitizenVote.bill_id),
        select(func.substr(ZkVoteReceipt.vote_scope_id, 6)).where(
            ZkVoteReceipt.vote_scope_id.like("bill:%"),
            ZkVoteReceipt.vote_commitment.in_([choice.value for choice in VoteChoice]),
        ),
    )


def visibility_snapshot_query(*, candidates=None, k=0):
    """Read indexed visibility metadata, restricting each vote source before grouping."""
    population = select(
        ParliamentBill.id, results_visible_filter().label("results_visible"),
        ParliamentBill.source, ParliamentBill.status, ParliamentBill.results_visibility,
    ).where(public_bill_filter())
    if candidates is not None:
        population = population.where(bill_ids_filter(ParliamentBill.id, candidates))
    if not k:
        return population.with_only_columns(
            ParliamentBill.id, results_visible_filter().label("results_visible"),
        ).order_by(ParliamentBill.id)
    visible = population.order_by(ParliamentBill.id).cte("visible_candidates").prefix_with(
        "MATERIALIZED", dialect="postgresql",
    )
    query = select(visible.c.id, visible.c.results_visible)
    if k:
        sources = []
        for model, key, choice in (
            (CitizenVote, CitizenVote.bill_id, CitizenVote.vote),
            (ZkVoteReceipt, ZkVoteReceipt.vote_scope_id, ZkVoteReceipt.vote_commitment),
        ):
            keys = select(visible.c.id) if model is CitizenVote else select("bill:" + visible.c.id).where(
                func.coalesce(visible.c.source, "PARLIAMENT") == "PARLIAMENT",
            )
            counts = select(key.label("bill_key"), *(
                func.count().filter(choice == value).label(value.value.lower()) for value in VoteChoice
            )).where(key.in_(keys)).group_by(key).subquery()
            join_key = visible.c.id if model is CitizenVote else "bill:" + visible.c.id
            query = query.outerjoin(counts, counts.c.bill_key == join_key)
            sources.append(counts)
        for index, counts in enumerate(sources):
            for value in VoteChoice:
                count = func.coalesce(counts.c[value.value.lower()], 0)
                if index:
                    count = case((func.coalesce(visible.c.source, "PARLIAMENT") == "PARLIAMENT", count), else_=0)
                query = query.add_columns(count)
        query = query.add_columns(visible.c.status, visible.c.results_visibility)
    return query


async def read_visibility_snapshot(db, *, candidates=None):
    """One scalar DB statement; Redis and ORM state cannot authorize a body."""
    k = small_cell_k()
    query = visibility_snapshot_query(candidates=candidates, k=k)
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
    return bill_ids_filter(column, snapshot.results if results else snapshot.listed) if snapshot is not None else true()


def snapshot_raw_filter(alias, *, results=False, db=None):
    if not alias.replace("_", "").isalnum():
        raise ValueError("SQL alias must be an identifier")
    snapshot = building_snapshot.get()
    if snapshot is None:
        return "1 = 1", {}
    return raw_bill_ids_filter(
        f"{alias}.id", snapshot.results if results else snapshot.listed,
        name=f"snapshot_{alias}_ids", db=db,
    )


def record_result_contributors(ids):
    snapshot = building_snapshot.get()
    if snapshot is not None:
        ids = set(ids)
        if ids - snapshot.results:
            raise ValueError("Vote contributor outside the captured visibility snapshot")
        snapshot.contributors.update(ids)

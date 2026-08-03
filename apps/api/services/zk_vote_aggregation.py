"""Public vote aggregation helpers for Tier-1 and Semaphore ZK receipts."""
from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime

from sqlalchemy import DateTime, String, cast, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from models import CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from services.bill_visibility import public_bill_filter
from services.zk_tier_lock import VoteScopeType, canonical_vote_scope_id


@dataclass(frozen=True)
class VoteTotals:
    yes: int
    no: int
    abstain: int
    unknown: int
    tier1_total: int
    zk_total: int

    @property
    def total(self) -> int:
        return self.yes + self.no + self.abstain + self.unknown


def include_zk_for_bill(bill: ParliamentBill) -> bool:
    """ZK receipts are currently defined only for Parliament bill scopes."""
    return (getattr(bill, "source", None) or "PARLIAMENT") == "PARLIAMENT"


def bill_vote_events_query(
    bill_id: str,
    *,
    include_zk: bool,
):
    """Return a UNION subquery for aggregate timelines without identity data."""
    tier1 = select(
        cast(CitizenVote.created_at, DateTime(timezone=False)).label("created_at"),
        cast(CitizenVote.vote, String).label("vote"),
    ).where(CitizenVote.bill_id == bill_id)
    if not include_zk:
        return tier1.subquery("bill_vote_events")

    scope = canonical_vote_scope_id(VoteScopeType.BILL, bill_id)
    zk = select(
        cast(ZkVoteReceipt.created_at, DateTime(timezone=False)).label("created_at"),
        ZkVoteReceipt.vote_commitment.label("vote"),
    ).where(
        ZkVoteReceipt.vote_scope_id == scope,
        ZkVoteReceipt.vote_commitment.in_([choice.value for choice in VoteChoice]),
    )
    return union_all(tier1, zk).subquery("bill_vote_events")


async def aggregate_bill_vote_totals(
    db: AsyncSession,
    bill_id: str,
    *,
    include_zk: bool,
) -> VoteTotals:
    tier_counts = await _count_tier1_votes(db, bill_id)
    zk_counts = await _count_zk_votes(db, bill_id) if include_zk else _empty_counts()
    return VoteTotals(
        yes=tier_counts[VoteChoice.YES] + zk_counts[VoteChoice.YES],
        no=tier_counts[VoteChoice.NO] + zk_counts[VoteChoice.NO],
        abstain=tier_counts[VoteChoice.ABSTAIN] + zk_counts[VoteChoice.ABSTAIN],
        unknown=tier_counts[VoteChoice.UNKNOWN] + zk_counts[VoteChoice.UNKNOWN],
        tier1_total=sum(tier_counts.values()),
        zk_total=sum(zk_counts.values()),
    )


async def count_public_votes(
    db: AsyncSession,
    *,
    since: datetime | None = None,
) -> int:
    """Count public Tier-1 and ZK votes with identical bill visibility rules."""
    tier1_query = (
        select(func.count(CitizenVote.id))
        .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
        .where(public_bill_filter(), ~CitizenVote.bill_id.like("DEMO-%"))
    )
    if since is not None:
        tier1_query = tier1_query.where(CitizenVote.created_at >= since)
    tier1_total = int(await db.scalar(tier1_query) or 0)

    zk_query = (
        select(func.count(ZkVoteReceipt.id))
        .join(
            ParliamentBill,
            ZkVoteReceipt.vote_scope_id == func.concat("bill:", ParliamentBill.id),
        )
        .where(
            public_bill_filter(),
            ParliamentBill.source == "PARLIAMENT",
            ~ParliamentBill.id.like("DEMO-%"),
            ZkVoteReceipt.vote_commitment.in_([choice.value for choice in VoteChoice]),
        )
    )
    if since is not None:
        zk_query = zk_query.where(ZkVoteReceipt.created_at >= since)
    zk_total = int(await db.scalar(zk_query) or 0)
    return tier1_total + zk_total


async def _count_tier1_votes(db: AsyncSession, bill_id: str) -> dict[VoteChoice, int]:
    result = await db.execute(
        select(CitizenVote.vote, func.count(CitizenVote.id))
        .where(CitizenVote.bill_id == bill_id)
        .group_by(CitizenVote.vote)
    )
    counts = _empty_counts()
    for vote, count in result.all():
        counts[VoteChoice(vote)] = int(count or 0)
    return counts


async def _count_zk_votes(db: AsyncSession, bill_id: str) -> dict[VoteChoice, int]:
    scope = canonical_vote_scope_id(VoteScopeType.BILL, bill_id)
    result = await db.execute(
        select(ZkVoteReceipt.vote_commitment, func.count(ZkVoteReceipt.id))
        .where(
            ZkVoteReceipt.vote_scope_id == scope,
            ZkVoteReceipt.vote_commitment.in_([choice.value for choice in VoteChoice]),
        )
        .group_by(ZkVoteReceipt.vote_commitment)
    )
    counts = _empty_counts()
    for vote_commitment, count in result.all():
        counts[VoteChoice(str(vote_commitment).upper())] = int(count or 0)
    return counts


def _empty_counts() -> dict[VoteChoice, int]:
    return {choice: 0 for choice in VoteChoice}

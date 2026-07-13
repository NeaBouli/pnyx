"""Public vote aggregation helpers for Tier-1 and Semaphore ZK receipts."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CitizenVote, VoteChoice, ZkVoteReceipt
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

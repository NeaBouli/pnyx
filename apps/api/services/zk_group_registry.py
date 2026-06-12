"""Scoped Semaphore group registry helpers for GH#112.

These helpers prepare per-scope group construction without computing a Merkle
root. Root construction must stay Semaphore-compatible and must not use a
placeholder hash.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ZkIdentityCommitment
from services.zk_merkle_root import SemaphoreGroupRoot, build_semaphore_group_root

VOTE_SCOPE_ID_RE = re.compile(r"^(bill|municipal|regional):[A-Za-z0-9._-]{1,110}$")


def validate_vote_scope_id(vote_scope_id: str) -> str:
    clean = vote_scope_id.strip()
    if not VOTE_SCOPE_ID_RE.fullmatch(clean):
        raise ValueError("invalid vote_scope_id")
    return clean


async def list_active_commitments_for_scope(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    limit: int = 5000,
) -> list[str]:
    scope = validate_vote_scope_id(vote_scope_id)
    if limit < 1 or limit > 5000:
        raise ValueError("limit must be between 1 and 5000")

    result = await db.execute(
        select(ZkIdentityCommitment.commitment)
        .where(
            ZkIdentityCommitment.vote_scope_id == scope,
            ZkIdentityCommitment.status == "ACTIVE",
        )
        .order_by(ZkIdentityCommitment.id)
        .limit(limit)
    )
    return [str(value) for value in result.scalars().all()]


async def count_active_commitments_for_scope(
    db: AsyncSession,
    *,
    vote_scope_id: str,
) -> int:
    scope = validate_vote_scope_id(vote_scope_id)
    result = await db.execute(
        select(func.count(ZkIdentityCommitment.id)).where(
            ZkIdentityCommitment.vote_scope_id == scope,
            ZkIdentityCommitment.status == "ACTIVE",
        )
    )
    return int(result.scalar_one())


async def build_active_group_root_for_scope(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    limit: int = 5000,
) -> SemaphoreGroupRoot:
    commitments = await list_active_commitments_for_scope(
        db,
        vote_scope_id=vote_scope_id,
        limit=limit,
    )
    return build_semaphore_group_root(commitments)

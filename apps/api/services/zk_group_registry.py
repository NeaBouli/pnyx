"""Scoped Semaphore group registry helpers for GH#112.

These helpers prepare per-scope group construction without computing a Merkle
root. Root construction must stay Semaphore-compatible and must not use a
placeholder hash.
"""
from __future__ import annotations

import hashlib
import re
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ZkIdentityCommitment
from services.zk_merkle_root import FIELD_MODULUS, SemaphoreGroupRoot, build_semaphore_group_root

VOTE_SCOPE_ID_RE = re.compile(r"^(bill|municipal|regional):[A-Za-z0-9._-]{1,110}$")
ZK_GROUP_MIN_PUBLIC_MEMBERS = 2
ZK_GROUP_PADDING_DOMAIN = b"ekklesia.zk.group.padding.v1:"


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


async def list_public_group_members_for_scope(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    limit: int = 5000,
) -> list[str]:
    """Return public members used for root/proof generation.

    The native Mopro/Semaphore prover has been verified with 2+ member groups.
    A singleton canary group stalled on S10, so we pad sparse public groups with
    deterministic dummy field elements. These dummy members are public and carry
    no identity, phone, nullifier, or tier-lock data.
    """
    commitments = await list_active_commitments_for_scope(
        db,
        vote_scope_id=vote_scope_id,
        limit=limit,
    )
    return public_group_members_for_root(commitments)


def public_group_members_for_root(commitments: Sequence[str]) -> list[str]:
    members = [str(value) for value in commitments]
    used = set(members)
    nonce = 0
    while len(members) < ZK_GROUP_MIN_PUBLIC_MEMBERS:
        candidate = str(_padding_member(nonce))
        nonce += 1
        if candidate in used:
            continue
        members.append(candidate)
        used.add(candidate)
    return members


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
    commitments = await list_public_group_members_for_scope(
        db,
        vote_scope_id=vote_scope_id,
        limit=limit,
    )
    return build_semaphore_group_root(commitments)


def _padding_member(nonce: int) -> int:
    digest = hashlib.sha256(ZK_GROUP_PADDING_DOMAIN + str(nonce).encode("ascii")).digest()
    return int.from_bytes(digest, "big") % FIELD_MODULUS

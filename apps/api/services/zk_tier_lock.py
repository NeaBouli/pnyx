"""Private cross-tier lock helpers for GH#112 Gate 3.

The tier_guard_hash prevents a citizen from using Tier 1 and Tier 2 for the
same voting scope. It is server-private and must never be published.
"""
from __future__ import annotations

import hashlib
import hmac
from enum import Enum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import ZkVoteTierLock


class VoteScopeType(str, Enum):
    BILL = "bill"
    MUNICIPAL = "municipal"
    REGIONAL = "regional"


def canonical_vote_scope_id(scope_type: VoteScopeType | str, object_id: str) -> str:
    scope = VoteScopeType(scope_type)
    clean_id = object_id.strip()
    if not clean_id:
        raise ValueError("vote scope object_id is required")
    return f"{scope.value}:{clean_id}"


def derive_tier_guard_hash(
    *,
    server_salt: str,
    vote_scope_id: str,
    tier1_nullifier_hash: str,
) -> str:
    if len(server_salt) < 32:
        raise ValueError("SERVER_SALT must be at least 32 characters")
    if not vote_scope_id:
        raise ValueError("vote_scope_id is required")
    if len(tier1_nullifier_hash) != 64:
        raise ValueError("tier1_nullifier_hash must be a 64-character hex digest")

    payload = f"ekklesia:vote-tier-lock:v1:{vote_scope_id}:{tier1_nullifier_hash}"
    return hmac.new(
        server_salt.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def tier_lock_exists(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    tier_guard_hash: str,
) -> bool:
    result = await db.execute(
        select(ZkVoteTierLock.id).where(
            ZkVoteTierLock.vote_scope_id == vote_scope_id,
            ZkVoteTierLock.tier_guard_hash == tier_guard_hash,
        )
    )
    return result.scalar_one_or_none() is not None


async def create_tier_lock(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    tier_guard_hash: str,
) -> ZkVoteTierLock:
    """Create a private tier lock inside the caller transaction.

    On IntegrityError the session is rolled back and the error is re-raised.
    Callers must treat that path as terminal for the current write attempt.
    """
    lock = ZkVoteTierLock(
        vote_scope_id=vote_scope_id,
        tier_guard_hash=tier_guard_hash,
    )
    db.add(lock)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise
    return lock


def public_zk_receipt_forbidden_fields() -> set[str]:
    return {
        "tier_guard_hash",
        "tier1_nullifier_hash",
        "identity_record_id",
        "phone_number",
        "ip_address",
        "hlr_metadata",
        "public_key_hex",
        "semaphore_identity_secret",
    }

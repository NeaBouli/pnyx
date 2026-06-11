"""GH#112 Gate 3 private tier-lock helper tests."""
import pytest
from sqlalchemy.exc import IntegrityError

from services.zk_tier_lock import (
    VoteScopeType,
    canonical_vote_scope_id,
    create_tier_lock,
    derive_tier_guard_hash,
    public_zk_receipt_forbidden_fields,
    tier1_vote_blocked_by_zk_lock,
    tier_lock_exists,
)


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, scalar_value=None, flush_error=None):
        self.scalar_value = scalar_value
        self.flush_error = flush_error
        self.added = []
        self.executed = []
        self.flushed = False
        self.rolled_back = False

    async def execute(self, statement):
        self.executed.append(statement)
        return _FakeScalarResult(self.scalar_value)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True
        if self.flush_error:
            raise self.flush_error

    async def rollback(self):
        self.rolled_back = True


def test_canonical_vote_scope_id_is_stable() -> None:
    assert canonical_vote_scope_id(VoteScopeType.BILL, "GR-0490a766") == "bill:GR-0490a766"
    assert canonical_vote_scope_id("municipal", "ATH-001") == "municipal:ATH-001"
    assert canonical_vote_scope_id(VoteScopeType.REGIONAL, "REG.006") == "regional:REG.006"


def test_canonical_vote_scope_id_rejects_empty_object_id() -> None:
    with pytest.raises(ValueError):
        canonical_vote_scope_id("bill", "  ")


def test_canonical_vote_scope_id_rejects_invalid_object_id_chars() -> None:
    with pytest.raises(ValueError):
        canonical_vote_scope_id("bill", "GR-1/bad")

    with pytest.raises(ValueError):
        canonical_vote_scope_id("bill", "GR-1:bad")


def test_tier_guard_hash_is_deterministic_and_scope_bound() -> None:
    salt = "s" * 64
    nullifier = "a" * 64

    bill_scope = canonical_vote_scope_id("bill", "GR-0490a766")
    other_scope = canonical_vote_scope_id("bill", "GR-5294")

    first = derive_tier_guard_hash(
        server_salt=salt,
        vote_scope_id=bill_scope,
        tier1_nullifier_hash=nullifier,
    )
    second = derive_tier_guard_hash(
        server_salt=salt,
        vote_scope_id=bill_scope,
        tier1_nullifier_hash=nullifier,
    )
    other = derive_tier_guard_hash(
        server_salt=salt,
        vote_scope_id=other_scope,
        tier1_nullifier_hash=nullifier,
    )

    assert first == second
    assert first != other
    assert len(first) == 64


def test_tier_guard_hash_rejects_weak_inputs() -> None:
    with pytest.raises(ValueError):
        derive_tier_guard_hash(server_salt="short", vote_scope_id="bill:GR-1", tier1_nullifier_hash="a" * 64)

    with pytest.raises(ValueError):
        derive_tier_guard_hash(server_salt="s" * 64, vote_scope_id="", tier1_nullifier_hash="a" * 64)

    with pytest.raises(ValueError):
        derive_tier_guard_hash(server_salt="s" * 64, vote_scope_id="bill:GR-1", tier1_nullifier_hash="bad")


def test_public_zk_receipt_forbidden_fields_cover_identity_bridge() -> None:
    forbidden = public_zk_receipt_forbidden_fields()

    assert "tier_guard_hash" in forbidden
    assert "tier1_nullifier_hash" in forbidden
    assert "identity_record_id" in forbidden
    assert "semaphore_identity_secret" in forbidden


@pytest.mark.asyncio
async def test_tier_lock_exists_returns_true_when_lock_id_found() -> None:
    db = _FakeDb(scalar_value=123)

    assert await tier_lock_exists(db, vote_scope_id="bill:GR-1", tier_guard_hash="a" * 64) is True
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_tier_lock_exists_returns_false_when_missing() -> None:
    db = _FakeDb(scalar_value=None)

    assert await tier_lock_exists(db, vote_scope_id="bill:GR-1", tier_guard_hash="a" * 64) is False


@pytest.mark.asyncio
async def test_create_tier_lock_adds_and_flushes_lock() -> None:
    db = _FakeDb()

    lock = await create_tier_lock(db, vote_scope_id="bill:GR-1", tier_guard_hash="a" * 64)

    assert lock.vote_scope_id == "bill:GR-1"
    assert lock.tier_guard_hash == "a" * 64
    assert db.added == [lock]
    assert db.flushed is True
    assert db.rolled_back is False


@pytest.mark.asyncio
async def test_create_tier_lock_rolls_back_on_duplicate() -> None:
    error = IntegrityError("statement", {}, Exception("duplicate"))
    db = _FakeDb(flush_error=error)

    with pytest.raises(IntegrityError):
        await create_tier_lock(db, vote_scope_id="bill:GR-1", tier_guard_hash="a" * 64)

    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_tier1_vote_blocked_by_zk_lock_uses_derived_guard_hash() -> None:
    db = _FakeDb(scalar_value=123)
    salt = "s" * 64
    nullifier = "a" * 64
    scope = canonical_vote_scope_id("bill", "GR-0490a766")

    blocked = await tier1_vote_blocked_by_zk_lock(
        db,
        server_salt=salt,
        vote_scope_id=scope,
        tier1_nullifier_hash=nullifier,
    )

    assert blocked is True
    statement = str(db.executed[0])
    assert "zk_vote_tier_locks" in statement


@pytest.mark.asyncio
async def test_tier1_vote_not_blocked_when_no_matching_lock_exists() -> None:
    db = _FakeDb(scalar_value=None)

    blocked = await tier1_vote_blocked_by_zk_lock(
        db,
        server_salt="s" * 64,
        vote_scope_id=canonical_vote_scope_id("bill", "GR-0490a766"),
        tier1_nullifier_hash="a" * 64,
    )

    assert blocked is False


@pytest.mark.asyncio
async def test_tier1_guard_hash_remains_scope_bound_for_block_checks() -> None:
    salt = "s" * 64
    nullifier = "a" * 64
    first_scope = canonical_vote_scope_id("bill", "GR-0490a766")
    second_scope = canonical_vote_scope_id("bill", "GR-5294")

    first_guard = derive_tier_guard_hash(
        server_salt=salt,
        vote_scope_id=first_scope,
        tier1_nullifier_hash=nullifier,
    )
    second_guard = derive_tier_guard_hash(
        server_salt=salt,
        vote_scope_id=second_scope,
        tier1_nullifier_hash=nullifier,
    )

    assert first_guard != second_guard

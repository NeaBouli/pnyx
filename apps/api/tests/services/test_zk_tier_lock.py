"""GH#112 Gate 3 private tier-lock helper tests."""
import pytest

from services.zk_tier_lock import (
    VoteScopeType,
    canonical_vote_scope_id,
    derive_tier_guard_hash,
    public_zk_receipt_forbidden_fields,
)


def test_canonical_vote_scope_id_is_stable() -> None:
    assert canonical_vote_scope_id(VoteScopeType.BILL, "GR-0490a766") == "bill:GR-0490a766"
    assert canonical_vote_scope_id("municipal", "ATH-001") == "municipal:ATH-001"


def test_canonical_vote_scope_id_rejects_empty_object_id() -> None:
    with pytest.raises(ValueError):
        canonical_vote_scope_id("bill", "  ")


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

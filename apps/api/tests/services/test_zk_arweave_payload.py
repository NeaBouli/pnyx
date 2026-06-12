"""GH#112 Gate 5 public ZK Arweave payload tests."""
from types import SimpleNamespace

import pytest

from services.zk_arweave_payload import (
    ZK_ARWEAVE_RECORD_VERSION,
    ZK_PUBLIC_RECEIPT_VERSION,
    build_public_zk_receipt_from_storage,
    build_zk_vote_arweave_record,
)
from services.zk_tier_lock import public_zk_receipt_forbidden_fields


def _record(**overrides):
    base = {
        "vote_scope_id": "bill:GR-0490a766",
        "bill_id": "GR-0490a766",
        "vote_commitment": "commitment:yes:example",
        "semaphore_nullifier": "123",
        "merkle_root": "456",
        "merkle_depth": 16,
        "proof_public": {
            "merkleTreeDepth": 16,
            "merkleTreeRoot": "456",
            "nullifier": "123",
            "message": "789",
            "scope": "101112",
            "points": ["1", "2", "3", "4", "5", "6", "7", "8"],
        },
        "verifier_version": "py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        "circuit_version": "semaphore-v4-depth16",
        "group_size": 25,
        "publication_bucket": "2026-06-11T12",
    }
    base.update(overrides)
    return build_zk_vote_arweave_record(**base)


def test_zk_arweave_record_contains_only_public_verifier_payload() -> None:
    record = _record()

    assert record["schema"] == ZK_ARWEAVE_RECORD_VERSION
    assert record["vote_scope_id"] == "bill:GR-0490a766"
    assert record["proof_public"]["points"] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert record["publication_bucket"] == "2026-06-11T12"

    serialized = str(record)
    for forbidden in public_zk_receipt_forbidden_fields():
        assert forbidden not in serialized


def test_zk_arweave_record_rejects_nested_identity_bridge_fields() -> None:
    with pytest.raises(ValueError):
        _record(proof_public={"message": "1", "identity_record_id": 42})


def test_public_zk_receipt_from_storage_excludes_identity_bridge_fields() -> None:
    receipt = SimpleNamespace(
        vote_scope_id="bill:GR-0490a766",
        vote_commitment="commitment:yes:example",
        semaphore_nullifier="123",
        merkle_root="456",
        merkle_depth=16,
        signal_hash="789",
        external_nullifier="101112",
        proof_public_json={"proof": {"pi_a": ["1", "2"]}},
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        circuit_version="semaphore-v4-depth16",
        arweave_tx_id=None,
        arweave_pending=True,
        publication_bucket="2026-06-12T00",
        tier_guard_hash="private",
        tier1_nullifier_hash="private",
        identity_record_id=1,
    )

    payload = build_public_zk_receipt_from_storage(receipt)

    assert payload["schema"] == ZK_PUBLIC_RECEIPT_VERSION
    assert payload["vote_scope_id"] == "bill:GR-0490a766"
    assert payload["vote_commitment"] == "commitment:yes:example"
    assert payload["arweave_pending"] is True
    assert payload["arweave_tx_id"] is None

    serialized = str(payload)
    for forbidden in public_zk_receipt_forbidden_fields():
        assert forbidden not in serialized


def test_public_zk_receipt_from_storage_rejects_nested_private_fields() -> None:
    receipt = SimpleNamespace(
        vote_scope_id="bill:GR-0490a766",
        vote_commitment="commitment:yes:example",
        semaphore_nullifier="123",
        merkle_root="456",
        merkle_depth=16,
        signal_hash="789",
        external_nullifier="101112",
        proof_public_json={"tier_guard_hash": "private"},
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        circuit_version="semaphore-v4-depth16",
        arweave_tx_id=None,
        arweave_pending=True,
        publication_bucket="2026-06-12T00",
    )

    with pytest.raises(ValueError):
        build_public_zk_receipt_from_storage(receipt)

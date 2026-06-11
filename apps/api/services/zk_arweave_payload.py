"""Public Arweave payload builder for GH#112 Gate 5.

This module builds only the public verifier record shape. It does not publish
to Arweave and it must never receive or emit identity bridge fields.
"""
from __future__ import annotations

from typing import Any, Mapping

from services.zk_tier_lock import public_zk_receipt_forbidden_fields

ZK_ARWEAVE_RECORD_VERSION = "ekklesia.zk_vote.v1"


def build_zk_vote_arweave_record(
    *,
    vote_scope_id: str,
    bill_id: str,
    vote_commitment: str,
    semaphore_nullifier: str,
    merkle_root: str,
    merkle_depth: int,
    proof_public: Mapping[str, Any],
    verifier_version: str,
    circuit_version: str,
    group_size: int,
    publication_bucket: str,
) -> dict[str, Any]:
    record = {
        "schema": ZK_ARWEAVE_RECORD_VERSION,
        "vote_scope_id": vote_scope_id,
        "bill_id": bill_id,
        "vote_commitment": vote_commitment,
        "semaphore_nullifier": semaphore_nullifier,
        "merkle_root": merkle_root,
        "merkle_depth": merkle_depth,
        "proof_public": dict(proof_public),
        "verifier_version": verifier_version,
        "circuit_version": circuit_version,
        "group_size": group_size,
        "publication_bucket": publication_bucket,
    }
    forbidden = public_zk_receipt_forbidden_fields()
    leaked = forbidden.intersection(_flatten_keys(record))
    if leaked:
        raise ValueError(f"ZK Arweave payload contains forbidden fields: {sorted(leaked)}")
    return record


def _flatten_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        keys = set(value.keys())
        for child in value.values():
            keys.update(_flatten_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_flatten_keys(child))
        return keys
    return set()

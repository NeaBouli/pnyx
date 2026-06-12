"""Canonical Semaphore message/scope binding for GH#112.

The native prover receives message/scope as strings and returns their BigInt
values in the public proof. For production votes we pass decimal field strings,
derived from a domain-separated SHA-256 digest, so the backend can recompute and
compare the exact logical vote binding before storing any receipt.
"""
from __future__ import annotations

import hashlib

from services.zk_group_registry import validate_vote_scope_id

ZK_PROOF_BINDING_VERSION = "ekklesia.zk.binding.v1"
ZK_SCOPE_DOMAIN = f"{ZK_PROOF_BINDING_VERSION}:scope:"
ZK_MESSAGE_DOMAIN = f"{ZK_PROOF_BINDING_VERSION}:message:"


def semaphore_text_to_bigint_string(value: str) -> str:
    """Match the native prover's short text-to-BigInt behavior for fixtures.

    Mopro/Semaphore encodes UTF-8 text as a 32-byte big-endian value, right
    padded with zero bytes when shorter than 32 bytes. Longer text is rejected;
    production vote bindings should use the canonical hash helpers below.
    """
    raw = value.encode("utf-8")
    if not raw or len(raw) > 32:
        raise ValueError("Semaphore text BigInt input must be 1..32 UTF-8 bytes")
    return str(int.from_bytes(raw.ljust(32, b"\x00"), "big"))


def canonical_zk_scope_value(vote_scope_id: str) -> str:
    scope = validate_vote_scope_id(vote_scope_id)
    return _sha256_to_field_decimal(f"{ZK_SCOPE_DOMAIN}{scope}".encode("utf-8"))


def canonical_zk_message_value(*, vote_scope_id: str, vote_commitment: str) -> str:
    scope = validate_vote_scope_id(vote_scope_id)
    clean_commitment = vote_commitment.strip()
    if not clean_commitment or len(clean_commitment) > 160:
        raise ValueError("vote_commitment must be 1..160 characters")
    payload = f"{ZK_MESSAGE_DOMAIN}{scope}:{clean_commitment}".encode("utf-8")
    return _sha256_to_field_decimal(payload)


def proof_matches_canonical_binding(
    *,
    proof_message: str | int,
    proof_scope: str | int,
    vote_scope_id: str,
    vote_commitment: str,
) -> bool:
    return (
        str(proof_scope) == canonical_zk_scope_value(vote_scope_id)
        and str(proof_message)
        == canonical_zk_message_value(
            vote_scope_id=vote_scope_id,
            vote_commitment=vote_commitment,
        )
    )


def _sha256_to_field_decimal(payload: bytes) -> str:
    # Shift away 8 bits so the value is safely below the BN254 scalar modulus.
    return str(int.from_bytes(hashlib.sha256(payload).digest(), "big") >> 8)

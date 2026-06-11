"""Semaphore Groth16 verifier helpers for GH#112 Gate 2.

This module verifies public Semaphore proof payloads only. It must never receive
or persist Semaphore identity secrets, phone numbers, HLR metadata, Tier-1
nullifiers, or tier_guard_hash values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from eth_utils.crypto import keccak
from py_ecc.bn128 import (
    FQ,
    FQ2,
    FQ12,
    add,
    b,
    b2,
    curve_order,
    is_on_curve,
    multiply,
    neg,
    pairing,
)

SEMAPHORE_V4_DEPTH16_VKEY_SHA256 = (
    "6ef3f6ae5ad8c50982b8c2ed5ec9626d7f92881fce3488ac2b8089c6edca2319"
)


def load_verification_key(path: Path, expected_sha256: str) -> dict[str, Any]:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Semaphore verification key checksum mismatch: {actual}")
    return json.loads(data)


def semaphore_public_hash(value: str | int) -> int:
    """Match @semaphore-protocol/proof hash(): keccak256(toBeHex(value, 32)) >> 8."""
    scalar = int(value)
    if scalar < 0:
        raise ValueError("Semaphore public input must be non-negative")
    return int.from_bytes(keccak(scalar.to_bytes(32, "big")), "big") >> 8


def normalize_native_proof(native_proof: Mapping[str, Any]) -> dict[str, Any]:
    """Map the Android/Mopro snake_case proof payload to canonical fields."""
    return {
        "merkleTreeDepth": int(native_proof["merkle_tree_depth"]),
        "merkleTreeRoot": str(native_proof["merkle_tree_root"]),
        "message": str(native_proof["message"]),
        "nullifier": str(native_proof["nullifier"]),
        "scope": str(native_proof["scope"]),
        "points": list(native_proof["points"]),
    }


def verify_semaphore_proof(proof: Mapping[str, Any], verification_key: Mapping[str, Any]) -> bool:
    """Verify a Semaphore v4 Groth16 proof against a pinned verification key."""
    try:
        normalized = _normalize_proof(proof)
        public_signals = [
            int(normalized["merkleTreeRoot"]),
            int(normalized["nullifier"]),
            semaphore_public_hash(normalized["message"]),
            semaphore_public_hash(normalized["scope"]),
        ]
        if any(signal < 0 or signal >= curve_order for signal in public_signals):
            return False

        ic = [_g1(point) for point in verification_key["IC"]]
        if len(ic) != len(public_signals) + 1:
            return False

        cpub = ic[0]
        for scalar, base in zip(public_signals, ic[1:]):
            cpub = add(cpub, multiply(base, scalar))

        points = normalized["points"]
        pi_a = _g1([points[0], points[1]])
        pi_b = _g2([[points[3], points[2]], [points[5], points[4]]])
        pi_c = _g1([points[6], points[7]])

        vk_alpha_1 = _g1(verification_key["vk_alpha_1"])
        vk_beta_2 = _g2(verification_key["vk_beta_2"])
        vk_gamma_2 = _g2(verification_key["vk_gamma_2"])
        vk_delta_2 = _g2(verification_key["vk_delta_2"])

        if not all(
            is_on_curve(point, b)
            for point in (pi_a, pi_c, cpub, vk_alpha_1)
        ):
            return False
        if not all(
            is_on_curve(point, b2)
            for point in (pi_b, vk_beta_2, vk_gamma_2, vk_delta_2)
        ):
            return False

        result = (
            pairing(pi_b, neg(pi_a))
            * pairing(vk_gamma_2, cpub)
            * pairing(vk_delta_2, pi_c)
            * pairing(vk_beta_2, vk_alpha_1)
        )
        return result == FQ12.one()
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def _normalize_proof(proof: Mapping[str, Any]) -> dict[str, Any]:
    if "merkle_tree_depth" in proof:
        proof = normalize_native_proof(proof)

    points = proof["points"]
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        raise TypeError("proof.points must be a sequence")
    if len(points) != 8:
        raise ValueError("proof.points must contain 8 packed Groth16 coordinates")

    return {
        "merkleTreeDepth": int(proof["merkleTreeDepth"]),
        "merkleTreeRoot": str(proof["merkleTreeRoot"]),
        "message": str(proof["message"]),
        "nullifier": str(proof["nullifier"]),
        "scope": str(proof["scope"]),
        "points": [str(point) for point in points],
    }


def _g1(point: Sequence[str | int]) -> tuple[FQ, FQ]:
    return (FQ(int(point[0])), FQ(int(point[1])))


def _g2(point: Sequence[Sequence[str | int]]) -> tuple[FQ2, FQ2]:
    return (
        FQ2([int(point[0][0]), int(point[0][1])]),
        FQ2([int(point[1][0]), int(point[1][1])]),
    )

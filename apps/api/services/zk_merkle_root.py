"""Semaphore-compatible LeanIMT/Poseidon root helpers for GH#112.

This module builds public group roots only. It must never receive Semaphore
identity secrets, phone numbers, HLR metadata, Tier-1 nullifiers, or
``tier_guard_hash`` values.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

FIELD_MODULUS = 21888242871839275222246405745257275088548364400416034343698204186575808495617
POSEIDON2_CONSTANTS_SHA256 = "91b68428e436a8ae184a90d63cc2ad58119725cb3acfb72349f7a8c8b94943b2"
CONSTANTS_PATH = Path(__file__).resolve().parents[1] / "data" / "poseidon2_constants.json"


@dataclass(frozen=True)
class SemaphoreGroupRoot:
    root: int
    depth: int
    size: int


def semaphore_member_hex_to_field(member_hex: str) -> int:
    """Convert native Mopro/Semaphore member hex bytes to the field element.

    The Android fixture exports member bytes in little-endian order. Official
    ``@semaphore-protocol/group`` reproduces the S10 proof root only when these
    bytes are reversed before converting to ``BigInt``.
    """
    clean = member_hex.removeprefix("0x").strip().lower()
    if not clean or len(clean) % 2 != 0:
        raise ValueError("member_hex must contain full bytes")
    try:
        raw = bytes.fromhex(clean)
    except ValueError as exc:
        raise ValueError("member_hex must be hexadecimal") from exc

    value = int.from_bytes(raw, "little")
    _require_field_element(value, "member")
    return value


def build_semaphore_group_root_from_member_hex(member_hex_values: Sequence[str]) -> SemaphoreGroupRoot:
    members = [semaphore_member_hex_to_field(value) for value in member_hex_values]
    return build_semaphore_group_root(members)


def build_semaphore_group_root(members: Sequence[int | str]) -> SemaphoreGroupRoot:
    """Build the dynamic LeanIMT root used by Semaphore group v4."""
    leaves = [_coerce_field_element(member, "member") for member in members]
    if not leaves:
        raise ValueError("at least one member is required")

    levels: list[list[int]] = [leaves]
    current = leaves
    while len(current) > 1:
        next_level: list[int] = []
        for index in range(0, len(current), 2):
            left = current[index]
            if index + 1 < len(current):
                next_level.append(poseidon2(left, current[index + 1]))
            else:
                next_level.append(left)
        levels.append(next_level)
        current = next_level

    return SemaphoreGroupRoot(root=levels[-1][0], depth=len(levels) - 1, size=len(leaves))


def poseidon2(left: int | str, right: int | str) -> int:
    constants = _load_poseidon2_constants()
    state = [0, _coerce_field_element(left, "left"), _coerce_field_element(right, "right")]
    c_values = constants["C"]
    m_values = constants["M"]

    n_rounds_f = int(constants["nRoundsF"])
    n_rounds_p = int(constants["nRoundsPForT3"])
    width = 3

    for round_index in range(n_rounds_f + n_rounds_p):
        for state_index in range(width):
            state[state_index] = (state[state_index] + c_values[round_index * width + state_index]) % FIELD_MODULUS
            if round_index < n_rounds_f // 2 or round_index >= n_rounds_f // 2 + n_rounds_p:
                state[state_index] = _pow5(state[state_index])
            elif state_index == 0:
                state[state_index] = _pow5(state[state_index])
        state = _mix(state, m_values)

    return state[0]


@lru_cache(maxsize=1)
def _load_poseidon2_constants() -> dict[str, object]:
    data = CONSTANTS_PATH.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != POSEIDON2_CONSTANTS_SHA256:
        raise ValueError(f"Poseidon2 constants checksum mismatch: {actual}")

    parsed = json.loads(data)
    if parsed.get("field") != str(FIELD_MODULUS):
        raise ValueError("Poseidon2 constants field mismatch")
    c_values = [int(value) for value in parsed["C"]]
    m_values = [[int(value) for value in row] for row in parsed["M"]]
    if len(c_values) != 195 or len(m_values) != 3 or any(len(row) != 3 for row in m_values):
        raise ValueError("Poseidon2 constants shape mismatch")
    return {
        "nRoundsF": int(parsed["nRoundsF"]),
        "nRoundsPForT3": int(parsed["nRoundsPForT3"]),
        "C": c_values,
        "M": m_values,
    }


def _mix(state: Sequence[int], matrix: Sequence[Sequence[int]]) -> list[int]:
    out: list[int] = []
    for x_index in range(len(state)):
        value = 0
        for y_index in range(len(state)):
            value += matrix[x_index][y_index] * state[y_index]
        out.append(value % FIELD_MODULUS)
    return out


def _pow5(value: int) -> int:
    squared = (value * value) % FIELD_MODULUS
    return (value * squared * squared) % FIELD_MODULUS


def _coerce_field_element(value: int | str, label: str) -> int:
    try:
        scalar = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer field element") from exc
    _require_field_element(scalar, label)
    return scalar


def _require_field_element(value: int, label: str) -> None:
    if value < 0 or value >= FIELD_MODULUS:
        raise ValueError(f"{label} must be in the BN254 scalar field")

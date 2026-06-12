"""GH#112 Semaphore LeanIMT/Poseidon root helper tests."""
import json
from pathlib import Path

import pytest

from services.zk_merkle_root import (
    FIELD_MODULUS,
    POSEIDON2_CONSTANTS_SHA256,
    build_semaphore_group_root,
    build_semaphore_group_root_from_member_hex,
    poseidon2,
    semaphore_member_hex_to_field,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gh112_s10_fixture.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_poseidon2_matches_poseidon_lite_reference_values() -> None:
    assert poseidon2(1, 2) == int(
        "7853200120776062878684798364095072458815029376092732009249414926327459813530"
    )
    assert poseidon2(0, 0) == int(
        "14744269619966411208579211824598458697587494354926760081771325075741142829156"
    )


def test_poseidon2_constants_checksum_is_pinned() -> None:
    assert POSEIDON2_CONSTANTS_SHA256 == "91b68428e436a8ae184a90d63cc2ad58119725cb3acfb72349f7a8c8b94943b2"


def test_s10_member_hex_little_endian_root_matches_native_proof() -> None:
    fixture = _fixture()
    native_proof = json.loads(fixture["proof"])

    group = build_semaphore_group_root_from_member_hex(fixture["memberHex"])

    assert group.root == int(native_proof["merkle_tree_root"])
    assert group.root == int.from_bytes(bytes.fromhex(fixture["groupRootHex"]), "little")
    assert group.depth == 1
    assert group.size == 2


def test_big_endian_member_interpretation_is_rejected_for_s10_fixture() -> None:
    fixture = _fixture()
    big_endian_members = [int(value, 16) for value in fixture["memberHex"]]

    with pytest.raises(ValueError):
        build_semaphore_group_root(big_endian_members)


def test_lean_imt_singletons_and_odd_nodes_carry_left_child_up() -> None:
    assert build_semaphore_group_root([123]).root == 123
    assert build_semaphore_group_root([1, 2, 3]).root == poseidon2(poseidon2(1, 2), 3)


def test_member_hex_conversion_is_little_endian() -> None:
    assert semaphore_member_hex_to_field("0100") == 1
    assert semaphore_member_hex_to_field("0x0100") == 1
    assert semaphore_member_hex_to_field("0001") == 256


@pytest.mark.parametrize("value", ["", "0", "abc", "zz"])
def test_member_hex_conversion_rejects_malformed_bytes(value: str) -> None:
    with pytest.raises(ValueError):
        semaphore_member_hex_to_field(value)


@pytest.mark.parametrize("members", [[], [-1], [FIELD_MODULUS]])
def test_group_root_rejects_invalid_members(members: list[int]) -> None:
    with pytest.raises(ValueError):
        build_semaphore_group_root(members)

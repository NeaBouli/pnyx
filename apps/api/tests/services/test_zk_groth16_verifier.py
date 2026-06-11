"""GH#112 Gate 2 verifier checks using the exported S10 fixture."""
import json
from pathlib import Path

from services.zk_groth16_verifier import (
    SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    load_verification_key,
    normalize_native_proof,
    semaphore_public_hash,
    verify_semaphore_proof,
)

ROOT = Path(__file__).resolve().parents[2]
VKEY_PATH = ROOT / "data" / "semaphore-v4-depth16-vkey.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gh112_s10_fixture.json"


def _fixture() -> tuple[dict, dict]:
    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    fixture = json.loads(FIXTURE_PATH.read_text())
    native_proof = json.loads(fixture["proof"])
    return vkey, native_proof


def test_depth16_verification_key_checksum_is_pinned() -> None:
    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    assert vkey["curve"] == "bn128"
    assert vkey["nPublic"] == 4
    assert len(vkey["IC"]) == 5


def test_s10_native_fixture_verifies_with_python_groth16() -> None:
    vkey, native_proof = _fixture()

    assert verify_semaphore_proof(native_proof, vkey) is True


def test_s10_fixture_rejects_mutated_message_scope_root_and_nullifier() -> None:
    vkey, native_proof = _fixture()

    for field in ("message", "scope", "merkle_tree_root", "nullifier"):
        mutated = dict(native_proof)
        mutated[field] = str(int(mutated[field]) + 1)
        assert verify_semaphore_proof(mutated, vkey) is False


def test_s10_fixture_rejects_malformed_points() -> None:
    vkey, native_proof = _fixture()
    mutated = dict(native_proof)
    mutated["points"] = native_proof["points"][:-1]

    assert verify_semaphore_proof(mutated, vkey) is False


def test_native_proof_normalization_matches_expected_public_fields() -> None:
    _, native_proof = _fixture()

    normalized = normalize_native_proof(native_proof)

    assert normalized["merkleTreeDepth"] == 16
    assert normalized["merkleTreeRoot"] == native_proof["merkle_tree_root"]
    assert normalized["nullifier"] == native_proof["nullifier"]
    assert normalized["message"] == native_proof["message"]
    assert normalized["scope"] == native_proof["scope"]
    assert len(normalized["points"]) == 8


def test_semaphore_public_hash_matches_official_js_reference_values() -> None:
    _, native_proof = _fixture()

    assert semaphore_public_hash(native_proof["message"]) == int(
        "147780066906587745451040582749603880002311048969600667959576108785972982215"
    )
    assert semaphore_public_hash(native_proof["scope"]) == int(
        "392471568387567921640950579947570299789363970096420979493477205894389626429"
    )

"""T-590: the bundled Semaphore zkey and its provenance manifest stay consistent with the server key.

The mobile app ships the depth-16 Semaphore v4 proving key instead of downloading it at
proof time. These checks pin the asset bytes to the manifest and the manifest to the
verification key the API enforces, so a swapped artifact fails CI before it can ship.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from services.zk_groth16_verifier import SEMAPHORE_V4_DEPTH16_VKEY_SHA256

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "apps" / "mobile" / "modules" / "semaphore-react-native"
MANIFEST = MODULE / "zk-artifacts.manifest.json"
SERVER_DEPTH = 16


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zkey_entry() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema"] == "ekklesia-zk-artifacts"
    entries = [a for a in manifest["artifacts"] if a["id"] == "semaphore-v4-depth16-zkey"]
    assert len(entries) == 1
    return entries[0]


def test_bundled_zkey_matches_manifest_hash_and_size() -> None:
    entry = _zkey_entry()
    asset = MODULE / entry["path"]

    assert asset.is_file()
    assert asset.stat().st_size == entry["bytes"]
    assert _sha256(asset) == entry["sha256"]
    # semaphore-rs looks the file up as semaphore-<artifacts version>-<depth>.zkey
    assert asset.name == entry["runtime_name"] == f"semaphore-{entry['artifacts_version']}-{SERVER_DEPTH}.zkey"


def test_manifest_verification_key_is_the_key_the_server_enforces() -> None:
    entry = _zkey_entry()
    vkey = REPO_ROOT / entry["verification_key"]["path"]

    assert entry["merkle_tree_depth"] == SERVER_DEPTH
    assert entry["verification_key"]["sha256"] == SEMAPHORE_V4_DEPTH16_VKEY_SHA256
    assert _sha256(vkey) == SEMAPHORE_V4_DEPTH16_VKEY_SHA256


def test_manifest_pins_immutable_provenance() -> None:
    entry = _zkey_entry()
    sha40 = re.compile(r"^[0-9a-f]{40}$")

    assert entry["source_url"].startswith("https://")
    assert entry["immutable_source"]["npm_integrity"].startswith("sha512-")
    assert entry["ceremony"]["beacon_anchor"].startswith("Ethereum mainnet block ")
    assert sha40.match(entry["consumer"]["bundled_binary_source"]["commit"])
    assert sha40.match(entry["consumer"]["bindings_rust_source"]["commit"])


def _device_proof() -> dict:
    fixture = Path(__file__).parent / "fixtures" / "semaphore_t590_device_proof.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["proof"]


def test_device_proof_from_bundled_zkey_is_accepted_by_the_pinned_server_key() -> None:
    from services.zk_groth16_verifier import load_verification_key, normalize_native_proof, verify_semaphore_proof

    vkey = load_verification_key(
        REPO_ROOT / _zkey_entry()["verification_key"]["path"], SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    )
    proof = _device_proof()
    assert proof["merkle_tree_depth"] == SERVER_DEPTH
    assert verify_semaphore_proof(normalize_native_proof(proof), vkey) is True

    tampered = dict(proof, message=proof["message"] + "-tampered")
    assert verify_semaphore_proof(normalize_native_proof(tampered), vkey) is False

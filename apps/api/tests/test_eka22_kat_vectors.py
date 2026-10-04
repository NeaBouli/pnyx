"""
test_eka22_kat_vectors.py
=========================
EKA-22 API adapter for the shared known-answer fixture
packages/crypto/tests/vectors/eka22_kat_v1.json (T-490).

Hop: fixture -> this adapter -> existing API crypto symbols -> expected bytes/hex/errors.
The same file is read by the web, mobile and packages/crypto vitest adapters.
Test-only: no production symbol is wrapped or changed. KDF entries are pinned
per implementation only (EKA-21 gate), never compared across implementations.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from nacl.signing import SigningKey

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from crypto.nullifier import VotePayload, build_signed_payload, validate_vote  # noqa: E402
from services.citizen_action_integrity import build_vote_status_read_payload  # noqa: E402
from services.evaluation_integrity import (  # noqa: E402
    build_evaluation_read_payload,
    build_evaluation_v2_payload,
)
from services.zk_group_registry import validate_vote_scope_id  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
FIXTURE_PATH = REPO_ROOT / "packages/crypto/tests/vectors/eka22_kat_v1.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
KEYS = {k["id"]: k for k in FIXTURE["keys"]}
ROOTS = {r["id"]: bytes.fromhex(r["root_hex"]) for r in FIXTURE["roots"]}


def _load(name: str, path: Path) -> ModuleType:
    """Load a module by path so the two `keypair.py` copies do not shadow each other."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Runtime verifier (voting.py puts packages/crypto first on sys.path) and its API mirror.
PKG_KEYPAIR = _load("eka22_pkg_keypair", REPO_ROOT / "packages/crypto/keypair.py")
API_KEYPAIR = _load("eka22_api_keypair", API_ROOT / "keypair.py")
VERIFIERS = {"packages/crypto/keypair.py": PKG_KEYPAIR.verify_signature,
             "apps/api/keypair.py": API_KEYPAIR.verify_signature}
PKG_NULLIFIER = _load("eka22_pkg_nullifier", REPO_ROOT / "packages/crypto/nullifier.py")


def _cases(kind: str) -> list[dict]:
    selected = [c for c in FIXTURE["cases"] if c["kind"] == kind and "api" in c["impls"]]
    assert selected, f"fixture has no api case of kind {kind}"
    return selected


def _ids(cases: list[dict]) -> list[str]:
    return [c["id"] for c in cases]


def _router_template(router: str, pattern: str) -> str:
    """Pin the inline f-string the router signs over; legacy payloads have no importable builder."""
    source = (API_ROOT / "routers" / router).read_text(encoding="utf-8")
    assert pattern in source, f"{router} no longer builds {pattern}"
    return pattern


LEGACY_TEMPLATE = _router_template(
    "voting.py", 'f"{req.bill_id}:{req.vote.upper()}:{req.nullifier_hash}"')
ZK_OPT_IN_TEMPLATE = _router_template(
    "zk.py", 'f"zk_opt_in:{req.bill_id}:{req.commitment}:{req.nullifier_hash}"')


def _api_legacy_message(bill_id: str, vote: str, nullifier_hash: str) -> str:
    """Mirror of the pinned voting.py f-string (LEGACY_TEMPLATE); the router has no importable builder."""
    return f"{bill_id}:{vote.upper()}:{nullifier_hash}"


def _api_zk_opt_in_message(bill_id: str, commitment: str, nullifier_hash: str) -> str:
    """Mirror of the pinned zk.py f-string (ZK_OPT_IN_TEMPLATE)."""
    return f"zk_opt_in:{bill_id}:{commitment}:{nullifier_hash}"


def _sign(key_id: str, message: bytes) -> str:
    return PKG_KEYPAIR.sign_payload(KEYS[key_id]["seed_hex"], message)


def _scores(raw: list[dict]) -> list[SimpleNamespace]:
    return [SimpleNamespace(**s) for s in raw]


# ── Fixture contract ──────────────────────────────────────────────────────────

def test_fixture_schema_and_classes():
    assert FIXTURE["schema"] == "ekklesia-kat"
    assert FIXTURE["version"] == 1
    ids = [c["id"] for c in FIXTURE["cases"]]
    assert len(ids) == len(set(ids))
    classes = {c["class"] for c in FIXTURE["cases"]}
    assert classes == {"identical", "validatable", "implementation_specific"}
    for case in FIXTURE["cases"]:
        assert set(case["impls"]) <= {"api", "web", "mobile", "tier1_lib"}
        if case["class"] == "identical":
            assert len(case["impls"]) >= 2 or case["kind"] == "domain_separation"


def test_fixture_kdf_inventory_is_within_impl_only():
    inventory = FIXTURE["kdf_inventory"]
    assert inventory["class"] == "implementation_specific"
    assert inventory["gate"] == "EKA-21"
    assert inventory["compare"] == "within_impl_only"
    versions = [e["version"] for e in inventory["entries"]]
    assert versions == ["server-v1", "server-v2", "tier1-lib-v1", "mobile-pbkdf2-v1"]
    for entry in inventory["entries"]:
        assert not {"equals", "same_as", "matches"} & set(entry["expect"])


def test_fixture_has_no_secret_like_material():
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "dev-salt-change-in-production" not in raw
    rfc_seeds = {k["seed_hex"] for k in FIXTURE["keys"]}
    assert len(rfc_seeds) == 3
    for entry in FIXTURE["kdf_inventory"]["entries"]:
        assert entry["input"]["phone"] == "+300000000000"
        if "server_salt" in entry["input"]:
            assert "not-a-secret" in entry["input"]["server_salt"]


def test_fixture_oracle_hmac_chain():
    """Stdlib oracle only: Python has no production HMAC-chain symbol (see fixture note)."""
    case = next(c for c in FIXTURE["cases"] if c["kind"] == "hmac_chain")
    root = ROOTS[case["root"]]
    domains = next(c for c in FIXTURE["cases"] if c["kind"] == "domain_separation")["input"]["domains"]
    mac = lambda key, msg: hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()  # noqa: E731
    assert mac(root, domains["IDENTITY_COMMITMENT"]).hex() == case["expect"]["identity_commitment_hex"]
    for bill in case["expect"]["bills"]:
        b = bill["bill_id"]
        assert mac(root, f"{domains['VOTE_NULLIFIER']}:{b}").hex() == bill["vote_nullifier_hex"]
        seed = mac(root, f"{domains['EPHEMERAL_SEED']}:{b}")
        assert bytes(SigningKey(seed).verify_key).hex() == bill["ephemeral_pk_hex"]
        assert mac(mac(root, domains["LINKAGE_TAG"]), b).hex() == bill["linkage_tag_hex"]


# ── identical ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _cases("ed25519_rfc8032"), ids=_ids(_cases("ed25519_rfc8032")))
def test_identical_ed25519_rfc8032(case):
    key = KEYS[case["key"]]
    message = bytes.fromhex(case["expect"]["message_hex"])
    assert bytes(SigningKey(bytes.fromhex(key["seed_hex"])).verify_key).hex() == case["expect"]["pk_hex"]
    assert PKG_KEYPAIR.sign_payload(key["seed_hex"], message) == case["expect"]["sig_hex"]
    for name, verify in VERIFIERS.items():
        assert verify(key["pk_hex"], message, case["expect"]["sig_hex"]) is True, name


@pytest.mark.parametrize("case", _cases("legacy_vote"), ids=_ids(_cases("legacy_vote")))
def test_identical_legacy_vote(case):
    message = _api_legacy_message(**case["input"])
    assert message == case["expect"]["message_utf8"]
    assert message.encode("utf-8").hex() == case["expect"]["message_hex"]
    assert _sign(case["key"], message.encode("utf-8")) == case["expect"]["sig_hex"]
    for name, verify in VERIFIERS.items():
        assert verify(KEYS[case["key"]]["pk_hex"], message.encode(), case["expect"]["sig_hex"]) is True, name


@pytest.mark.parametrize("case", _cases("tier1_signed_payload"), ids=_ids(_cases("tier1_signed_payload")))
def test_identical_tier1_signed_payload(case):
    i = case["input"]
    payload = build_signed_payload(
        bill_id=i["bill_id"],
        choice=i["choice"],
        pk_eph=bytes.fromhex(i["pk_eph_hex"]),
        vote_nullifier=bytes.fromhex(i["vote_nullifier_hex"]),
        linkage_tag=bytes.fromhex(i["linkage_tag_hex"]),
        timestamp_ms=i["timestamp_ms"],
    )
    assert payload.hex() == case["expect"]["payload_hex"]
    vote = VotePayload(
        bill_id=i["bill_id"], choice=i["choice"], pk_eph=i["pk_eph_hex"],
        vote_nullifier=i["vote_nullifier_hex"], linkage_tag=i["linkage_tag_hex"],
        signature=case["expect"]["sig_hex"], timestamp_ms=i["timestamp_ms"], version=i["version"],
    )
    assert validate_vote(vote, set(), now_ms=i["timestamp_ms"]) is None


_JSON_KINDS = ("evaluation_v2", "evaluation_read", "vote_status_read")
_JSON_CASES = [c for k in _JSON_KINDS for c in _cases(k)]


@pytest.mark.parametrize("case", _JSON_CASES, ids=_ids(_JSON_CASES))
def test_identical_json_integrity_payloads(case):
    i = case["input"]
    if case["kind"] == "evaluation_v2":
        payload = build_evaluation_v2_payload(
            i["ada_number"], i["nullifier_hash"], i["timestamp_ms"], _scores(i["scores"]))
    elif case["kind"] == "evaluation_read":
        payload = build_evaluation_read_payload(i["ada_number"], i["nullifier_hash"], i["timestamp_ms"])
    else:
        payload = build_vote_status_read_payload(i["bill_id"], i["nullifier_hash"], i["timestamp_ms"])
    assert payload == case["expect"]["payload_utf8"]
    assert payload.encode("utf-8").hex() == case["expect"]["payload_hex"]
    for name, verify in VERIFIERS.items():
        assert verify(KEYS[case["key"]]["pk_hex"], payload, case["expect"]["sig_hex"]) is True, name


@pytest.mark.parametrize("case", _cases("zk_opt_in"), ids=_ids(_cases("zk_opt_in")))
def test_identical_zk_opt_in_scope_string(case):
    message = _api_zk_opt_in_message(**case["input"])
    assert message == case["expect"]["message_utf8"]
    for name, verify in VERIFIERS.items():
        assert verify(KEYS[case["key"]]["pk_hex"], message.encode(), case["expect"]["sig_hex"]) is True, name


@pytest.mark.parametrize("case", _cases("v1_nullifier"), ids=_ids(_cases("v1_nullifier")))
def test_identical_v1_nullifier(case, monkeypatch):
    monkeypatch.setattr(PKG_NULLIFIER, "SERVER_SALT", case["input"]["salt"])
    assert PKG_NULLIFIER.generate_nullifier_hash(case["input"]["phone"]) == case["expect"]["nullifier_hex"]


@pytest.mark.parametrize("case", _cases("domain_separation"), ids=_ids(_cases("domain_separation")))
def test_identical_scope_domain_separation(case):
    scope_ids = case["input"]["scope_ids"]
    normalized = [validate_vote_scope_id(s) for s in scope_ids]
    assert normalized == scope_ids
    assert len(set(normalized)) == len(normalized)
    domains = list(case["input"]["domains"].values())
    assert len(set(domains)) == len(domains)


# ── validatable ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _cases("legacy_vote_verify"), ids=_ids(_cases("legacy_vote_verify")))
def test_validatable_legacy_vote_rejected(case):
    i = case["input"]
    assert case["impl_error"]["api"] == "False"
    message = _api_legacy_message(i["bill_id"], i["vote"], i["nullifier_hash"])
    for name, verify in VERIFIERS.items():
        assert verify(i["pk_hex"], message.encode(), i["sig_hex"]) is False, name


@pytest.mark.parametrize("case", _cases("tier1_validate"), ids=_ids(_cases("tier1_validate")))
def test_validatable_tier1_error_codes(case):
    p = case["input"]["payload"]
    vote = VotePayload(
        bill_id=p["bill_id"], choice=p["choice"], pk_eph=p["pk_eph_hex"],
        vote_nullifier=p["vote_nullifier_hex"], linkage_tag=p["linkage_tag_hex"],
        signature=p["signature_hex"], timestamp_ms=p["timestamp_ms"], version=p["version"],
    )
    result = validate_vote(vote, set(case["input"].get("used_nullifiers", [])),
                           now_ms=case["input"]["now_ms"])
    if case["expect"]["accepted"]:
        assert result is None
    else:
        assert result is not None and result.code == case["expect"]["api_code"]


@pytest.mark.parametrize("case", _cases("evaluation_v2_error"), ids=_ids(_cases("evaluation_v2_error")))
def test_validatable_evaluation_duplicate_question(case):
    i = case["input"]
    assert case["impl_error"]["api"] == "ValueError"
    with pytest.raises(ValueError):
        build_evaluation_v2_payload(i["ada_number"], i["nullifier_hash"], i["timestamp_ms"], _scores(i["scores"]))


@pytest.mark.parametrize("case", _cases("scope_id"), ids=_ids(_cases("scope_id")))
def test_validatable_scope_id(case):
    if case["expect"]["accepted"]:
        assert validate_vote_scope_id(case["input"]["vote_scope_id"]) == case["expect"]["normalized"]
    else:
        assert case["impl_error"]["api"] == "ValueError"
        with pytest.raises(ValueError):
            validate_vote_scope_id(case["input"]["vote_scope_id"])


# ── implementation_specific / known divergences ──────────────────────────────

@pytest.mark.parametrize("case", _cases("lowercase_vote_divergence"), ids=_ids(_cases("lowercase_vote_divergence")))
def test_divergence_lowercase_mobile_vote_rejected_by_api(case):
    i = case["input"]
    canonical = next(c for c in FIXTURE["cases"] if c["id"] == case["expect"]["canonical_case"])
    api_message = _api_legacy_message(**i).encode()
    assert api_message.decode() == canonical["expect"]["message_utf8"]
    pk_hex = KEYS[case["key"]]["pk_hex"]
    for name, verify in VERIFIERS.items():
        assert verify(pk_hex, api_message, canonical["expect"]["sig_hex"]) is True, name
        accepted = verify(pk_hex, api_message, case["expect"]["mobile_sig_hex"])
        assert accepted is case["expect"]["api_accepts_mobile_sig"], name


def _kdf(entry_id: str) -> dict:
    return next(e for e in FIXTURE["kdf_inventory"]["entries"] if e["id"] == entry_id)


def test_kdf_server_v1_sha256_pinned(monkeypatch):
    entry = _kdf("kdf-server-v1-sha256")
    assert entry["impl"] == "api"
    monkeypatch.setattr(PKG_NULLIFIER, "SERVER_SALT", entry["input"]["server_salt"])
    assert PKG_NULLIFIER.generate_nullifier_hash(entry["input"]["phone"]) == entry["expect"]["output"]


def test_kdf_server_v2_argon2id_t2_pinned(monkeypatch):
    entry = _kdf("kdf-server-v2-argon2id-t2")
    assert entry["impl"] == "api"
    assert (PKG_NULLIFIER.IDENTITY_NULLIFIER_V2_TIME_COST, PKG_NULLIFIER.IDENTITY_NULLIFIER_V2_MEMORY_KIB,
            PKG_NULLIFIER.IDENTITY_NULLIFIER_V2_PARALLELISM, PKG_NULLIFIER.IDENTITY_NULLIFIER_V2_HASH_LEN) == (
        entry["params"]["t"], entry["params"]["m_kib"], entry["params"]["p"], entry["params"]["len"])
    assert PKG_NULLIFIER.normalize_phone_number(entry["input"]["phone"]) == entry["expect"]["normalized"]
    monkeypatch.setattr(PKG_NULLIFIER, "SERVER_SALT", entry["input"]["server_salt"])
    output = PKG_NULLIFIER.generate_nullifier_hash_v2(entry["input"]["phone"])
    assert output == entry["expect"]["output"]
    assert re.fullmatch(r"v2:[0-9a-f]{64}", output)

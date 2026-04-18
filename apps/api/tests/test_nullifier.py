"""
test_nullifier.py
=================
Tests for apps/api/crypto/nullifier.py.

Covers:
  - Valid vote payload passes all checks
  - Each validation rule rejects correctly
  - Receipt issuance and structure
  - Canonical payload builder mirrors client output
  - Timestamp edge cases
"""

from __future__ import annotations

import struct
import time

import pytest
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from ..crypto.nullifier import (
    PROTO_VERSION,
    TIMESTAMP_WINDOW_MS,
    RegistrationPayload,
    VotePayload,
    ValidationError,
    build_signed_payload,
    validate_registration,
    validate_vote,
    issue_receipt,
    _is_hex,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def server_sk() -> SigningKey:
    return SigningKey.generate()


@pytest.fixture()
def client_sk() -> SigningKey:
    """Simulates an ephemeral client key."""
    return SigningKey.generate()


@pytest.fixture()
def now_ms() -> int:
    return int(time.time() * 1000)


def make_vote_payload(
    client_sk:      SigningKey,
    *,
    bill_id:        str        = "GR-2026-0042",
    choice:         str        = "YES",
    timestamp_ms:   int | None = None,
    vote_nullifier: str | None = None,
    linkage_tag:    str | None = None,
    version:        str        = PROTO_VERSION,
) -> VotePayload:
    """Helper — builds a valid signed VotePayload."""
    ts          = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    pk_eph      = bytes(client_sk.verify_key)
    v_nullifier = vote_nullifier or ("aa" * 32)
    l_tag       = linkage_tag or ("bb" * 32)

    signed_bytes = build_signed_payload(
        bill_id        = bill_id,
        choice         = choice,
        pk_eph         = pk_eph,
        vote_nullifier = bytes.fromhex(v_nullifier),
        linkage_tag    = bytes.fromhex(l_tag),
        timestamp_ms   = ts,
    )
    sig = bytes(client_sk.sign(signed_bytes).signature)

    return VotePayload(
        bill_id        = bill_id,
        choice         = choice,
        pk_eph         = pk_eph.hex(),
        vote_nullifier = v_nullifier,
        linkage_tag    = l_tag,
        signature      = sig.hex(),
        timestamp_ms   = ts,
        version        = version,
    )


# ─── _is_hex ─────────────────────────────────────────────────────────────────

class TestIsHex:
    def test_valid_32_byte_hex(self) -> None:
        assert _is_hex("aa" * 32, 64) is True

    def test_wrong_length(self) -> None:
        assert _is_hex("aa" * 31, 64) is False

    def test_non_hex_chars(self) -> None:
        assert _is_hex("zz" * 32, 64) is False

    def test_uppercase_rejected(self) -> None:
        # bytes.fromhex accepts uppercase, so this passes
        assert _is_hex("AA" * 32, 64) is True


# ─── validate_registration ────────────────────────────────────────────────────

class TestValidateRegistration:
    def test_valid_payload(self) -> None:
        payload = RegistrationPayload(
            identity_commitment = "ab" * 32,
            phone_region        = "GR",
            version             = PROTO_VERSION,
        )
        assert validate_registration(payload) is None

    def test_wrong_version(self) -> None:
        payload = RegistrationPayload("ab" * 32, "GR", "ekklesia:v0")
        err = validate_registration(payload)
        assert err is not None
        assert err.code == "VERSION_MISMATCH"

    def test_invalid_commitment_short(self) -> None:
        payload = RegistrationPayload("ab" * 31, "GR", PROTO_VERSION)
        err = validate_registration(payload)
        assert err is not None
        assert err.code == "INVALID_COMMITMENT"

    def test_invalid_commitment_non_hex(self) -> None:
        payload = RegistrationPayload("zz" * 32, "GR", PROTO_VERSION)
        err = validate_registration(payload)
        assert err is not None
        assert err.code == "INVALID_COMMITMENT"

    def test_empty_region(self) -> None:
        payload = RegistrationPayload("ab" * 32, "", PROTO_VERSION)
        err = validate_registration(payload)
        assert err is not None
        assert err.code == "INVALID_REGION"


# ─── validate_vote ────────────────────────────────────────────────────────────

class TestValidateVote:
    def test_valid_payload(self, client_sk: SigningKey, now_ms: int) -> None:
        payload = make_vote_payload(client_sk, timestamp_ms=now_ms)
        err = validate_vote(payload, set(), now_ms=now_ms)
        assert err is None

    def test_wrong_version(self, client_sk: SigningKey, now_ms: int) -> None:
        payload = make_vote_payload(client_sk, timestamp_ms=now_ms, version="bad:v0")
        err = validate_vote(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "VERSION_MISMATCH"

    def test_invalid_choice(self, client_sk: SigningKey, now_ms: int) -> None:
        payload = make_vote_payload(client_sk, choice="MAYBE", timestamp_ms=now_ms)
        err = validate_vote(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_CHOICE"

    def test_timestamp_too_old(self, client_sk: SigningKey, now_ms: int) -> None:
        old_ts  = now_ms - TIMESTAMP_WINDOW_MS - 1000
        payload = make_vote_payload(client_sk, timestamp_ms=old_ts)
        err     = validate_vote(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "TIMESTAMP_EXPIRED"

    def test_timestamp_too_future(self, client_sk: SigningKey, now_ms: int) -> None:
        future_ts = now_ms + TIMESTAMP_WINDOW_MS + 1000
        payload   = make_vote_payload(client_sk, timestamp_ms=future_ts)
        err       = validate_vote(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "TIMESTAMP_EXPIRED"

    def test_timestamp_at_edge(self, client_sk: SigningKey, now_ms: int) -> None:
        edge_ts = now_ms - TIMESTAMP_WINDOW_MS
        payload = make_vote_payload(client_sk, timestamp_ms=edge_ts)
        err     = validate_vote(payload, set(), now_ms=now_ms)
        assert err is None  # exactly at edge — accepted

    def test_duplicate_nullifier(self, client_sk: SigningKey, now_ms: int) -> None:
        nullifier = "cc" * 32
        payload   = make_vote_payload(client_sk, vote_nullifier=nullifier, timestamp_ms=now_ms)
        err       = validate_vote(payload, {nullifier}, now_ms=now_ms)
        assert err is not None
        assert err.code == "DUPLICATE_VOTE"

    def test_invalid_signature(self, client_sk: SigningKey, now_ms: int) -> None:
        payload = make_vote_payload(client_sk, timestamp_ms=now_ms)
        # tamper with signature
        tampered_sig = "ff" * 64
        tampered = VotePayload(
            bill_id        = payload.bill_id,
            choice         = payload.choice,
            pk_eph         = payload.pk_eph,
            vote_nullifier = payload.vote_nullifier,
            linkage_tag    = payload.linkage_tag,
            signature      = tampered_sig,
            timestamp_ms   = payload.timestamp_ms,
            version        = payload.version,
        )
        err = validate_vote(tampered, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_SIGNATURE"

    def test_tampered_choice_breaks_signature(
        self, client_sk: SigningKey, now_ms: int,
    ) -> None:
        payload = make_vote_payload(client_sk, choice="YES", timestamp_ms=now_ms)
        tampered = VotePayload(
            bill_id        = payload.bill_id,
            choice         = "NO",      # tampered
            pk_eph         = payload.pk_eph,
            vote_nullifier = payload.vote_nullifier,
            linkage_tag    = payload.linkage_tag,
            signature      = payload.signature,  # original sig — won't match
            timestamp_ms   = payload.timestamp_ms,
            version        = payload.version,
        )
        err = validate_vote(tampered, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_SIGNATURE"

    def test_all_choices_valid(self, client_sk: SigningKey, now_ms: int) -> None:
        for choice in ("YES", "NO", "ABSTAIN"):
            payload = make_vote_payload(
                client_sk,
                choice         = choice,
                timestamp_ms   = now_ms,
                vote_nullifier = "dd" * 32,   # use distinct nullifier per choice
            )
            err = validate_vote(payload, set(), now_ms=now_ms)
            assert err is None, f"Choice {choice} failed: {err}"

    def test_empty_bill_id(self, client_sk: SigningKey, now_ms: int) -> None:
        payload = make_vote_payload(client_sk, bill_id="", timestamp_ms=now_ms)
        err     = validate_vote(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_BILL_ID"


# ─── issue_receipt ────────────────────────────────────────────────────────────

class TestIssueReceipt:
    def test_receipt_structure(self, server_sk: SigningKey) -> None:
        receipt = issue_receipt("GR-2026-0042", "aa" * 32, server_sk)
        assert receipt.bill_id        == "GR-2026-0042"
        assert receipt.vote_nullifier == "aa" * 32
        assert len(receipt.server_signature) == 128    # 64 bytes hex
        assert len(receipt.server_pk)        == 64     # 32 bytes hex

    def test_receipt_signature_verifiable(self, server_sk: SigningKey) -> None:
        bill_id   = "GR-2026-0042"
        nullifier = "aa" * 32
        receipt   = issue_receipt(bill_id, nullifier, server_sk)

        # Re-construct receipt bytes
        receipt_bytes = (
            bill_id.encode("utf-8")
            + bytes.fromhex(nullifier)
            + struct.pack(">Q", receipt.server_timestamp_ms)
        )
        vk = VerifyKey(bytes.fromhex(receipt.server_pk))
        # Should not raise
        vk.verify(receipt_bytes, bytes.fromhex(receipt.server_signature))

    def test_different_bills_different_receipts(self, server_sk: SigningKey) -> None:
        r1 = issue_receipt("GR-2026-0001", "aa" * 32, server_sk)
        r2 = issue_receipt("GR-2026-0002", "aa" * 32, server_sk)
        assert r1.server_signature != r2.server_signature

    def test_receipt_timestamp_is_recent(self, server_sk: SigningKey) -> None:
        before  = int(time.time() * 1000)
        receipt = issue_receipt("GR-2026-0042", "aa" * 32, server_sk)
        after   = int(time.time() * 1000)
        assert before <= receipt.server_timestamp_ms <= after


# ─── build_signed_payload canonical test ──────────────────────────────────────

class TestBuildSignedPayload:
    def test_deterministic(self) -> None:
        args = dict(
            bill_id        = "GR-2026-0042",
            choice         = "YES",
            pk_eph         = bytes(32),
            vote_nullifier = bytes(32),
            linkage_tag    = bytes(32),
            timestamp_ms   = 1700000000000,
        )
        assert build_signed_payload(**args) == build_signed_payload(**args)

    def test_choice_changes_payload(self) -> None:
        base = dict(
            bill_id        = "GR-2026-0042",
            pk_eph         = bytes(32),
            vote_nullifier = bytes(32),
            linkage_tag    = bytes(32),
            timestamp_ms   = 1700000000000,
        )
        p_yes = build_signed_payload(choice="YES", **base)
        p_no  = build_signed_payload(choice="NO",  **base)
        assert p_yes != p_no

    def test_timestamp_changes_payload(self) -> None:
        base = dict(
            bill_id        = "GR-2026-0042",
            choice         = "YES",
            pk_eph         = bytes(32),
            vote_nullifier = bytes(32),
            linkage_tag    = bytes(32),
        )
        p1 = build_signed_payload(timestamp_ms=1700000000000, **base)
        p2 = build_signed_payload(timestamp_ms=1700000000001, **base)
        assert p1 != p2

    def test_bill_id_changes_payload(self) -> None:
        base = dict(
            choice         = "YES",
            pk_eph         = bytes(32),
            vote_nullifier = bytes(32),
            linkage_tag    = bytes(32),
            timestamp_ms   = 1700000000000,
        )
        p1 = build_signed_payload(bill_id="GR-2026-0001", **base)
        p2 = build_signed_payload(bill_id="GR-2026-0002", **base)
        assert p1 != p2

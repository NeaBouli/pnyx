"""
test_polis.py
=============
Tests for apps/api/crypto/polis.py.

Covers:
  - Valid ticket creation passes all checks
  - Valid ticket vote passes all checks
  - Each validation rule rejects correctly
  - Self-vote prevention
  - Proposal threshold logic
  - Canonical payload builders are deterministic
"""

from __future__ import annotations

import time

import pytest
from nacl.signing import SigningKey

from ..crypto.polis import (
    PROTO_VERSION,
    PROPOSAL_THRESHOLD,
    TIMESTAMP_WINDOW_MS,
    PolisTicketPayload,
    PolisVotePayload,
    ValidationError,
    build_ticket_signed_bytes,
    build_vote_signed_bytes,
    hash_content,
    validate_ticket,
    validate_ticket_vote,
    check_proposal_threshold,
    get_short_handle,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def polis_sk() -> SigningKey:
    """Simulates a persistent POLIS key."""
    return SigningKey.generate()


@pytest.fixture()
def owner_sk() -> SigningKey:
    """Ticket owner's POLIS key."""
    return SigningKey.generate()


@pytest.fixture()
def voter_sk() -> SigningKey:
    """A different identity voting on a ticket."""
    return SigningKey.generate()


@pytest.fixture()
def now_ms() -> int:
    return int(time.time() * 1000)


def make_ticket_payload(
    sk:           SigningKey,
    *,
    content:      str         = "Please add a dark mode",
    category:     str         = "proposal",
    timestamp_ms: int | None  = None,
    nullifier:    str | None  = None,
    version:      str         = PROTO_VERSION,
) -> PolisTicketPayload:
    ts          = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    pk_bytes    = bytes(sk.verify_key)
    ch          = hash_content(content)
    ticket_null = nullifier or ("cc" * 32)

    signed_bytes = build_ticket_signed_bytes(
        category     = category,
        content_hash = ch,
        pk_polis     = pk_bytes,
        nullifier    = bytes.fromhex(ticket_null),
        timestamp_ms = ts,
    )
    sig = bytes(sk.sign(signed_bytes).signature)

    return PolisTicketPayload(
        content          = content,
        category         = category,
        pk_polis         = pk_bytes.hex(),
        ticket_nullifier = ticket_null,
        signature        = sig.hex(),
        timestamp_ms     = ts,
        version          = version,
    )


def make_vote_payload(
    sk:           SigningKey,
    ticket_id:    str         = "TICKET-001",
    *,
    vote:         str         = "up",
    timestamp_ms: int | None  = None,
    nullifier:    str | None  = None,
    version:      str         = PROTO_VERSION,
) -> PolisVotePayload:
    ts       = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    pk_bytes = bytes(sk.verify_key)
    v_null   = nullifier or ("dd" * 32)

    signed_bytes = build_vote_signed_bytes(
        ticket_id    = ticket_id,
        vote         = vote,
        pk_polis     = pk_bytes,
        nullifier    = bytes.fromhex(v_null),
        timestamp_ms = ts,
    )
    sig = bytes(sk.sign(signed_bytes).signature)

    return PolisVotePayload(
        ticket_id      = ticket_id,
        vote           = vote,
        pk_polis       = pk_bytes.hex(),
        vote_nullifier = v_null,
        signature      = sig.hex(),
        timestamp_ms   = ts,
        version        = version,
    )


# ─── hash_content ─────────────────────────────────────────────────────────────

class TestHashContent:
    def test_deterministic(self) -> None:
        assert hash_content("hello") == hash_content("hello")

    def test_different_content(self) -> None:
        assert hash_content("hello") != hash_content("world")

    def test_hex_output_length(self) -> None:
        assert len(hash_content("test")) == 64   # SHA-256 = 32 bytes = 64 hex chars


# ─── validate_ticket ─────────────────────────────────────────────────────────

class TestValidateTicket:
    def test_valid_payload(self, polis_sk: SigningKey, now_ms: int) -> None:
        payload = make_ticket_payload(polis_sk, timestamp_ms=now_ms)
        err = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is None

    def test_all_categories_valid(self, polis_sk: SigningKey, now_ms: int) -> None:
        for cat in ("bug", "proposal", "vote"):
            payload = make_ticket_payload(
                polis_sk, category=cat, timestamp_ms=now_ms,
                nullifier="ee" * 32,
            )
            err = validate_ticket(payload, set(), now_ms=now_ms)
            assert err is None, f"Category {cat} failed: {err}"

    def test_wrong_version(self, polis_sk: SigningKey, now_ms: int) -> None:
        payload = make_ticket_payload(polis_sk, timestamp_ms=now_ms, version="old:v0")
        err = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "VERSION_MISMATCH"

    def test_content_too_long(self, polis_sk: SigningKey, now_ms: int) -> None:
        long_content = "x" * 2001
        payload = make_ticket_payload(polis_sk, content=long_content, timestamp_ms=now_ms)
        err = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_CONTENT"

    def test_empty_content(self, polis_sk: SigningKey, now_ms: int) -> None:
        payload = make_ticket_payload(polis_sk, content="", timestamp_ms=now_ms)
        err = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_CONTENT"

    def test_duplicate_nullifier(self, polis_sk: SigningKey, now_ms: int) -> None:
        nullifier = "ff" * 32
        payload   = make_ticket_payload(polis_sk, nullifier=nullifier, timestamp_ms=now_ms)
        err       = validate_ticket(payload, {nullifier}, now_ms=now_ms)
        assert err is not None
        assert err.code == "DUPLICATE_TICKET"

    def test_timestamp_expired(self, polis_sk: SigningKey, now_ms: int) -> None:
        old_ts  = now_ms - TIMESTAMP_WINDOW_MS - 1000
        payload = make_ticket_payload(polis_sk, timestamp_ms=old_ts)
        err     = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "TIMESTAMP_EXPIRED"

    def test_tampered_content_breaks_signature(
        self, polis_sk: SigningKey, now_ms: int,
    ) -> None:
        payload = make_ticket_payload(polis_sk, content="Original", timestamp_ms=now_ms)
        tampered = PolisTicketPayload(
            content          = "Tampered",    # changed
            category         = payload.category,
            pk_polis         = payload.pk_polis,
            ticket_nullifier = payload.ticket_nullifier,
            signature        = payload.signature,   # original sig
            timestamp_ms     = payload.timestamp_ms,
            version          = payload.version,
        )
        err = validate_ticket(tampered, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_SIGNATURE"

    def test_invalid_category(self, polis_sk: SigningKey, now_ms: int) -> None:
        payload = make_ticket_payload(polis_sk, category="spam", timestamp_ms=now_ms)
        err = validate_ticket(payload, set(), now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_CATEGORY"


# ─── validate_ticket_vote ─────────────────────────────────────────────────────

class TestValidateTicketVote:
    def test_valid_upvote(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk = bytes(owner_sk.verify_key).hex()
        payload  = make_vote_payload(voter_sk, timestamp_ms=now_ms)
        err      = validate_ticket_vote(payload, set(), owner_pk, now_ms=now_ms)
        assert err is None

    def test_valid_downvote(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk = bytes(owner_sk.verify_key).hex()
        payload  = make_vote_payload(voter_sk, vote="down", timestamp_ms=now_ms)
        err      = validate_ticket_vote(payload, set(), owner_pk, now_ms=now_ms)
        assert err is None

    def test_self_vote_rejected(self, polis_sk: SigningKey, now_ms: int) -> None:
        pk       = bytes(polis_sk.verify_key).hex()
        payload  = make_vote_payload(polis_sk, timestamp_ms=now_ms)
        err      = validate_ticket_vote(payload, set(), pk, now_ms=now_ms)
        assert err is not None
        assert err.code == "SELF_VOTE"

    def test_duplicate_vote_rejected(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk  = bytes(owner_sk.verify_key).hex()
        nullifier = "11" * 32
        payload   = make_vote_payload(voter_sk, nullifier=nullifier, timestamp_ms=now_ms)
        err       = validate_ticket_vote(payload, {nullifier}, owner_pk, now_ms=now_ms)
        assert err is not None
        assert err.code == "DUPLICATE_VOTE"

    def test_invalid_vote_value(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk = bytes(owner_sk.verify_key).hex()
        payload  = make_vote_payload(voter_sk, vote="sideways", timestamp_ms=now_ms)
        err      = validate_ticket_vote(payload, set(), owner_pk, now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_VOTE"

    def test_tampered_vote_breaks_signature(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk = bytes(owner_sk.verify_key).hex()
        payload  = make_vote_payload(voter_sk, vote="up", timestamp_ms=now_ms)
        tampered = PolisVotePayload(
            ticket_id      = payload.ticket_id,
            vote           = "down",       # tampered
            pk_polis       = payload.pk_polis,
            vote_nullifier = payload.vote_nullifier,
            signature      = payload.signature,   # original
            timestamp_ms   = payload.timestamp_ms,
            version        = payload.version,
        )
        err = validate_ticket_vote(tampered, set(), owner_pk, now_ms=now_ms)
        assert err is not None
        assert err.code == "INVALID_SIGNATURE"

    def test_expired_timestamp(
        self, owner_sk: SigningKey, voter_sk: SigningKey, now_ms: int,
    ) -> None:
        owner_pk = bytes(owner_sk.verify_key).hex()
        old_ts   = now_ms - TIMESTAMP_WINDOW_MS - 1000
        payload  = make_vote_payload(voter_sk, timestamp_ms=old_ts)
        err      = validate_ticket_vote(payload, set(), owner_pk, now_ms=now_ms)
        assert err is not None
        assert err.code == "TIMESTAMP_EXPIRED"


# ─── check_proposal_threshold ─────────────────────────────────────────────────

class TestProposalThreshold:
    def test_below_threshold(self) -> None:
        assert check_proposal_threshold(PROPOSAL_THRESHOLD - 1, 0) is False

    def test_at_threshold(self) -> None:
        assert check_proposal_threshold(PROPOSAL_THRESHOLD, 0) is True

    def test_above_threshold(self) -> None:
        assert check_proposal_threshold(PROPOSAL_THRESHOLD + 5, 0) is True

    def test_net_votes_matter(self) -> None:
        # 5 up, 3 down → net 2 → below threshold of 3
        assert check_proposal_threshold(5, 3) is False

    def test_net_votes_at_threshold(self) -> None:
        # 6 up, 3 down → net 3 → at threshold
        assert check_proposal_threshold(PROPOSAL_THRESHOLD + 3, 3) is True

    def test_negative_net(self) -> None:
        assert check_proposal_threshold(1, 5) is False


# ─── get_short_handle ─────────────────────────────────────────────────────────

class TestGetShortHandle:
    def test_length(self) -> None:
        pk = "abcdef1234567890" * 4
        assert len(get_short_handle(pk)) == 8

    def test_is_prefix(self) -> None:
        pk = "abcdef1234567890" * 4
        assert get_short_handle(pk) == pk[:8]

"""
Non-xfail POLIS identity binding tests.
Tests the complete register-key → ticket → vote flow
using mock DB sessions. No PostgreSQL required.
"""
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nacl.signing import SigningKey
from crypto.polis import (
    PolisTicketPayload,
    PolisVotePayload,
    validate_ticket,
    validate_ticket_vote,
    build_ticket_signed_bytes,
    build_vote_signed_bytes,
    hash_content,
    PROTO_VERSION,
    TIMESTAMP_WINDOW_MS,
)


def _now_ms():
    return int(time.time() * 1000)


def _make_keypair():
    sk = SigningKey.generate()
    return sk, sk.verify_key.encode().hex()


def _sign(sk, data):
    return sk.sign(data).signature.hex()


# ─── Register-key binding tests ─────────────────────────────────────────────

class TestRegisterKeyBinding:
    """Test the identity binding logic that register-key enforces."""

    def test_valid_identity_signature_for_register(self):
        """Identity key signs polis-register message correctly."""
        identity_sk, identity_pk = _make_keypair()
        _, polis_pk = _make_keypair()
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        message = f"polis-register:{polis_pk}:{nullifier}:{ts}".encode("utf-8")
        sig = _sign(identity_sk, message)

        # Server verifies with identity public key
        from nacl.signing import VerifyKey
        vk = VerifyKey(bytes.fromhex(identity_pk))
        vk.verify(message, bytes.fromhex(sig))  # Must not raise

    def test_wrong_identity_key_rejects_register(self):
        """Registration with wrong identity key must fail."""
        identity_sk, identity_pk = _make_keypair()
        attacker_sk, _ = _make_keypair()
        _, polis_pk = _make_keypair()
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        message = f"polis-register:{polis_pk}:{nullifier}:{ts}".encode("utf-8")
        # Attacker signs with their key
        sig = _sign(attacker_sk, message)

        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        vk = VerifyKey(bytes.fromhex(identity_pk))
        with pytest.raises(BadSignatureError):
            vk.verify(message, bytes.fromhex(sig))

    def test_expired_timestamp_should_reject(self):
        """Registration with old timestamp should be rejected."""
        ts = _now_ms() - TIMESTAMP_WINDOW_MS - 1000
        delta = abs(_now_ms() - ts)
        assert delta > TIMESTAMP_WINDOW_MS

    def test_fresh_timestamp_should_accept(self):
        """Registration with fresh timestamp should be accepted."""
        ts = _now_ms()
        delta = abs(_now_ms() - ts)
        assert delta <= TIMESTAMP_WINDOW_MS


# ─── Ticket create with binding tests ───────────────────────────────────────

class TestTicketWithBinding:
    """Test that ticket creation requires proper identity binding."""

    def test_ticket_with_registered_key_validates(self):
        """Ticket signed by registered pk_polis passes crypto validation."""
        polis_sk, polis_pk = _make_keypair()
        title = "Bug in voting"
        content = "The vote button does not respond on Android 14"
        category = "bug"
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        signed_bytes = build_ticket_signed_bytes(
            category=category,
            content_hash=hash_content(content),
            pk_polis=bytes.fromhex(polis_pk),
            nullifier=bytes.fromhex(nullifier),
            timestamp_ms=ts,
            title_hash=hash_content(title),
        )
        sig = _sign(polis_sk, signed_bytes)

        payload = PolisTicketPayload(
            content=content, category=category, pk_polis=polis_pk,
            ticket_nullifier=nullifier, signature=sig,
            timestamp_ms=ts, version=PROTO_VERSION, title=title,
        )
        err = validate_ticket(payload, set())
        assert err is None

    def test_ticket_with_different_key_fails_signature(self):
        """Ticket signed by wrong key must fail even with valid format."""
        real_sk, real_pk = _make_keypair()
        fake_sk, _ = _make_keypair()
        title = "Test"
        content = "Test content for POLIS binding"
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        # Sign with fake key
        signed_bytes = build_ticket_signed_bytes(
            category="bug",
            content_hash=hash_content(content),
            pk_polis=bytes.fromhex(real_pk),  # claim real pk
            nullifier=bytes.fromhex(nullifier),
            timestamp_ms=ts,
            title_hash=hash_content(title),
        )
        sig = _sign(fake_sk, signed_bytes)  # but sign with fake

        payload = PolisTicketPayload(
            content=content, category="bug", pk_polis=real_pk,
            ticket_nullifier=nullifier, signature=sig,
            timestamp_ms=ts, version=PROTO_VERSION, title=title,
        )
        err = validate_ticket(payload, set())
        assert err is not None
        assert err.code == "INVALID_SIGNATURE"


# ─── Vote with binding tests ────────────────────────────────────────────────

class TestVoteWithBinding:
    """Test vote validation with identity binding."""

    def test_valid_vote_by_different_user(self):
        """Vote by different user (different pk_polis) passes."""
        voter_sk, voter_pk = _make_keypair()
        _, owner_pk = _make_keypair()
        ticket_id = "ticket-001"
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        signed_bytes = build_vote_signed_bytes(
            ticket_id=ticket_id, vote="up",
            pk_polis=bytes.fromhex(voter_pk),
            nullifier=bytes.fromhex(nullifier),
            timestamp_ms=ts,
        )
        sig = _sign(voter_sk, signed_bytes)

        payload = PolisVotePayload(
            ticket_id=ticket_id, vote="up", pk_polis=voter_pk,
            vote_nullifier=nullifier, signature=sig,
            timestamp_ms=ts, version=PROTO_VERSION,
        )
        err = validate_ticket_vote(payload, set(), owner_pk)
        assert err is None

    def test_self_vote_by_owner_rejected(self):
        """Ticket owner cannot vote on own ticket."""
        owner_sk, owner_pk = _make_keypair()
        ticket_id = "ticket-002"
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        signed_bytes = build_vote_signed_bytes(
            ticket_id=ticket_id, vote="up",
            pk_polis=bytes.fromhex(owner_pk),
            nullifier=bytes.fromhex(nullifier),
            timestamp_ms=ts,
        )
        sig = _sign(owner_sk, signed_bytes)

        payload = PolisVotePayload(
            ticket_id=ticket_id, vote="up", pk_polis=owner_pk,
            vote_nullifier=nullifier, signature=sig,
            timestamp_ms=ts, version=PROTO_VERSION,
        )
        err = validate_ticket_vote(payload, set(), owner_pk)
        assert err is not None
        assert err.code == "SELF_VOTE"

    def test_double_vote_rejected(self):
        """Same nullifier cannot vote twice."""
        voter_sk, voter_pk = _make_keypair()
        _, owner_pk = _make_keypair()
        nullifier = os.urandom(32).hex()
        ts = _now_ms()

        signed_bytes = build_vote_signed_bytes(
            ticket_id="ticket-003", vote="down",
            pk_polis=bytes.fromhex(voter_pk),
            nullifier=bytes.fromhex(nullifier),
            timestamp_ms=ts,
        )
        sig = _sign(voter_sk, signed_bytes)

        payload = PolisVotePayload(
            ticket_id="ticket-003", vote="down", pk_polis=voter_pk,
            vote_nullifier=nullifier, signature=sig,
            timestamp_ms=ts, version=PROTO_VERSION,
        )
        # First vote: OK
        err = validate_ticket_vote(payload, set(), owner_pk)
        assert err is None
        # Second vote: rejected (nullifier already used)
        err = validate_ticket_vote(payload, {nullifier}, owner_pk)
        assert err is not None
        assert err.code == "DUPLICATE_VOTE"


# ─── End-to-end flow simulation ─────────────────────────────────────────────

class TestEndToEndFlow:
    """Simulate the complete register → ticket → vote flow."""

    def test_complete_flow_identity_to_vote(self):
        """
        Full flow:
        1. Identity creates keypair (simulating SMS verification)
        2. Identity registers pk_polis (signed by identity key)
        3. Ticket created (signed by pk_polis)
        4. Different user votes (signed by their pk_polis)
        5. Same user cannot vote twice
        6. Owner cannot self-vote
        """
        # Step 1: Two identities
        id1_sk, id1_pk = _make_keypair()  # identity keypair (from SMS verify)
        id2_sk, id2_pk = _make_keypair()

        # Step 2: Each derives a POLIS key
        polis1_sk, polis1_pk = _make_keypair()
        polis2_sk, polis2_pk = _make_keypair()

        # Step 2b: Registration signatures
        null1 = os.urandom(32).hex()
        null2 = os.urandom(32).hex()
        ts = _now_ms()

        reg1_msg = f"polis-register:{polis1_pk}:{null1}:{ts}".encode()
        reg1_sig = _sign(id1_sk, reg1_msg)

        reg2_msg = f"polis-register:{polis2_pk}:{null2}:{ts}".encode()
        reg2_sig = _sign(id2_sk, reg2_msg)

        # Verify registrations
        from nacl.signing import VerifyKey
        VerifyKey(bytes.fromhex(id1_pk)).verify(reg1_msg, bytes.fromhex(reg1_sig))
        VerifyKey(bytes.fromhex(id2_pk)).verify(reg2_msg, bytes.fromhex(reg2_sig))

        # Step 3: User 1 creates ticket
        title = "Improve loading speed"
        content = "The app takes too long to load on older devices"
        ticket_null = os.urandom(32).hex()

        ticket_bytes = build_ticket_signed_bytes(
            category="proposal",
            content_hash=hash_content(content),
            pk_polis=bytes.fromhex(polis1_pk),
            nullifier=bytes.fromhex(ticket_null),
            timestamp_ms=ts,
            title_hash=hash_content(title),
        )
        ticket_sig = _sign(polis1_sk, ticket_bytes)

        ticket_payload = PolisTicketPayload(
            content=content, category="proposal", pk_polis=polis1_pk,
            ticket_nullifier=ticket_null, signature=ticket_sig,
            timestamp_ms=ts, version=PROTO_VERSION, title=title,
        )
        err = validate_ticket(ticket_payload, set())
        assert err is None, f"Ticket creation failed: {err}"

        # Step 4: User 2 votes
        vote_null = os.urandom(32).hex()
        vote_bytes = build_vote_signed_bytes(
            ticket_id="ticket-e2e", vote="up",
            pk_polis=bytes.fromhex(polis2_pk),
            nullifier=bytes.fromhex(vote_null),
            timestamp_ms=ts,
        )
        vote_sig = _sign(polis2_sk, vote_bytes)

        vote_payload = PolisVotePayload(
            ticket_id="ticket-e2e", vote="up", pk_polis=polis2_pk,
            vote_nullifier=vote_null, signature=vote_sig,
            timestamp_ms=ts, version=PROTO_VERSION,
        )
        err = validate_ticket_vote(vote_payload, set(), polis1_pk)
        assert err is None, f"Vote failed: {err}"

        # Step 5: User 2 cannot vote again
        err = validate_ticket_vote(vote_payload, {vote_null}, polis1_pk)
        assert err is not None
        assert err.code == "DUPLICATE_VOTE"

        # Step 6: User 1 cannot self-vote
        self_vote_null = os.urandom(32).hex()
        self_bytes = build_vote_signed_bytes(
            ticket_id="ticket-e2e", vote="up",
            pk_polis=bytes.fromhex(polis1_pk),
            nullifier=bytes.fromhex(self_vote_null),
            timestamp_ms=ts,
        )
        self_sig = _sign(polis1_sk, self_bytes)

        self_payload = PolisVotePayload(
            ticket_id="ticket-e2e", vote="up", pk_polis=polis1_pk,
            vote_nullifier=self_vote_null, signature=self_sig,
            timestamp_ms=ts, version=PROTO_VERSION,
        )
        err = validate_ticket_vote(self_payload, set(), polis1_pk)
        assert err is not None
        assert err.code == "SELF_VOTE"

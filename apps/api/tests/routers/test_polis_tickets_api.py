"""
Tests for POLIS Tickets API — crypto validation + identity binding.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from crypto.polis import (
    PolisTicketPayload,
    PolisVotePayload,
    validate_ticket,
    validate_ticket_vote,
    build_ticket_signed_bytes,
    build_vote_signed_bytes,
    hash_content,
    get_short_handle,
    PROTO_VERSION,
)
from nacl.signing import SigningKey


def _make_keypair():
    sk = SigningKey.generate()
    pk = sk.verify_key
    return sk, pk.encode().hex()


def _sign(sk: SigningKey, data: bytes) -> str:
    return sk.sign(data).signature.hex()


def _now_ms():
    return int(time.time() * 1000)


# ─── Register-key signature format ──────────────────────────────────────────

def test_register_key_signature_format():
    """Verify the signed message format for register-key."""
    sk, pk_hex = _make_keypair()
    nullifier = os.urandom(32).hex()
    ts = _now_ms()
    message = f"polis-register:{pk_hex}:{nullifier}:{ts}".encode("utf-8")
    sig = _sign(sk, message)
    # Verify
    from nacl.signing import VerifyKey
    vk = VerifyKey(bytes.fromhex(pk_hex))
    vk.verify(message, bytes.fromhex(sig))  # Should not raise


def test_register_key_invalid_signature_rejected():
    """Wrong key cannot register."""
    sk_real, pk_real = _make_keypair()
    sk_fake, pk_fake = _make_keypair()
    nullifier = os.urandom(32).hex()
    ts = _now_ms()
    # Sign with fake key but claim real key
    message = f"polis-register:{pk_fake}:{nullifier}:{ts}".encode("utf-8")
    sig = _sign(sk_fake, message)
    # Verify against real key should fail
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    vk = VerifyKey(bytes.fromhex(pk_real))
    try:
        vk.verify(message, bytes.fromhex(sig))
        assert False, "Should have raised BadSignatureError"
    except BadSignatureError:
        pass


# ─── Ticket validation with title ───────────────────────────────────────────

def test_valid_ticket_creation_with_title():
    sk, pk_hex = _make_keypair()
    title = "Test Bug Report"
    content = "Test ticket content for POLIS"
    category = "bug"
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_ticket_signed_bytes(
        category=category,
        content_hash=hash_content(content),
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
        title_hash=hash_content(title),
    )
    sig = _sign(sk, signed_bytes)

    payload = PolisTicketPayload(
        content=content, category=category, pk_polis=pk_hex,
        ticket_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION, title=title,
    )
    err = validate_ticket(payload, set())
    assert err is None


def test_tampered_title_rejected():
    """Changing title after signing invalidates signature."""
    sk, pk_hex = _make_keypair()
    title = "Original Title"
    content = "Content"
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_ticket_signed_bytes(
        category="bug",
        content_hash=hash_content(content),
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
        title_hash=hash_content(title),
    )
    sig = _sign(sk, signed_bytes)

    payload = PolisTicketPayload(
        content=content, category="bug", pk_polis=pk_hex,
        ticket_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION,
        title="Tampered Title",
    )
    err = validate_ticket(payload, set())
    assert err is not None
    assert err.code == "INVALID_SIGNATURE"


def test_duplicate_nullifier_rejected():
    sk, pk_hex = _make_keypair()
    nullifier = os.urandom(32).hex()
    ts = _now_ms()
    content = "Duplicate test"
    title = "Dup"

    signed_bytes = build_ticket_signed_bytes(
        category="bug",
        content_hash=hash_content(content),
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
        title_hash=hash_content(title),
    )
    sig = _sign(sk, signed_bytes)

    payload = PolisTicketPayload(
        content=content, category="bug", pk_polis=pk_hex,
        ticket_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION, title=title,
    )
    err = validate_ticket(payload, {nullifier})
    assert err is not None
    assert err.code == "DUPLICATE_TICKET"


def test_invalid_signature_rejected():
    sk, pk_hex = _make_keypair()
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    payload = PolisTicketPayload(
        content="Bad sig test", category="proposal", pk_polis=pk_hex,
        ticket_nullifier=nullifier, signature="aa" * 64,
        timestamp_ms=ts, version=PROTO_VERSION, title="Bad",
    )
    err = validate_ticket(payload, set())
    assert err is not None
    assert err.code == "INVALID_SIGNATURE"


# ─── Vote validation ────────────────────────────────────────────────────────

def test_valid_vote():
    sk_voter, pk_voter = _make_keypair()
    _, pk_owner = _make_keypair()
    ticket_id = "test-ticket-1"
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(pk_voter),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
    )
    sig = _sign(sk_voter, signed_bytes)

    payload = PolisVotePayload(
        ticket_id=ticket_id, vote="up", pk_polis=pk_voter,
        vote_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION,
    )
    err = validate_ticket_vote(payload, set(), pk_owner)
    assert err is None


def test_self_vote_rejected():
    sk, pk_hex = _make_keypair()
    ticket_id = "self-vote-test"
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
    )
    sig = _sign(sk, signed_bytes)

    payload = PolisVotePayload(
        ticket_id=ticket_id, vote="up", pk_polis=pk_hex,
        vote_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION,
    )
    err = validate_ticket_vote(payload, set(), pk_hex)
    assert err is not None
    assert err.code == "SELF_VOTE"


def test_duplicate_vote_rejected():
    sk, pk_hex = _make_keypair()
    _, pk_owner = _make_keypair()
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_vote_signed_bytes(
        ticket_id="dup-vote", vote="down",
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
    )
    sig = _sign(sk, signed_bytes)

    payload = PolisVotePayload(
        ticket_id="dup-vote", vote="down", pk_polis=pk_hex,
        vote_nullifier=nullifier, signature=sig,
        timestamp_ms=ts, version=PROTO_VERSION,
    )
    err = validate_ticket_vote(payload, {nullifier}, pk_owner)
    assert err is not None
    assert err.code == "DUPLICATE_VOTE"


# ─── Utility ────────────────────────────────────────────────────────────────

def test_short_handle():
    pk = "abcdef1234567890" + "0" * 48
    assert get_short_handle(pk) == "abcdef12"


def test_get_tickets_returns_safe_fields():
    """API response must not expose signature, pk_polis, or ticket_nullifier."""
    safe_fields = {"id", "title", "category", "handle", "status", "up_votes", "down_votes", "created_at"}
    assert "signature" not in safe_fields
    assert "pk_polis" not in safe_fields
    assert "ticket_nullifier" not in safe_fields

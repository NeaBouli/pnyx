"""
polis.py
========
Server-side POLIS ticket crypto for ekklesia.gr.

Responsibilities:
  - Validate ticket creation payloads
  - Validate ticket vote payloads
  - Enforce nullifier uniqueness (no duplicate tickets / no double votes)
  - Manage reputation via persistent pk_polis
  - Enforce 3-vote-threshold for proposals
"""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass
from typing import Literal

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# ─── Constants ────────────────────────────────────────────────────────────────

PROTO_VERSION       = "ekklesia:v1"
TIMESTAMP_WINDOW_MS = 300_000   # 5 minutes
MAX_CONTENT_LEN     = 2000      # characters
MAX_TICKET_ID_LEN   = 64
HEX_32_LEN          = 64
HEX_64_LEN          = 128

PROPOSAL_THRESHOLD  = 3         # min up-votes for proposal to be promoted
SPAM_BLOCK_COUNT    = 5         # max rejected tickets per pk_polis per 24h

TicketCategory = Literal["bug", "proposal", "vote"]
TicketVote     = Literal["up", "down"]

VOTE_MAP: dict[str, int] = {"up": 1, "down": 2}


# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PolisTicketPayload:
    content:          str
    category:         TicketCategory
    pk_polis:         str   # 64-char hex — persistent per identity
    ticket_nullifier: str   # 64-char hex
    signature:        str   # 128-char hex
    timestamp_ms:     int
    version:          str


@dataclass(frozen=True)
class PolisVotePayload:
    ticket_id:      str
    vote:           TicketVote
    pk_polis:       str
    vote_nullifier: str
    signature:      str
    timestamp_ms:   int
    version:        str


@dataclass(frozen=True)
class ValidationError:
    code:    str
    message: str


# ─── Canonical payload builders (mirror client) ───────────────────────────────

def build_ticket_signed_bytes(
    category:     TicketCategory,
    content_hash: str,           # hex string of SHA-256(content)
    pk_polis:     bytes,
    nullifier:    bytes,
    timestamp_ms: int,
) -> bytes:
    """
    Builds the canonical bytes for ticket creation signature.
    Must exactly mirror polis.ts::buildTicketSignedBytes.

    Layout: version(1B) | category_len(1B) | category | content_hash(32B) |
            pk_polis(32B) | nullifier(32B) | timestamp(8B BE)
    """
    cat_bytes  = category.encode("utf-8")
    ch_bytes   = bytes.fromhex(content_hash)
    return (
        b"\x01"
        + bytes([len(cat_bytes)])
        + cat_bytes
        + ch_bytes
        + pk_polis
        + nullifier
        + struct.pack(">Q", timestamp_ms)
    )


def build_vote_signed_bytes(
    ticket_id:   str,
    vote:        TicketVote,
    pk_polis:    bytes,
    nullifier:   bytes,
    timestamp_ms: int,
) -> bytes:
    """
    Builds the canonical bytes for a ticket vote signature.
    Must exactly mirror polis.ts::buildVoteSignedBytes.

    Layout: version(1B) | ticket_id_len(2B BE) | ticket_id | vote(1B) |
            pk_polis(32B) | vote_nullifier(32B) | timestamp(8B BE)
    """
    ticket_bytes = ticket_id.encode("utf-8")
    return (
        b"\x01"
        + struct.pack(">H", len(ticket_bytes))
        + ticket_bytes
        + bytes([VOTE_MAP[vote]])
        + pk_polis
        + nullifier
        + struct.pack(">Q", timestamp_ms)
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_hex(s: str, expected_len: int) -> bool:
    if len(s) != expected_len:
        return False
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False


def _now_ms() -> int:
    return int(time.time() * 1000)


def hash_content(content: str) -> str:
    """SHA-256 of content as hex string. Mirrors polis.ts::hashContent."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ─── Ticket validation ────────────────────────────────────────────────────────

def validate_ticket(
    payload:              PolisTicketPayload,
    existing_nullifiers:  set[str],
    *,
    now_ms:               int | None = None,
) -> ValidationError | None:
    """
    Full server-side validation of a ticket creation payload.

    Checks (in order):
      1. Protocol version
      2. Content length and field formats
      3. Timestamp freshness
      4. Ticket nullifier uniqueness (no duplicate content from same identity)
      5. Ed25519 signature validity

    Args:
        payload:             The PolisTicketPayload from the client.
        existing_nullifiers: Set of ticket_nullifiers already in the DB.
        now_ms:              Current time ms (injectable for tests).

    Returns:
        None on success, ValidationError on failure.
    """
    # 1. Version
    if payload.version != PROTO_VERSION:
        return ValidationError("VERSION_MISMATCH", f"Expected {PROTO_VERSION}")

    # 2. Content
    if not payload.content or len(payload.content) > MAX_CONTENT_LEN:
        return ValidationError("INVALID_CONTENT", f"Content must be 1–{MAX_CONTENT_LEN} chars")

    if payload.category not in ("bug", "proposal", "vote"):
        return ValidationError("INVALID_CATEGORY", f"Unknown category: {payload.category}")

    for field, value in [
        ("pk_polis",         payload.pk_polis),
        ("ticket_nullifier", payload.ticket_nullifier),
    ]:
        if not _is_hex(value, HEX_32_LEN):
            return ValidationError("INVALID_HEX", f"{field} must be 64-char hex")

    if not _is_hex(payload.signature, HEX_64_LEN):
        return ValidationError("INVALID_SIGNATURE_FORMAT", "signature must be 128-char hex")

    # 3. Timestamp freshness
    now   = now_ms if now_ms is not None else _now_ms()
    delta = abs(now - payload.timestamp_ms)
    if delta > TIMESTAMP_WINDOW_MS:
        return ValidationError("TIMESTAMP_EXPIRED", f"Timestamp delta {delta}ms exceeds window")

    # 4. Nullifier uniqueness
    if payload.ticket_nullifier in existing_nullifiers:
        return ValidationError("DUPLICATE_TICKET", "Identical ticket already submitted")

    # 5. Ed25519 signature
    content_hash = hash_content(payload.content)
    try:
        pk_bytes  = bytes.fromhex(payload.pk_polis)
        sig_bytes = bytes.fromhex(payload.signature)
        vk        = VerifyKey(pk_bytes)

        signed_bytes = build_ticket_signed_bytes(
            category     = payload.category,
            content_hash = content_hash,
            pk_polis     = pk_bytes,
            nullifier    = bytes.fromhex(payload.ticket_nullifier),
            timestamp_ms = payload.timestamp_ms,
        )
        vk.verify(signed_bytes, sig_bytes)

    except BadSignatureError:
        return ValidationError("INVALID_SIGNATURE", "Ed25519 signature verification failed")
    except Exception as e:
        return ValidationError("CRYPTO_ERROR", f"Crypto error: {type(e).__name__}")

    return None


# ─── Vote validation ─────────────────────────────────────────────────────────

def validate_ticket_vote(
    payload:             PolisVotePayload,
    existing_nullifiers: set[str],
    ticket_owner_pk:     str,
    *,
    now_ms:              int | None = None,
) -> ValidationError | None:
    """
    Full server-side validation of a ticket vote payload.

    Checks (in order):
      1. Protocol version
      2. Field formats
      3. Timestamp freshness
      4. Self-vote prevention (pk_polis != ticket_owner_pk)
      5. Vote nullifier uniqueness
      6. Ed25519 signature validity

    Args:
        payload:             The PolisVotePayload from the client.
        existing_nullifiers: Set of vote_nullifiers already used for this ticket.
        ticket_owner_pk:     pk_polis of the ticket creator (prevent self-voting).
        now_ms:              Current time ms (injectable for tests).

    Returns:
        None on success, ValidationError on failure.
    """
    # 1. Version
    if payload.version != PROTO_VERSION:
        return ValidationError("VERSION_MISMATCH", f"Expected {PROTO_VERSION}")

    # 2. Field formats
    if not payload.ticket_id or len(payload.ticket_id) > MAX_TICKET_ID_LEN:
        return ValidationError("INVALID_TICKET_ID", "ticket_id invalid")

    if payload.vote not in ("up", "down"):
        return ValidationError("INVALID_VOTE", f"Unknown vote: {payload.vote}")

    for field, value in [
        ("pk_polis",       payload.pk_polis),
        ("vote_nullifier", payload.vote_nullifier),
    ]:
        if not _is_hex(value, HEX_32_LEN):
            return ValidationError("INVALID_HEX", f"{field} must be 64-char hex")

    if not _is_hex(payload.signature, HEX_64_LEN):
        return ValidationError("INVALID_SIGNATURE_FORMAT", "signature must be 128-char hex")

    # 3. Timestamp freshness
    now   = now_ms if now_ms is not None else _now_ms()
    delta = abs(now - payload.timestamp_ms)
    if delta > TIMESTAMP_WINDOW_MS:
        return ValidationError("TIMESTAMP_EXPIRED", f"Timestamp delta {delta}ms exceeds window")

    # 4. Self-vote prevention
    if payload.pk_polis == ticket_owner_pk:
        return ValidationError("SELF_VOTE", "Cannot vote on own ticket")

    # 5. Vote nullifier uniqueness
    if payload.vote_nullifier in existing_nullifiers:
        return ValidationError("DUPLICATE_VOTE", "Already voted on this ticket")

    # 6. Ed25519 signature
    try:
        pk_bytes  = bytes.fromhex(payload.pk_polis)
        sig_bytes = bytes.fromhex(payload.signature)
        vk        = VerifyKey(pk_bytes)

        signed_bytes = build_vote_signed_bytes(
            ticket_id    = payload.ticket_id,
            vote         = payload.vote,
            pk_polis     = pk_bytes,
            nullifier    = bytes.fromhex(payload.vote_nullifier),
            timestamp_ms = payload.timestamp_ms,
        )
        vk.verify(signed_bytes, sig_bytes)

    except BadSignatureError:
        return ValidationError("INVALID_SIGNATURE", "Ed25519 signature verification failed")
    except Exception as e:
        return ValidationError("CRYPTO_ERROR", f"Crypto error: {type(e).__name__}")

    return None


# ─── Threshold check ─────────────────────────────────────────────────────────

def check_proposal_threshold(up_votes: int, down_votes: int) -> bool:
    """
    Returns True if a proposal has reached the promotion threshold.

    Threshold: ≥ PROPOSAL_THRESHOLD net up-votes (up - down).
    Community can configure this in a future governance vote.
    """
    return (up_votes - down_votes) >= PROPOSAL_THRESHOLD


# ─── Reputation helpers ───────────────────────────────────────────────────────

def get_short_handle(pk_polis_hex: str) -> str:
    """First 8 chars of pk_polis — used as display handle in ticket board."""
    return pk_polis_hex[:8]

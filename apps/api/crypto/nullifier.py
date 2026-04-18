"""
Server-side validation for Tier 1 HMAC-Nullifier-Chain voting protocol.

Validates:
  - Registration payloads (identity_commitment)
  - Vote payloads (ephemeral key + Ed25519 signature + vote_nullifier)
  - Issues VoteReceipts (server-signed acknowledgement)

Does NOT contain key derivation (that's client-side only).
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Set

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

# ── Protocol constants ────────────────────────────────────────────────────────

PROTO_VERSION = "ekklesia:v1"
TIMESTAMP_WINDOW_MS = 300_000  # 5 minutes
VALID_CHOICES = {"YES", "NO", "ABSTAIN"}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RegistrationPayload:
    identity_commitment: str  # 64-char hex (32 bytes)
    phone_region: str         # e.g. "GR"
    version: str


@dataclass
class VotePayload:
    bill_id: str
    choice: str               # YES | NO | ABSTAIN
    pk_eph: str               # 64-char hex — ephemeral public key
    vote_nullifier: str       # 64-char hex
    linkage_tag: str          # 64-char hex
    signature: str            # 128-char hex — Ed25519 sig
    timestamp_ms: int
    version: str


@dataclass
class VoteReceipt:
    bill_id: str
    vote_nullifier: str
    server_signature: str     # 128-char hex
    server_pk: str            # 64-char hex
    server_timestamp_ms: int


@dataclass
class ValidationError:
    code: str
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_hex(s: str, expected_len: int) -> bool:
    """Check if string is valid hex of expected length."""
    if len(s) != expected_len:
        return False
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False


# ── Canonical payload builder ─────────────────────────────────────────────────

def build_signed_payload(
    *,
    bill_id: str,
    choice: str,
    pk_eph: bytes,
    vote_nullifier: bytes,
    linkage_tag: bytes,
    timestamp_ms: int,
) -> bytes:
    """
    Build the canonical byte sequence that the client signs.
    Must match the TypeScript client implementation exactly.

    Format: bill_id_utf8 | choice_utf8 | pk_eph(32) | vote_nullifier(32) | linkage_tag(32) | timestamp_ms(big-endian u64)
    """
    return (
        bill_id.encode("utf-8")
        + choice.encode("utf-8")
        + pk_eph
        + vote_nullifier
        + linkage_tag
        + struct.pack(">Q", timestamp_ms)
    )


# ── Registration validation ──────────────────────────────────────────────────

def validate_registration(payload: RegistrationPayload) -> ValidationError | None:
    """Validate a registration payload. Returns None on success."""
    if payload.version != PROTO_VERSION:
        return ValidationError("VERSION_MISMATCH", f"Expected {PROTO_VERSION}")

    if not _is_hex(payload.identity_commitment, 64):
        return ValidationError("INVALID_COMMITMENT", "identity_commitment must be 64-char hex")

    if not payload.phone_region or len(payload.phone_region) < 2:
        return ValidationError("INVALID_REGION", "phone_region required (e.g. 'GR')")

    return None


# ── Vote validation ──────────────────────────────────────────────────────────

def validate_vote(
    payload: VotePayload,
    used_nullifiers: Set[str],
    *,
    now_ms: int | None = None,
) -> ValidationError | None:
    """
    Validate a vote payload. Returns None on success, ValidationError on failure.

    Checks: version, choice, bill_id, hex formats, timestamp window,
    duplicate nullifier, Ed25519 signature.
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    # Version
    if payload.version != PROTO_VERSION:
        return ValidationError("VERSION_MISMATCH", f"Expected {PROTO_VERSION}")

    # Bill ID
    if not payload.bill_id:
        return ValidationError("INVALID_BILL_ID", "bill_id required")

    # Choice
    if payload.choice not in VALID_CHOICES:
        return ValidationError("INVALID_CHOICE", f"Must be one of {VALID_CHOICES}")

    # Hex format checks
    for field, name in [
        (payload.pk_eph, "pk_eph"),
        (payload.vote_nullifier, "vote_nullifier"),
        (payload.linkage_tag, "linkage_tag"),
    ]:
        if not _is_hex(field, 64):
            return ValidationError("INVALID_HEX", f"{name} must be 64-char hex")

    if not _is_hex(payload.signature, 128):
        return ValidationError("INVALID_SIGNATURE_FORMAT", "signature must be 128-char hex")

    # Timestamp window
    delta = abs(now_ms - payload.timestamp_ms)
    if delta > TIMESTAMP_WINDOW_MS:
        return ValidationError("TIMESTAMP_EXPIRED", f"Timestamp delta {delta}ms exceeds window")

    # Duplicate nullifier
    if payload.vote_nullifier in used_nullifiers:
        return ValidationError("DUPLICATE_VOTE", "vote_nullifier already used")

    # Ed25519 signature verification
    try:
        vk = VerifyKey(bytes.fromhex(payload.pk_eph))
        signed_bytes = build_signed_payload(
            bill_id=payload.bill_id,
            choice=payload.choice,
            pk_eph=bytes.fromhex(payload.pk_eph),
            vote_nullifier=bytes.fromhex(payload.vote_nullifier),
            linkage_tag=bytes.fromhex(payload.linkage_tag),
            timestamp_ms=payload.timestamp_ms,
        )
        vk.verify(signed_bytes, bytes.fromhex(payload.signature))
    except BadSignatureError:
        return ValidationError("INVALID_SIGNATURE", "Ed25519 signature verification failed")
    except Exception as e:
        return ValidationError("CRYPTO_ERROR", f"Crypto error: {type(e).__name__}")

    return None


# ── VoteReceipt issuance ─────────────────────────────────────────────────────

def issue_receipt(
    bill_id: str,
    vote_nullifier: str,
    server_sk: SigningKey,
) -> VoteReceipt:
    """
    Issue a server-signed VoteReceipt (ADR-008).
    Proves the server acknowledged this vote at this time.
    """
    ts = int(time.time() * 1000)
    receipt_bytes = (
        bill_id.encode("utf-8")
        + bytes.fromhex(vote_nullifier)
        + struct.pack(">Q", ts)
    )
    signed = server_sk.sign(receipt_bytes)

    return VoteReceipt(
        bill_id=bill_id,
        vote_nullifier=vote_nullifier,
        server_signature=bytes(signed.signature).hex(),
        server_pk=bytes(server_sk.verify_key).hex(),
        server_timestamp_ms=ts,
    )

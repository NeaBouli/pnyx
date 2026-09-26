"""
Ed25519 Keypair Utilities
Signature verification for vote payloads and QR-Code auth.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)


class SignatureVerificationError(RuntimeError):
    """Unexpected Ed25519 verifier failure — never an ordinary invalid signature."""


def verify_signature(public_key_hex: str, payload: str | bytes, signature_hex: str) -> bool:
    """Verify Ed25519 signature. Returns True if valid, False if invalid/malformed.

    Mirror of packages/crypto/keypair.py (which shadows this module at runtime).
    Raises SignatureVerificationError on unexpected verifier/programming faults.
    """
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError

    if not isinstance(public_key_hex, str) or not isinstance(signature_hex, str):
        return False
    try:
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        message = payload.encode("utf-8") if isinstance(payload, str) else payload
        signature = bytes.fromhex(signature_hex)
        vk.verify(message, signature)
        return True
    except (BadSignatureError, ValueError):
        return False
    except Exception as exc:
        logger.error("Ed25519 verifier failure: %s", type(exc).__name__)
        raise SignatureVerificationError(type(exc).__name__) from exc


def verify_challenge(public_key_hex: str, challenge: str, signature_hex: str) -> bool:
    """Verify Ed25519 signature on a challenge string (for QR auth)."""
    return verify_signature(public_key_hex, challenge, signature_hex)

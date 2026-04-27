"""
Ed25519 Keypair Utilities
Signature verification for vote payloads and QR-Code auth.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)


def verify_signature(public_key_hex: str, payload: str, signature_hex: str) -> bool:
    """Verify Ed25519 signature. Returns True if valid."""
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError

        vk = VerifyKey(bytes.fromhex(public_key_hex))
        message = payload.encode("utf-8") if isinstance(payload, str) else payload
        signature = bytes.fromhex(signature_hex)
        vk.verify(message, signature)
        return True
    except (BadSignatureError, Exception) as e:
        logger.warning("Signature verification failed: %s", e)
        return False


def verify_challenge(public_key_hex: str, challenge: str, signature_hex: str) -> bool:
    """Verify Ed25519 signature on a challenge string (for QR auth)."""
    return verify_signature(public_key_hex, challenge, signature_hex)

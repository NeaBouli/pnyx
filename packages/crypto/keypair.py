"""
MOD-01: Ed25519 Keypair Generierung & Verwaltung
Kein Personenbezug. Private Key verlässt nie den Server in diesem Kontext —
auf Mobile lebt er im Secure Enclave (expo-secure-store).
"""
import hashlib
import logging
import secrets
import gc
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

logger = logging.getLogger(__name__)


class SignatureVerificationError(RuntimeError):
    """
    Unexpected Ed25519 verifier failure (library/programming fault).

    Distinct from an invalid signature: callers must not treat it as False.
    It propagates (fail closed, HTTP 500) so monitoring sees it.
    """


def generate_keypair() -> dict:
    """
    Erzeugt ein neues Ed25519 Schlüsselpaar.
    Returns: { private_key_hex, public_key_hex }
    Private Key wird dem Client übergeben und NICHT gespeichert.
    """
    signing_key = SigningKey.generate()
    private_key_hex = signing_key.encode(encoder=HexEncoder).decode()
    public_key_hex  = signing_key.verify_key.encode(encoder=HexEncoder).decode()
    return {
        "private_key_hex": private_key_hex,
        "public_key_hex":  public_key_hex,
    }


def sign_payload(private_key_hex: str, payload: bytes) -> str:
    """
    Signiert einen Payload mit dem privaten Ed25519-Schlüssel.
    Returns: signature_hex
    """
    signing_key = SigningKey(private_key_hex.encode(), encoder=HexEncoder)
    signed = signing_key.sign(payload)
    return signed.signature.hex()


def verify_signature(public_key_hex: str, payload: str | bytes, signature_hex: str) -> bool:
    """
    Verifiziert eine Ed25519-Signatur.
    Returns: True wenn gültig, False bei ungültiger Signatur oder fehlerhaftem
    Schlüssel-/Signaturmaterial.
    Raises: SignatureVerificationError bei unerwarteten Verifier-/Programmierfehlern.
    """
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError

    # Key and signature are client-supplied: wrong types are malformed input.
    if not isinstance(public_key_hex, str) or not isinstance(signature_hex, str):
        return False
    try:
        verify_key = VerifyKey(public_key_hex.encode(), encoder=HexEncoder)
        message = payload.encode("utf-8") if isinstance(payload, str) else payload
        verify_key.verify(message, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError):
        # Forged signature, non-hex input, or wrong key/signature length.
        return False
    except Exception as exc:
        # Type only — never log key, payload or signature material.
        logger.error("Ed25519 verifier failure: %s", type(exc).__name__)
        raise SignatureVerificationError(type(exc).__name__) from exc

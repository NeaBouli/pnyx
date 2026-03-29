"""
MOD-01: Ed25519 Keypair Generierung & Verwaltung
Kein Personenbezug. Private Key verlässt nie den Server in diesem Kontext —
auf Mobile lebt er im Secure Enclave (expo-secure-store).
"""
import hashlib
import secrets
import gc
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder


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


def verify_signature(public_key_hex: str, payload: bytes, signature_hex: str) -> bool:
    """
    Verifiziert eine Ed25519-Signatur.
    Returns: True wenn gültig, False sonst.
    """
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    try:
        verify_key = VerifyKey(public_key_hex.encode(), encoder=HexEncoder)
        verify_key.verify(payload, bytes.fromhex(signature_hex))
        return True
    except BadSignatureError:
        return False

"""Representative invite codes are stored only as a keyed hash (EVA-033).

The plaintext code is returned exactly once, in the creation response. The
database keeps an HMAC-SHA256 digest (namespaced, keyed with SERVER_SALT,
which production startup already validates) and a short display hint.
"""
from __future__ import annotations

import hashlib
import hmac
import os

INVITE_HASH_NAMESPACE = b"rep-invite:v1:"


def _invite_key() -> bytes:
    salt = (os.getenv("SERVER_SALT") or "").strip()
    if not salt:
        # Fail closed: never hash invite codes with a public fallback key.
        raise RuntimeError("SERVER_SALT is required to hash representative invite codes")
    return salt.encode("utf-8")


def invite_code_hash(code: str) -> str:
    """Full 64-hex HMAC of the code exactly as entered (no trimming or case change)."""
    return hmac.new(_invite_key(), INVITE_HASH_NAMESPACE + code.encode("utf-8"), hashlib.sha256).hexdigest()


def invite_code_hint(code: str) -> str:
    """Non-secret display mask for admin lists, e.g. 'AB**-****'."""
    return code[:2] + "**-****" if len(code) == 9 else "****-****"

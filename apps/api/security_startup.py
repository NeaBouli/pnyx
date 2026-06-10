"""Production startup guards for high-value security configuration."""

from __future__ import annotations

import logging
import os
import importlib.util
from collections.abc import Mapping

logger = logging.getLogger(__name__)

MIN_SERVER_SALT_LENGTH = 32
WEAK_SERVER_SALT_VALUES = {
    "",
    "dev-salt",
    "dev-salt-change-in-production",
}


def validate_server_salt_config(environ: Mapping[str, str] | None = None) -> None:
    """Fail closed in production if SERVER_SALT is missing or obviously weak."""
    env = environ or os.environ
    environment = env.get("ENVIRONMENT", env.get("ENV", "production"))
    salt = (env.get("SERVER_SALT", "") or "").strip()

    if environment != "production":
        if salt in WEAK_SERVER_SALT_VALUES or len(salt) < MIN_SERVER_SALT_LENGTH:
            logger.warning("[SECURITY] SERVER_SALT is weak/missing in non-production")
        return

    if salt in WEAK_SERVER_SALT_VALUES:
        raise RuntimeError("SERVER_SALT startup check failed: missing or default value")

    if len(salt) < MIN_SERVER_SALT_LENGTH:
        raise RuntimeError(
            f"SERVER_SALT startup check failed: must be at least {MIN_SERVER_SALT_LENGTH} characters"
        )


def validate_identity_kdf_config(environ: Mapping[str, str] | None = None) -> None:
    """Fail closed if v2 identity nullifiers are enabled without Argon2 support."""
    env = environ or os.environ
    version = env.get("IDENTITY_NULLIFIER_KDF_VERSION", "v1").lower()

    if version not in {"v1", "v2"}:
        raise RuntimeError("IDENTITY_NULLIFIER_KDF_VERSION must be v1 or v2")

    if version == "v2" and importlib.util.find_spec("argon2") is None:
        raise RuntimeError("IDENTITY_NULLIFIER_KDF_VERSION=v2 requires argon2-cffi")

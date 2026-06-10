"""
MOD-01: Beta identity nullifier — prevents duplicate registration without storing phones.
Principle: SHA256(phone + server_salt). The phone number is never stored; the
server salt is a critical secret because this is not a memory-hard derivation.
"""
import hashlib
import secrets
import gc
import os
import re


SERVER_SALT = os.environ.get("SERVER_SALT", "dev-salt-change-in-production")
IDENTITY_NULLIFIER_V2_PREFIX = "v2:"
IDENTITY_NULLIFIER_V2_SALT_CONTEXT = b"ekklesia:identity-nullifier:v2"
IDENTITY_NULLIFIER_V2_TIME_COST = 2
IDENTITY_NULLIFIER_V2_MEMORY_KIB = 65536
IDENTITY_NULLIFIER_V2_PARALLELISM = 1
IDENTITY_NULLIFIER_V2_HASH_LEN = 32


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize Greek phone input for v2 identity nullifiers.
    v1 deliberately keeps the legacy raw input for compatibility.
    """
    cleaned = re.sub(r"[\s().-]", "", phone_number)
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    elif cleaned.startswith("30") and len(cleaned) == 12:
        cleaned = f"+{cleaned}"
    elif cleaned.startswith("69") and len(cleaned) == 10:
        cleaned = f"+30{cleaned}"
    return cleaned


def generate_nullifier_hash(phone_number: str) -> str:
    """
    Erzeugt einen server-salted Beta-Nullifier-Hash aus der Telefonnummer.
    Die Telefonnummer wird nach dieser Operation sofort gelöscht.
    Returns: SHA256 hex string (64 Zeichen)
    """
    raw = f"{phone_number}:{SERVER_SALT}"
    result = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # Rohdaten sofort löschen
    del raw
    del phone_number
    gc.collect()

    return result


def generate_nullifier_hash_v2(phone_number: str) -> str:
    """
    Versioned, memory-hard identity nullifier for new registrations.
    Returns: "v2:" + 64 hex chars.
    """
    try:
        from argon2.low_level import Type, hash_secret_raw
    except ImportError as exc:
        raise RuntimeError("argon2-cffi is required for identity nullifier v2") from exc

    normalized_phone = normalize_phone_number(phone_number)
    kdf_salt = hashlib.sha256(
        IDENTITY_NULLIFIER_V2_SALT_CONTEXT + SERVER_SALT.encode("utf-8")
    ).digest()
    result = hash_secret_raw(
        normalized_phone.encode("utf-8"),
        kdf_salt,
        time_cost=IDENTITY_NULLIFIER_V2_TIME_COST,
        memory_cost=IDENTITY_NULLIFIER_V2_MEMORY_KIB,
        parallelism=IDENTITY_NULLIFIER_V2_PARALLELISM,
        hash_len=IDENTITY_NULLIFIER_V2_HASH_LEN,
        type=Type.ID,
    ).hex()

    del normalized_phone
    del kdf_salt
    gc.collect()

    return f"{IDENTITY_NULLIFIER_V2_PREFIX}{result}"


def generate_demographic_hash(age_group: str, region: str, gender_code: str) -> str:
    """
    MOD-09 (Alpha): Demographischer Hash für gov.gr Integration.
    Hinweis: Der Suchraum ist klein; SERVER_SALT muss geheim bleiben.
    SHA256(age_group + region + gender_code + SERVER_SALT)
    Returns: SHA256 hex string (64 Zeichen)
    """
    raw = f"{age_group}_{region}_{gender_code}_{SERVER_SALT}"
    result = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    del raw
    gc.collect()
    return result

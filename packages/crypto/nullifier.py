"""
MOD-01: Nullifier Hash — verhindert Doppelregistrierung ohne Personenbezug.
Prinzip: SHA256(phone_prefix + server_salt) — Telefonnummer nie gespeichert.
"""
import hashlib
import secrets
import gc
import os


SERVER_SALT = os.environ.get("SERVER_SALT", "dev-salt-change-in-production")


def generate_nullifier_hash(phone_number: str) -> str:
    """
    Erzeugt einen nicht umkehrbaren Nullifier Hash aus der Telefonnummer.
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


def generate_demographic_hash(age_group: str, region: str, gender_code: str) -> str:
    """
    MOD-09 (Alpha): Demographischer Hash für gov.gr Integration.
    SHA256(age_group + region + gender_code + SERVER_SALT)
    Returns: SHA256 hex string (64 Zeichen)
    """
    raw = f"{age_group}_{region}_{gender_code}_{SERVER_SALT}"
    result = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    del raw
    gc.collect()
    return result

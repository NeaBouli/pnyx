"""
MOD-01: HLR (Home Location Register) Verifikation
Verifiziert griechische Mobilnummern ohne SMS.

Griechische SIM-Karten sind per Gesetz an Personalausweis gebunden.
HLR prüft ob Nummer im griechischen Netz aktiv ist.

Provider: HLR Lookups (hlrlookups.com)
- Crypto prepaid (BTC/ETH/USDC)
- ~$0.002/query
- Community Wallet — Balance öffentlich auf community.html

@ai-anchor MOD01_HLR
@update-hint Provider-Wechsel: nur HLR_PROVIDER_URL + Auth ändern
"""
import re
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# ── Griechische Nummer Validierung ────────────────────────────────────────────

def normalize_greek_number(phone: str) -> Optional[str]:
    """
    Normalisiert griechische Mobilnummer → +306XXXXXXXXX
    Akzeptiert: 6912345678, 06912345678, 306912345678, +306912345678
    """
    digits = re.sub(r"[\s\-\.\(\)]", "", phone)

    if digits.startswith("+30"):
        normalized = digits
    elif digits.startswith("0030"):
        normalized = "+" + digits[2:]
    elif digits.startswith("30") and len(digits) == 12:
        normalized = "+" + digits
    elif digits.startswith("69") and len(digits) == 10:
        normalized = "+30" + digits
    else:
        return None

    if not re.match(r"^\+3069\d{8}$", normalized):
        return None

    return normalized


def is_valid_greek_mobile(phone: str) -> bool:
    """Schnelle Validierung ohne API-Call."""
    return normalize_greek_number(phone) is not None


# ── HLR Provider: HLR Lookups ─────────────────────────────────────────────────

async def hlr_lookup(phone: str) -> dict:
    """
    HLR Query für griechische Mobilnummer.

    Returns:
        {
            "valid": bool,
            "network": str | None,
            "country": str | None,
            "status": str,
            "error": str | None
        }

    Dry Run wenn HLRLOOKUPS_USERNAME nicht gesetzt.
    """
    normalized = normalize_greek_number(phone)

    if not normalized:
        return {
            "valid": False,
            "network": None,
            "country": None,
            "status": "INVALID_FORMAT",
            "error": "Μη έγκυρος ελληνικός αριθμός κινητού"
        }

    api_username = os.getenv("HLRLOOKUPS_USERNAME")
    api_password = os.getenv("HLRLOOKUPS_PASSWORD")

    # Dry Run — kein Provider konfiguriert
    if not api_username:
        logger.info(f"[MOD-01] HLR Dry Run für {normalized[:6]}XXXX")
        return {
            "valid":   True,
            "network": "Cosmote GR (Dry Run)",
            "country": "GR",
            "status":  "DRY_RUN",
            "error":   None
        }

    # Echter HLR Lookup via hlrlookups.com
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.hlrlookups.com/",
                params={
                    "username": api_username,
                    "password": api_password,
                    "msisdn":   normalized.replace("+", ""),
                },
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status", "")
            network = data.get("network", None)
            country = data.get("country_code", None)

            is_greek  = country == "GR" or normalized.startswith("+30")
            is_active = status in ("0", "active", "ACTIVE", "Live")

            logger.info(
                f"[MOD-01] HLR result: {normalized[:6]}XXXX "
                f"status={status} network={network} country={country}"
            )

            return {
                "valid":   is_greek and is_active,
                "network": network,
                "country": country,
                "status":  status,
                "error":   None if (is_greek and is_active) else "Ο αριθμός δεν είναι ενεργός ελληνικός αριθμός"
            }

    except httpx.TimeoutException:
        logger.error("[MOD-01] HLR timeout")
        return {
            "valid": False, "network": None, "country": None,
            "status": "TIMEOUT",
            "error": "HLR timeout — δοκιμάστε ξανά"
        }
    except Exception as e:
        logger.error(f"[MOD-01] HLR error: {e}")
        return {
            "valid": False, "network": None, "country": None,
            "status": "ERROR",
            "error": str(e)
        }


# ── Alternative Provider: Melrose Labs ───────────────────────────────────────

async def hlr_lookup_melrose(phone: str) -> dict:
    """
    Alternative: Melrose Labs HLR API
    Aktivieren: HLRLOOKUPS_PROVIDER=melrose in .env
    """
    normalized = normalize_greek_number(phone)
    if not normalized:
        return {"valid": False, "status": "INVALID_FORMAT", "error": "Invalid number",
                "network": None, "country": None}

    api_key = os.getenv("MELROSE_API_KEY")
    if not api_key:
        return {"valid": True, "status": "DRY_RUN", "network": "Dry Run",
                "country": "GR", "error": None}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://meirons.melroselabs.com/hlr",
                json={"msisdn": normalized},
                headers={"x-api-key": api_key, "Content-Type": "application/json"}
            )
            r.raise_for_status()
            data = r.json()
            return {
                "valid":   data.get("present") == "yes",
                "network": data.get("network"),
                "country": data.get("country"),
                "status":  data.get("status", "UNKNOWN"),
                "error":   None
            }
    except Exception as e:
        return {"valid": False, "status": "ERROR", "error": str(e),
                "network": None, "country": None}


# ── Provider Router ───────────────────────────────────────────────────────────

async def verify_greek_number(phone: str) -> dict:
    """
    Hauptfunktion — wählt Provider automatisch.
    HLRLOOKUPS_PROVIDER=hlrlookups (default) | melrose
    """
    provider = os.getenv("HLRLOOKUPS_PROVIDER", "hlrlookups")

    if provider == "melrose":
        return await hlr_lookup_melrose(phone)

    return await hlr_lookup(phone)

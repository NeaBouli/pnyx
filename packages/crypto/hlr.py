"""
MOD-01: HLR (Home Location Register) Verifikation
Verifiziert griechische Mobilnummern ohne SMS.

Griechische SIM-Karten sind per Gesetz an Personalausweis gebunden.
HLR prüft ob Nummer im griechischen Netz aktiv ist.

Primary: HLR Lookup (www.hlrlookup.com)
- PayPal prepaid (15€ = 2500 Credits)
- ~0.006 EUR/query
- REST API v2: POST /apiv2/hlr mit api_key+api_secret im Body

Fallback: HLR Lookups (www.hlr-lookups.com)
- Crypto prepaid (BTC/ETH/USDC)
- ~0.01 EUR/query
- REST API v2: POST /api/v2/hlr-lookup mit HTTP Basic Auth

Auto-Failover Trigger:
A) Primary TIMEOUT oder ERROR
B) Primary Credits < 50
C) Primary HTTP 401/403 (Auth-Problem)

@ai-anchor MOD01_HLR
@update-hint Provider-Wechsel: hlr_lookup() url + auth anpassen
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


# ── HLR Provider: hlrlookup.com (Primary) ────────────────────────────────────

HLRLOOKUP_COM_URL = "https://api.hlrlookup.com/apiv2/hlr"


async def hlr_lookup_hlrlookupcom(phone: str) -> dict:
    """
    Primary HLR Query via api.hlrlookup.com API v2.
    POST mit api_key + api_secret im JSON Body.
    """
    normalized = normalize_greek_number(phone)

    if not normalized:
        return {
            "valid": False, "network": None, "country": None,
            "status": "INVALID_FORMAT",
            "error": "Μη έγκυρος ελληνικός αριθμός κινητού"
        }

    api_key = os.getenv("HLR_FALLBACK_API_KEY")
    api_secret = os.getenv("HLR_FALLBACK_API_SECRET")

    if not api_key or not api_secret:
        logger.warning(f"[MOD-01] HLR Primary — Credentials fehlen, fail-closed für {normalized[:6]}XXXX")
        return {
            "valid": False, "network": None,
            "country": None, "status": "NOT_CONFIGURED",
            "error": "HLR nicht konfiguriert — Verifikation nicht möglich"
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                HLRLOOKUP_COM_URL,
                json={
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "requests": [{"telephone_number": normalized}]
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code in (401, 403):
                logger.error(f"[MOD-01] HLR Primary auth error: {response.status_code}")
                return {
                    "valid": False, "network": None, "country": None,
                    "status": "AUTH_ERROR", "error": f"HLR Auth Error {response.status_code}"
                }

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return {
                    "valid": False, "network": None, "country": None,
                    "status": "NO_RESULT", "error": "Keine Ergebnisse vom Primary-Provider"
                }

            r = results[0]

            if r.get("error") not in ("NONE", None, ""):
                return {
                    "valid": False, "network": None, "country": None,
                    "status": "ERROR", "error": r.get("error", "Unknown error")
                }

            live_status = r.get("live_status", "")
            orig_details = r.get("original_network_details", {})
            curr_details = r.get("current_network_details", {})
            network = curr_details.get("name") or orig_details.get("name")
            country_iso = orig_details.get("country_iso3", "")
            number_type = r.get("telephone_number_type", "")

            is_greek = country_iso in ("GRC", "GR") or normalized.startswith("+30")
            is_mobile = number_type == "MOBILE"
            is_live = live_status == "LIVE"

            logger.info(
                f"[MOD-01] HLR Primary: {normalized[:6]}XXXX "
                f"live={live_status} network={network} type={number_type}"
            )

            return {
                "valid": is_greek and is_mobile and is_live,
                "network": network,
                "country": "GR" if is_greek else country_iso,
                "status": live_status or "UNKNOWN",
                "error": None if (is_greek and is_mobile and is_live)
                    else "Ο αριθμός δεν είναι ενεργός ελληνικός αριθμός κινητού"
            }

    except httpx.TimeoutException:
        logger.error("[MOD-01] HLR Primary timeout")
        return {
            "valid": False, "network": None, "country": None,
            "status": "TIMEOUT", "error": "HLR Primary timeout"
        }
    except Exception as e:
        logger.error(f"[MOD-01] HLR Primary error: {e}")
        return {
            "valid": False, "network": None, "country": None,
            "status": "ERROR", "error": str(e)
        }


# ── HLR Provider: hlr-lookups.com (Fallback) ─────────────────────────────────

HLR_LOOKUPS_URL = "https://www.hlr-lookups.com/api/v2/hlr-lookup"


async def hlr_lookup(phone: str) -> dict:
    """
    Fallback HLR Query via www.hlr-lookups.com REST API v2.
    HTTP Basic Auth (API_KEY:API_SECRET).
    """
    normalized = normalize_greek_number(phone)

    if not normalized:
        return {
            "valid": False, "network": None, "country": None,
            "status": "INVALID_FORMAT",
            "error": "Μη έγκυρος ελληνικός αριθμός κινητού"
        }

    api_key = os.getenv("HLRLOOKUPS_API_KEY")
    api_secret = os.getenv("HLRLOOKUPS_API_SECRET")

    if not api_key or not api_secret:
        logger.warning("[MOD-01] HLR Fallback (hlr-lookups.com) not configured (no API key)")
        return {
            "valid": False, "network": None, "country": None,
            "status": "FALLBACK_NOT_CONFIGURED",
            "error": "Fallback HLR provider not configured"
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                HLR_LOOKUPS_URL,
                json={"msisdn": normalized},
                auth=(api_key, api_secret),
                headers={"Accept": "application/json"},
            )

            if response.status_code in (401, 403):
                logger.error(f"[MOD-01] HLR Fallback auth error: {response.status_code}")
                return {
                    "valid": False, "network": None, "country": None,
                    "status": "AUTH_ERROR", "error": f"Fallback Auth Error {response.status_code}"
                }

            response.raise_for_status()
            data = response.json()

            conn_status = data.get("connectivity_status", "")
            network = data.get("original_network_name")
            country = data.get("original_country_code")

            is_greek = country == "GR" or normalized.startswith("+30")
            is_active = conn_status == "CONNECTED"

            logger.info(
                f"[MOD-01] HLR Fallback: {normalized[:6]}XXXX "
                f"status={conn_status} network={network} country={country}"
            )

            return {
                "valid": is_greek and is_active,
                "network": network,
                "country": country,
                "status": conn_status or "UNKNOWN",
                "error": None if (is_greek and is_active) else "Ο αριθμός δεν είναι ενεργός ελληνικός αριθμός"
            }

    except httpx.TimeoutException:
        logger.error("[MOD-01] HLR Fallback timeout")
        return {
            "valid": False, "network": None, "country": None,
            "status": "TIMEOUT", "error": "Fallback HLR timeout — δοκιμάστε ξανά"
        }
    except Exception as e:
        logger.error(f"[MOD-01] HLR Fallback error: {e}")
        return {
            "valid": False, "network": None, "country": None,
            "status": "ERROR", "error": str(e)
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
        return {"valid": False, "status": "NOT_CONFIGURED", "network": None,
                "country": None, "error": "Melrose not configured"}

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


# ── Provider Router mit intelligentem Auto-Failover ──────────────────────────

async def _get_primary_credits_remaining() -> int:
    """Liest verbleibende Primary-Credits (hlrlookup.com) aus Redis."""
    try:
        import redis.asyncio as aioredis
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = aioredis.from_url(url, decode_responses=True)
        val = await r.get("hlr:hlrlookupcom:used")
        await r.aclose()
        used = int(val) if val else 0
        initial = int(os.getenv("HLR_PRIMARY_INITIAL_CREDITS", "2499"))
        return max(0, initial - used)
    except Exception:
        return 999  # Im Fehlerfall nicht triggern


async def verify_greek_number(phone: str) -> dict:
    """
    Hauptfunktion — wählt Provider, Auto-Failover bei:
    Trigger A: Primary TIMEOUT oder ERROR
    Trigger B: Primary Credits < 50
    Trigger C: Primary HTTP 401/403 (AUTH_ERROR)
    """
    provider = os.getenv("HLRLOOKUPS_PROVIDER", "hlrlookupcom")
    fallback_enabled = os.getenv("HLR_FALLBACK_ENABLED", "false").lower() == "true"

    # Primary-Lookup
    if provider == "melrose":
        result = await hlr_lookup_melrose(phone)
    else:
        result = await hlr_lookup_hlrlookupcom(phone)

    # Dry Run braucht keinen Failover
    if result.get("status") == "DRY_RUN":
        return result

    # Failover-Trigger prüfen
    trigger_a = result.get("status") in ("TIMEOUT", "ERROR")
    trigger_c = result.get("status") == "AUTH_ERROR"

    credits_remaining = await _get_primary_credits_remaining()
    trigger_b = credits_remaining < 50

    if fallback_enabled and (trigger_a or trigger_b or trigger_c):
        reason = "timeout/error" if trigger_a else \
                 f"low_credits ({credits_remaining})" if trigger_b else \
                 "auth_error"
        logger.warning(f"[MOD-01] Auto-Failover → hlr-lookups.com — Grund: {reason}")

        # Redis Warning setzen (für Dashboard / Credits-Endpoint)
        try:
            import redis.asyncio as aioredis
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            r = aioredis.from_url(url, decode_responses=True)
            await r.setex("hlr:failover:reason", 3600, reason)
            await r.setex("hlr:failover:active", 3600, "true")
            await r.aclose()
        except Exception as e:
            logger.error(f"[MOD-01] Redis failover write error: {e}")

        fallback = await hlr_lookup(phone)
        if fallback.get("status") not in ("FALLBACK_NOT_CONFIGURED", "ERROR", "AUTH_ERROR"):
            return fallback
        else:
            logger.error(f"[MOD-01] Fallback also failed: {fallback.get('status')}")

    return result

"""
MOD-09: gov.gr OAuth2.0 — Phase A Browser-Verifikation
Vorbereitung für Alpha Deployment.

PHASE A FLOW (Browser — Desktop + Mobile):
  1. User klickt "Σύνδεση με gov.gr"
  2. Redirect zu oauth2.gov.gr (Taxisnet)
  3. User authentifiziert sich
  4. Callback mit Authorization Code
  5. Server tauscht Code → Access Token
  6. Server holt User-Info (AMKA-Hash, NICHT Klarname)
  7. Server generiert anonymen Nullifier = HMAC(AMKA-Hash, REGISTRATION_SALT)
  8. Rückgabe: nullifier_root + identity_commitment
  9. KEINE persönlichen Daten gespeichert — nur kryptographischer Hash

PHASE B FLOW (aktuell aktiv — Smartphone-Only):
  - HLR-Netzstatusprüfung für eine griechische Mobilnummer
  - Key-Speicherung im Android Keystore / iOS Keychain

HLR beweist weder SIM-Besitz noch Identität, Alter, Staatsbürgerschaft,
Wohnsitz oder Wahlberechtigung.

AKTIVIERUNG Phase A NUR WENN:
- 500+ aktive Nutzer
- 3+ NGO Partnerschaften
- gov.gr OAuth-Zugang genehmigt (GSRT)
- Holder-Authentifizierung und verfügbare Claims offiziell dokumentiert
- DPIA, Credential-Migration und unabhängiger Security-Review abgeschlossen
- Sandbox-Canary bestanden und expliziter Runtime-Schalter aktiviert

@ai-anchor MOD09_GOVGR_OAUTH
@activation-gate explicit_enable + official_approval + holder_auth + DPIA + security_review + canary
"""
import os
import re
import json
import time
import secrets
import hashlib
import hmac
import logging
from typing import Any
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth/govgr", tags=["MOD-09 gov.gr OAuth"])

GOVGR_CLIENT_ID = os.getenv("GOVGR_CLIENT_ID", "")
GOVGR_CLIENT_SECRET = os.getenv("GOVGR_CLIENT_SECRET", "")
GOVGR_REDIRECT_URI = os.getenv("GOVGR_REDIRECT_URI", "https://ekklesia.gr/auth/govgr/callback")
GOVGR_FLOW_ENABLED = os.getenv("GOVGR_FLOW_ENABLED", "false").lower() == "true"
GOVGR_AUTH_URL = "https://oauth2.gov.gr/oauth2/authorize"
GOVGR_TOKEN_URL = "https://oauth2.gov.gr/oauth2/token"
GOVGR_USERINFO_URL = "https://oauth2.gov.gr/oauth2/userinfo"
REGISTRATION_SALT = os.getenv("SERVER_SALT", "")

ACTIVATION_GATES = {
    "users_500":                    False,
    "ngos_3":                       False,
    "roadmap_published":            True,
    "govgr_approved":               False,
    "holder_authentication_reviewed": False,
    "privacy_dpia_approved":        False,
    "credential_migration_reviewed": False,
    "security_review_passed":       False,
    "sandbox_canary_passed":        False,
}


def is_active() -> bool:
    return (
        GOVGR_FLOW_ENABLED
        and all(ACTIVATION_GATES.values())
        and bool(GOVGR_CLIENT_ID and GOVGR_CLIENT_SECRET)
        and len(REGISTRATION_SALT) >= 32
    )

# ── OAuth state (EKA-11) ─────────────────────────────────────────────────────
# State lives only in the shared Redis (REDIS_URL) so every worker and every
# restarted process sees the same single-use record. There is deliberately no
# in-process fallback: if Redis is unavailable, login and callback fail closed.
GOVGR_STATE_TTL_SECONDS = 600
GOVGR_STATE_PURPOSE = "govgr_oauth_login:v1"
_STATE_KEY_PREFIX = "govgr:oauth_state:v1:"
_STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")

_state_redis: aioredis.Redis | None = None


class OAuthStateStoreUnavailable(Exception):
    """Shared OAuth state store could not be reached; callers must fail closed."""


class OAuthStateInvalid(Exception):
    """State is unknown, expired, already consumed or bound to another context."""


def _now() -> float:
    return time.time()


async def _get_state_redis() -> aioredis.Redis:
    global _state_redis
    if _state_redis is None:
        _state_redis = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True
        )
    return _state_redis


def _state_key(state: str) -> str:
    # Only a digest of the state is used as key, so the raw value never rests in Redis.
    return _STATE_KEY_PREFIX + hashlib.sha256(state.encode()).hexdigest()


def _state_context() -> dict[str, str]:
    return {
        "purpose": GOVGR_STATE_PURPOSE,
        "client_id": GOVGR_CLIENT_ID,
        "redirect_uri": GOVGR_REDIRECT_URI,
    }


async def _issue_oauth_state(redirect_after: str) -> str:
    """Create a fresh, TTL-bounded, single-use state bound to this OAuth context."""
    state = secrets.token_urlsafe(32)
    issued_at = int(_now())
    record = {
        **_state_context(),
        "redirect_after": redirect_after,
        "iat": issued_at,
        "exp": issued_at + GOVGR_STATE_TTL_SECONDS,
    }
    try:
        r = await _get_state_redis()
        stored = await r.set(
            _state_key(state), json.dumps(record), nx=True, ex=GOVGR_STATE_TTL_SECONDS
        )
    except Exception as exc:
        raise OAuthStateStoreUnavailable() from exc
    if not stored:
        # 256-bit collision is not expected; refuse instead of overwriting.
        raise OAuthStateStoreUnavailable()
    return state


async def _consume_oauth_state(state: str | None) -> dict[str, Any]:
    """Atomically consume a state exactly once and verify its bound context."""
    if not state or not _STATE_PATTERN.fullmatch(state):
        raise OAuthStateInvalid()
    try:
        r = await _get_state_redis()
        raw = await r.getdel(_state_key(state))
    except Exception as exc:
        raise OAuthStateStoreUnavailable() from exc
    if raw is None:
        raise OAuthStateInvalid()
    try:
        record = json.loads(raw)
        exp = int(record["exp"]) if isinstance(record, dict) else None
    except (ValueError, TypeError, KeyError):
        raise OAuthStateInvalid() from None
    if exp is None or _now() >= exp:
        raise OAuthStateInvalid()
    for field, expected in _state_context().items():
        value = record.get(field)
        if not isinstance(value, str) or not hmac.compare_digest(value, expected):
            raise OAuthStateInvalid()
    return record


@router.get("/status")
async def govgr_status():
    """Status der gov.gr OAuth Integration."""
    gates_met = sum(1 for v in ACTIVATION_GATES.values() if v)
    return {
        "module": "MOD-09 gov.gr OAuth2.0",
        "status": "active" if is_active() else "stub",
        "progress": f"{gates_met}/{len(ACTIVATION_GATES)} Προϋποθέσεις Ενεργοποίησης",
        "gates": {
            "500_aktive_nutzer":     ACTIVATION_GATES["users_500"],
            "3_ngo_partnerschaften": ACTIVATION_GATES["ngos_3"],
            "roadmap_publiziert":    ACTIVATION_GATES["roadmap_published"],
            "govgr_genehmigung":     ACTIVATION_GATES["govgr_approved"],
            "holder_auth_geprueft":  ACTIVATION_GATES["holder_authentication_reviewed"],
            "dpia_genehmigt":        ACTIVATION_GATES["privacy_dpia_approved"],
            "migration_geprueft":    ACTIVATION_GATES["credential_migration_reviewed"],
            "security_review":       ACTIVATION_GATES["security_review_passed"],
            "sandbox_canary":        ACTIVATION_GATES["sandbox_canary_passed"],
        },
        "alternative": {
            "module": "MOD-01 HLR",
            "endpoint": "/api/v1/identity/verify",
            "assurance": "network_status_only",
        },
        "runtime_enabled": GOVGR_FLOW_ENABLED,
        "env_configured": bool(GOVGR_CLIENT_ID and GOVGR_CLIENT_SECRET),
    }


@router.get("/login")
async def govgr_login(redirect_after: str = Query("/")):
    """
    Startet gov.gr OAuth2.0 Flow (Phase A).
    Redirect zu oauth2.gov.gr → Taxisnet Login.
    """
    if not is_active():
        raise HTTPException(503, detail={
            "error": "govgr_not_active",
            "message_el": "Η σύνδεση με gov.gr δεν είναι ακόμη ενεργή. Στη Beta διατίθεται μόνο HLR έλεγχος κατάστασης ελληνικού αριθμού· δεν αποδεικνύει κατοχή SIM ή ταυτότητα.",
            "message_en": "gov.gr login is not active. Beta provides only an HLR Greek-number network-status check; it does not prove SIM possession or identity.",
            "gates": ACTIVATION_GATES,
            "alternative": {
                "method": "HLR_NETWORK_STATUS",
                "endpoint": "/api/v1/identity/verify",
                "assurance": "network_status_only",
            },
        })

    try:
        state = await _issue_oauth_state(redirect_after)
    except OAuthStateStoreUnavailable:
        logger.error("[MOD-09] OAuth state store unavailable — login refused")
        raise HTTPException(503, "gov.gr OAuth vorübergehend nicht verfügbar")
    auth_url = (
        f"{GOVGR_AUTH_URL}?client_id={GOVGR_CLIENT_ID}"
        f"&redirect_uri={GOVGR_REDIRECT_URI}"
        f"&response_type=code&scope=openid+profile&state={state}"
    )
    logger.info("[MOD-09] OAuth login initiated")
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def govgr_callback(
    code: str = Query(None), state: str = Query(None), error: str = Query(None)
):
    """
    OAuth2.0 Callback von gov.gr.
    Phase A: tauscht Code → Token → UserInfo → anonymer Nullifier.
    KEINE persönlichen Daten werden gespeichert.
    """
    if error:
        raise HTTPException(400, f"gov.gr OAuth Fehler: {error}")
    if not is_active():
        raise HTTPException(503, "gov.gr OAuth nicht aktiv")
    if not code:
        raise HTTPException(400, "Kein Authorization Code")

    # Validate state: atomic single-use consume from the shared store
    try:
        state_data = await _consume_oauth_state(state)
    except OAuthStateStoreUnavailable:
        logger.error("[MOD-09] OAuth state store unavailable — callback refused")
        raise HTTPException(503, "gov.gr OAuth vorübergehend nicht verfügbar")
    except OAuthStateInvalid:
        raise HTTPException(400, "Ungültiger OAuth State — mögliche CSRF-Attacke")

    # Exchange code for token
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(GOVGR_TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": GOVGR_REDIRECT_URI,
                "client_id": GOVGR_CLIENT_ID,
                "client_secret": GOVGR_CLIENT_SECRET,
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens.get("access_token")

            if not access_token:
                raise HTTPException(502, "gov.gr gab kein Access Token")

            # Fetch user info
            userinfo_resp = await client.get(GOVGR_USERINFO_URL, headers={
                "Authorization": f"Bearer {access_token}",
            })
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

    except httpx.HTTPError as e:
        logger.error(f"[MOD-09] gov.gr token exchange failed: {e}")
        raise HTTPException(502, "gov.gr Kommunikationsfehler")

    # Extract anonymous identifier (AMKA hash or sub)
    # gov.gr returns a 'sub' claim (opaque user ID) — we hash it
    govgr_sub = userinfo.get("sub", "")
    if not govgr_sub:
        raise HTTPException(502, "gov.gr UserInfo enthält keine Identifikation")

    # Generate anonymous nullifier from gov.gr sub
    # HMAC(sub, REGISTRATION_SALT) → nullifier_root (same pattern as HLR)
    nullifier_root = hmac.new(
        REGISTRATION_SALT.encode(),
        f"govgr:{govgr_sub}".encode(),
        hashlib.sha256,
    ).hexdigest()

    # Generate identity_commitment (only this goes to server DB)
    identity_commitment = hmac.new(
        bytes.fromhex(nullifier_root),
        b"ekklesia:identity_commitment:v1",
        hashlib.sha256,
    ).hexdigest()

    # WICHTIG: Wir speichern NICHT: Name, AMKA, Adresse, govgr_sub
    # Nur: identity_commitment (kryptographischer Hash)
    logger.info(f"[MOD-09] gov.gr auth success, commitment={identity_commitment[:12]}...")

    # Zero sensitive data
    del govgr_sub, access_token, userinfo

    return {
        "success": True,
        "method": "govgr_oauth",
        "nullifier_root": nullifier_root,
        "identity_commitment": identity_commitment,
        "message_el": "Επιτυχής ταυτοποίηση μέσω gov.gr. Ο Nullifier Root αποθηκεύεται μόνο στη συσκευή σας.",
        "message_en": "Successfully verified via gov.gr. The Nullifier Root is stored only on your device.",
        "redirect": state_data.get("redirect_after", "/"),
    }


@router.get("/family/verify")
async def family_verify_stub():
    """Liquid Democracy: Verwandte 1. Grades via gov.gr. STUB."""
    return {
        "module": "Liquid Democracy — Familien-Verifikation",
        "status": "stub", "active": False,
        "requires": [
            "gov.gr OAuth aktiv (MOD-09)",
            "Beide Nutzer via Taxisnet verifiziert",
            "Verwandtschaft 1. Grades im AMKA-Register",
        ],
        "privacy": "AMKA wird nie gespeichert — nur Verwandtschafts-Hash",
    }


@router.get("/info")
async def govgr_info():
    return {
        "name": "MOD-09: gov.gr OAuth2.0", "phase": "Alpha 0.1 (design-only stub)",
        "runtime_enabled": GOVGR_FLOW_ENABLED,
        "assurance": "No gov.gr, holder, citizenship, residence, age or eligibility claim is active in Beta.",
        "flow": {
            "1": "Nutzer klickt 'Mit gov.gr anmelden'",
            "2": "Redirect zu oauth2.gov.gr",
            "3": "Nutzer loggt sich mit Taxisnet ein",
            "4": "gov.gr gibt Authorization Code zurück",
            "5": "Code → Token → anonymer Nullifier-Hash",
            "6": "NIEMALS: AMKA, Name, Adresse gespeichert",
        },
        "activation_gates": ACTIVATION_GATES,
        "endpoints": {
            "GET /status": "Aktivierungsstatus",
            "GET /login": "OAuth Login (wenn aktiv)",
            "GET /callback": "OAuth Callback",
            "GET /family/verify": "Liquid Democracy Stub",
        },
        "gsrt_contact": "https://www.gsrt.gr",
    }

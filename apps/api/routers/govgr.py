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
import secrets
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx

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

# In-memory state store (production: Redis)
_oauth_states: dict[str, dict] = {}


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

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created": datetime.now(timezone.utc).isoformat(),
        "redirect_after": redirect_after,
    }
    auth_url = (
        f"{GOVGR_AUTH_URL}?client_id={GOVGR_CLIENT_ID}"
        f"&redirect_uri={GOVGR_REDIRECT_URI}"
        f"&response_type=code&scope=openid+profile&state={state}"
    )
    logger.info(f"[MOD-09] OAuth login initiated, state={state[:8]}...")
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

    # Validate state
    if state not in _oauth_states:
        raise HTTPException(400, "Ungültiger OAuth State — mögliche CSRF-Attacke")
    state_data = _oauth_states.pop(state)

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

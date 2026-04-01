"""
MOD-09: gov.gr OAuth2.0 Stub
Vorbereitung für Alpha Deployment.

AKTIVIERUNG NUR WENN:
- 500+ aktive Nutzer
- 3+ NGO Partnerschaften
- Publiziertes Roadmap
- Offizielle Anfrage an GSRT (gov.gr OAuth Provider)

@ai-anchor MOD09_GOVGR_OAUTH
@activation-gate 500_users + 3_ngos + published_roadmap
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth/govgr", tags=["MOD-09 gov.gr OAuth"])

ACTIVATION_GATES = {
    "users_500":         False,
    "ngos_3":            False,
    "roadmap_published": True,
    "govgr_approved":    False,
}

def is_active() -> bool:
    return all(ACTIVATION_GATES.values())

GOVGR_CLIENT_ID    = os.getenv("GOVGR_CLIENT_ID", "")
GOVGR_REDIRECT_URI = os.getenv("GOVGR_REDIRECT_URI", "https://ekklesia.gr/auth/govgr/callback")
GOVGR_AUTH_URL     = "https://oauth2.gov.gr/oauth2/authorize"


@router.get("/status")
async def govgr_status():
    """Status der gov.gr OAuth Integration."""
    gates_met = sum(1 for v in ACTIVATION_GATES.values() if v)
    return {
        "module": "MOD-09 gov.gr OAuth2.0",
        "status": "active" if is_active() else "stub",
        "progress": f"{gates_met}/{len(ACTIVATION_GATES)} Aktivierungsbedingungen",
        "gates": {
            "500_aktive_nutzer":     ACTIVATION_GATES["users_500"],
            "3_ngo_partnerschaften": ACTIVATION_GATES["ngos_3"],
            "roadmap_publiziert":    ACTIVATION_GATES["roadmap_published"],
            "govgr_genehmigung":     ACTIVATION_GATES["govgr_approved"],
        },
        "alternative": {"module": "MOD-01 HLR", "endpoint": "/api/v1/identity/verify"},
        "env_configured": bool(GOVGR_CLIENT_ID),
    }


@router.get("/login")
async def govgr_login(redirect_after: str = Query("/")):
    """Startet gov.gr OAuth2.0 Flow. STUB wenn nicht aktiv."""
    if not is_active():
        raise HTTPException(503, detail={
            "error": "govgr_not_active",
            "message": "gov.gr OAuth ist noch nicht aktiviert",
            "gates": ACTIVATION_GATES,
            "alternative": {"method": "HLR Verifikation", "endpoint": "/api/v1/identity/verify"},
        })

    import secrets
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"{GOVGR_AUTH_URL}?client_id={GOVGR_CLIENT_ID}"
        f"&redirect_uri={GOVGR_REDIRECT_URI}"
        f"&response_type=code&scope=openid+profile&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def govgr_callback(
    code: str = Query(None), state: str = Query(None), error: str = Query(None)
):
    """OAuth2.0 Callback von gov.gr. STUB."""
    if error:
        raise HTTPException(400, f"gov.gr OAuth Fehler: {error}")
    if not is_active():
        raise HTTPException(503, "gov.gr OAuth nicht aktiv")
    if not code:
        raise HTTPException(400, "Kein Authorization Code")

    return {
        "status": "stub",
        "message": "Callback erhalten — echter Flow bei Aktivierung",
        "code": code[:8] + "..." if code else None,
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
        "name": "MOD-09: gov.gr OAuth2.0", "phase": "Alpha (Stub)",
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

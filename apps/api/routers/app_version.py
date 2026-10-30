"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from rate_limit import client_flow
from fastapi import APIRouter, Request

from routers.identity import identity_key_check_enabled, identity_rotate_enabled

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.37"
LATEST_VERSION_CODE = 66
# v1.0.33 signs vote-status reads and uses v2 evaluations. F-Droid adds
# an ABI digit (1-4) to the base code; keep the scalar for legacy clients.
MIN_REQUIRED_VERSION_CODE = 62
MIN_REQUIRED_VERSION_CODE_BY_CHANNEL = {
    "direct": MIN_REQUIRED_VERSION_CODE,
    "play": MIN_REQUIRED_VERSION_CODE,
    "fdroid": MIN_REQUIRED_VERSION_CODE * 10 + 1,
}
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.37 — Ημερομηνία και ώρα τελευταίας ενημέρωσης των δεδομένων της Βουλής στις λίστες νομοσχεδίων και δημοφιλών. Ειδοποίηση όταν τα δεδομένα ενδέχεται να μην είναι ενημερωμένα."
RELEASE_NOTES_EN = "v1.0.37 — Last update date and time for Parliament data in the bills and trending lists. Notice when the data may be outdated."

FDROID_URL = "https://f-droid.org/packages/ekklesia.gr/"
PLAYSTORE_URL = "https://play.google.com/apps/testing/ekklesia.gr"
DIRECT_APK_URL = "https://github.com/NeaBouli/pnyx/releases/download/v1.0.37/ekklesia-v1.0.37-vC66-DIRECT.apk"


@router.get("/version")
@client_flow
async def app_version(request: Request = None):
    return {
        "latest_version": LATEST_VERSION,
        "latest_version_code": LATEST_VERSION_CODE,
        "min_required_version_code": MIN_REQUIRED_VERSION_CODE,
        "min_required_version_code_by_channel": MIN_REQUIRED_VERSION_CODE_BY_CHANNEL,
        "release_notes_el": RELEASE_NOTES_EL,
        "release_notes_en": RELEASE_NOTES_EN,
        "fdroid_url": FDROID_URL,
        "playstore_url": PLAYSTORE_URL,
        "direct_apk_url": DIRECT_APK_URL,
        "force_update": FORCE_UPDATE,
        # Released v34 profiles call this endpoint but read camelCase fields.
        "version": LATEST_VERSION,
        "downloadUrl": DIRECT_APK_URL,
        "playStoreUrl": PLAYSTORE_URL,
        # EVA-001 PR4: clients rotate legacy server-generated keys only when the
        # server advertises it (IDENTITY_ROTATE_ENABLED).
        "features": {"identity_rotate": identity_rotate_enabled(), "identity_key_check": identity_key_check_enabled()},
    }

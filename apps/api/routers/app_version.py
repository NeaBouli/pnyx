"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.15"
LATEST_VERSION_CODE = 44
MIN_REQUIRED_VERSION_CODE = 1
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.15 — Στοχευμένη ZK ψηφοφορία, βελτιωμένος έλεγχος πηγών και νεότερη έκδοση Android."
RELEASE_NOTES_EN = "v1.0.15 — Scoped ZK voting, improved source checks, and latest Android release metadata."

FDROID_URL = ""  # Not live yet — MR !38007 pending
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=ekklesia.gr"
DIRECT_APK_URL = "https://ekklesia.gr/download/"


@router.get("/version")
async def app_version():
    return {
        "latest_version": LATEST_VERSION,
        "latest_version_code": LATEST_VERSION_CODE,
        "min_required_version_code": MIN_REQUIRED_VERSION_CODE,
        "release_notes_el": RELEASE_NOTES_EL,
        "release_notes_en": RELEASE_NOTES_EN,
        "fdroid_url": FDROID_URL,
        "playstore_url": PLAYSTORE_URL,
        "direct_apk_url": DIRECT_APK_URL,
        "force_update": FORCE_UPDATE,
    }

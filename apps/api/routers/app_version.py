"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.31"
LATEST_VERSION_CODE = 60
MIN_REQUIRED_VERSION_CODE = 1
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.31 — Βελτιωμένη συμβατότητα επιλογής Περιφέρειας και Δήμου σε συσκευές Xiaomi/MIUI και ανθεκτικότερη κανονικοποίηση ελληνικών αριθμών κινητού από πληκτρολόγηση ή επικόλληση."
RELEASE_NOTES_EN = "v1.0.31 — Improved Region and Municipality selection compatibility on Xiaomi/MIUI devices and more robust normalization of Greek mobile numbers entered or pasted from different keyboards."

FDROID_URL = "https://f-droid.org/packages/ekklesia.gr/"
PLAYSTORE_URL = "https://play.google.com/apps/testing/ekklesia.gr"
DIRECT_APK_URL = "https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk"


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
        # Released v34 profiles call this endpoint but read camelCase fields.
        "version": LATEST_VERSION,
        "downloadUrl": DIRECT_APK_URL,
        "playStoreUrl": PLAYSTORE_URL,
    }

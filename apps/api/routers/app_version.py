"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.29"
LATEST_VERSION_CODE = 58
MIN_REQUIRED_VERSION_CODE = 1
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.29 — Διορθώθηκε η εισαγωγή ελληνικών αριθμών κινητού κατά την επαλήθευση. Υποστηρίζονται με ασφάλεια οι μορφές +30, 0030 και η επικόλληση πλήρους αριθμού χωρίς εσφαλμένη απόρριψη ή περικοπή ψηφίων. Περιλαμβάνονται επίσης ενημερώσεις ασφάλειας εξαρτήσεων."
RELEASE_NOTES_EN = "v1.0.29 — Fixed Greek mobile-number entry during verification. +30, 0030, and full-number paste formats are now handled safely without false rejection or digit truncation. Dependency security updates are also included."

FDROID_URL = ""  # Not live yet — MR !38007 pending
PLAYSTORE_URL = "https://play.google.com/apps/testing/ekklesia.gr"
DIRECT_APK_URL = "https://github.com/NeaBouli/pnyx/releases/download/v1.0.29/ekklesia-v1.0.29-vC58-DIRECT.apk"


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

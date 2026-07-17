"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.27"
LATEST_VERSION_CODE = 56
MIN_REQUIRED_VERSION_CODE = 1
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.27 — Οι ψηφοφορίες προσαρμόζονται πλέον με ασφάλεια στον επαληθευμένο Δήμο και την Περιφέρεια, ενώ τα νομοσχέδια της Βουλής παραμένουν διαθέσιμα πανελλαδικά. Ενισχύθηκαν οι έλεγχοι δικαιώματος ψήφου, η ασφαλής εισαγωγή λογαριασμού και η ενιαία καταμέτρηση Tier-1 και Semaphore ZK."
RELEASE_NOTES_EN = "v1.0.27 — Voting lists now safely follow the verified municipality and region, while Parliament bills remain available nationwide. Vote eligibility, secure account import, and unified Tier-1 plus Semaphore ZK counting were also strengthened."

FDROID_URL = ""  # Not live yet — MR !38007 pending
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=ekklesia.gr"
DIRECT_APK_URL = "https://ekklesia.gr/download/ekklesia-latest.apk"


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

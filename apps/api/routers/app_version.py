"""
App Version Check Endpoint
GET /api/v1/app/version — kein Auth noetig
Liefert aktuelle Version + Update-Info fuer Mobile Clients.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/app", tags=["App Version"])

# Hardcoded — bei neuem Release hier anpassen
LATEST_VERSION = "1.0.30"
LATEST_VERSION_CODE = 59
MIN_REQUIRED_VERSION_CODE = 1
FORCE_UPDATE = False

RELEASE_NOTES_EL = "v1.0.30 — Η εφαρμογή διαβάζει πλέον την εγκατεστημένη εγγενή έκδοση Android (όνομα και κωδικό) για την εμφάνιση και τη σύγκριση ενημερώσεων, αποτρέποντας επαναλαμβανόμενες ή εσφαλμένες ειδοποιήσεις ενημέρωσης. Οι σύνδεσμοι ενημέρωσης παραμένουν συμβατοί με παλαιότερες εγκαταστάσεις vC34."
RELEASE_NOTES_EN = "v1.0.30 — The app now reads the installed native Android version name and code for display and update comparison, preventing repeated or incorrect update prompts. Update links remain compatible with legacy vC34 installs."

FDROID_URL = ""  # Not live yet — MR !38007 pending
PLAYSTORE_URL = "https://play.google.com/apps/testing/ekklesia.gr"
DIRECT_APK_URL = "https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/ekklesia-v1.0.30-vC59-DIRECT.apk"


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

"""Exact R3 content deltas for the public EKA audit disclosure."""

import hashlib

import r0_inventory

# Exact inventory hashes, recomputed from the combined tree (T-434). Layers:
# EKA audit disclosure (index/security); EKA-37 API rows and vote example
# corrected against OpenAPI (api); T-419 / EKA-38 F-Droid availability sentence
# (faq/roadmap); T-420 (EKA-50/51/52) wiki fact corrections: every page gets the
# "24 Ώρες" footer target /el/bills?status=WINDOW_24H; modules.html drops the
# unregistered MOD-13/MOD-17 rows and the duplicate dot-mod02 id; database.html
# replaces phantom MOD-25 tables with the runtime ORM and raw-SQL tables
# (incl. cplm_history, MOD-24); community.html drops the duplicate FAQ nav link.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "27279cbac3f839856179b4c3c860a96a13c242ef048454d02b3592597dbabfa6",
    "docs/wiki/api.html": "230ee1433143181c8b5415e412c7fa76783f324f9b919bbd9053b700f529057c",
    "docs/wiki/architecture.html": "3d02bab990a434ce76edcafc0cd68341835d10c7014cce26095b01e10ebee0a7",
    "docs/wiki/broadcasting.html": "a8fddee2bd52978dcb390a442c541ee56aec2ffdf4a0db49e2ec59a772ac2c85",
    "docs/wiki/contributing.html": "9e506159cf02f75cfc0ae1df2c6a774d76bc3a7f6b158fe48350189475a22cc9",
    "docs/wiki/database.html": "bcb8ccacb2e45c2cd63313235a4089e6b705c6138f70f0cd0ec9deb4c4a789e4",
    "docs/wiki/delete-account.html": "ef1841838c9748cda7a3ef1e07c4f7e0219ecbdfe3faad924141e0d806e7bbd9",
    "docs/wiki/faq.html": "3fafa69517258b1fc58d47c1f22f0ebb29c3772a53514a53d421f7b86a668854",
    "docs/wiki/index.html": "9d8788021cdd68f3c8c139959b9630c9aacf87e5b38cbafb28d820a2d7f31eb1",
    "docs/wiki/modules.html": "ef38a2a2d1ade010f1aef89ac3872d623b62eb0993ea0b94a80dd2c352e28df9",
    "docs/wiki/privacy.html": "5d5873d6aa5495337338da0e5efee6d11dc5c430a5e618966e7b8b9434f59b3a",
    "docs/wiki/roadmap.html": "8d10185a202cbd0bc01425a98802ba10b804b2317c52ab456a83b1655a1fe809",
    "docs/wiki/security.html": "71ee2739bc17db75a4ea7e1752f6e3f1d41052394cb1c17f244f6df68f894094",
    "docs/wiki/whitepaper.html": "0d1d466177a4cd86f3a9aa17e4e16d671bc7108bb03dd417f5f951b947c5ade3",
}
# T-420 changed only the "24 Ώρες" footer target; findings text is unchanged.
APPROVED_AUDIT_PAGE_SHA256 = "7cc7410945f48e8fdfe614d49b4b36a6b75d00f96f206e32ccaea4f3066ba973"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

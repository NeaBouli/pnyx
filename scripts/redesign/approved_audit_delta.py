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
# T-421 (EKA-48): head metadata only — the same-URL hreflang="en" alternate is
# removed, x-default added where missing, and zk-voting gains og:site_name and
# a twitter card; wiki/index and wiki/roadmap gain a WebPage JSON-LD block.
# T-473 (#365): faq.html toggleLang also sets document.documentElement.lang.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "1c6af6ce632db8cc239b24d6446896694f2afda0c37b8a94d107bc295be5aaef",
    "docs/wiki/api.html": "373f48127cfc5b39885a2265bc919f14f358a5aa6d1a8ba1e1301a0fd603834a",
    "docs/wiki/architecture.html": "190c8db92dce0d7b70f4c06e82922e6c3085cff62328eeaaf0c4fdc8b96fd21b",
    "docs/wiki/broadcasting.html": "faa500a62568a696b39470103fc024905ac68b447f6c37421bf4bfd9ef39c517",
    "docs/wiki/contributing.html": "d71786cb758b2296e49830cfcc5e25ef2c7a205c7126050a6e2f9f6e0fedc429",
    "docs/wiki/database.html": "4d15f4b7e9a0e46ea6ca6e1500c1a7174a1a7e5f49f405c108c01f787a053662",
    "docs/wiki/delete-account.html": "621f7cbb772dee4c0c427ecf93282a8547c25d3b7e354b8121ab1403ec26fdf9",
    "docs/wiki/faq.html": "b68cb7ffb7afdf818dc509034a8610d9ffd22e942dcd0f36488e71502656ed0a",
    "docs/wiki/index.html": "b06a9584b220efbd0d974d78e0035199a72f6e25230ea97ecdb1e257bf15e001",
    "docs/wiki/modules.html": "eff962d4be3dff4a17e8be1bb13f734ce5e66e117229e428c50dadb8bc33e8a8",
    "docs/wiki/privacy.html": "c0fc1c241da278b4e8cd10289f7bce8e7f9ccc8c6b96bbfcade005b78f8a2a1b",
    "docs/wiki/roadmap.html": "4388843469990e77dc8c00528f4a228ed2944c4b5cefdc5a4e81412444246883",
    "docs/wiki/security.html": "984ac68364a1eafe4276e027074bac1ae0a539f15d6acddcfa655b67749fed2a",
    "docs/wiki/whitepaper.html": "446087437e0d24bfbd948ef9f8cc5e72e3559415d8d4910dc3562b6e2dcdaf1a",
    "docs/wiki/zk-voting.html": "9972052c4edfc131d9a19199c8e148ba4190682f4fde3c144c3aab98091af475",
}
# T-420 changed only the "24 Ώρες" footer target; T-421 only drops the same-URL
# hreflang="en" head link. Findings text is unchanged.
APPROVED_AUDIT_PAGE_SHA256 = "da5941f263ad117d68f41cd93d919b45ac6b8d894410255b89b5d43a1ff077e7"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

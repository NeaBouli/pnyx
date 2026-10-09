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
# T-475/T-479: r3-wiki.css pins the <=920px nav language switch (inset focus ring).
# T-592 (owner-approved 2026-10-04): zk-voting status text says the guarded Parliament ZK
# rollout is paused since 2026-10-03 (security review; Tier-1 unaffected) in meta, JSON-LD,
# badge, Tier-2 heading and the status sentence; the Arweave paragraph says no new ZK votes are
# accepted during the pause and ZK auto-publication applies only if the rollout is re-enabled;
# the intro and status data-el/data-en attributes say the same.
# T-595: zk-voting gets the same nav language switch (langBtn + inline toggleLang) as the other
# wiki pages; it was the only wiki page without one. The initial Greek text of each data-el
# element now equals its data-el value, so toggling EN → ΕΛ restores the same copy.
# T-512/T-540 (EKA-53, #431): community.html's DeepL usage fetch moves from
# /api/v1/admin/deepl/usage to /api/v1/public/deepl/usage; nothing else changes.
# T-614 (coordinator-approved 2026-10-09, Gio delegation): faq.html and roadmap.html say the
# direct Android APK v1.0.33/vC62 is published and vC62 is live in Google Play Closed Testing
# for testers with production access pending (EL and EN, incl. the FAQ JSON-LD answer).
# T-617 (coordinator-approved 2026-10-09): community.html names the production server Hetzner
# CX43 (8 vCPU / 16 GB, verified on host) instead of CX33, in the server tile subtitle and the
# development-support cost row; the row's monthly figure follows the API config (server
# cost_monthly 10.0 €), shown as ~€10/μ.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "8eb8f6893a3d796b023801860df727023513815d33769fc65dd0ca1a4fea0694",
    "docs/wiki/api.html": "0f2b6771a112f089c7fba6b1ef3185e061b073cd338f3db10a38a3c3c3c2515f",
    "docs/wiki/architecture.html": "8198bc8764e1d848f512a14195d2a219e6ce36398227f6744ce2793f401273d3",
    "docs/wiki/broadcasting.html": "9e14ffa72fa9e524c109748881d2ed941aeeb257d44570b191aaa24d5fb47b62",
    "docs/wiki/contributing.html": "08d936e733910ef72639759b7ec5ff92993db2d7a2ad9ef21d86fa3a1cf3838c",
    "docs/wiki/database.html": "9a86616c03c17a3cf3b8f95458d10286056bb99c760e0daf944ed1e54e4d35b2",
    "docs/wiki/delete-account.html": "426b3c7c2a252a4b1520ad1bdd0bfee812904c43f057e8c805114803f09778e9",
    "docs/wiki/faq.html": "4bda2ccff854016b88249d18952e3c62de297b909d70a8e5e15886cc170a09db",
    "docs/wiki/index.html": "933348ee7f46e0244edd90d76c03daeb46781255325c0f6ae5bd8c3bb02854d5",
    "docs/wiki/modules.html": "f0f54584009d7727b5f13ab16fa48046339e7ea3f7542f045f7e2242e1849fcd",
    "docs/wiki/privacy.html": "8887a4b19c0fdca6f52cec50289d5c4e17eb21e8839c5dc9405cd9395ee97ba1",
    "docs/wiki/roadmap.html": "0bc54ef66ee79ec0db67ed8f1e334dc22174039f1e6d64d23ed2723763e34b77",
    "docs/wiki/security.html": "5dac9dce20e8552fa031fdd03c0501a752e6e4ae05f16c384c697882258da44f",
    "docs/wiki/whitepaper.html": "ebf88a4bbbbaf7c4350cdfe9076c5010eaa2f207ef4a275e0d65d5aa9828b6c0",
    "docs/wiki/zk-voting.html": "a9d955a74ad6b0f50a6d504effb3f38c0a07210e9b6a948241e89dead0401e24",
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

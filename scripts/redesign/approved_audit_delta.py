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
# T-9022 (owner-approved 2026-10-10): current CX43 monthly figures follow the
# owner's approximate 25 EUR cost basis, explicitly dated 10.2026 in EL/EN;
# the existing zero-receipts fallback uses the same 25 EUR monthly estimate.
# Historical audit/planning records and the immutable R0 inventory are unchanged.
# T-658 (coordinator decision (a), 2026-10-10): community.html gains a reserve tile that shows the
# public monetary reserve from payments/status (surplus beyond server target and domain need);
# unknown/unavailable data shows "—" with a notice, never a zero balance.
# T-9026 (#508-P3, owner-approved 2026-10-10): server/domain likewise start with
# unknown loading balances and bilingual unavailable notices, not seeded debt.
# Refresh failures retain each last valid snapshot with a stale-data notice;
# the existing reserve behavior, costs and paused payment links are unchanged.
# T-9030 (owner-requested 2026-10-10): reserve now retains its last valid snapshot
# on refresh failure with the same EL/EN stale notice as server/domain; zero is
# valid, unknown stays "—" and valid recovery hides the notice. Display only.
# T-9035 (owner-requested 2026-10-10): explicit public-projection availability
# preserves the existing stale/unknown UI contract. Both annual-cost displays
# show server + domain (~309.30 EUR/year, 10.2026); recurring USD, one-time and
# variable costs remain separately disclosed, without currency conversion.
# T-9106 (Gio approved "correct now", 2026-10-11, EVA-001/002/006/010/013/015/032):
# public claims match the current implementation. Every page's legal modal says
# "Ψήφοι (ψευδώνυμα)"; privacy/faq/roadmap/zk-voting/whitepaper/delete-account/api
# say the Ed25519 key pair is created on the server and handed to the device once
# (not stored or logged), votes are pseudonymous (not anonymous towards the
# operator), raw demographics are not stored for new/renewed verifications,
# region is self-declared and locked, GDPR/"no personal data" badges are replaced
# by factual minimization statements, and TrueRepublic/iOS are labelled planned /
# not available. community.html: "Data minimization." and pseudonymous POLIS identity.
# T-9128: community result counters render null as withheld.
# T-9132 (Gio approved 2026-10-16, ADR-007 S1): ordinary votes use no-name /
# pseudonymous wording; retention, VAA, IP handling and scoped k>=10 assurances
# follow the code. Ordinary Arweave aggregates are distinguished from paused ZK.
# T-9132 review: IP counters expire; access logs rotate by size with no fixed
# retention period. FAQ default Greek matches EL/JSON-LD, votes are pseudonymous,
# and FAQ/roadmap ZK status follows the security-review pause since 2026-10-03.
# T-9140 (owner-requested): community.html links to the existing sandbox mirror
# README instead of the obsolete setup page (mirror-setup.sh is absent). EL/EN
# mirror copy follows the current read-only sandbox boundary, without promising
# a one-command installer, five-minute cache sync or unsupported minimum specs.
# T-9148 (#636, owner-requested): neutral AI labels and FAQ text (EL/EN/JSON-LD);
# community model attribution is fixed to V-Labs Artificial Systems · vlabs.gr.
# Only the changed pages below receive new exact inventory fingerprints.
# T-9149: exact script/listener migration; public copy and JSON-LD are unchanged.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "ae24926c43df3cc008cbed1a652a4a947bd1453b295c7c5b7b2526427cf5b3bc",  # T-9148: reviewed EL/EN AI wording
    "docs/wiki/api.html": "346edd578d6cbc4c9910bbda0932a18b546bf11d23b90b1710cd754da136d49c",  # T-9148: reviewed EL/EN AI wording
    "docs/wiki/architecture.html": "ea6ee279e1faab60cf8992f9ad8962cedb75e8b369d76d39dc19e81c2eb40e24",
    "docs/wiki/broadcasting.html": "6829e43472185780402c627c86725d908eef8397ea276ae450887f0980318f56",
    "docs/wiki/contributing.html": "932b3ec81659495889cdc833fede10bfd3af757fea9c7da34264f15ae7d3551d",
    "docs/wiki/database.html": "5eca4ae8c7bedadcc395a9b95fbe6fd7f7cfd29dbdd15e519c1373d3be5d82a5",
    "docs/wiki/delete-account.html": "82c76020a3a7552002a4299405d38f8dfbe19a3ed837dd066dfb4590f8fd4e27",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/faq.html": "3832235dd443d3d12bc48895eb488ecf7083967780dc53cd2f57ad28237e6195",  # T-9148: neutral public AI wording
    "docs/wiki/index.html": "c63a5fdcace1e259b8e7ada62c7159af2d787e22c6f8861b71d365d7877c9ccd",  # T-9047/T-9048: named code region, contrast, headings and document language; T-9106: legal-modal claims text
    "docs/wiki/modules.html": "316b661eb540b6aafe91841b8935931ba9ad0e89db277a5c7c9f492dc696ee53",  # T-9148: reviewed EL/EN AI wording
    "docs/wiki/privacy.html": "67de629d0d035ebd4e9715ea8c9c471c1f9cf4ec502966b1539b42dbc7b4034a",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/roadmap.html": "a4d32da00db577ca47ba683ecf01692cd34542070c819213a6a5868c67ea55b4",
    "docs/wiki/security.html": "c2fa9fa3ebb846d421a58cd507968b8044fdfb1f98125e0fca6d2b164be16bff",  # T-9127: OPEN_END voting closed
    "docs/wiki/whitepaper.html": "cc7725fcbccb1eb1c1d286c16b4c640a3760ebfcc49869d96262ac8a1c8d6072",  # T-9127: OPEN_END voting closed
    "docs/wiki/zk-voting.html": "63c08e5655437d2afca0f32d71c417029c37bae90e75c03877b78a135a4d6e3a",
}
# T-420 changed only the "24 Ώρες" footer target; T-421 only drops the same-URL
# hreflang="en" head link. Findings text is unchanged.
APPROVED_AUDIT_PAGE_SHA256 = "4f6db0cbd17dc6928bff56364cf52aabffaa6931d7fba82b29e8ef9f5798095f"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

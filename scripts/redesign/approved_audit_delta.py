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
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "070111774fa4640a4bde4857a2aca7bbf73f0a06db73e748e73c5e045422084f",  # T-9048: scoped contrast, heading semantics and document-language toggle; T-9106: legal-modal claims text
    "docs/wiki/api.html": "e56012799245533915b72606ffc8955bd4c3ce61f3ba5f9926fd07abb101106c",
    "docs/wiki/architecture.html": "1af2aa9c102d66887e52627c277ebfea03935a2ff3b772235cf07ed3d4313f0b",
    "docs/wiki/broadcasting.html": "eb345ed4551a94220e47aeb4b40c7c745bf6dfeaa5f330eac6f629a09d31f716",
    "docs/wiki/contributing.html": "bb4048480c3b75cb98ee668305833fe36b2c939f29ef27f1f8bec230c9d49d88",
    "docs/wiki/database.html": "08ac70323ffa6a6db969f41678ad8de9afd5fdd8f5b74981665cbf8e38afb9f9",
    "docs/wiki/delete-account.html": "3d7090ca86d5d17207477b664fa9d29066c0073a446d67e13dfd7eaf26822d1e",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/faq.html": "0d9583ac4244b4dfe44dbf96ceeff530adc1ed2d807c51df2d2984393296454f",  # T-9127: OPEN_END voting closed
    "docs/wiki/index.html": "ea418f9164a41aafa72721bdc8feaf7612a26fc83a32e7e781d7f166fe278419",  # T-9047/T-9048: named code region, contrast, headings and document language; T-9106: legal-modal claims text
    "docs/wiki/modules.html": "dd1f4addfdc25337790028ac3f3d4d608832a11ad682c9068dae1c9b0a265544",  # T-9072: neutral unknown health dots, MOD-23/25 mapping, localized status labels; T-9106: legal-modal claims text
    "docs/wiki/privacy.html": "58550c4a6d68fb39a43c46b2810819dcb8af70cc141f43d9fa5651aac4e990b8",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/roadmap.html": "8fae28938db627f3cade818fc490e1fac5f1be3984544c72a16817fd9aa84ff5",
    "docs/wiki/security.html": "0546a8aaf80b51cd4a9de72a33ce82059f8da96ce7ab2a20af7ad278932edc36",  # T-9127: OPEN_END voting closed
    "docs/wiki/whitepaper.html": "c657de01e6cb47060bae0b28b2dab96349e0d663eb16e584daafc0940af56f1f",  # T-9127: OPEN_END voting closed
    "docs/wiki/zk-voting.html": "5dafa29250109c593a4aaabe65b7bc2a824d9f1efc90485d0278dd6325b07ccf",
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

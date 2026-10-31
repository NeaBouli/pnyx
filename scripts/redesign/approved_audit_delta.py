"""Exact R3 content deltas for the public EKA audit disclosure."""

import hashlib

import r0_inventory

# B09/B10 (user-requested, 2026-10-31): dated source counts/cost basis in the
# landing, community, wiki index, API/database/modules metadata and whitepaper;
# audit's 188 endpoints explicitly labelled historical (2026-09-15); FAQ cost
# answer and JSON-LD; canonical privacy identity/newsletter facts mirrored in
# security, whitepaper and database; security's server-generated one-time key
# handoff and Argon2id v2 + compatibility anchor; planned/inactive future bridge
# with no runtime module ID. Privacy/whitepaper hosting wording stays generic.
# PR #728 fix (operator-approved 2026-10-31): production Argon2id v2 is
# dated 2026-10-31, conditional on the v2 setting/column; code defaults to v1.
# Apply that scope in the shared paragraph and every security/whitepaper label.
# Move the audit date immediately before its 188-endpoint claim (EL/EN), so
# historical exemptions cannot cover a neighbouring router/current claim.
# The approved planned bridge remains unchanged.
# Exact fingerprints below protect all of these visible deltas and existing
# interactions. The immutable R0 inventory is not regenerated.
APPROVED_LANDING_FACT_REPLACEMENTS = {
    ("13 Πίνακες, Schema", "13 Tables, Schema"):
        ("24 πίνακες ORM, Schema", "24 ORM tables, Schema"),
}

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
# B08/B12/B17 (user-requested): Compass/server-history and conditional Arweave
# disclosures; production small-cell/sensitivity facts; FAQ grouping/counts/schema;
# initial Greek copy; established legal-name attribution and operator responsibility.
# PR #722 fix round: AES key availability and incomplete migrations (EL/EN/FAQ schema).
# T-9149: deferred script/listener migration; public copy and JSON-LD are unchanged.
# T-9172: Direct APK copy is v1.0.37/vC66 in EL/EN/FAQ JSON-LD; Play stays vC62.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "c4b86025530dfb7f79efefe3d39af6e5e40b40771343de6cd20d26abceebc662",  # T-9153: paused donations; neutral Arweave tooltip, no acquisition prompts or exchange links
    "docs/wiki/api.html": "85c11c8e1186fc6fde591793cafa662a09926205d95226125fd4afa86c85b5f7",  # B01 / PR #706: explicit read/heavy/generate classes and bounded work
    "docs/wiki/architecture.html": "4afb91b2dcee4ce3ce136746205cd9669916ae7aea7f4b2dd46f531cf153b920",
    "docs/wiki/broadcasting.html": "13f44b28b80bd7eda2f354db950597103a36d567aa4dfa967d6137f4b78fd23c",
    "docs/wiki/contributing.html": "ce5f0381727ea54d45929c4d919150dc90a2d8c772505d5d17241c90165c257f",
    "docs/wiki/database.html": "221900a3a53767262512e6f23b7c124df006c9287d81f56f86840150ed9b4900",
    "docs/wiki/delete-account.html": "a62e22bd83f648660cb5b53d3beaf25f0c0270e50b722459278f87391e14cacd",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/faq.html": "61556df675fd43a764de2fff92d0893ba69a369505d9508d7a5ad1532718b703",  # T-9153: paused donations; HLR information and FAQ EL/EN/JSON-LD
    "docs/wiki/index.html": "ad0c2211c3787564029b42214b5c979adfc643ebd07f339585117d0e3bcd3ee1",  # T-9047/T-9048: named code region, contrast, headings and document language; T-9106: legal-modal claims text
    "docs/wiki/modules.html": "dee125fdcee6c374909982e6559fe913a08e9a286c9422f189631254af4321a5",  # T-9148: reviewed EL/EN AI wording
    "docs/wiki/privacy.html": "8f41fb87b6a8c53a52721b8c386134b14f3225bce6cae747fca539ea71034412",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/roadmap.html": "c81071d697e2a626945d2274fb417195b77330194d49d8f9b532711a47d5850c",
    "docs/wiki/security.html": "bae405a791e025495cccf82f34c35fe11f33c613190d98af6308645843a4349c",  # T-9127: OPEN_END voting closed
    "docs/wiki/whitepaper.html": "01903972f484ef5627d94290e353af5dfdbe5d5ffc6a343a442bf0ae80c66802",  # T-9127: OPEN_END voting closed
    "docs/wiki/zk-voting.html": "650a3e85f98db88751c2702229eb016cc722206758da1a03fa7af73e5914af9c",
}
# T-420/T-421: footer target and hreflang; B17: canonical legal-name attribution.
# Published finding counts and finding text are unchanged.
APPROVED_AUDIT_PAGE_SHA256 = "a8a0d507ada4ba294efa387e81eef5e6656d694cd2ae2e0c1a4a4e0bfb43c93d"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

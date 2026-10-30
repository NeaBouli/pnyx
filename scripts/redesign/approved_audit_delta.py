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
# T-9149: deferred script/listener migration; public copy and JSON-LD are unchanged.
# T-9172: Direct APK copy is v1.0.37/vC66 in EL/EN/FAQ JSON-LD; Play stays vC62.
APPROVED_WIKI_INVENTORY_HASH = {
    "docs/community.html": "3056fa1108b6f6701eda9888653a0eee27153b7c2af26d8865350fb3cd651383",  # T-9153: paused donations; neutral Arweave tooltip, no acquisition prompts or exchange links
    "docs/wiki/api.html": "c9ab8e5d6a4ffcae272c877f12672741c92a00c6834f1f664c06048ecf319301",  # B01 / PR #706: explicit read/heavy/generate classes and bounded work
    "docs/wiki/architecture.html": "15bf107d472a1a299c1a0f91ad42c90d6542146eb8f384b09f0ee2d39b0c34ca",
    "docs/wiki/broadcasting.html": "b5e2ee8a6c84697b9e5921d1910adc7a222de8fc41630f72cffa7c61aba106e0",
    "docs/wiki/contributing.html": "44b72f926ea13ed3d6000269ac8be6444997d8096f6d8f9377a533f29f53d842",
    "docs/wiki/database.html": "b5eb36171a860d2b0466c29d2e31d6b7461bda1d08eea83aa3bd39c48c26d219",
    "docs/wiki/delete-account.html": "de0002a7852aab5de44262c4d8ad8a86e51453a491ff3fbcfe0daa8a7d03ee25",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/faq.html": "dc44f919d09557503372a89cf612a2feb44a33fbc0500af725386dfc1a748989",  # T-9153: paused donations; HLR information and FAQ EL/EN/JSON-LD
    "docs/wiki/index.html": "3903bcd0ff9928025235f924c78724ff0e4fbecf20d07572dbf3f2cc41271b97",  # T-9047/T-9048: named code region, contrast, headings and document language; T-9106: legal-modal claims text
    "docs/wiki/modules.html": "3debb7c511a4a2702b7924cb1e20fba5f1a0a44289fd225a01645adb478fcb0e",  # T-9148: reviewed EL/EN AI wording
    "docs/wiki/privacy.html": "418e942092ae40c39565fdccbd9afcd1e38535068683a4a58c4f266babc3bec2",  # T-9106: EVA claims (keys, pseudonymous votes, demographics, email/newsletter)
    "docs/wiki/roadmap.html": "3b575ee5724570cd922ddc049a856f08314e0c96af4a0983636650a4302ef880",
    "docs/wiki/security.html": "9d2303450e9b2fbf74cb218d512cfd43ebcaf72027679e36cb2b05101ab12723",  # T-9127: OPEN_END voting closed
    "docs/wiki/whitepaper.html": "1e704f1b0b586a85cdead864cd1ba6428eeee2f360b0386c11c7ffa7f6cc91c5",  # T-9127: OPEN_END voting closed
    "docs/wiki/zk-voting.html": "5b2d5e1fe862adf56e746683077c22139e2501ba3cf45121fef93b97c8084edb",
}
# T-420 changed only the "24 Ώρες" footer target; T-421 only drops the same-URL
# hreflang="en" head link. Findings text is unchanged.
APPROVED_AUDIT_PAGE_SHA256 = "ec76a7e97fad62d71dcefb4da8cd31ee5f7a809aadf3363e143fb24e30a37fa9"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

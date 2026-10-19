"""Explicit owner-approved delta from the frozen R0 public-page baseline.

The original inventory remains immutable. Only the precise Plausible loader
removed under EKA-33 is excluded when comparing semantic page contracts.
Non-gated pages retain exact post-removal byte hashes below.
"""

from __future__ import annotations

from copy import deepcopy

SCRIPT = {
    "src": "https://analytics.ekklesia.gr/js/script.js",
    "attrs": {
        "data-domain": "ekklesia.gr",
        "defer": "",
        "src": "https://analytics.ekklesia.gr/js/script.js",
    },
}
RESOURCE = {
    "host": "analytics.ekklesia.gr",
    "kind": "external",
    "source": "script.src",
    "url": "https://analytics.ekklesia.gr/js/script.js",
}

# T-9149: pins cover deferred script/listener migration, safe embed DOM, and local fonts.
# Generated from the reviewed single-line removal, pinned to prevent any other
# change to public pages outside the R2-R4 redesign gates.
# T-9138 (EVA-023): exact script-only externalization on mirror-setup and
# tickets/auth/callback; source bodies are unchanged, execution order preserved.
# Callback also sets no-referrer first in head to protect OAuth asset referrers.
POST_REMOVAL_SHA256 = {
    "docs/govgr-dimos.html": "01b0565a81c035df4ae426fce7184828d025aed826d186b4a8b121e110c928a9",
    "docs/mirror-setup.html": "155a289804224367d2470478e6bfbe2e3dd509203f24c0b3d1a460aca0dc932c",
    "docs/municipality/article.html": "b99329c1090137cef98943defa903aadbb69990d12e9e120eaa4dc601f034d3e",
    "docs/municipality/index.html": "4c4bed7281ac29db322dbe338f8b9bb46d9e76880f27d5d019618b33c006679d",
    "docs/sso-verify.html": "4b1db11d51d41e22568d56e721c5eddcbc3a70c713e6365f25415405300760ee",  # T-614: APK v1.0.33/vC62, Play vC62 closed testing
    "docs/tickets/auth/callback.html": "a11ccd12e9c35e51582f6d7c0e07a7c98159d9a3cc7a551cc32cd6fe9a28266a",
    "docs/tickets/index.html": "f5939db716a2e6e9a13c3cda202da6ef3d24fda3477a7b553fd1cf4e4d8480ee",
    "docs/votes/active.html": "3f0f66f9b994de76c70392eb04cf15f405f7892c731ae9230aec2937c343125a",
    "docs/votes/recent.html": "fc8beb7d125cc0d93824053c4759128391671a9bc59ce3d24a189f5b66109ab8",
    "docs/votes/results.html": "7e7686b50d4d9ed60d9ac4fd1790093ec4145bb7862aa162e837ce12d0b5230a",
}

# T-394 (EKA-14): reviewed security remediation on a non-gated page (API error
# detail rendered via textContent), pinned to its exact post-fix bytes.
SECURITY_REMEDIATION_SHA256 = {
    "docs/embed/qr-login.html": "b4350dffb479679a4db917471283889e522013584d68e9d4942263c068b68173",
}


# T-420 (EKA-51): "24 Ώρες" footer now targets /el/bills?status=WINDOW_24H;
# single-line change on top of the post-removal bytes above.
# T-421 (EKA-48/49): head metadata only on top of the bytes above — no
# same-URL hreflang="en", complete og/twitter/hreflang/JSON-LD on legal.html,
# twitter cards on tickets and municipality, municipality canonical/og:url on
# the final /municipality/index.html document.
# T-9132 (Gio approved 2026-10-16, ADR-007 S1): no-name / pseudonymous
# ordinary-vote claims and qualified IP assurances; T-9127 OPEN_END logic retained.
# T-9132 review: demo discloses possible linkage through verification; demo and
# govgr-dimos separate expiring daily HMAC counters from size-rotated IP logs.
CONTENT_REMEDIATION_SHA256 = {
    "docs/demo/admin.html": "10ab247905f2399cf93e2d733e83e33c4a8319553f9cf653326689a1c1e1f867",  # T-9148: neutral AI label without a zero-cost claim.
    "docs/embed/results.html": "aecebcb2965f4443fc29f486706a9364e1e052af99c97825788737c37ffe5699",  # T-9128: nullable public result cells
    "docs/demo/index.html": "0b5b6325ca36af9f8ffa056b171f197fc4daef520c17238923dfd1825779439e",  # T-9132: approved pseudonymous vote wording
    "docs/demo/bills.html": "ee790f059aa59e053532da15516c464851ea5c0ebb228e9fcfbc27986d690301",  # T-9127: OPEN_END voting closed
    "docs/embed/vote.html": "2c065daa0cc82b22c695b2634f7738b3cc6766233db2541965f56e982aaab98b",  # T-9127: OPEN_END voting closed
    "docs/govgr-dimos.html": "01b0565a81c035df4ae426fce7184828d025aed826d186b4a8b121e110c928a9",
    "docs/legal.html": "b444bf53ec77adbb783100d9d1f03c083e33864906b3562fb46f245bb00b165c",  # T-9147: bilingual bot footer link.
    "docs/municipality/article.html": "b99329c1090137cef98943defa903aadbb69990d12e9e120eaa4dc601f034d3e",
    "docs/municipality/index.html": "4c4bed7281ac29db322dbe338f8b9bb46d9e76880f27d5d019618b33c006679d",
    "docs/tickets/index.html": "f5939db716a2e6e9a13c3cda202da6ef3d24fda3477a7b553fd1cf4e4d8480ee",
}

# T-9148 (#636, owner-requested): replace only the two vendor-naming landing
# pairs. The R2 gate requires their exact neutral replacements, including both
# languages, rather than permitting the feature text to disappear.
LANDING_BILINGUAL_REPLACEMENTS = {
    ("Ollama + DeepL: Περιλήψεις νόμων, Chat Q&A, επιτήρηση server, αυτόματη επισκευή scraper, ανάλυση logs.",
     "Ollama + DeepL: Bill summaries, Chat Q&A, server monitoring, auto-healing scraper, log analysis."):
    ("AI: Περιλήψεις νομοσχεδίων, ερωτήσεις και απαντήσεις πολιτών, παρακολούθηση διακομιστή, αυτόματη επιδιόρθωση του συλλέκτη δεδομένων, ανάλυση αρχείων καταγραφής.",
     "AI: Bill summaries, citizen Q&A, server monitoring, auto-healing scraper, log analysis."),
    ("AI Agent (Ollama + DeepL)", "AI Agent (Ollama + DeepL)"): ("AI Agent", "AI Agent"),
}

# T-9128: embed vote/results nullable counts and withheld breakdowns.
# T-421 (EKA-48): landing head drops only the same-URL hreflang="en" alternate.
# Pinned hash of the r0 "seo" category; any other SEO change fails the R2 gate.
APPROVED_SEO_HASH = {
    "docs/index.html": "dde736d4392f47b4f7a7ad2e5101bb4abe2a6b6a03a4ad2609670e298883e69a",
}


def expected_sha256(path: str, frozen_sha256: str) -> str:
    """Return the exact approved byte hash, or the frozen hash otherwise."""
    if path in SECURITY_REMEDIATION_SHA256:
        return SECURITY_REMEDIATION_SHA256[path]
    if path in CONTENT_REMEDIATION_SHA256:
        return CONTENT_REMEDIATION_SHA256[path]
    return POST_REMOVAL_SHA256.get(path, frozen_sha256)


def baseline_without_analytics(page: dict) -> dict:
    """Drop only the exact old loader's parser evidence from an R0 page."""
    expected = deepcopy(page)
    external = expected["scripts"]["external"]
    if SCRIPT not in external:
        return expected
    external.remove(SCRIPT)
    expected["resources"].remove(RESOURCE)
    expected["external_hosts"].remove("analytics.ekklesia.gr")
    return expected

# T-9147 (Gio, 2026-10-18): bilingual bot policy, exact new-page bytes.
ADDITIONAL_PAGE_SHA256 = {
    "docs/bot.html": "21092ed849430fe1e2b78472c7a3f99f18b8cb8793bdc1ae262a7477a0b101f9",  # T-9148: neutral EL/EN bot-policy text.
}

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

# T-9149: pins also cover external script/listener migration and municipality font removal.
# Generated from the reviewed single-line removal, pinned to prevent any other
# change to public pages outside the R2-R4 redesign gates.
# T-9138 (EVA-023): exact script-only externalization on mirror-setup and
# tickets/auth/callback; source bodies are unchanged, execution order preserved.
# Callback also sets no-referrer first in head to protect OAuth asset referrers.
POST_REMOVAL_SHA256 = {
    "docs/govgr-dimos.html": "09faf9059c49f81491a17023e5b1de374db232629cd631f08f535486f39f80b2",
    "docs/mirror-setup.html": "f5eec5b34dd882c000f4840512e81a4bb94db3f9d64d8afecda52b705a281555",
    "docs/municipality/article.html": "b192c264c15a1414771eff6a602d9aa0b101b8ca1e72e4382302e21ca100cff5",
    "docs/municipality/index.html": "4c4bed7281ac29db322dbe338f8b9bb46d9e76880f27d5d019618b33c006679d",
    "docs/sso-verify.html": "6ebdeb265ca038b64947947ea3b2ecb1c2c6f266c7ab2dbc570d0faf083a31b8",  # T-614: APK v1.0.33/vC62, Play vC62 closed testing
    "docs/tickets/auth/callback.html": "aca9846fb28bce18b38d73a7d941dbc368105b975b26b28193aea5799800b9c4",
    "docs/tickets/index.html": "23ad29cb02df116f5aec52b45d7c026ab0857cd6fc14889013364bd51a84383f",
    "docs/votes/active.html": "3f0f66f9b994de76c70392eb04cf15f405f7892c731ae9230aec2937c343125a",
    "docs/votes/recent.html": "fc8beb7d125cc0d93824053c4759128391671a9bc59ce3d24a189f5b66109ab8",
    "docs/votes/results.html": "7e7686b50d4d9ed60d9ac4fd1790093ec4145bb7862aa162e837ce12d0b5230a",
}

# T-394 (EKA-14): reviewed security remediation on a non-gated page (API error
# detail rendered via textContent), pinned to its exact post-fix bytes.
SECURITY_REMEDIATION_SHA256 = {
    "docs/embed/qr-login.html": "d6eecc9f3aa5ece4d56e90b1607991bd09a93e4630c89515ef517bc079b56256",
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
    "docs/demo/admin.html": "1d13cb7c51bdd2430cb12c2dee6bd21454ddf092647f236fba74ad834086fb5d",  # T-9148: neutral AI label without a zero-cost claim.
    "docs/embed/results.html": "9de3d606bdb07e6bf3ad55850b19597d60461078732964e3bce19d660ead6ccd",  # T-9128: nullable public result cells
    "docs/demo/index.html": "0b5b6325ca36af9f8ffa056b171f197fc4daef520c17238923dfd1825779439e",  # T-9132: approved pseudonymous vote wording
    "docs/demo/bills.html": "c64fba047db9dd7ba7bb1019e4249b378f860e7e780a427b2c5880738367cd00",  # T-9127: OPEN_END voting closed
    "docs/embed/vote.html": "a426ec7ed2ae81cc480d4d16a2cba88095a5568dbdc7cab1f6a1a454d188d272",  # T-9127: OPEN_END voting closed
    "docs/govgr-dimos.html": "09faf9059c49f81491a17023e5b1de374db232629cd631f08f535486f39f80b2",
    "docs/legal.html": "c15652ae4d9ab89d66461c340c038059a8e2dcf8ee271765080fd0e380e93661",  # T-9147: bilingual bot footer link.
    "docs/municipality/article.html": "b192c264c15a1414771eff6a602d9aa0b101b8ca1e72e4382302e21ca100cff5",
    "docs/municipality/index.html": "4c4bed7281ac29db322dbe338f8b9bb46d9e76880f27d5d019618b33c006679d",
    "docs/tickets/index.html": "23ad29cb02df116f5aec52b45d7c026ab0857cd6fc14889013364bd51a84383f",
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
    "docs/bot.html": "b8b19fb58ca2320030fc7df67e0734a8bd5c901f7a5ecea60fc36a15320e005f",  # T-9148: neutral EL/EN bot-policy text.
}

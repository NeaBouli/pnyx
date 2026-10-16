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

# Generated from the reviewed single-line removal, pinned to prevent any other
# change to public pages outside the R2-R4 redesign gates.
POST_REMOVAL_SHA256 = {
    "docs/govgr-dimos.html": "8fd6a06f5bbff423264fc64cb056cc48714825df8d8de7f26a1484aba7006444",
    "docs/mirror-setup.html": "938972f6a82369bee414c3c263410d22948fb021a20ad5b74a0e277413a0f442",
    "docs/municipality/article.html": "70b9fa2dea161c0efb1db00b0e7cc5a48f4b123aa08d448b50713623c2306090",
    "docs/municipality/index.html": "7b18713d511375a834bb1747856ba4303ac7f57ff8148b3636dcb659878956c2",
    "docs/sso-verify.html": "4c2f138fb4971fec0a25169f8a9701f6af31d9f1b062984dc32df3d4fccb5976",  # T-614: APK v1.0.33/vC62, Play vC62 closed testing
    "docs/tickets/auth/callback.html": "f12e059521cd411a938b531c2f17865073b6d0331d5401b6f2a6b6c340ef74d8",
    "docs/tickets/index.html": "a39a982850a6c951cef2615694408c04b5570e50fee28fa1491a8bcab45ba9ab",
    "docs/votes/active.html": "3f0f66f9b994de76c70392eb04cf15f405f7892c731ae9230aec2937c343125a",
    "docs/votes/recent.html": "fc8beb7d125cc0d93824053c4759128391671a9bc59ce3d24a189f5b66109ab8",
    "docs/votes/results.html": "7e7686b50d4d9ed60d9ac4fd1790093ec4145bb7862aa162e837ce12d0b5230a",
}

# T-394 (EKA-14): reviewed security remediation on a non-gated page (API error
# detail rendered via textContent), pinned to its exact post-fix bytes.
SECURITY_REMEDIATION_SHA256 = {
    "docs/embed/qr-login.html": "342b71087a9b370ec4c27d8771d693efbe532c57231c521717108e7ecb1c2882",
}


# T-420 (EKA-51): "24 Ώρες" footer now targets /el/bills?status=WINDOW_24H;
# single-line change on top of the post-removal bytes above.
# T-421 (EKA-48/49): head metadata only on top of the bytes above — no
# same-URL hreflang="en", complete og/twitter/hreflang/JSON-LD on legal.html,
# twitter cards on tickets and municipality, municipality canonical/og:url on
# the final /municipality/index.html document.
# T-9132 (Gio approved 2026-10-16, ADR-007 S1): no-name / pseudonymous
# ordinary-vote claims and qualified IP assurances; T-9127 OPEN_END logic retained.
CONTENT_REMEDIATION_SHA256 = {
    "docs/demo/index.html": "41475d41b01cd765ed0dcaa189fcab0aaede720bd06b76d653ffa509821eb8f2",  # T-9132: approved pseudonymous vote wording
    "docs/demo/bills.html": "bcc57f45c9e25c3ac3a6eb0fe9b17b29a2908c5863ad744407dc2cd56215dee8",  # T-9127: OPEN_END voting closed
    "docs/embed/vote.html": "2afc2f067db2fb4adf91e7e9bbebaf69f155eff87aa429976d48b94d59667576",  # T-9127: OPEN_END voting closed
    "docs/govgr-dimos.html": "369b6d3f5203d126058dc2bfbab9c66d2c8ede936a8b6d9a0aa6758887668159",
    "docs/legal.html": "42edc8e9c7db5d3fa4bb141adc915d47acc232ff93d405a38871b83ee1b5b4b7",
    "docs/municipality/article.html": "aebe3b819ec76fc9c3769ad38a847246657bd5d85b70c914cb84528d4b658123",
    "docs/municipality/index.html": "b553913780f18868fc49157f303379cbf630b12651ad1877b31a09b3483f5f84",
    "docs/tickets/index.html": "e7ac386295ade2c52c6d3826c89ade8ffc140f290dbc78ac8487d32394f2b225",
}

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

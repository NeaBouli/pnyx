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
    "docs/sso-verify.html": "b705884f32872ef2781066af91bdc3853c8853f8dd1f2aa9b3f7fd033f7246ca",
    "docs/tickets/auth/callback.html": "f12e059521cd411a938b531c2f17865073b6d0331d5401b6f2a6b6c340ef74d8",
    "docs/tickets/index.html": "a39a982850a6c951cef2615694408c04b5570e50fee28fa1491a8bcab45ba9ab",
    "docs/votes/active.html": "3f0f66f9b994de76c70392eb04cf15f405f7892c731ae9230aec2937c343125a",
    "docs/votes/recent.html": "fc8beb7d125cc0d93824053c4759128391671a9bc59ce3d24a189f5b66109ab8",
    "docs/votes/results.html": "7e7686b50d4d9ed60d9ac4fd1790093ec4145bb7862aa162e837ce12d0b5230a",
}


def expected_sha256(path: str, frozen_sha256: str) -> str:
    """Return the exact approved byte hash, or the frozen hash otherwise."""
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

"""Shared transport-error markers for fetched and generated document text."""

from __future__ import annotations

import re


# The boolean marks generic headings, which may also be quoted in real prose.
ERROR_PAGE_MARKERS: tuple[tuple[str, bool], ...] = (
    ("you don't have permission to access", False),
    ("errors.edgesuite.net", False),
    ("access denied", True),
    ("403 forbidden", True),
    ("request rejected", True),
    ("authenticationrequirederror", False),
    ("blocked from performing anonymous queries", False),
    ("attention required! | cloudflare", False),
    ("sorry, you have been blocked", False),
    ("the requested url was rejected", False),
    ("checking your browser before accessing", False),
    ("enable javascript and cookies to continue", False),
    ("cloudflare ray id", False),
    ("akamai reference", False),
    ("akamaighost", False),
)
_TAG = re.compile(r"<[^<>\n]*>")


def looks_like_error_page(text: str | None) -> bool:
    """Detect block pages while allowing error terms quoted in official prose."""
    if not text:
        return False
    lowered = text.lower()
    for marker, heading_only in ERROR_PAGE_MARKERS:
        if marker not in lowered:
            continue
        if not heading_only:
            return True
        for line in _TAG.sub(" ", lowered).splitlines():
            if line.lstrip(" \t#*>_`-").startswith(marker):
                return True
    return False

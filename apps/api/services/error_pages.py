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
_HEADING_TAG = re.compile(r"</?(?:title|h[1-6])\b[^<>]*>", re.IGNORECASE)
# Extraction can flatten a generic title and the denial heading onto one line.
# Require the transport reference immediately after the heading in that case.
_PREFIXED_REFERENCE = re.compile(
    r"^error +(?:access denied|403 forbidden|request rejected) +reference *#"
)
_HORIZONTAL_SPACE = re.compile(r"[ \t]+")


def looks_like_error_page(text: str | None) -> bool:
    """Detect block pages while allowing error terms quoted in official prose."""
    if not text:
        return False
    lowered = text.lower()
    if not any(marker in lowered for marker, _ in ERROR_PAGE_MARKERS) and "reference" not in lowered:
        return False
    from services.text_quality import without_quotes

    # Keep heading boundaries before stripping tags, even for minified HTML.
    # Then mask complete quotations (after tags, so attribute quotes cannot pair
    # up across elements): generic headings quoted in official prose
    # («<h2>Access denied</h2>») are discussion, not a block page, and the
    # placeholder keeps later prose from becoming a line-leading "heading".
    flattened = _TAG.sub(" ", _HEADING_TAG.sub("\n", lowered))
    lines = [
        _HORIZONTAL_SPACE.sub(" ", line).lstrip(" #*>_`-")
        for line in without_quotes(flattened, placeholder=" \u00a7q\u00a7 ").splitlines()
    ]
    if any(_PREFIXED_REFERENCE.match(line) for line in lines):
        return True
    for marker, heading_only in ERROR_PAGE_MARKERS:
        if marker not in lowered:
            continue
        if not heading_only:
            return True
        for line in lines:
            if line.startswith(marker) and (len(line) == len(marker) or not line[len(marker)].isalnum()):
                return True
    return False

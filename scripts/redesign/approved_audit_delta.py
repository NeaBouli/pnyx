"""Exact R3 content deltas for the public EKA audit disclosure."""

import hashlib

import r0_inventory

APPROVED_WIKI_INVENTORY_HASH = {
    "docs/wiki/index.html": "afbe64244c7f6f89cf31dcfdca0c208bd62ba68b4352ba0407a73de9e80dc86e",
    "docs/wiki/security.html": "defc9bfdaede11ee6659e93302906e6d6c3c8746cd904297c1e84c101ea95398",
}
APPROVED_AUDIT_PAGE_SHA256 = "8e83bd71dd438c7caa27b5d59ca9f190634445834846a29170db9b8ccfe83b0f"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

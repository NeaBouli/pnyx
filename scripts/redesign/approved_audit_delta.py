"""Exact R3 content deltas for the public EKA audit disclosure."""

import hashlib

import r0_inventory

APPROVED_WIKI_INVENTORY_HASH = {
    "docs/wiki/index.html": "d1d4082591ab76371b7f248a31a382db4744962be1041229475cedbe83d9b566",
    "docs/wiki/security.html": "905a5387128312df960cacce87f2d88582294520a19fe3db53e96cfeed1c6359",
}
APPROVED_AUDIT_PAGE_SHA256 = "c8d358a50fc4cdd29ee0af25430b6d4b0b4109f4e1a32bbfe4a84bebd3f334f2"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

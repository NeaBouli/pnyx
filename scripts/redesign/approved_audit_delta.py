"""Exact R3 content deltas for the public EKA audit disclosure."""

import hashlib

import r0_inventory

APPROVED_WIKI_INVENTORY_HASH = {
    # EKA-37: API reference rows and vote example corrected against OpenAPI.
    "docs/wiki/api.html": "4fe6ed101c0e2d0e43c4b717b4ec66863a86e53f73f19b5584b05b56ff2109e9",
    "docs/wiki/index.html": "d1d4082591ab76371b7f248a31a382db4744962be1041229475cedbe83d9b566",
    "docs/wiki/security.html": "905a5387128312df960cacce87f2d88582294520a19fe3db53e96cfeed1c6359",
    # T-419 / EKA-38: F-Droid availability sentence in the download notice.
    "docs/wiki/faq.html": "60f12a55835d5b114dd170e44aa2339dc033453fe164cc65911bbe23f2370ebf",
    "docs/wiki/roadmap.html": "2fa24bf2075e671b7459c73336723e49b24d753159edccd618202d51b3cae26d",
}
APPROVED_AUDIT_PAGE_SHA256 = "c8d358a50fc4cdd29ee0af25430b6d4b0b4109f4e1a32bbfe4a84bebd3f334f2"


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)


def matches_audit_page(content: str) -> bool:
    """Reject unreviewed changes to published finding counts and claims."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest() == APPROVED_AUDIT_PAGE_SHA256

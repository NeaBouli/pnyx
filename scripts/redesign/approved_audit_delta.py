"""Exact R3 content deltas for the public EKA audit disclosure."""

import r0_inventory

APPROVED_WIKI_INVENTORY_HASH = {
    "docs/wiki/index.html": "afbe64244c7f6f89cf31dcfdca0c208bd62ba68b4352ba0407a73de9e80dc86e",
    "docs/wiki/security.html": "8f38e2a73c393fc1cad71e9c29915fe9720cabcbec83c75ef50cf5382929c6e3",
}


def matches_approved_content(path: str, current: dict) -> bool:
    """Any other change to these pages falls back to the R0/R3 gate."""
    return r0_inventory.hash_category(current) == APPROVED_WIKI_INVENTORY_HASH.get(path)

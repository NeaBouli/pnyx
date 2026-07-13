"""Forward-only ownership guards for automatically generated bill content."""

from __future__ import annotations

import hashlib
from typing import Any


SUMMARY_FIELDS = frozenset({"pill_el", "summary_short_el"})
FORUM_BODY_FIELD = "forum_body"


def content_sha256(value: str | None) -> str | None:
    """Hash content after normalizing transport-only newline differences."""
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _provenance(bill: Any) -> dict[str, str]:
    value = getattr(bill, "generated_content_provenance", None)
    return dict(value) if isinstance(value, dict) else {}


def record_generated_content(bill: Any, field: str, value: str | None) -> None:
    """Record that the current field value was produced by the system."""
    digest = content_sha256(value)
    provenance = _provenance(bill)
    if digest is None:
        provenance.pop(field, None)
    else:
        provenance[field] = digest
    bill.generated_content_provenance = provenance or None


def clear_generated_content(bill: Any, field: str) -> None:
    """Mark a field as externally owned so automation cannot replace it."""
    provenance = _provenance(bill)
    provenance.pop(field, None)
    bill.generated_content_provenance = provenance or None


def has_generated_content_provenance(bill: Any, field: str) -> bool:
    """Return whether automation has an ownership digest for this field."""
    return bool(_provenance(bill).get(field))


def is_generated_content_unchanged(bill: Any, field: str, value: str | None) -> bool:
    """Return true only when provenance exists and still matches exactly."""
    expected = _provenance(bill).get(field)
    actual = content_sha256(value)
    return bool(expected and actual and expected == actual)


def apply_generated_content(bill: Any, field: str, candidate: str | None) -> bool:
    """Fill or refresh a system-owned summary without touching manual content."""
    if field not in SUMMARY_FIELDS:
        raise ValueError(f"Unsupported generated summary field: {field}")
    if not candidate:
        return False
    if getattr(bill, "ai_summary_reviewed", False):
        return False

    current = getattr(bill, field, None)
    if current:
        if not is_generated_content_unchanged(bill, field, current):
            return False
        if current == candidate:
            return False

    setattr(bill, field, candidate)
    record_generated_content(bill, field, candidate)
    return True

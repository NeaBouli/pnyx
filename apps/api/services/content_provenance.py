"""Forward-only ownership guards for automatically generated bill content."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from services.public_bill_index import SENSITIVE_PATTERN
from services.text_quality import check_generated_text

logger = logging.getLogger(__name__)


class OfficialText(str):
    """An official excerpt or deterministic template, never generated prose."""


def contains_sensitive_marker(value: str | None) -> bool:
    """Match the existing visibility predicate without changing its policy."""
    return bool(value and re.search(SENSITIVE_PATTERN, value.lower()))


def accepted_generated_text(text: str | None, *, field: str, bill_id: str) -> str | None:
    """Return accepted prose, logging rejection codes without content."""
    quality = check_generated_text(text, field=field)
    if not quality.ok:
        logger.warning("Generated text rejected bill_id=%s reasons=%s", bill_id, quality.reasons)
        return None
    return text


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
    candidate = accepted_generated_text(candidate, field=field, bill_id=getattr(bill, "id", "unknown"))
    if not candidate:
        return False
    if getattr(bill, "ai_summary_reviewed", False):
        return False

    current = getattr(bill, field, None)
    if contains_sensitive_marker(current):
        return False
    if current:
        if not is_generated_content_unchanged(bill, field, current):
            return False
        if current == candidate:
            return False

    setattr(bill, field, candidate)
    record_generated_content(bill, field, candidate)
    return True


def apply_official_summary(
    bill: Any, field: str, candidate: str | None, *, replace_metadata: bool = False,
) -> bool:
    """Update official metadata using existing ownership/review protections."""
    if field not in SUMMARY_FIELDS:
        raise ValueError(f"Unsupported official summary field: {field}")
    if not candidate or getattr(bill, "ai_summary_reviewed", False):
        return False
    current = getattr(bill, field, None)
    if contains_sensitive_marker(current):
        return False
    if current and not replace_metadata and not is_generated_content_unchanged(bill, field, current):
        return False
    changed = current != candidate or has_generated_content_provenance(bill, field)
    setattr(bill, field, candidate)
    clear_generated_content(bill, field)
    return changed

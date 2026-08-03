"""Shared visibility guards for non-public or operator-only bills."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.sql.elements import ColumnElement

from models import DiavgeiaDecision, ParliamentBill

DIAVGEIA_SENSITIVE_PUBLIC_TERMS = (
    "αμκα",
    "α.μ.κ.α",
    "amka",
    "ασθεν",
    "εοπυυ",
    "eopyy",
)


def public_bill_raw_sql(
    alias: str,
    *,
    param_prefix: str = "sensitive_term",
) -> tuple[str, dict[str, str]]:
    """Return the shared public-bill guard for parameterized raw SQL."""
    if not alias.replace("_", "").isalnum():
        raise ValueError("SQL alias must be an identifier")

    checks: list[str] = []
    params: dict[str, str] = {}
    for index, term in enumerate(DIAVGEIA_SENSITIVE_PUBLIC_TERMS):
        name = f"{param_prefix}_{index}"
        params[name] = f"%{term}%"
        checks.extend((
            f"LOWER(COALESCE({alias}.title_el, '')) LIKE :{name}",
            f"LOWER(COALESCE({alias}.summary_short_el, '')) LIKE :{name}",
            f"LOWER(COALESCE({alias}.summary_long_el, '')) LIKE :{name}",
        ))
    return (
        f"COALESCE({alias}.admin_hidden, FALSE) = FALSE AND NOT ("
        + " OR ".join(checks)
        + ")",
        params,
    )


def _text_contains_sensitive_diavgeia_marker(value: str | None) -> bool:
    if not value:
        return False
    text = value.casefold()
    return any(term in text for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS)


def sensitive_diavgeia_filter() -> ColumnElement[bool]:
    """SQL predicate for DIAVGEIA rows that must not be shown publicly.

    The guard is intentionally narrow: it targets patient/AMKA/insurance-fund
    markers seen in live public rows, without blocking every hospital purchase.
    """

    haystacks = (
        func.lower(func.coalesce(ParliamentBill.title_el, "")),
        func.lower(func.coalesce(ParliamentBill.summary_short_el, "")),
        func.lower(func.coalesce(ParliamentBill.summary_long_el, "")),
    )
    term_checks = [
        haystack.contains(term)
        for haystack in haystacks
        for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS
    ]
    return and_(
        ParliamentBill.source == "DIAVGEIA",
        or_(*term_checks),
    )


def sensitive_raw_diavgeia_filter() -> ColumnElement[bool]:
    """Predicate for sensitive markers in raw DIAVGEIA decisions."""
    subject = func.lower(func.coalesce(DiavgeiaDecision.subject, ""))
    return or_(*(subject.contains(term) for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS))


def public_raw_diavgeia_filter() -> ColumnElement[bool]:
    """Exclude raw decisions that must not be exposed by public endpoints."""
    return not_(sensitive_raw_diavgeia_filter())


def is_public_raw_diavgeia_decision(decision: Any) -> bool:
    """Object-level equivalent of public_raw_diavgeia_filter()."""
    if decision is None:
        return False
    return not _text_contains_sensitive_diavgeia_marker(getattr(decision, "subject", None))


def public_bill_filter() -> ColumnElement[bool]:
    """SQLAlchemy predicate for bills that may appear in public surfaces."""
    return and_(
        ParliamentBill.admin_hidden.is_not(True),
        not_(sensitive_diavgeia_filter()),
    )


def public_bill_with_demo_filter() -> ColumnElement[bool]:
    """Predicate for public surfaces that also exclude legacy DEMO rows."""
    return and_(public_bill_filter(), ~ParliamentBill.id.like("DEMO-%"))


def is_public_bill(bill: Any) -> bool:
    """Object-level guard matching public_bill_filter()."""
    if bill is None:
        return False
    if bool(getattr(bill, "admin_hidden", False)):
        return False
    if (getattr(bill, "source", None) or "PARLIAMENT") == "DIAVGEIA":
        return not any(
            _text_contains_sensitive_diavgeia_marker(getattr(bill, field, None))
            for field in ("title_el", "summary_short_el", "summary_long_el")
        )
    return True

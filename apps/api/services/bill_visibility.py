"""Shared visibility guards for non-public or operator-only bills."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, literal, not_, or_, select
from sqlalchemy.sql.elements import ColumnElement

from models import BillStatus, DiavgeiaDecision, ParliamentBill
from services.public_bill_index import SENSITIVE_PATTERN
from services.bill_id_set import bill_ids_filter

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


def public_bill_metadata_sql(alias: str, *, db=None) -> tuple[str, dict]:
    """The exact partial-index predicate, including under generic prepared plans."""
    if not alias.replace("_", "").isalnum():
        raise ValueError("SQL alias must be an identifier")
    from services.bill_id_set import db_dialect
    dialect = db_dialect(db)
    predicate = str(public_bill_filter().compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    return predicate.replace("parliament_bills.", f"{alias}."), {}


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
        func.lower(func.coalesce(column, literal("", literal_execute=True)))
        for column in (ParliamentBill.title_el, ParliamentBill.summary_short_el, ParliamentBill.summary_long_el)
    )
    # Match the same literal substrings while lowercasing each large text once,
    # rather than once per marker. Escape punctuation (notably dotted AMKA).
    pattern = literal(SENSITIVE_PATTERN, literal_execute=True)
    term_checks = [haystack.regexp_match(pattern) for haystack in haystacks]
    return and_(
        ParliamentBill.source == literal("DIAVGEIA", literal_execute=True),
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


async def filter_public_bill_rows(rows, *, db, id_key="id", **_arguments):
    """Recheck candidate primary keys on every response, including stale hits.

    Select scalar IDs so the session identity map cannot return an older bill's
    visibility fields. A failed check propagates; it cannot authorize a hit.
    """
    def bill_id(row):
        return row[id_key] if isinstance(row, dict) else getattr(row, id_key)

    ids = {bill_id(row) for row in rows}
    if not ids:
        return rows
    visible = set((await db.execute(select(ParliamentBill.id).where(
        bill_ids_filter(ParliamentBill.id, ids), public_bill_filter(),
    ))).scalars().all())
    return [row for row in rows if bill_id(row) in visible]


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


# ── Result visibility ─────────────────────────────────────────────────────────
# A running vote must not publish interim counts: an ACTIVE bill keeps its results hidden
# unless the bill opts into WINDOW/ALWAYS. Every public surface that reports per-bill vote counts
# uses these guards, the same rule as routers.voting.get_results.

def results_hidden(bill: Any) -> bool:
    """True while a bill's vote counts must not be published."""
    status = getattr(getattr(bill, "status", None), "value", getattr(bill, "status", None))
    visibility = getattr(bill, "results_visibility", None) or "HIDDEN"
    return status == "ACTIVE" and visibility == "HIDDEN"


def results_visible_filter() -> ColumnElement[bool]:
    """SQLAlchemy predicate matching bills whose vote counts may be published."""
    return not_(and_(
        ParliamentBill.status == BillStatus.ACTIVE,
        func.coalesce(ParliamentBill.results_visibility, "HIDDEN") == "HIDDEN",
    ))


def results_visible_raw_sql(alias: str) -> str:
    """Raw SQL form of results_visible_filter() for a parliament_bills alias."""
    if not alias.replace("_", "").isalnum():
        raise ValueError("SQL alias must be an identifier")
    return (
        f"NOT ({alias}.status::text = 'ACTIVE' "
        f"AND COALESCE({alias}.results_visibility, 'HIDDEN') = 'HIDDEN')"
    )

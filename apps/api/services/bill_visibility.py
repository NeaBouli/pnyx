"""Shared visibility guards for non-public or operator-only bills."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, and_, func, literal, not_, or_, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import FunctionElement

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

    return (
        f"{alias}.admin_hidden IS NOT TRUE AND "
        f"coalesce({alias}.sensitive_override, {alias}.sensitive_public_block) IS NOT TRUE",
        {},
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


class _SensitiveDiavgeia(FunctionElement[bool]):
    type = Boolean()
    inherit_cache = True
    _is_implicitly_boolean = True


@compiles(_SensitiveDiavgeia)
def _sensitive_expression(element: _SensitiveDiavgeia, compiler: SQLCompiler, **kwargs: Any) -> str:
    source, *columns = element.clauses
    pattern = literal(SENSITIVE_PATTERN, literal_execute=True)
    checks = [
        func.lower(func.coalesce(column, literal("", literal_execute=True))).regexp_match(pattern)
        for column in columns
    ]
    expression = and_(
        source == literal("DIAVGEIA", literal_execute=True), or_(*checks),
    )
    return f"({compiler.process(expression, **kwargs)})"


@compiles(_SensitiveDiavgeia, "postgresql")
def _sensitive_function(element: _SensitiveDiavgeia, compiler: SQLCompiler, **kwargs: Any) -> str:
    return compiler.process(func.public_bill_sensitive(*element.clauses), **kwargs)


def sensitive_diavgeia_filter() -> ColumnElement[bool]:
    """Text scanner for operator redaction tooling, never a visibility predicate.

    The guard is intentionally narrow: it targets patient/AMKA/insurance-fund
    markers seen in live public rows, without blocking every hospital purchase.
    """

    return _SensitiveDiavgeia(
        ParliamentBill.source, ParliamentBill.title_el,
        ParliamentBill.summary_short_el, ParliamentBill.summary_long_el,
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
        func.coalesce(ParliamentBill.sensitive_override, ParliamentBill.sensitive_public_block).is_not(True),
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
    override = getattr(bill, "sensitive_override", None)
    blocked = override if override is not None else getattr(bill, "sensitive_public_block", False)
    return not bool(blocked)


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

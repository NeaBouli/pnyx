"""Privacy regressions for the public list query's literal marker optimization."""
import itertools
from collections.abc import Iterator

import pytest
from sqlalchemy import Boolean, Column, MetaData, String, Table, and_, create_engine, func, not_, or_, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.sql.elements import ColumnElement

from models import ParliamentBill as Bill
from services.bill_visibility import (
    DIAVGEIA_SENSITIVE_PUBLIC_TERMS,
    public_bill_with_demo_filter,
)


def _previous_guard() -> ColumnElement[bool]:
    fields = (Bill.title_el, Bill.summary_short_el, Bill.summary_long_el)
    return and_(
        Bill.admin_hidden.is_not(True),
        not_(and_(Bill.source == "DIAVGEIA", or_(*(
            func.lower(func.coalesce(field, "")).contains(term)
            for field in fields for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS
        )))),
        ~Bill.id.like("DEMO-%"),
    )


@pytest.fixture
def visibility_db() -> Iterator[tuple[Connection, Table]]:
    engine = create_engine("sqlite://")
    metadata = MetaData()
    table = Table(
        "parliament_bills", metadata,
        Column("id", String, primary_key=True), Column("source", String),
        Column("admin_hidden", Boolean), Column("title_el", String),
        Column("summary_short_el", String), Column("summary_long_el", String),
    )
    metadata.create_all(engine)
    with engine.connect() as connection:
        # SQLite's built-in lower is ASCII-only. Exercise Greek uppercase too.
        connection.connection.driver_connection.create_function("lower", 1, lambda s: s.lower())
        yield connection, table
    engine.dispose()


def test_literal_marker_optimization_preserves_all_visibility_decisions(
    visibility_db: tuple[Connection, Table],
) -> None:
    connection, table = visibility_db
    samples = [None, "", "ordinary procurement", "αXμXκXα", "a.m.k.a", "α.μ.κ", "am\nka"]
    for term in DIAVGEIA_SENSITIVE_PUBLIC_TERMS:
        samples.extend((term, term.upper(), "prefix" + term + "suffix", "\n" + term + "\n"))
    rows = []
    for source, hidden, demo, field, value in itertools.product(
        ("DIAVGEIA", "PARLIAMENT", None), (False, True, None), (False, True),
        ("title_el", "summary_short_el", "summary_long_el"), samples,
    ):
        row = dict(id=("DEMO-" if demo else "B-") + str(len(rows)), source=source,
                   admin_hidden=hidden, title_el=None, summary_short_el=None, summary_long_el=None)
        row[field] = value
        rows.append(row)
    # No marker may be synthesized across field boundaries; long text must match.
    rows.extend((
        dict(id="split", source="DIAVGEIA", admin_hidden=False,
             title_el="am", summary_short_el="ka", summary_long_el=None),
        dict(id="long", source="DIAVGEIA", admin_hidden=False,
             title_el=None, summary_short_el=None, summary_long_el="x" * 100000 + "AMKA"),
        dict(id="literal-dot", source="DIAVGEIA", admin_hidden=False,
             title_el="αXμXκXα", summary_short_el=None, summary_long_el=None),
    ))
    connection.execute(table.insert(), rows)
    previous = set(connection.execute(select(Bill.id).where(_previous_guard())).scalars())
    optimized = set(connection.execute(select(Bill.id).where(public_bill_with_demo_filter())).scalars())
    assert optimized == previous
    assert "split" in optimized
    assert "literal-dot" in optimized
    assert "long" not in optimized


def test_postgresql_checks_each_field_once_and_binds_literal_pattern() -> None:
    query = select(Bill.id).where(public_bill_with_demo_filter())
    compiled = query.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert sql.count("lower(") == 3
    assert sql.count(" ~ ") == 3
    assert any(r"α\.μ\.κ\.α" in value for value in compiled.params.values() if isinstance(value, str))
    assert "ασθεν" not in sql
    assert "admin_hidden" in sql and "DEMO-%" in compiled.params.values()

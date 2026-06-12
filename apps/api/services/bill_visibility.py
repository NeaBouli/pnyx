"""Shared visibility guards for non-public or operator-only bills."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from models import ParliamentBill


def public_bill_filter() -> ColumnElement[bool]:
    """SQLAlchemy predicate for bills that may appear in public surfaces."""
    return ParliamentBill.admin_hidden.is_not(True)


def public_bill_with_demo_filter() -> ColumnElement[bool]:
    """Predicate for public surfaces that also exclude legacy DEMO rows."""
    return and_(public_bill_filter(), ~ParliamentBill.id.like("DEMO-%"))


def is_public_bill(bill: Any) -> bool:
    """Object-level guard matching public_bill_filter()."""
    if bill is None:
        return False
    return not bool(getattr(bill, "admin_hidden", False))

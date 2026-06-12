"""Regression tests for hidden/operator-only bill isolation."""
from types import SimpleNamespace

from services.bill_visibility import is_public_bill, public_bill_filter, public_bill_with_demo_filter


def test_is_public_bill_allows_normal_bill() -> None:
    bill = SimpleNamespace(admin_hidden=False)
    assert is_public_bill(bill) is True


def test_is_public_bill_blocks_admin_hidden_bill() -> None:
    bill = SimpleNamespace(admin_hidden=True)
    assert is_public_bill(bill) is False


def test_is_public_bill_treats_none_as_not_public() -> None:
    assert is_public_bill(None) is False


def test_public_bill_filter_excludes_admin_hidden_rows() -> None:
    compiled = str(public_bill_filter())
    assert "admin_hidden" in compiled
    assert "true" in compiled.lower()


def test_public_bill_with_demo_filter_keeps_both_guards() -> None:
    compiled = str(public_bill_with_demo_filter())
    assert "admin_hidden" in compiled
    assert "NOT LIKE" in compiled

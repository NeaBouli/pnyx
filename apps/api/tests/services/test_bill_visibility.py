"""Regression tests for hidden/operator-only bill isolation."""
from types import SimpleNamespace

from services.bill_visibility import (
    is_public_bill,
    is_public_raw_diavgeia_decision,
    public_bill_filter,
    public_bill_with_demo_filter,
    public_raw_diavgeia_filter,
)


def _compiled_literal(expr) -> str:
    return str(expr.compile(compile_kwargs={"literal_binds": True}))


def test_is_public_bill_allows_normal_bill() -> None:
    bill = SimpleNamespace(admin_hidden=False, source="PARLIAMENT")
    assert is_public_bill(bill) is True


def test_is_public_bill_blocks_admin_hidden_bill() -> None:
    bill = SimpleNamespace(admin_hidden=True, source="PARLIAMENT")
    assert is_public_bill(bill) is False


def test_is_public_bill_treats_none_as_not_public() -> None:
    assert is_public_bill(None) is False


def test_public_bill_filter_excludes_admin_hidden_rows() -> None:
    compiled = _compiled_literal(public_bill_filter())
    assert "admin_hidden" in compiled
    assert "true" in compiled.lower()
    assert "DIAVGEIA" in compiled


def test_public_bill_with_demo_filter_keeps_both_guards() -> None:
    compiled = _compiled_literal(public_bill_with_demo_filter())
    assert "admin_hidden" in compiled
    assert "NOT LIKE" in compiled


def test_is_public_bill_blocks_diavgeia_amka_marker() -> None:
    bill = SimpleNamespace(
        admin_hidden=False,
        source="DIAVGEIA",
        title_el="Έγκριση δαπάνης με ΑΜΚΑ 12345678901",
        summary_short_el=None,
        summary_long_el=None,
    )
    assert is_public_bill(bill) is False


def test_is_public_bill_blocks_diavgeia_dotted_amka_marker() -> None:
    bill = SimpleNamespace(
        admin_hidden=False,
        source="DIAVGEIA",
        title_el="Απόφαση με Α.Μ.Κ.Α. ασφαλισμένου",
        summary_short_el=None,
        summary_long_el=None,
    )
    assert is_public_bill(bill) is False


def test_is_public_bill_blocks_diavgeia_patient_marker_in_summary() -> None:
    bill = SimpleNamespace(
        admin_hidden=False,
        source="DIAVGEIA",
        title_el="Έγκριση δαπάνης για προμήθεια υλικών",
        summary_short_el="Υλικό που χρησιμοποιήθηκε σε ασθενή",
        summary_long_el=None,
    )
    assert is_public_bill(bill) is False


def test_is_public_bill_allows_normal_diavgeia_procurement() -> None:
    bill = SimpleNamespace(
        admin_hidden=False,
        source="DIAVGEIA",
        title_el="Έγκριση συμμετοχής υπαλλήλων σε σεμινάριο",
        summary_short_el="Απόφαση δημάρχου για υπηρεσιακή εκπαίδευση",
        summary_long_el=None,
    )
    assert is_public_bill(bill) is True


def test_sensitive_diavgeia_filter_compiles_marker_checks() -> None:
    compiled = _compiled_literal(public_bill_filter()).lower()
    assert "diavgeia" in compiled
    assert "amka" in compiled
    assert "ασθεν" in compiled


def test_raw_diavgeia_filter_and_object_guard_block_patient_markers() -> None:
    compiled = _compiled_literal(public_raw_diavgeia_filter()).lower()
    assert "diavgeia_decisions.subject" in compiled
    assert "amka" in compiled
    assert "ασθεν" in compiled
    assert is_public_raw_diavgeia_decision(
        SimpleNamespace(subject="Δαπάνη για ασθενή με ΑΜΚΑ 123")
    ) is False
    assert is_public_raw_diavgeia_decision(
        SimpleNamespace(subject="Απόφαση δημοτικού συμβουλίου")
    ) is True

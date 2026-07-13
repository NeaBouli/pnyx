from types import SimpleNamespace

from services.content_provenance import (
    apply_generated_content,
    clear_generated_content,
    content_sha256,
    has_generated_content_provenance,
    is_generated_content_unchanged,
    record_generated_content,
)


def _bill(**overrides):
    values = {
        "pill_el": None,
        "summary_short_el": None,
        "generated_content_provenance": None,
        "ai_summary_reviewed": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_empty_generated_field_is_filled_and_claimed():
    bill = _bill()

    changed = apply_generated_content(bill, "summary_short_el", "Νέα σύνοψη")

    assert changed is True
    assert bill.summary_short_el == "Νέα σύνοψη"
    assert bill.generated_content_provenance == {
        "summary_short_el": content_sha256("Νέα σύνοψη")
    }
    assert has_generated_content_provenance(bill, "summary_short_el") is True


def test_unchanged_generated_field_can_refresh():
    bill = _bill(summary_short_el="Παλιά σύνοψη")
    record_generated_content(bill, "summary_short_el", bill.summary_short_el)

    changed = apply_generated_content(bill, "summary_short_el", "Νέα σύνοψη")

    assert changed is True
    assert bill.summary_short_el == "Νέα σύνοψη"
    assert is_generated_content_unchanged(bill, "summary_short_el", "Νέα σύνοψη")


def test_manual_edit_is_never_overwritten():
    bill = _bill(summary_short_el="Αυτόματη σύνοψη")
    record_generated_content(bill, "summary_short_el", bill.summary_short_el)
    bill.summary_short_el = "Χειροκίνητη διόρθωση"

    changed = apply_generated_content(bill, "summary_short_el", "Νεότερη αυτόματη σύνοψη")

    assert changed is False
    assert bill.summary_short_el == "Χειροκίνητη διόρθωση"


def test_legacy_nonempty_field_without_provenance_is_preserved():
    bill = _bill(summary_short_el="Υπάρχουσα σύνοψη")

    changed = apply_generated_content(bill, "summary_short_el", "Νέα σύνοψη")

    assert changed is False
    assert bill.summary_short_el == "Υπάρχουσα σύνοψη"
    assert bill.generated_content_provenance is None


def test_reviewed_summary_is_preserved_even_when_hash_matches():
    bill = _bill(summary_short_el="Ελεγμένη σύνοψη", ai_summary_reviewed=True)
    record_generated_content(bill, "summary_short_el", bill.summary_short_el)

    changed = apply_generated_content(bill, "summary_short_el", "Νέα σύνοψη")

    assert changed is False
    assert bill.summary_short_el == "Ελεγμένη σύνοψη"


def test_reviewed_empty_summary_is_not_filled_automatically():
    bill = _bill(ai_summary_reviewed=True)

    changed = apply_generated_content(bill, "summary_short_el", "Νέα σύνοψη")

    assert changed is False
    assert bill.summary_short_el is None


def test_manual_clear_removes_only_selected_ownership():
    bill = _bill(pill_el="Pill", summary_short_el="Σύνοψη")
    record_generated_content(bill, "pill_el", bill.pill_el)
    record_generated_content(bill, "summary_short_el", bill.summary_short_el)

    clear_generated_content(bill, "summary_short_el")

    assert bill.generated_content_provenance == {
        "pill_el": content_sha256("Pill")
    }

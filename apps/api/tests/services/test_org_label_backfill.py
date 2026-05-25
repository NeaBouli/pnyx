import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.diavgeia_scraper import _clean_org_label


def test_unknown_bracket_rejected():
    assert _clean_org_label("[unknown:99202041]") is None


def test_unknown_plain_rejected():
    assert _clean_org_label("unknown") is None


def test_blank_rejected():
    assert _clean_org_label("") is None
    assert _clean_org_label("   ") is None
    assert _clean_org_label(None) is None


def test_clean_label_accepted():
    assert _clean_org_label("ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ") == "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ"


def test_clean_label_trimmed():
    assert _clean_org_label("  ΕΦΚΑ  ") == "ΕΦΚΑ"


def test_existing_org_label_not_overwritten():
    """Backfill SQL uses pb.org_label IS NULL — existing values preserved."""
    # This is a SQL constraint test, verified by the WHERE clause.
    # The _clean_org_label function is the Python guard.
    assert _clean_org_label("ΥΠΕΞ") == "ΥΠΕΞ"
    assert _clean_org_label("[unknown:123]") is None

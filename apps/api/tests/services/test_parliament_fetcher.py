"""
Golden Path Regression Test: _is_bad_parliament_text Quality Gate
Protects: parliament_fetcher.py — prevents boilerplate from being stored as summary_long_el
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from services.parliament_fetcher import _is_bad_parliament_text


class TestIsBadParliamentText:
    """Quality gate must reject navigation/menu boilerplate."""

    def test_empty_is_bad(self):
        assert _is_bad_parliament_text("") is True

    def test_none_is_bad(self):
        assert _is_bad_parliament_text(None) is True

    def test_short_text_is_bad(self):
        assert _is_bad_parliament_text("Σύντομο κείμενο.") is True

    def test_navigation_boilerplate_is_bad(self):
        text = """Μετάβαση στο κύριο περιεχόμενο
        Νομοθετική Διαδικασία
        Ημερ. Διάταξη Ολομέλειας
        Εβδομαδιαίο Δελτίο"""
        assert _is_bad_parliament_text(text) is True

    def test_single_boilerplate_pattern_is_bad(self):
        text = "Νομοθετική Διαδικασία " * 20  # >200 chars but boilerplate
        assert _is_bad_parliament_text(text) is True

    def test_accessibility_menu_is_bad(self):
        text = "Εμφανίζονται τα σχέδια ή οι προτάσεις νόμων " * 10
        assert _is_bad_parliament_text(text) is True

    def test_markdown_links_mostly_is_bad(self):
        lines = ["* [Link](https://hellenicparliament.gr/page) text"] * 10
        lines.append("Ένα κείμενο.")
        text = "\n".join(lines)
        assert _is_bad_parliament_text(text) is True

    def test_real_law_text_is_good(self):
        text = (
            "Ο νόμος ορίζει τη δημιουργία του Κοινωνικού Κλιματικού Ταμείου "
            "και του Ταμείου Εκσυγχρονισμού για να υποστηρίξουν προγράμματα "
            "ενέργειας και κοινωνική αλλαγή. Ο νόμος συμπληρώνει την ενέργεια "
            "και την κοινωνική πολιτική της χώρας. Προβλέπεται η σύσταση "
            "επιτροπής παρακολούθησης και η υποβολή ετήσιας έκθεσης."
        )
        assert _is_bad_parliament_text(text) is False

    def test_diavgeia_decision_text_is_good(self):
        text = (
            "ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ ΑΝΑΡΤΗΤΕΑ ΣΤΟ ΔΙΑΔΙΚΤΥΟ "
            "Απόσπασμα από το πρακτικό της 7ης/2026 τακτικής συνεδρίασης "
            "του Διοικητικού Συμβουλίου του Δημοτικού Λιμενικού Ταμείου Σπετσών. "
            "ΘΕΜΑ 8ο: Εξέταση αίτησης Ναυτικού Ομίλου Ελλάδος για την παροχή "
            "διευκολύνσεων στο πλαίσιο του διεθνούς αγώνα."
        )
        assert _is_bad_parliament_text(text) is False

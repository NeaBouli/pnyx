"""
Golden Path Regression Test: _is_bad_parliament_text Quality Gate
Protects: parliament_fetcher.py — prevents boilerplate from being stored as summary_long_el
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from services.parliament_fetcher import (
    _is_bad_parliament_text,
    _is_parliament_document_block_only,
    _merge_text_with_existing_document_block,
)


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

    def test_search_result_metadata_prefix_is_bad(self):
        text = (
            "Αναζήτηση Τίτλος Ενίσχυση της εφαρμογής της ισότητας της αμοιβής "
            "μεταξύ ανδρών και γυναικών για όμοια εργασία ή για εργασία ίσης αξίας "
            "και λοιπές διατάξεις - Ενσωμάτωση Οδηγίας (Ε.) 2023/970 - "
            "Συνταξιοδοτικές ρυθμίσεις Τύπος Σχέδιο νόμου Υπουργείο Εργασίας "
            "και Κοινωνικής Ασφάλισης Επιτροπή Διαρκής Επιτροπή Κοινωνικών "
            "Υποθέσεων Φάση Επεξεργασίας Κατατεθέντα Ημερομηνία Φάσης επεξεργασίας "
            "23/06/2026 Το φωτοτυπημένο σχέδιο νόμου δεν αποτελεί το τελικό κείμενο."
        )

        assert _is_bad_parliament_text(text) is True

    def test_upstream_access_denial_is_bad(self):
        text = (
            "You don't have permission to access '/' on this server. "
            "Reference #18.63c7cf17.1783640051.9520c14 "
            "https://errors.edgesuite.net/18.63c7cf17.1783640051.9520c14 "
        ) * 3

        assert _is_bad_parliament_text(text) is True

    def test_access_denied_words_alone_do_not_reject_real_text(self):
        text = (
            "Η φράση Access Denied αναφέρεται ως τεχνικός όρος μέσα σε νόμιμο "
            "επίσημο κείμενο. Το υπόλοιπο άρθρο περιγράφει αναλυτικά τις "
            "προϋποθέσεις, τις αρμοδιότητες και τις εγγυήσεις εφαρμογής. "
        ) * 3

        assert _is_bad_parliament_text(text) is False

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


class TestParliamentDocumentBlockOnly:
    """PDF fallback blocks must stay usable but should not block enrichment."""

    def test_pdf_only_document_block_is_detected(self):
        text = (
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο Βουλής 1 (13325042.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325042.pdf)\n"
            "- [Έγγραφο Βουλής 2 (13325043.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325043.pdf)"
        )

        assert _is_parliament_document_block_only(text) is True

    def test_real_text_plus_document_block_is_not_pdf_only(self):
        text = (
            "Σκοπός του νόμου είναι η οργάνωση της τοπικής αυτοδιοίκησης "
            "και η αποσαφήνιση αρμοδιοτήτων για τους δήμους και τις περιφέρειες.\n\n"
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο Βουλής 1 (13325042.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325042.pdf)"
        )

        assert _is_parliament_document_block_only(text) is False

    def test_document_block_detector_rejects_non_parliament_links(self):
        text = (
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο](https://example.com/13325042.pdf)"
        )

        assert _is_parliament_document_block_only(text) is False

    def test_merge_preserves_existing_pdf_links_after_fetch_success(self):
        fetched_text = (
            "Σκοπός του νόμου είναι η οργάνωση της τοπικής αυτοδιοίκησης "
            "και η αποσαφήνιση αρμοδιοτήτων για τους δήμους και τις περιφέρειες."
        )
        document_block = (
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο Βουλής 1 (13325042.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325042.pdf)"
        )

        merged = _merge_text_with_existing_document_block(fetched_text, document_block)

        assert merged.startswith(fetched_text)
        assert "### Πλήρη έγγραφα" in merged
        assert "13325042.pdf" in merged

    def test_merge_does_not_append_when_existing_summary_is_real_text(self):
        fetched_text = "Νέο καθαρό κείμενο νόμου με επαρκές περιεχόμενο."
        existing_text = "Παλαιότερο πραγματικό κείμενο νόμου, όχι απλός σύνδεσμος PDF."

        assert _merge_text_with_existing_document_block(fetched_text, existing_text) == fetched_text

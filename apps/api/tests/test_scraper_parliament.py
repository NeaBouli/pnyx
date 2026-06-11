import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers.scraper import _parse_parliament_markdown


def test_parse_all_laws_current_rows_with_date_and_phase():
    md = """
| Βρέθηκαν 346 Αποτελέσματα | Σελίδα 1 από 35 |
| --- |
| [Αδειοδότηση παρόχων περιεχομένου επίγειας ψηφιακής τηλεοπτικής ευρυεκπομπής ελεύθερης λήψης...](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=3aba3e72-d5b0-414b-8649-b45901603f92) | Σχέδιο νόμου | 10/06/2026 | Έτοιμα για συζήτηση στη Βουλή |
| [Εφαρμογή του Συμφώνου για τη Μετανάστευση και το Άσυλο και λοιπές διατάξεις του Υπουργείου...](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=fa1f20de-a5f8-4704-9b87-b45600ebe012) | Σχέδιο νόμου | 09/06/2026 | Συζήτηση και Ψήφιση |
"""

    bills = _parse_parliament_markdown(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/all-laws",
    )

    assert [bill["law_id"] for bill in bills] == [
        "3aba3e72-d5b0-414b-8649-b45901603f92",
        "fa1f20de-a5f8-4704-9b87-b45600ebe012",
    ]
    assert bills[0]["submitted_date"] == "2026-06-10T00:00:00+00:00"
    assert bills[0]["date"] is None
    assert bills[0]["type"] == "Σχέδιο νόμου"
    assert bills[0]["phase"] == "Έτοιμα για συζήτηση στη Βουλή"
    assert bills[1]["submitted_date"] is None
    assert bills[1]["date"] == "2026-06-09T00:00:00+00:00"


def test_parse_katatethenta_date_first_rows_remain_supported():
    md = """
| Ημ. Κατάθεσης | Τίτλος | Τύπος | Υπουργείο |
| 02/06/2026 | [Κύρωση Συμφωνίας](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=54ec1c41-616a-405d-89e3-b45e00ad2542) | Διεθνής Σύμβαση | Εθνικής Άμυνας |
"""

    bills = _parse_parliament_markdown(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    )

    assert len(bills) == 1
    assert bills[0]["law_id"] == "54ec1c41-616a-405d-89e3-b45e00ad2542"
    assert bills[0]["submitted_date"] == "2026-06-02T00:00:00+00:00"
    assert bills[0]["date"] is None
    assert bills[0]["type"] == "Διεθνής Σύμβαση"
    assert bills[0]["ministry"] == "Εθνικής Άμυνας"


def test_parse_katatethenta_pdf_column_into_document_block():
    md = """
| Ημ. Κατάθεσης | Τίτλος | Τύπος | Υπουργείο | PDFs |
| 10/06/2026 | [ΚΩΔΙΚΑΣ ΤΟΠΙΚΗΣ ΑΥΤΟΔΙΟΙΚΗΣΗΣ](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia?law_id=357e304b-d7d7-410a-8bef-b465011c6f24) | Σχέδιο νόμου | Εσωτερικών | [![Image 1: Αιτιολογική Έκθεση & Λοιπές Συνοδευτικές Εκθέσεις](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325042.pdf)[![Image 2: Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325043.pdf) |
"""

    bills = _parse_parliament_markdown(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    )

    assert len(bills) == 1
    assert "### Πλήρη έγγραφα" in bills[0]["summary_long_el"]
    assert "[Έγγραφο Βουλής 1 (13325042.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325042.pdf)" in bills[0]["summary_long_el"]
    assert "[Έγγραφο Βουλής 2 (13325043.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13325043.pdf)" in bills[0]["summary_long_el"]


def test_parse_katatethenta_preserves_blank_type_ministry_before_pdf_column():
    md = """
| Ημ. Κατάθεσης | Τίτλος | Τύπος | Υπουργείο | PDFs |
| 10/06/2026 | [Πρόταση για τη Συνταγματική Αναθεώρηση](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia?law_id=f84ba259-f13d-4155-bc09-b46600ac010a) |  |  | [![Image 5: Αιτιολογική Έκθεση & Λοιπές Συνοδευτικές Εκθέσεις](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13324903.pdf) |
"""

    bills = _parse_parliament_markdown(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    )

    assert len(bills) == 1
    assert bills[0]["type"] is None
    assert bills[0]["ministry"] is None
    assert "[Έγγραφο Βουλής 1 (13324903.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13324903.pdf)" in bills[0]["summary_long_el"]

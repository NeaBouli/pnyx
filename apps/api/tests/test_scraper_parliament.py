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

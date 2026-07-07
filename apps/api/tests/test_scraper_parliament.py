import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import scraper as scraper_router
from routers.scraper import _finalize_scraped_bills, _parse_parliament_markdown, prefer_scraped_title


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


def test_parse_preserves_long_title_without_artificial_200_char_cutoff():
    long_title = ("Κύρωση " + ("της διεθνούς συμφωνίας " * 12)).strip()
    md = f"""
| [ {long_title} ](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=3aba3e72-d5b0-414b-8649-b45901603f92) | Σχέδιο νόμου | 10/06/2026 | Κατατεθέντα |
"""

    bills = _parse_parliament_markdown(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/all-laws",
    )

    assert bills[0]["title_el"] == long_title
    assert len(bills[0]["title_el"]) > 200


def test_prefer_scraped_title_replaces_only_truncated_existing_title():
    truncated = "Κύρωση της υπ’ αριθμόν 1 Τροποποίησης της Συμφωνίας μεταξύ της Κυβέρνησης..."
    full = "Κύρωση της υπ’ αριθμόν 1 Τροποποίησης της Συμφωνίας μεταξύ της Κυβέρνησης της Ελληνικής Δημοκρατίας και της Κυβέρνησης της Κυπριακής Δημοκρατίας"

    assert prefer_scraped_title(truncated, full) == full
    assert prefer_scraped_title(full, truncated) == full


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


def test_finalize_scraped_bills_can_filter_undated_fallback_rows():
    bills = [
        {"title_el": "title-only fallback", "date": None, "submitted_date": None},
        {"title_el": "dated row", "date": None, "submitted_date": "2026-06-23T00:00:00+00:00"},
    ]

    strict = _finalize_scraped_bills(bills, limit=10, require_dates=True)
    loose = _finalize_scraped_bills(bills, limit=10, require_dates=False)

    assert strict == [bills[1]]
    assert loose == bills


@pytest.mark.asyncio
async def test_parliament_freshness_probe_requires_dated_scraper(monkeypatch):
    async def fake_scrape(limit: int, require_dates: bool = False, probe_errors=None):
        assert limit == 20
        assert require_dates is True
        return [
            {"title_el": "submitted", "date": None, "submitted_date": "2026-06-23T00:00:00+00:00"},
            {"title_el": "voted", "date": "2026-06-22T00:00:00+00:00", "submitted_date": None},
        ]

    monkeypatch.setattr(scraper_router, "scrape_parliament_bills", fake_scrape)

    payload = await scraper_router.get_parliament_freshness_probe(limit=20)

    assert payload["count"] == 2
    assert payload["dated_count"] == 2
    assert payload["source_latest"] == "2026-06-23T00:00:00+00:00"


@pytest.mark.asyncio
async def test_strict_scrape_falls_back_when_stage_one_has_only_undated_rows(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "Data": [
                    {
                        "Title": "Undated API row that should not stop strict fallback",
                        "LawPhaseDate": "",
                        "ID": "undated-stage-one",
                    }
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    async def fake_fetch_jina_markdown(url: str, probe_errors=None):
        if "all-laws" not in url:
            return ""
        return """
| [Dated fallback row](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=3aba3e72-d5b0-414b-8649-b45901603f92) | Σχέδιο νόμου | 23/06/2026 | Κατατεθέντα |
"""

    monkeypatch.setattr(scraper_router.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(scraper_router, "_fetch_jina_markdown", fake_fetch_jina_markdown)
    monkeypatch.setattr(scraper_router, "SCRAPE_DELAY_SECONDS", 0)

    bills = await scraper_router.scrape_parliament_bills(limit=10, require_dates=True)

    assert len(bills) == 1
    assert bills[0]["law_id"] == "3aba3e72-d5b0-414b-8649-b45901603f92"
    assert bills[0]["submitted_date"] == "2026-06-23T00:00:00+00:00"


@pytest.mark.asyncio
async def test_jina_access_denied_markdown_is_reported_as_blocked(monkeypatch):
    class ApiBlockedResponse:
        status_code = 403

        def json(self):
            return {}

    class DirectBlockedResponse:
        status_code = 403
        text = "Access Denied"

    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ApiBlockedResponse()
            return DirectBlockedResponse()

    async def fake_fetch_jina_markdown(_url: str, probe_errors=None):
        if probe_errors is not None and "jina_target_access_denied" not in probe_errors:
            probe_errors.append("jina_target_access_denied")
        return None

    monkeypatch.setattr(scraper_router.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(scraper_router, "_fetch_jina_markdown", fake_fetch_jina_markdown)
    monkeypatch.setattr(scraper_router, "SCRAPE_DELAY_SECONDS", 0)

    payload = await scraper_router.get_parliament_freshness_probe(limit=20)

    assert payload["source_status"] == "blocked"
    assert payload["count"] == 0
    assert payload["dated_count"] == 0
    assert "api_http_403" in payload["probe_errors"]
    assert "jina_target_access_denied" in payload["probe_errors"]
    assert "direct_html_http_403" in payload["probe_errors"]

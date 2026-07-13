import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import scraper as scraper_router
from routers.scraper import (
    BillImportItem,
    BillImportRequest,
    _build_parliament_metadata_summary,
    _finalize_scraped_bills,
    _parse_parliament_markdown,
    import_parliament_bills,
    prefer_scraped_title,
)
from models import BillStatus


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
    assert bills[0]["pill_el"] == "Σχέδιο νόμου — Εσωτερικών"
    assert "Η Βουλή δημοσίευσε εγγραφή για: ΚΩΔΙΚΑΣ ΤΟΠΙΚΗΣ ΑΥΤΟΔΙΟΙΚΗΣΗΣ." in bills[0]["summary_short_el"]
    assert "Τύπος: Σχέδιο νόμου" in bills[0]["summary_short_el"]
    assert "Υπουργείο: Εσωτερικών" in bills[0]["summary_short_el"]
    assert "Ημερομηνία κατάθεσης: 10/06/2026" in bills[0]["summary_short_el"]
    assert "Για το πλήρες περιεχόμενο δείτε τα επίσημα έγγραφα της Βουλής." in bills[0]["summary_short_el"]
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
    assert bills[0]["pill_el"] == "Πρόταση για τη Συνταγματική Αναθεώρηση"
    assert "Η Βουλή δημοσίευσε εγγραφή για: Πρόταση για τη Συνταγματική Αναθεώρηση." in bills[0]["summary_short_el"]
    assert "Ημερομηνία κατάθεσης: 10/06/2026" in bills[0]["summary_short_el"]
    assert "[Έγγραφο Βουλής 1 (13324903.pdf)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13324903.pdf)" in bills[0]["summary_long_el"]


def test_metadata_summary_is_descriptive_not_interpretive():
    summary = _build_parliament_metadata_summary(
        title_el="Παράδειγμα νομοσχεδίου",
        bill_type="Σχέδιο νόμου",
        ministry="Υπουργείο Δοκιμής",
        phase="Κατατεθέντα",
        submitted_date="2026-07-02T00:00:00+00:00",
        vote_date=None,
    )

    assert "Η Βουλή δημοσίευσε εγγραφή" in summary
    assert "Για το πλήρες περιεχόμενο" in summary
    assert "ρυθμίζει" not in summary
    assert "αποσκοπεί" not in summary


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


class _FakeScalarResult:
    def __init__(self, row):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class _FakeImportDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        return _FakeScalarResult(self.existing)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_github_import_fills_missing_metadata_without_touching_status():
    existing = type("ExistingBill", (), {})()
    existing.title_el = "Κύρωση συμφωνίας..."
    existing.parliament_url = None
    existing.submitted_date = None
    existing.parliament_vote_date = None
    existing.pill_el = None
    existing.summary_short_el = None
    existing.summary_long_el = None
    existing.categories = None
    existing.status = BillStatus.ACTIVE

    db = _FakeImportDb(existing)
    payload = BillImportRequest(
        admin_key="test",
        bills=[
            BillImportItem(
                bill_id="GR-e744abc6",
                title_el="Κύρωση συμφωνίας με πλήρη τίτλο",
                ministry="Εξωτερικών",
                type="Διεθνής Σύμβαση",
                url="https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=e744abc6-3e81-4e56-a4cd-b47f0174f2b1",
                submitted_date="2026-07-06T00:00:00+00:00",
                summary_long_el="### Πλήρη έγγραφα\n- [Έγγραφο Βουλής 1](https://example.test/doc.pdf)",
            )
        ],
    )

    result = await import_parliament_bills(payload, _auth=True, db=db)

    assert result == {"success": True, "imported": 0, "updated": 1, "skipped": 0}
    assert existing.status == BillStatus.ACTIVE
    assert existing.title_el == "Κύρωση συμφωνίας με πλήρη τίτλο"
    assert existing.pill_el == "Διεθνής Σύμβαση — Εξωτερικών"
    assert existing.summary_short_el.startswith("Η Βουλή δημοσίευσε εγγραφή")
    assert existing.summary_long_el.startswith("### Πλήρη έγγραφα")
    assert existing.categories == ["Εξωτερικών"]
    assert db.committed is True


@pytest.mark.asyncio
async def test_github_import_does_not_overwrite_existing_official_text():
    existing = type("ExistingBill", (), {})()
    existing.title_el = "Πλήρης υπάρχων τίτλος"
    existing.parliament_url = "https://old.example.test"
    existing.submitted_date = None
    existing.parliament_vote_date = None
    existing.pill_el = "Υπάρχον pill"
    existing.summary_short_el = "Υπάρχουσα σύνοψη"
    existing.summary_long_el = "Υπάρχον επίσημο κείμενο"
    existing.categories = ["Υπάρχουσα"]
    existing.status = BillStatus.WINDOW_24H

    db = _FakeImportDb(existing)
    payload = BillImportRequest(
        admin_key="test",
        bills=[
            BillImportItem(
                bill_id="GR-e744abc6",
                title_el="Πλήρης υπάρχων τίτλος...",
                ministry="Νέο υπουργείο",
                url="https://new.example.test",
                summary_short_el="Νέα σύνοψη",
                summary_long_el="Νέο επίσημο κείμενο",
            )
        ],
    )

    result = await import_parliament_bills(payload, _auth=True, db=db)

    assert result["updated"] == 1
    assert existing.status == BillStatus.WINDOW_24H
    assert existing.title_el == "Πλήρης υπάρχων τίτλος"
    assert existing.parliament_url == "https://new.example.test"
    assert existing.pill_el == "Υπάρχον pill"
    assert existing.summary_short_el == "Υπάρχουσα σύνοψη"
    assert existing.summary_long_el == "Υπάρχον επίσημο κείμενο"
    assert existing.categories == ["Υπάρχουσα"]


@pytest.mark.asyncio
async def test_github_import_refreshes_only_unchanged_generated_summary():
    from services.content_provenance import record_generated_content

    existing = type("ExistingBill", (), {})()
    existing.title_el = "Πλήρης τίτλος"
    existing.parliament_url = None
    existing.submitted_date = None
    existing.parliament_vote_date = None
    existing.pill_el = "Παλιό pill"
    existing.summary_short_el = "Παλιά αυτόματη σύνοψη"
    existing.summary_long_el = "### Πλήρη έγγραφα\n- [PDF](https://example.test/doc.pdf)"
    existing.categories = None
    existing.status = BillStatus.ACTIVE
    existing.ai_summary_reviewed = False
    existing.generated_content_provenance = None
    record_generated_content(existing, "pill_el", existing.pill_el)
    record_generated_content(existing, "summary_short_el", existing.summary_short_el)

    db = _FakeImportDb(existing)
    payload = BillImportRequest(
        admin_key="test",
        bills=[
            BillImportItem(
                bill_id="GR-refresh",
                title_el="Πλήρης τίτλος",
                pill_el="Νέο pill",
                summary_short_el="Νέα αυτόματη σύνοψη",
                summary_long_el="Νέο κείμενο που δεν επιτρέπεται να αντικαταστήσει το PDF",
            )
        ],
    )

    result = await import_parliament_bills(payload, _auth=True, db=db)

    assert result["updated"] == 1
    assert existing.pill_el == "Νέο pill"
    assert existing.summary_short_el == "Νέα αυτόματη σύνοψη"
    assert existing.summary_long_el.startswith("### Πλήρη έγγραφα")


@pytest.mark.asyncio
async def test_github_import_preserves_manual_summary_after_generated_version_changed():
    from services.content_provenance import record_generated_content

    existing = type("ExistingBill", (), {})()
    existing.title_el = "Πλήρης τίτλος"
    existing.parliament_url = None
    existing.submitted_date = None
    existing.parliament_vote_date = None
    existing.pill_el = "Χειροκίνητο pill"
    existing.summary_short_el = "Αυτόματη σύνοψη"
    existing.summary_long_el = "Επίσημο κείμενο"
    existing.categories = ["Υπάρχουσα"]
    existing.status = BillStatus.ACTIVE
    existing.ai_summary_reviewed = False
    existing.generated_content_provenance = None
    record_generated_content(existing, "summary_short_el", existing.summary_short_el)
    existing.summary_short_el = "Χειροκίνητη διόρθωση"

    db = _FakeImportDb(existing)
    payload = BillImportRequest(
        admin_key="test",
        bills=[
            BillImportItem(
                bill_id="GR-manual",
                title_el="Πλήρης τίτλος",
                pill_el="Νεότερο pill",
                summary_short_el="Νεότερη αυτόματη σύνοψη",
            )
        ],
    )

    await import_parliament_bills(payload, _auth=True, db=db)

    assert existing.pill_el == "Χειροκίνητο pill"
    assert existing.summary_short_el == "Χειροκίνητη διόρθωση"
    assert existing.summary_long_el == "Επίσημο κείμενο"

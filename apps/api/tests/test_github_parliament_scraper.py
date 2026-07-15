import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.scraper import (  # noqa: E402
    BillImportItem,
    _official_text_attestation_message,
    _official_text_attestation_valid,
)


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "parliament_scraper.py"
spec = importlib.util.spec_from_file_location("parliament_scraper_script", SCRIPT_PATH)
parliament_scraper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = parliament_scraper
spec.loader.exec_module(parliament_scraper)


def test_workflow_attestation_matches_api_verifier():
    key = "test-parliament-attestation-key-32-chars-minimum"
    bill = {
        "bill_id": "GR-daceffb6",
        "law_id": "daceffb6-deca-4695-a9f0-b4830135158e",
        "title_el": "Πλήρης τίτλος",
        "url": (
            "https://www.hellenicparliament.gr/Nomothetiko-Ergo/all-laws"
            "?law_id=daceffb6-deca-4695-a9f0-b4830135158e"
        ),
        "summary_short_el": "Σκοπός του νόμου είναι η ασφαλής δοκιμή της ροής εισαγωγής.",
        "summary_long_el": (
            "Σκοπός του νόμου είναι η ασφαλής δοκιμή.\n\n"
            "### Πλήρη έγγραφα\n"
            "- [PDF](https://www.hellenicparliament.gr/UserFiles/doc.pdf)"
        ),
        "official_text_verified": True,
        "official_text_source_url": "https://www.hellenicparliament.gr/UserFiles/doc.pdf",
    }

    parliament_scraper.attest_verified_official_text(bill, key)
    item = BillImportItem(**bill)

    assert parliament_scraper.official_text_attestation_message(bill) == _official_text_attestation_message(item)
    assert _official_text_attestation_valid(item, key)


def test_parse_api_payload_preserves_law_id_and_metadata():
    payload = {
        "Data": [
            {
                "ID": "e744abc6-3e81-4e56-a4cd-b47f0174f2b1",
                "Title": "Μέτρα εφαρμογής του Κανονισμού (ΕΕ) 2024/1689",
                "Type": "Σχέδιο νόμου",
                "Ministry": "Ψηφιακής Διακυβέρνησης",
                "LawPhaseDate": "/Date(1783296000000)/",
            }
        ]
    }

    bills = parliament_scraper.parse_api_payload(json.dumps(payload))

    assert bills[0]["bill_id"] == "GR-e744abc6"
    assert bills[0]["law_id"] == "e744abc6-3e81-4e56-a4cd-b47f0174f2b1"
    assert bills[0]["url"].endswith("law_id=e744abc6-3e81-4e56-a4cd-b47f0174f2b1")
    assert bills[0]["vote_date"].startswith("2026-07-06")
    assert "Ψηφιακής Διακυβέρνησης" in bills[0]["summary_short_el"]


def test_parse_markdown_fallback_keeps_pdf_document_block():
    md = """
| 06/07/2026 | [Μέτρα εφαρμογής του Κανονισμού](https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia?law_id=e744abc6-3e81-4e56-a4cd-b47f0174f2b1) | Σχέδιο νόμου | Ψηφιακής Διακυβέρνησης | [![Image 1: Αιτιολογική Έκθεση](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13353094.pdf) |
"""

    bills = parliament_scraper.parse_markdown_table(
        md,
        "https://www.hellenicparliament.gr/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    )

    assert bills[0]["bill_id"] == "GR-e744abc6"
    assert bills[0]["submitted_date"] == "2026-07-06T00:00:00+00:00"
    assert bills[0]["summary_long_el"].startswith("### Πλήρη έγγραφα")
    assert "13353094.pdf" in bills[0]["summary_long_el"]


def test_scrape_uses_direct_html_when_api_is_blocked(monkeypatch):
    html = """
<table><tr>
<td><a href="/Nomothetiko-Ergo/Katatethenta-Nomosxedia?law_id=e744abc6-3e81-4e56-a4cd-b47f0174f2b1">Μέτρα εφαρμογής του Κανονισμού</a></td>
<td>Σχέδιο νόμου</td><td>06/07/2026</td><td>Κατατεθέντα</td>
<td><a href="https://www.hellenicparliament.gr/UserFiles/c8827c35/13353094.pdf">PDF</a></td>
</tr></table>
"""

    def fake_get(url, *, accept="*/*", timeout=30):
        if "api.ashx" in url:
            return parliament_scraper.FetchResult(url=url, status=403, text="Access Denied", error="http_403")
        if url.startswith("https://r.jina.ai/"):
            return parliament_scraper.FetchResult(url=url, status=401, text="AuthenticationRequiredError", error="http_401")
        return parliament_scraper.FetchResult(url=url, status=200, text=html)

    monkeypatch.setattr(parliament_scraper, "_http_get", fake_get)
    monkeypatch.setattr(parliament_scraper.time, "sleep", lambda *_args, **_kwargs: None)

    bills, errors = parliament_scraper.scrape(limit=20)

    assert bills
    assert bills[0]["bill_id"] == "GR-e744abc6"
    assert bills[0]["submitted_date"] == "2026-07-06T00:00:00+00:00"
    assert any(error.startswith("api_blocked_or_unavailable") for error in errors)


def test_parse_detail_markdown_recovers_full_title_and_labeled_pdfs():
    truncated = (
        "Κύρωση της Συμφωνίας μεταξύ του Υπουργείου Άμυνας "
        "της Δημοκρατίας της Βουλγαρίας και του..."
    )
    full = (
        "Κύρωση της Συμφωνίας μεταξύ του Υπουργείου Άμυνας της Δημοκρατίας "
        "της Βουλγαρίας και του Υπουργείου Εθνικής Άμυνας της Ελληνικής "
        "Δημοκρατίας σχετικά με την παροχή υποστήριξης προς το Ελληνικό "
        "Στρατιωτικό Απόσπασμα"
    )
    markdown = f"""
Title: Επεξεργασία στις Επιτροπές
Markdown Content:

Τίτλος
{full}
Τύπος
Διεθνής Σύμβαση
Υπουργείο
Εθνικής Άμυνας
Αιτιολογική Έκθεση[![Image: .pdf](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13359710.pdf)
Διατάξεις Σχεδίου Νόμου[![Image: .pdf](https://www.hellenicparliament.gr/images/mime/pdf.png)](https://www.hellenicparliament.gr/UserFiles/c8827c35/13359711.pdf)
"""

    detail = parliament_scraper.parse_detail_markdown(markdown)

    assert detail["title_el"] == full
    assert detail["type"] == "Διεθνής Σύμβαση"
    assert detail["ministry"] == "Εθνικής Άμυνας"
    assert detail["pdf_links"] == [
        {
            "label": "Αιτιολογική Έκθεση",
            "url": "https://www.hellenicparliament.gr/UserFiles/c8827c35/13359710.pdf",
        },
        {
            "label": "Διατάξεις Σχεδίου Νόμου",
            "url": "https://www.hellenicparliament.gr/UserFiles/c8827c35/13359711.pdf",
        },
    ]
    assert parliament_scraper.prefer_complete_title(truncated, detail["title_el"]) == full


def test_detail_enrichment_rejects_title_from_another_bill():
    current = "Κύρωση της Συμφωνίας μεταξύ Ελλάδας και..."
    unrelated = "Ρυθμίσεις για την αγορά ενέργειας και την προστασία καταναλωτών"

    assert parliament_scraper.prefer_complete_title(current, unrelated) == current

    bill = {
        "title_el": current,
        "type": "Διεθνής Σύμβαση",
        "ministry": "Εθνικής Άμυνας",
        "summary_short_el": "Ασφαλή μεταδεδομένα",
        "summary_long_el": None,
    }
    markdown = f"""
Τίτλος
{unrelated}
Τύπος
Σχέδιο νόμου
Υπουργείο
Περιβάλλοντος
[Αιτιολογική Έκθεση](https://www.hellenicparliament.gr/UserFiles/wrong.pdf)
"""

    assert parliament_scraper.enrich_bill_from_detail(bill, markdown) == []
    assert bill == {
        "title_el": current,
        "type": "Διεθνής Σύμβαση",
        "ministry": "Εθνικής Άμυνας",
        "summary_short_el": "Ασφαλή μεταδεδομένα",
        "summary_long_el": None,
    }


def test_detail_enrichment_requires_a_complete_matching_detail_title():
    truncated = "Κύρωση της Συμφωνίας μεταξύ Ελλάδας και..."
    markdown = """
Τίτλος
Κύρωση της Συμφωνίας μεταξύ Ελλάδας και...
[PDF](https://www.hellenicparliament.gr/UserFiles/unbound.pdf)
"""
    bill = {"title_el": truncated, "summary_long_el": None}

    assert parliament_scraper.enrich_bill_from_detail(bill, markdown) == []
    assert bill["summary_long_el"] is None


def test_verified_pdf_text_builds_extractive_summary_and_keeps_documents():
    bill = {
        "title_el": "Ρυθμίσεις για τη δημόσια διοίκηση...",
        "summary_short_el": "Μεταδεδομένα μόνο",
        "summary_long_el": (
            "### Πλήρη έγγραφα\n"
            "- [Αιτιολογική Έκθεση](https://www.hellenicparliament.gr/UserFiles/c8827c35/13350000.pdf)"
        ),
    }
    pdf_text = """
Markdown Content:
ΑΙΤΙΟΛΟΓΙΚΗ ΕΚΘΕΣΗ
Σκοπός
Σκοπός του σχεδίου νόμου είναι η απλούστευση των διοικητικών διαδικασιών
και η καθιέρωση ενιαίων προθεσμιών για τις δημόσιες υπηρεσίες. Παράλληλα,
προβλέπεται ηλεκτρονική ενημέρωση των πολιτών για την πορεία κάθε αίτησης.
Οι αρμόδιοι φορείς υποχρεούνται να δημοσιεύουν ετήσια στοιχεία εφαρμογής.
""" * 5

    source_url = "https://www.hellenicparliament.gr/UserFiles/c8827c35/13350000.pdf"
    changed = parliament_scraper.enrich_bill_from_pdf_text(bill, pdf_text, source_url)

    assert changed is True
    assert bill["official_text_verified"] is True
    assert bill["official_text_source_url"] == source_url
    assert bill["summary_short_el"].startswith("Σκοπός του σχεδίου νόμου")
    assert "ΑΙΤΙΟΛΟΓΙΚΗ ΕΚΘΕΣΗ" in bill["summary_long_el"]
    assert "13350000.pdf" in bill["summary_long_el"]


def test_access_denial_cannot_become_verified_official_text():
    bill = {
        "title_el": "Δοκιμαστικό νομοσχέδιο",
        "summary_short_el": "Ασφαλή μεταδεδομένα",
        "summary_long_el": "### Πλήρη έγγραφα\n- [PDF](https://www.hellenicparliament.gr/UserFiles/doc.pdf)",
    }
    denial = (
        "Access Denied. You don't have permission to access this server. "
        "Reference #18.123 errors.edgesuite.net "
    ) * 30

    assert parliament_scraper.enrich_bill_from_pdf_text(
        bill,
        denial,
        "https://www.hellenicparliament.gr/UserFiles/doc.pdf",
    ) is False
    assert bill["summary_short_el"] == "Ασφαλή μεταδεδομένα"
    assert bill.get("official_text_verified") is None


def test_direct_detail_html_is_normalized_before_field_parsing():
    full_title = "Κύρωση διεθνούς συμφωνίας για στρατιωτική συνεργασία"
    html = f"""
    <dl>
      <dt>Τίτλος</dt><dd>{full_title}</dd>
      <dt>Τύπος</dt><dd>Διεθνής Σύμβαση</dd>
      <dt>Υπουργείο</dt><dd>Εθνικής Άμυνας</dd>
    </dl>
    <a href="/UserFiles/c8827c35/13359710.pdf">Αιτιολογική Έκθεση</a>
    """

    markdown = parliament_scraper.detail_html_to_markdown(html)
    detail = parliament_scraper.parse_detail_markdown(markdown)

    assert detail["title_el"] == full_title
    assert detail["type"] == "Διεθνής Σύμβαση"
    assert detail["ministry"] == "Εθνικής Άμυνας"
    assert detail["pdf_links"] == [{
        "label": "Αιτιολογική Έκθεση",
        "url": "https://www.hellenicparliament.gr/UserFiles/c8827c35/13359710.pdf",
    }]


def test_scrape_bounds_expensive_detail_enrichment(monkeypatch):
    bills = [
        {
            "bill_id": f"GR-{index:08d}",
            "law_id": f"{index:08d}-0000-0000-0000-000000000000",
            "title_el": f"Πλήρης τίτλος νομοσχεδίου {index}",
            "url": (
                "https://www.hellenicparliament.gr/Nomothetiko-Ergo/all-laws"
                f"?law_id={index:08d}-0000-0000-0000-000000000000"
            ),
            "submitted_date": f"2026-07-{index + 1:02d}T00:00:00+00:00",
        }
        for index in range(10)
    ]
    enriched: list[str] = []

    def fake_get(url, *, accept="*/*", timeout=30):
        if "api.ashx" in url:
            return parliament_scraper.FetchResult(url=url, status=200, text="{}")
        return parliament_scraper.FetchResult(url=url, status=403, text="Access Denied", error="http_403")

    monkeypatch.setattr(parliament_scraper, "_http_get", fake_get)
    monkeypatch.setattr(parliament_scraper, "parse_api_payload", lambda _payload: bills)
    monkeypatch.setattr(
        parliament_scraper,
        "enrich_bill_from_official_sources",
        lambda bill: enriched.append(bill["bill_id"]),
    )
    monkeypatch.setattr(parliament_scraper.time, "sleep", lambda *_args, **_kwargs: None)

    result, _errors = parliament_scraper.scrape(limit=20)

    assert len(result) == 10
    assert enriched == [bill["bill_id"] for bill in result[:parliament_scraper.MAX_ENRICHED_BILLS]]

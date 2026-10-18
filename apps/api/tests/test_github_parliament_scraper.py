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


def test_runner_never_fetches_parliament_or_third_party_content(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Runner must use the canonical server policy")

    monkeypatch.setattr(parliament_scraper.urllib.request, "urlopen", unexpected)
    for url in (parliament_scraper.PARLIAMENT_API,
                "https://r.jina.ai/https://www.hellenicparliament.gr/law"):
        assert parliament_scraper._http_get(url).error == "runner_source_access_disabled"
    monkeypatch.setattr(parliament_scraper, "_http_get", unexpected)
    assert parliament_scraper.scrape(20) == ([], ["runner_source_access_disabled"])


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


def test_parse_detail_markdown_recovers_compact_jina_fields():
    full = (
        "Κύρωση σύμβασης παραχώρησης του δικαιώματος διοίκησης, διαχείρισης, "
        "λειτουργίας, ανάπτυξης, επέκτασης, συντήρησης και εκμετάλλευσης του "
        "Διεθνούς Αερολιμένα Καλαμάτας «Καπετάν Βασ. Κωνσταντακόπουλος»"
    )
    markdown = (
        "# Αναζήτηση\n\n"
        f"Τίτλος {full}"
        "Τύπος Σχέδιο νόμου "
        "Υπουργείο Εθνικής Οικονομίας και Οικονομικών "
        "Επιτροπή Διαρκής Επιτροπή Οικονομικών Υποθέσεων "
        "Φάση Επεξεργασίας Κατατεθέντα "
        "Ημερ/νια Φάσης επεξεργασίας 17/07/2026 "
        "Το φωτοτυπημένο σ/ν ή π/ν δεν αποτελεί το τελικό κείμενο"
    )

    detail = parliament_scraper.parse_detail_markdown(markdown)

    assert detail["title_el"] == full
    assert detail["type"] == "Σχέδιο νόμου"
    assert detail["ministry"] == "Εθνικής Οικονομίας και Οικονομικών"
    assert detail["phase"] == "Κατατεθέντα"


def test_compact_detail_enrichment_still_rejects_another_bill():
    bill = {
        "title_el": "Κύρωση της Συμφωνίας μεταξύ Ελλάδας και...",
        "type": "Διεθνής Σύμβαση",
        "ministry": "Εθνικής Άμυνας",
        "summary_short_el": "Ασφαλή μεταδεδομένα",
        "summary_long_el": None,
    }
    markdown = (
        "Τίτλος Ρυθμίσεις για την αγορά ενέργειας και την προστασία καταναλωτών"
        "Τύπος Σχέδιο νόμου "
        "Υπουργείο Περιβάλλοντος και Ενέργειας "
        "Επιτροπή Διαρκής Επιτροπή Παραγωγής και Εμπορίου "
        "Φάση Επεξεργασίας Κατατεθέντα "
        "Ημερ/νια Φάσης επεξεργασίας 17/07/2026"
    )

    assert parliament_scraper.enrich_bill_from_detail(bill, markdown) == []
    assert bill["title_el"] == "Κύρωση της Συμφωνίας μεταξύ Ελλάδας και..."
    assert bill["ministry"] == "Εθνικής Άμυνας"


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


def test_runner_import_uses_canonical_server_data(monkeypatch):
    payload = {"source_status": "ok", "dated_count": 1, "bills": [{
        "title_el": "Πλήρης τίτλος νομοσχεδίου",
        "url": "https://www.hellenicparliament.gr/Nomothetiko-Ergo/all-laws?law_id=test-id",
        "submitted_date": "2026-10-17T00:00:00+00:00",
    }]}
    url = "https://api.ekklesia.gr/api/v1/scraper/parliament/freshness?limit=20"
    calls = []

    def fake_get(target, **kwargs):
        calls.append(target)
        return parliament_scraper.FetchResult(target, 200, json.dumps(payload))

    monkeypatch.setattr(parliament_scraper, "_http_get", fake_get)
    result = parliament_scraper.fetch_server_fallback(url, limit=20)
    assert len(result) == 1
    assert calls == [url]

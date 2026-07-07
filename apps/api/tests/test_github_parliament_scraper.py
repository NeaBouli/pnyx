import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "parliament_scraper.py"
spec = importlib.util.spec_from_file_location("parliament_scraper_script", SCRIPT_PATH)
parliament_scraper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = parliament_scraper
spec.loader.exec_module(parliament_scraper)


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

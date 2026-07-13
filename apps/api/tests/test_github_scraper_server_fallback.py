from __future__ import annotations

import importlib.util
import json
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "parliament_scraper.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "scraper.yml"


def _load_scraper_module():
    spec = importlib.util.spec_from_file_location("github_parliament_scraper", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scraper = _load_scraper_module()


class GithubScraperServerFallbackTests(unittest.TestCase):
    def test_http_context_never_disables_certificate_validation(self) -> None:
        context = scraper._verified_ssl_context()

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_server_fallback_normalizes_canonical_bill_shape(self) -> None:
        payload = {
            "source_status": "ok",
            "dated_count": 1,
            "source_latest": "2026-07-13T00:00:00+00:00",
            "bills": [
                {
                    "title_el": "Μέτρα εφαρμογής του Κανονισμού της Ευρωπαϊκής Ένωσης",
                    "url": "https://www.hellenicparliament.gr/example?law_id=e744abc6-3e81-4e56-a4cd-b47f0174f2b1",
                    "law_id": "e744abc6-3e81-4e56-a4cd-b47f0174f2b1",
                    "law_num": None,
                    "type": "Σχέδιο νόμου",
                    "phase": "Επεξεργασία στις Επιτροπές",
                    "date": "2026-07-13T00:00:00+00:00",
                    "submitted_date": None,
                    "pill_el": "Σχέδιο νόμου",
                    "summary_short_el": "Ασφαλής μεταδεδομένη σύνοψη.",
                    "summary_long_el": "### Πλήρη έγγραφα\n- [PDF](https://example.test/official.pdf)",
                }
            ],
        }

        bills = scraper.normalize_server_fallback_payload(payload, limit=20)

        self.assertEqual(len(bills), 1)
        self.assertEqual(bills[0]["bill_id"], "GR-e744abc6")
        self.assertEqual(bills[0]["vote_date"], "2026-07-13T00:00:00+00:00")
        self.assertIsNone(bills[0]["submitted_date"])
        self.assertEqual(bills[0]["summary_short_el"], "Ασφαλής μεταδεδομένη σύνοψη.")
        self.assertIn("official.pdf", bills[0]["summary_long_el"])
        self.assertNotIn("date", bills[0])

    def test_server_fallback_rejects_unproved_source_data(self) -> None:
        payloads = [
            {"source_status": "blocked", "dated_count": 0, "bills": []},
            {"source_status": "ok", "dated_count": 0, "bills": []},
            {"source_status": "ok", "dated_count": [], "bills": []},
            {
                "source_status": "ok",
                "dated_count": 1,
                "bills": [{"title_el": "Undated bill", "law_id": "deadbeef"}],
            },
        ]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                scraper.normalize_server_fallback_payload(payload, limit=20)

    def test_workflow_enables_strict_production_fallback(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("--fallback-url", workflow)
        self.assertIn(
            "https://api.ekklesia.gr/api/v1/scraper/parliament/freshness?limit=20",
            workflow,
        )
        self.assertIn("No dated Parliament bills fetched from any source", workflow)

    def test_main_never_calls_fallback_when_primary_source_succeeds(self) -> None:
        primary_bill = {"bill_id": "GR-primary", "title_el": "Primary source bill"}
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "bills.json"
            argv = [
                str(SCRIPT_PATH),
                "--output",
                str(output),
                "--fallback-url",
                "https://api.example.test/freshness",
            ]
            with (
                mock.patch.object(scraper, "scrape", return_value=([primary_bill], [])),
                mock.patch.object(scraper, "fetch_server_fallback") as fallback,
                mock.patch.object(sys, "argv", argv),
            ):
                exit_code = scraper.main()

            self.assertEqual(exit_code, 0)
            fallback.assert_not_called()
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [primary_bill])

    def test_main_remains_fail_closed_when_fallback_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "bills.json"
            argv = [
                str(SCRIPT_PATH),
                "--output",
                str(output),
                "--fallback-url",
                "https://api.example.test/freshness",
            ]
            with (
                mock.patch.object(scraper, "scrape", return_value=([], ["primary blocked"])),
                mock.patch.object(
                    scraper,
                    "fetch_server_fallback",
                    side_effect=ValueError("source not proved"),
                ),
                mock.patch.object(sys, "argv", argv),
            ):
                exit_code = scraper.main()

            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()

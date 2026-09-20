#!/usr/bin/env python3
"""Focused tests for scripts/redesign/r0_inventory.py.

All fail-closed fixture tests run in temporary directories; the real tree is
never modified. Run with: python3 -m unittest scripts/redesign/test_r0_inventory.py
(also runnable directly: python3 scripts/redesign/test_r0_inventory.py)
"""

from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path

import r0_inventory  # noqa: E402  (same-directory import)

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKED_INVENTORY = REPO_ROOT / "docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json"
CHECKED_REPORT = REPO_ROOT / "docs/planning/r0/R0_REPORT.md"

MINIMAL_PAGE = """<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Fixture</title>
<meta name="description" content="fixture page">
</head>
<body>
<h1 id="top">Fixture</h1>
<p data-el="Γεια" data-en="Hello">Γεια</p>
<a href="#top">top</a>
</body>
</html>
"""

EMPTY_KNOWN_DEFECTS = {"schema": "r0-known-baseline-defects/1", "note": "fixture", "duplicate_ids": []}


@contextlib.contextmanager
def fixture_tree(extra_pages: dict[str, str] | None = None, allowlist_extra: list[str] | None = None,
                 allowlist_drop: list[str] | None = None, known_defects: dict | None = None):
    """Patch r0_inventory module paths onto a temporary fixture tree."""
    pages = {"docs/a.html": MINIMAL_PAGE, "docs/sub/b.html": MINIMAL_PAGE.replace("<h1 id=\"top\">", "<h1 id=\"beta\">")}
    if extra_pages:
        pages.update(extra_pages)
    allowlist = sorted(pages)
    if allowlist_extra:
        allowlist = sorted(allowlist + allowlist_extra)
    if allowlist_drop:
        allowlist = [p for p in allowlist if p not in allowlist_drop]

    saved = {name: getattr(r0_inventory, name) for name in (
        "REPO_ROOT", "DOCS_DIR", "R0_DIR", "ALLOWLIST_FILE", "KNOWN_DEFECTS_FILE", "INVENTORY_FILE", "REPORT_FILE")}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()  # resolve macOS /var symlink so resolved candidates stay relative to it
        docs = root / "docs"
        for rel, content in pages.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        r0 = docs / "planning" / "r0"
        r0.mkdir(parents=True)
        (r0 / "PUBLIC_HTML_ALLOWLIST.txt").write_text("\n".join(allowlist) + "\n", encoding="utf-8")
        (r0 / "R0_KNOWN_BASELINE_DEFECTS.json").write_text(
            json.dumps(known_defects if known_defects is not None else EMPTY_KNOWN_DEFECTS), encoding="utf-8")

        r0_inventory.REPO_ROOT = root
        r0_inventory.DOCS_DIR = docs
        r0_inventory.R0_DIR = r0
        r0_inventory.ALLOWLIST_FILE = r0 / "PUBLIC_HTML_ALLOWLIST.txt"
        r0_inventory.KNOWN_DEFECTS_FILE = r0 / "R0_KNOWN_BASELINE_DEFECTS.json"
        r0_inventory.INVENTORY_FILE = r0 / "R0_DOCS_SURFACE_INVENTORY.json"
        r0_inventory.REPORT_FILE = r0 / "R0_REPORT.md"
        try:
            yield root
        finally:
            for name, value in saved.items():
                setattr(r0_inventory, name, value)


class RealTreeTest(unittest.TestCase):
    def test_real_tree_reproduces_checked_in_artifacts(self) -> None:
        first_inv, first_report = r0_inventory.generate()
        second_inv, second_report = r0_inventory.generate()
        self.assertEqual(first_inv, second_inv, "regeneration is not deterministic")
        self.assertEqual(first_report, second_report, "report regeneration is not deterministic")
        self.assertTrue(CHECKED_INVENTORY.is_file(), "checked-in inventory missing")
        self.assertTrue(CHECKED_REPORT.is_file(), "checked-in report missing")
        checked_inv = CHECKED_INVENTORY.read_bytes()
        checked_report = CHECKED_REPORT.read_bytes()
        if first_inv == checked_inv:
            self.assertEqual(first_report, checked_report, "checked-in report is stale")
            return

        # R0 is the frozen pre-redesign baseline. The gated R2 landing and R3
        # wiki pilot may diverge; their full semantic parity is enforced by the
        # phase validators. Normalize those pages back to R0 and require every
        # other page plus both artifacts to remain exact.
        current = json.loads(first_inv)
        checked = json.loads(checked_inv)
        current_by_path = {page["path"]: page for page in current["pages"]}
        checked_by_path = {page["path"]: page for page in checked["pages"]}
        differing = sorted(
            path for path in checked_by_path
            if current_by_path.get(path) != checked_by_path[path]
        )
        self.assertEqual(
            ["docs/index.html", "docs/wiki/index.html"],
            differing,
            "only the gated R2 landing and R3 wiki pilot may differ from R0",
        )

        landing = (REPO_ROOT / "docs/index.html").read_text(encoding="utf-8")
        for href in (
            "assets/redesign-v2/tokens.css",
            "assets/redesign-v2/foundation.css",
            "assets/redesign-v2/r2-landing.css",
        ):
            self.assertIn(f'href="{href}"', landing, "unexpected landing drift outside the R2 gate")

        wiki_pilot = (REPO_ROOT / "docs/wiki/index.html").read_text(encoding="utf-8")
        for href in (
            "../assets/redesign-v2/tokens.css",
            "../assets/redesign-v2/foundation.css",
            "../assets/redesign-v2/r3-wiki.css",
        ):
            self.assertIn(f'href="{href}"', wiki_pilot, "unexpected wiki drift outside the R3 gate")

        normalized_pages = [
            checked_by_path[page["path"]]
            if page["path"] in {"docs/index.html", "docs/wiki/index.html"}
            else page
            for page in current["pages"]
        ]
        normalized = r0_inventory.build_inventory(normalized_pages)
        self.assertEqual(r0_inventory.serialize_inventory(normalized), checked_inv)
        self.assertEqual(r0_inventory.build_report(normalized).encode("utf-8"), checked_report)

    def test_real_tree_exactly_35_allowlisted_pages(self) -> None:
        allowlist = r0_inventory.read_allowlist()
        self.assertEqual(35, len(allowlist), "allowlist must contain exactly 35 paths")
        self.assertEqual([], r0_inventory.verify_surface(allowlist))
        inventory = json.loads(CHECKED_INVENTORY.read_text(encoding="utf-8"))
        self.assertEqual(35, inventory["page_count"])
        self.assertEqual(allowlist, [p["path"] for p in inventory["pages"]])

    def test_real_tree_bilingual_values_preserved(self) -> None:
        inventory = json.loads(CHECKED_INVENTORY.read_text(encoding="utf-8"))
        index = next(p for p in inventory["pages"] if p["path"] == "docs/index.html")
        self.assertGreater(index["bilingual"]["counts"]["pairs"], 0)
        sample = index["bilingual"]["pairs"][0]
        self.assertIn("data_el", sample)
        self.assertIn("data_en", sample)
        self.assertTrue(sample["data_el"], "data-el must be captured, not normalized away")

    def test_markup_contracts_and_inline_styles_are_inventoried(self) -> None:
        page = MINIMAL_PAGE.replace(
            '<h1 id="top">',
            '<h1 id="top" style="width:640px" data-api="/api/v1/example">',
        )
        with fixture_tree(extra_pages={"docs/contract.html": page}):
            inventory_bytes, _ = r0_inventory.generate()
            inventory = json.loads(inventory_bytes)
            contract = next(p for p in inventory["pages"] if p["path"] == "docs/contract.html")
            self.assertEqual(640, contract["responsive"]["fixed_px_widths_over_360"][0])
            self.assertEqual("/api/v1/example", contract["api_contracts"]["relative_paths"][0])
            self.assertEqual("width:640px", contract["styles"]["inline_attributes"][0]["value"])
            self.assertIn("resources", contract["hashes"])


class FailClosedTest(unittest.TestCase):
    def test_extra_html_file_fails(self) -> None:
        # The extra file exists in the tree but is deliberately not allowlisted.
        with fixture_tree(extra_pages={"docs/sneaky.html": MINIMAL_PAGE}, allowlist_drop=["docs/sneaky.html"]):
            with self.assertRaises(SystemExit) as ctx:
                r0_inventory.generate()
            self.assertIn("extra public HTML file", str(ctx.exception))

    def test_missing_html_file_fails(self) -> None:
        with fixture_tree(allowlist_extra=["docs/ghost.html"]):
            with self.assertRaises(SystemExit) as ctx:
                r0_inventory.generate()
            self.assertIn("allowlisted file missing", str(ctx.exception))

    def test_malformed_json_ld_fails(self) -> None:
        bad = MINIMAL_PAGE.replace(
            "</head>",
            '<script type="application/ld+json">{"@type": "WebPage",}</script>\n</head>')
        with fixture_tree(extra_pages={"docs/bad.html": bad}):
            with self.assertRaises(SystemExit) as ctx:
                r0_inventory.generate()
            self.assertIn("malformed JSON-LD", str(ctx.exception))

    def test_duplicate_id_fails(self) -> None:
        dup = MINIMAL_PAGE.replace("</body>", '<p id="top">again</p>\n</body>')
        with fixture_tree(extra_pages={"docs/dup.html": dup}):
            with self.assertRaises(SystemExit) as ctx:
                r0_inventory.generate()
            self.assertIn("duplicate id", str(ctx.exception))

    def test_known_defect_tolerated_exactly(self) -> None:
        dup = MINIMAL_PAGE.replace("</body>", '<p id="top">again</p>\n</body>')
        known = {"schema": 1, "duplicate_ids": [{"path": "docs/dup.html", "id": "top", "occurrences": 2}]}
        with fixture_tree(extra_pages={"docs/dup.html": dup}, known_defects=known):
            inventory_bytes, report_bytes = r0_inventory.generate()
            self.assertIn(b"docs/dup.html", inventory_bytes)
            self.assertIn(b"pre-existing baseline defects", report_bytes)

    def test_stale_known_defect_record_fails(self) -> None:
        known = {"schema": 1, "duplicate_ids": [{"path": "docs/a.html", "id": "gone", "occurrences": 2}]}
        with fixture_tree(known_defects=known):
            with self.assertRaises(SystemExit) as ctx:
                r0_inventory.generate()
            self.assertIn("no longer matches", str(ctx.exception))

    def test_fixture_generation_is_deterministic(self) -> None:
        with fixture_tree():
            first = r0_inventory.generate()
            second = r0_inventory.generate()
            self.assertEqual(first, second)


class RelativeFileResolutionTest(unittest.TestCase):
    def test_nested_page_relative_stylesheet_resolves_within_docs(self) -> None:
        # page_rel already carries the docs/ prefix, so relative-file
        # resolution must anchor at the repo root: docs/tickets/index.html +
        # style.css resolves to docs/tickets/style.css, not docs/docs/...
        page = MINIMAL_PAGE.replace("</head>", '<link rel="stylesheet" href="style.css">\n</head>')
        css = "@media (max-width: 360px) { .x { width: 320px; } }\n"
        with fixture_tree(extra_pages={"docs/tickets/index.html": page}) as root:
            (root / "docs/tickets/style.css").write_text(css, encoding="utf-8")
            inventory_bytes, _ = r0_inventory.generate()
            inventory = json.loads(inventory_bytes)
            tickets = next(p for p in inventory["pages"] if p["path"] == "docs/tickets/index.html")
            entry = tickets["styles"]["external"][0]
            self.assertTrue(entry["resolved"])
            self.assertEqual("docs/tickets/style.css", entry["repo_path"])
            self.assertIn("@media (max-width: 360px)", tickets["responsive"]["media_queries"])

    def test_relative_stylesheet_traversal_outside_docs_is_rejected(self) -> None:
        page = MINIMAL_PAGE.replace("</head>", '<link rel="stylesheet" href="../../outside.css">\n</head>')
        with fixture_tree(extra_pages={"docs/tickets/index.html": page}) as root:
            (root / "outside.css").write_text("body { color: red; }\n", encoding="utf-8")
            inventory_bytes, _ = r0_inventory.generate()
            inventory = json.loads(inventory_bytes)
            tickets = next(p for p in inventory["pages"] if p["path"] == "docs/tickets/index.html")
            entry = tickets["styles"]["external"][0]
            self.assertFalse(entry["resolved"])
            self.assertEqual("escapes-docs", entry["reason"])

    def test_root_relative_stylesheet_behavior_unchanged(self) -> None:
        page = MINIMAL_PAGE.replace("</head>", '<link rel="stylesheet" href="/shared.css">\n</head>')
        with fixture_tree(extra_pages={"docs/tickets/index.html": page}) as root:
            (root / "docs/shared.css").write_text("body { margin: 0; }\n", encoding="utf-8")
            inventory_bytes, _ = r0_inventory.generate()
            inventory = json.loads(inventory_bytes)
            tickets = next(p for p in inventory["pages"] if p["path"] == "docs/tickets/index.html")
            entry = tickets["styles"]["external"][0]
            self.assertTrue(entry["resolved"])
            self.assertEqual("docs/shared.css", entry["repo_path"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Focused tests for scripts/redesign/r2_landing_check.py.

The real-tree test verifies the current branch state is clean.
Fixture tests exercise every fail-closed check in isolation using
temporary directories; the real docs/ tree is never modified.

Run with:
    python3 -m unittest scripts/redesign/test_r2_landing_check.py
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import r2_landing_check

# ---------------------------------------------------------------------------
# Minimal fixture content — passes all checks
# ---------------------------------------------------------------------------

# A minimal HTML that satisfies all structural checks.
# Bilingual pairs, JSON-LD, forms, storage and interactions are deliberately
# absent in these unit fixtures; those are checked against the real R0
# inventory only in the real-tree test.
MINIMAL_HTML = """<!DOCTYPE html>
<html lang="el" data-lang="el">
<head>
<meta charset="UTF-8"/>
<link rel="stylesheet" href="assets/redesign-v2/tokens.css"/>
<link rel="stylesheet" href="assets/redesign-v2/foundation.css"/>
<link rel="stylesheet" href="assets/redesign-v2/r2-landing.css"/>
</head>
<body>
<a href="#main" class="pnx2-skip">Skip</a>
<nav class="pnx2-header"><a href="#">Home</a></nav>
<section id="main" class="landing-hero">main</section>
<footer class="pnx2-footer"><p>&copy; 2026</p></footer>
</body>
</html>
"""

# Minimal passing tokens CSS (no prohibited patterns)
MINIMAL_TOKENS_CSS = """:root {
  --pnx2-ink: #0f172a;
  --pnx2-accent: #2563eb;
  --pnx2-bg: #ffffff;
  --pnx2-bg-tinted: #f8fafc;
  --pnx2-radius: 0;
  --pnx2-target-min: 44px;
}
"""

# Minimal passing foundation CSS
MINIMAL_FOUNDATION_CSS = """*,*::before,*::after { box-sizing: border-box; }
a:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.pnx2-skip { position: absolute; top: -48px; }
.pnx2-header { position: sticky; top: 0; border-bottom: 2px solid #0f172a; }
.pnx2-footer { background: #0f172a; color: #cbd5e1; }
"""

# Minimal passing r2-landing CSS (shadow removal via none is allowed)
MINIMAL_R2_CSS = """/* r2 overrides */
:root { --radius: 0; --shadow: none; }
*,*::before,*::after { border-radius: 0 !important; box-shadow: none !important; }
nav.pnx2-header { background: #fff !important; backdrop-filter: none !important; }
.landing-hero { background: #f8fafc !important; }
footer { background: #0f172a !important; }
"""


def _write_css_files(docs_dir: Path) -> None:
    css_dir = docs_dir / "assets/redesign-v2"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "tokens.css").write_text(MINIMAL_TOKENS_CSS, encoding="utf-8")
    (css_dir / "foundation.css").write_text(MINIMAL_FOUNDATION_CSS, encoding="utf-8")
    (css_dir / "r2-landing.css").write_text(MINIMAL_R2_CSS, encoding="utf-8")


# ---------------------------------------------------------------------------
# Real-tree test
# ---------------------------------------------------------------------------

class RealTreeTest(unittest.TestCase):
    def test_real_tree_passes(self) -> None:
        """The current branch (feat/redesign-r2-landing-20260920) must be clean."""
        violations = r2_landing_check.check_r2()
        self.assertEqual(
            [],
            violations,
            f"R2 check failed on real tree:\n" + "\n".join(violations),
        )


class PreservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        inv = json.loads(r2_landing_check.R0_INVENTORY_FILE.read_text(encoding="utf-8"))
        cls.baseline = next(page for page in inv["pages"] if page["path"] == "docs/index.html")
        cls.current = r2_landing_check.r0_inventory.inventory_page("docs/index.html")

    def test_real_parsed_contract_has_only_allowed_r2_deltas(self) -> None:
        self.assertEqual(
            [],
            r2_landing_check.check_index_preservation(self.baseline, self.current),
        )

    def test_api_contract_change_fails_closed(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["api_contracts"]["absolute_urls"].pop()
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("api_contracts" in item for item in violations))

    def test_new_external_host_fails_closed(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["external_hosts"].append("example.invalid")
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("external_hosts" in item for item in violations))

    def test_lost_bilingual_pair_fails_closed(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["bilingual"]["pairs"].pop(0)
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("bilingual pairs" in item for item in violations))


# ---------------------------------------------------------------------------
# check_structural — isolated HTML snippet tests
# ---------------------------------------------------------------------------

class StructuralTest(unittest.TestCase):

    def test_minimal_passing_html(self) -> None:
        self.assertEqual([], r2_landing_check.check_structural(MINIMAL_HTML))

    def test_missing_skip_class(self) -> None:
        html = MINIMAL_HTML.replace('class="pnx2-skip"', 'class="skip-link"')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("pnx2-skip" in s for s in v))

    def test_missing_skip_href(self) -> None:
        html = MINIMAL_HTML.replace('href="#main"', 'href="#content"')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("href=#main" in s for s in v))

    def test_missing_id_main(self) -> None:
        html = MINIMAL_HTML.replace('id="main"', 'id="top"')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("id=main" in s for s in v))

    def test_missing_pnx2_header_on_nav(self) -> None:
        html = MINIMAL_HTML.replace('<nav class="pnx2-header"', '<nav')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("pnx2-header" in s for s in v))

    def test_missing_pnx2_footer_on_footer(self) -> None:
        html = MINIMAL_HTML.replace('class="pnx2-footer"', 'class="site-footer"')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("pnx2-footer" in s for s in v))

    def test_missing_tokens_css_link(self) -> None:
        html = MINIMAL_HTML.replace(
            '<link rel="stylesheet" href="assets/redesign-v2/tokens.css"/>\n', ""
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("tokens.css" in s for s in v))

    def test_missing_foundation_css_link(self) -> None:
        html = MINIMAL_HTML.replace(
            '<link rel="stylesheet" href="assets/redesign-v2/foundation.css"/>\n', ""
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("foundation.css" in s for s in v))

    def test_missing_r2_landing_css_link(self) -> None:
        html = MINIMAL_HTML.replace(
            '<link rel="stylesheet" href="assets/redesign-v2/r2-landing.css"/>\n', ""
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("r2-landing.css" in s for s in v))


# ---------------------------------------------------------------------------
# check_css_files — isolated CSS fixture tests
# ---------------------------------------------------------------------------

class CssFilesTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_and_check(self, overrides: dict[str, str]) -> list[str]:
        _write_css_files(self.tmp)
        css_dir = self.tmp / "assets/redesign-v2"
        for name, content in overrides.items():
            (css_dir / name).write_text(content, encoding="utf-8")
        return r2_landing_check.check_css_files(self.tmp)

    def test_minimal_css_passes(self) -> None:
        _write_css_files(self.tmp)
        self.assertEqual([], r2_landing_check.check_css_files(self.tmp))

    def test_missing_tokens_css_fails(self) -> None:
        _write_css_files(self.tmp)
        (self.tmp / "assets/redesign-v2/tokens.css").unlink()
        v = r2_landing_check.check_css_files(self.tmp)
        self.assertTrue(any("tokens.css" in s for s in v))

    def test_missing_foundation_css_fails(self) -> None:
        _write_css_files(self.tmp)
        (self.tmp / "assets/redesign-v2/foundation.css").unlink()
        v = r2_landing_check.check_css_files(self.tmp)
        self.assertTrue(any("foundation.css" in s for s in v))

    def test_missing_r2_landing_css_fails(self) -> None:
        _write_css_files(self.tmp)
        (self.tmp / "assets/redesign-v2/r2-landing.css").unlink()
        v = r2_landing_check.check_css_files(self.tmp)
        self.assertTrue(any("r2-landing.css" in s for s in v))

    def test_gradient_in_r2_css_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\n.hero { background: linear-gradient(#fff,#eee); }\n"
        })
        self.assertTrue(any("gradient" in s for s in v))

    def test_non_none_box_shadow_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\n.card { box-shadow: 0 2px 8px #000; }\n"
        })
        self.assertTrue(any("box-shadow" in s for s in v))

    def test_box_shadow_none_allowed(self) -> None:
        # box-shadow: none is a removal rule and must NOT trigger a violation
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\n.x { box-shadow: none; }\n"
        })
        self.assertEqual([], v)

    def test_negative_letter_spacing_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\nh1 { letter-spacing: -0.02em; }\n"
        })
        self.assertTrue(any("letter-spacing" in s for s in v))

    def test_viewport_scaled_font_size_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\nh1 { font-size: 5vw; }\n"
        })
        self.assertTrue(any("viewport-scaled" in s for s in v))

    def test_external_import_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + '\n@import url("https://fonts.example.com/x.css");\n'
        })
        self.assertTrue(any("http" in s for s in v))

    def test_gradient_in_tokens_css_fails(self) -> None:
        v = self._write_and_check({
            "tokens.css": MINIMAL_TOKENS_CSS + "\n:root { --bg: radial-gradient(#fff, #eee); }\n"
        })
        self.assertTrue(any("gradient" in s for s in v))


# ---------------------------------------------------------------------------
# check_parity — isolated parity tests using fake inventory
# ---------------------------------------------------------------------------

class ParityTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        # Create a minimal docs-like structure for two pages
        docs = self.tmp / "docs"
        docs.mkdir()
        # Write a dummy page
        (docs / "page_a.html").write_text("content-a", encoding="utf-8")
        # Build a fake inventory with the correct sha256 for page_a
        import hashlib
        sha = hashlib.sha256(b"content-a").hexdigest()
        self.fake_inv = {
            "pages": [
                {"path": "docs/index.html", "sha256": "any"},
                {"path": "docs/page_a.html", "sha256": sha},
            ]
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_matching_sha256_passes(self) -> None:
        v = r2_landing_check.check_parity(self.fake_inv, self.tmp)
        self.assertEqual([], v)

    def test_modified_non_index_page_fails(self) -> None:
        # Modify page_a — sha256 no longer matches
        (self.tmp / "docs/page_a.html").write_text("modified", encoding="utf-8")
        v = r2_landing_check.check_parity(self.fake_inv, self.tmp)
        self.assertTrue(any("docs/page_a.html" in s and "sha256 changed" in s for s in v))

    def test_missing_non_index_page_fails(self) -> None:
        (self.tmp / "docs/page_a.html").unlink()
        v = r2_landing_check.check_parity(self.fake_inv, self.tmp)
        self.assertTrue(any("docs/page_a.html" in s and "missing" in s for s in v))

    def test_index_html_sha256_not_checked(self) -> None:
        # Modifying docs/index.html sha256 in the inventory should have no effect
        # on parity (docs/index.html is excluded from parity check)
        inv = {"pages": [{"path": "docs/index.html", "sha256": "WRONG"}]}
        v = r2_landing_check.check_parity(inv, self.tmp)
        self.assertEqual([], v)


if __name__ == "__main__":
    unittest.main()

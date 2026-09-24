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
import hashlib
import json
import re
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
<link rel="stylesheet" href="assets/redesign-v2/r5-landing-fidelity.css"/>
</head>
<body>
<a href="#main" class="pnx2-skip">Skip</a>
<nav class="pnx2-header"><div class="pnx2-header-frame"><a href="#main">Brand</a><a href="#main">Platform</a><a href="#votes">Votes</a><a href="#roadmap">Roadmap</a><a href="#wiki-section">Docs</a><a href="wiki/">Wiki</a><a href="community.html">Community</a><a href="#download">Download</a></div></nav>
<main id="main"><section class="landing-hero"><div class="pnx2-live-panel"><b id="heroParliamentDecision"></b><b id="heroLiveStatus"></b><b id="heroCitizenDecision"></b><b id="heroCitizenMeta"></b><b id="heroTier1"></b><b id="heroTier2"></b><b id="heroTier3"></b></div></section><section class="pnx2-democracy-data"></section><section class="pnx2-history-band"><h2 id="historyTitle">History</h2></section><section id="votes"></section><section id="roadmap"></section><section id="download"></section></main>
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

MINIMAL_R5_CSS = """/* owner handoff fidelity */
.pnx2-header-frame { display: flex; }
.pnx2-live-panel { border-bottom: 2px solid #0f172a; }
.pnx2-history-band { background: #2563eb; }
"""


def _write_css_files(docs_dir: Path) -> None:
    css_dir = docs_dir / "assets/redesign-v2"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "tokens.css").write_text(MINIMAL_TOKENS_CSS, encoding="utf-8")
    (css_dir / "foundation.css").write_text(MINIMAL_FOUNDATION_CSS, encoding="utf-8")
    (css_dir / "r2-landing.css").write_text(MINIMAL_R2_CSS, encoding="utf-8")
    (css_dir / "r5-landing-fidelity.css").write_text(MINIMAL_R5_CSS, encoding="utf-8")


# ---------------------------------------------------------------------------
# Real-tree test
# ---------------------------------------------------------------------------

class RealTreeTest(unittest.TestCase):
    def test_real_tree_r2_contract_still_passes(self) -> None:
        """Later redesign phases must preserve the accepted R2 contracts."""
        inv = json.loads(r2_landing_check.R0_INVENTORY_FILE.read_text(encoding="utf-8"))
        baseline = next(page for page in inv["pages"] if page["path"] == "docs/index.html")
        current = r2_landing_check.r0_inventory.inventory_page("docs/index.html")
        html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        violations = []
        violations.extend(r2_landing_check.check_index_preservation(baseline, current))
        violations.extend(r2_landing_check.check_structural(html))
        violations.extend(r2_landing_check.check_css_files(r2_landing_check.DOCS_DIR))
        self.assertEqual(
            [],
            violations,
            f"R2 contract check failed on real tree:\n" + "\n".join(violations),
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
        target = next(
            (item.get("data_el", ""), item.get("data_en", ""))
            for item in self.baseline["bilingual"]["pairs"]
            if (item.get("data_el", ""), item.get("data_en", ""))
            not in r2_landing_check.REMOVABLE_HEADER_PAIRS
        )
        changed["bilingual"]["pairs"] = [
            item for item in changed["bilingual"]["pairs"]
            if (item.get("data_el", ""), item.get("data_en", "")) != target
        ]
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("bilingual content" in item for item in violations))

    def test_header_pair_body_occurrence_remains_protected(self) -> None:
        changed = copy.deepcopy(self.current)
        target = ("Πώς λειτουργεί", "How it works")
        changed["bilingual"]["pairs"] = [
            item for item in changed["bilingual"]["pairs"]
            if (item.get("data_el", ""), item.get("data_en", "")) != target
        ]
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("bilingual content" in item for item in violations))

    def test_handler_swap_between_distinct_links_fails_closed(self) -> None:
        """Swapping inline event handlers between links with different hrefs
        must be detected even though DOM reordering is tolerated (T-358)."""
        changed = copy.deepcopy(self.current)
        handlers = changed["interactions"]["element_handlers"]
        # Find two link handlers with distinct hrefs
        link_indices = [
            i for i, h in enumerate(handlers)
            if h["tag"] == "a" and "href" in h
        ]
        self.assertGreaterEqual(len(link_indices), 2, "Need at least two link handlers")
        i, j = link_indices[0], link_indices[1]
        # Swap the handler values while keeping the element identity
        handlers[i]["value"], handlers[j]["value"] = handlers[j]["value"], handlers[i]["value"]
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(
            any("element_handlers" in item for item in violations),
            "Handler swap between distinct links must trigger a violation",
        )

    def test_dom_reorder_without_handler_swap_passes(self) -> None:
        """Reordering DOM sections (and thus handler sequence) must not
        trigger a violation when no handler is reassigned (T-358)."""
        changed = copy.deepcopy(self.current)
        handlers = changed["interactions"]["element_handlers"]
        # Reverse the handler list — simulates complete DOM reorder
        changed["interactions"]["element_handlers"] = list(reversed(handlers))
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertFalse(
            any("element_handlers" in item for item in violations),
            "Pure DOM reorder must not trigger handler violation",
        )

    def test_inline_script_change_fails_closed(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["scripts"]["inline"][0]["sha256"] = "0" * 64
        violations = r2_landing_check.check_index_preservation(self.baseline, changed)
        self.assertTrue(any("inline script fingerprints" in item for item in violations))


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
        self.assertTrue(any("targeting #main" in s for s in v))

    def test_missing_id_main(self) -> None:
        html = MINIMAL_HTML.replace('<main id="main"', '<main id="top"')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("main#main" in s for s in v))

    def test_main_id_on_unrelated_element_fails(self) -> None:
        html = MINIMAL_HTML.replace('<main id="main">', '<main><div id="main"></div>')
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("main#main" in s for s in v))

    def test_hero_outside_main_fails(self) -> None:
        html = MINIMAL_HTML.replace(
            '<main id="main"><section class="landing-hero">',
            '<section class="landing-hero"></section><main id="main"><section>',
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("landing hero" in s for s in v))

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

    def test_missing_r5_fidelity_css_link(self) -> None:
        html = MINIMAL_HTML.replace(
            '<link rel="stylesheet" href="assets/redesign-v2/r5-landing-fidelity.css"/>\n', ""
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("r5-landing-fidelity.css" in s for s in v))

    def test_commented_structural_markup_does_not_pass(self) -> None:
        html = MINIMAL_HTML.replace(
            '<nav class="pnx2-header">',
            '<!-- <nav class="pnx2-header"></nav> --><nav>',
        )
        v = r2_landing_check.check_structural(html)
        self.assertTrue(any("nav.pnx2-header" in s for s in v))


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

    def test_missing_r5_fidelity_css_fails(self) -> None:
        _write_css_files(self.tmp)
        (self.tmp / "assets/redesign-v2/r5-landing-fidelity.css").unlink()
        v = r2_landing_check.check_css_files(self.tmp)
        self.assertTrue(any("r5-landing-fidelity.css" in s for s in v))

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

    def test_viewport_scaled_font_size_in_calc_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\nh1 { font-size: calc(1rem + 2vw); }\n"
        })
        self.assertTrue(any("viewport-scaled" in s for s in v))

    def test_viewport_scaled_font_size_in_clamp_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + "\nh1 { font-size: clamp(2rem, 5vw, 4rem); }\n"
        })
        self.assertTrue(any("viewport-scaled" in s for s in v))

    def test_external_import_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + '\n@import url("https://fonts.example.com/x.css");\n'
        })
        self.assertTrue(any("external @import" in s for s in v))

    def test_quoted_external_import_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + '\n@import "https://fonts.example.com/x.css";\n'
        })
        self.assertTrue(any("external @import" in s for s in v))

    def test_protocol_relative_import_fails(self) -> None:
        v = self._write_and_check({
            "r2-landing.css": MINIMAL_R2_CSS + '\n@import url("//fonts.example.com/x.css");\n'
        })
        self.assertTrue(any("external @import" in s for s in v))

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


# ---------------------------------------------------------------------------
# HistorySectionTest — Acropolis/Pnyx silhouette regression
# ---------------------------------------------------------------------------

class HistorySectionTest(unittest.TestCase):
    """Verify the blue historical band uses the correct local Acropolis asset."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        from html.parser import HTMLParser

        class _ImgCollector(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.in_history = False
                self.history_imgs: list[dict] = []

            def handle_starttag(self, tag: str, attrs: list) -> None:
                ad = dict(attrs)
                if tag == "section" and "pnx2-history-band" in ad.get("class", ""):
                    self.in_history = True
                if self.in_history and tag == "img":
                    self.history_imgs.append(ad)

            def handle_endtag(self, tag: str) -> None:
                if tag == "section" and self.in_history:
                    self.in_history = False

        p = _ImgCollector()
        p.feed(cls.html)
        cls.history_imgs = p.history_imgs

    def test_history_band_has_exactly_one_image(self) -> None:
        self.assertEqual(1, len(self.history_imgs),
                         f"Expected 1 img in .pnx2-history-band, found {len(self.history_imgs)}")

    def test_history_image_src_is_acropolis_asset(self) -> None:
        img = self.history_imgs[0]
        self.assertEqual(
            "assets/redesign-v2/pnyx-acropolis-white.png",
            img.get("src"),
            "History band img src must point to pnyx-acropolis-white.png",
        )

    def test_history_image_not_app_logo(self) -> None:
        img = self.history_imgs[0]
        self.assertNotEqual("pnx.png", img.get("src"),
                            "History band must not use the app logo pnx.png")

    def test_history_image_is_aria_hidden(self) -> None:
        img = self.history_imgs[0]
        self.assertEqual("true", img.get("aria-hidden"),
                         "Decorative Acropolis image must carry aria-hidden='true'")

    def test_history_image_has_no_loading_lazy(self) -> None:
        img = self.history_imgs[0]
        self.assertNotEqual("lazy", img.get("loading"),
                            "Decorative Acropolis image must not use loading='lazy'")

    def test_acropolis_asset_file_exists_on_disk(self) -> None:
        asset = r2_landing_check.DOCS_DIR / "assets/redesign-v2/pnyx-acropolis-white.png"
        self.assertTrue(asset.is_file(),
                        f"Asset not found on disk: {asset}")

    def test_acropolis_asset_matches_owner_handoff(self) -> None:
        asset = r2_landing_check.DOCS_DIR / "assets/redesign-v2/pnyx-acropolis-white.png"
        self.assertEqual(
            "5e2459bf00b0322640aa3a0814187a1008406bd31e5981b9d691409a41b2623b",
            hashlib.sha256(asset.read_bytes()).hexdigest(),
        )

    def test_history_band_has_handoff_separator(self) -> None:
        self.assertIn('class="pnx2-history-separator"', self.html)


# ---------------------------------------------------------------------------
# FailClosedResultsTest — live-result guard regression
# ---------------------------------------------------------------------------

class FailClosedResultsTest(unittest.TestCase):
    """Verify the inline JS enforces the fail-closed total_votes >= 1 guard."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        cls.css = (
            r2_landing_check.DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"
        ).read_text(encoding="utf-8")

    def function_body(self, name: str, next_name: str) -> str:
        start = self.html.index(f"function {name}")
        end = self.html.index(f"function {next_name}", start)
        return self.html[start:end]

    def css_rule_bodies(self, selector: str) -> list[str]:
        """Return declaration blocks for a selector, including nested at-rules."""
        source = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)
        pattern = rf"(?:^|}})[^{{}}]*{re.escape(selector)}[^{{}}]*\{{([^{{}}]*)\}}"
        return re.findall(pattern, source, flags=re.DOTALL | re.MULTILINE)

    def test_fail_closed_guard_present(self) -> None:
        """The guard that returns early when total_votes < 1 must be in the script."""
        body = self.function_body("fillResultData", "runCycle")
        self.assertIn(
            "Number(live.total_votes)<1",
            body,
            "Fail-closed guard 'Number(live.total_votes)<1' missing from inline script",
        )

    def test_hero_result_elements_have_dash_initial_state(self) -> None:
        """heroParliamentDecision must start with the empty-state dash, not live data."""
        import re
        # Match <b id="heroParliamentDecision">...</b> and check content is a dash
        m = re.search(
            r'<b\s+id="heroParliamentDecision">([^<]*)</b>',
            self.html,
        )
        self.assertIsNotNone(m, "Element heroParliamentDecision not found in HTML")
        content = m.group(1).strip()
        self.assertIn(content, ("—", "–", "-", ""),
                      f"heroParliamentDecision should start empty/dash, got: {content!r}")

    def test_clear_result_data_function_present(self) -> None:
        """clearResultData() must exist to reset state when no valid result."""
        self.assertIn(
            "clearResultData",
            self.html,
            "clearResultData function missing from inline script",
        )

    def test_latest_citizen_result_does_not_write_hero_comparison(self) -> None:
        body = self.function_body("renderLiveResult", "fillResultData")
        self.assertNotIn("heroParliamentDecision", body)
        self.assertNotIn("heroLiveStatus", body)
        self.assertNotIn("heroCitizenDecision", body)
        self.assertNotIn("heroCitizenMeta", body)
        self.assertIn("resultParticipation", body)
        self.assertIn("total/electorate*100", body)
        self.assertIn("Κατάσταση νομοσχεδίου", body)

    def test_citizen_participation_has_dedicated_target(self) -> None:
        self.assertIn('id="resultParticipation"', self.html)
        self.assertIn("Συμμετοχή στην πλατφόρμα", self.html)

    def test_representation_uses_actual_fail_closed_fields(self) -> None:
        self.assertIn(
            "bills < 1 || score === null || score === undefined",
            self.html,
        )
        self.assertIn("var bills = d.bills_analyzed || 0", self.html)
        self.assertNotIn("d.completed_bills", self.html)

    def test_hardcoded_divergence_example_removed(self) -> None:
        self.assertNotIn("67% ΚΑΤΑ", self.html)
        self.assertIn('<div id="divBadge" hidden></div>', self.html)

    def test_tablet_header_remains_sticky_and_single_row(self) -> None:
        self.assertIn("position: sticky;", self.css)
        self.assertNotIn("nav.pnx2-header {\n    position: relative;", self.css)
        self.assertIn("flex-wrap: nowrap !important;", self.css)
        self.assertIn("white-space: nowrap;", self.css)
        self.assertIn("height: 84px;", self.css)
        self.assertIn("height: 70px;", self.css)

    def test_touched_controls_are_flat(self) -> None:
        """Each touched control selector must own both flat-style declarations."""
        for selector in ("#chatPanel", "#newsletter input", "#forum .forum-feature"):
            bodies = self.css_rule_bodies(selector)
            self.assertTrue(bodies, f"No CSS rule found for {selector}")
            declarations = "\n".join(bodies)
            self.assertIn("border-radius: 0 !important;", declarations)
            self.assertIn("box-shadow: none !important;", declarations)


# ---------------------------------------------------------------------------
# PR342RegressionTest — T-348 review findings
# ---------------------------------------------------------------------------

class PR342RegressionTest(unittest.TestCase):
    """Regression tests for the three PR #342 review findings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.index_html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        cls.folds_js = (r2_landing_check.DOCS_DIR / "assets/redesign-v2/landing-folds.js").read_text(encoding="utf-8")
        cls.rep_html = (r2_landing_check.DOCS_DIR / "representative.html").read_text(encoding="utf-8")

    # -- Finding 1: #main must not open a fold --

    def test_fold_opener_does_not_use_unscoped_queryselector(self) -> None:
        """openHashTarget must not blindly querySelector('.pnx2-fold') —
        the found fold must belong to the target, not a descendant section."""
        self.assertIn(
            'fold.closest("[id]") === target',
            self.folds_js,
            "landing-folds.js must scope querySelector result to target's own fold",
        )

    def test_fold_opener_checks_closest_before_queryselector(self) -> None:
        """The fold opener should try closest('details') first, then
        fall back to querySelector only with the scoping guard."""
        idx_closest = self.folds_js.index("target.closest(\"details\")")
        idx_query = self.folds_js.index('target.querySelector(".pnx2-fold")')
        self.assertLess(idx_closest, idx_query,
                        "closest('details') must precede querySelector('.pnx2-fold')")

    # -- Finding 2: aria-live must not re-announce unchanged text --

    def test_mood_status_guards_textcontent_change(self) -> None:
        """setMood() must only mutate textContent when the value changes,
        to avoid repeated aria-live announcements."""
        self.assertIn(
            "if (status.textContent !== newText)",
            self.index_html,
            "setMood must guard textContent assignment against unchanged values",
        )

    # -- Finding 3: neutral mood copy must be truthful --

    def test_neutral_mood_copy_el_says_comparable_data(self) -> None:
        self.assertIn(
            "αρκετά συγκρίσιμα δεδομένα",
            self.index_html,
            "Greek neutral mood copy must mention 'sufficient comparable data'",
        )

    def test_neutral_mood_copy_en_says_comparable_data(self) -> None:
        self.assertIn(
            "sufficient comparable data",
            self.index_html,
            "English neutral mood copy must mention 'sufficient comparable data'",
        )

    def test_neutral_mood_copy_no_first_completed_vote(self) -> None:
        self.assertNotIn(
            "first completed vote",
            self.index_html,
            "Neutral mood copy must not say 'first completed vote'",
        )

    def test_neutral_mood_copy_el_no_first_vote(self) -> None:
        self.assertNotIn(
            "πρώτη ολοκληρωμένη ψηφοφορία",
            self.index_html,
            "Greek neutral mood copy must not say 'first completed vote'",
        )

    # -- Finding 4: representative source link survives language toggle --

    def test_representative_source_link_not_inside_data_el(self) -> None:
        """The <a> to GitHub must not be inside an element whose data-el
        attribute would cause toggleLang to replace its innerHTML."""
        # The <p> that used to carry data-el must no longer carry it;
        # instead a child <span> carries the translatable label.
        self.assertRegex(
            self.rep_html,
            r'<span[^>]*data-el="Πηγαίος κώδικας:"[^>]*>.*?</span>\s*<a[^>]*github',
            "Source label must be in a <span> so the <a> link survives toggleLang",
        )

    def test_representative_source_link_present(self) -> None:
        self.assertIn(
            'href="https://github.com/NeaBouli/pnyx"',
            self.rep_html,
            "GitHub source link must remain in representative.html",
        )


# ---------------------------------------------------------------------------
# T349OwlSpecificityTest — mobile owl logo specificity regression
# ---------------------------------------------------------------------------

class T349OwlSpecificityTest(unittest.TestCase):
    """Regression: R5 mobile owl selector must beat R2's specificity."""

    @classmethod
    def setUpClass(cls) -> None:
        css_dir = r2_landing_check.DOCS_DIR / "assets/redesign-v2"
        cls.r2_css = (css_dir / "r2-landing.css").read_text(encoding="utf-8")
        cls.r5_css = (css_dir / "r5-landing-fidelity.css").read_text(encoding="utf-8")

    def test_r5_mobile_owl_uses_nav_element_qualifier(self) -> None:
        """R5 ≤640px owl rule must include 'nav.pnx2-header' to match or
        exceed R2's specificity so the 52px size wins."""
        # Extract the ≤640px media block(s) from R5
        blocks = re.findall(
            r"@media\s*\(\s*max-width:\s*640px\s*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            self.r5_css,
        )
        self.assertTrue(blocks, "No @media (max-width: 640px) block found in R5 CSS")
        combined = "\n".join(blocks)
        self.assertIn(
            "nav.pnx2-header .nav-logo img",
            combined,
            "R5 mobile owl rule must use 'nav.pnx2-header' element qualifier "
            "to beat R2's specificity (T-349)",
        )

    def test_r5_mobile_owl_targets_39px(self) -> None:
        """The mobile owl must render at 39×43px (~25% reduction from 52×57)."""
        blocks = re.findall(
            r"@media\s*\(\s*max-width:\s*640px\s*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            self.r5_css,
        )
        combined = "\n".join(blocks)
        self.assertIn("width: 39px", combined)
        self.assertIn("height: 43px", combined)

    def test_r2_mobile_owl_rule_unchanged(self) -> None:
        """R2 must not be edited — its 32px rule should still be present."""
        blocks = re.findall(
            r"@media\s*\(\s*max-width:\s*640px\s*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            self.r2_css,
        )
        combined = "\n".join(blocks)
        self.assertIn("width: 32px", combined)


class T351IOSAppStoreLinkTest(unittest.TestCase):
    """Regression: iOS App Store link must point to the real Discourse Hub listing."""

    CORRECT_ID = "id1173672076"
    BROKEN_ID = "id1442328667"

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")

    def test_ios_link_uses_correct_app_id(self) -> None:
        """The iOS App button must link to Discourse Hub id1173672076 (T-351)."""
        self.assertIn(
            f"apps.apple.com/app/discourse-hub/{self.CORRECT_ID}",
            self.html,
            "iOS App Store link must use the correct Discourse Hub ID "
            f"({self.CORRECT_ID}), not the broken {self.BROKEN_ID}",
        )

    def test_broken_ios_id_absent(self) -> None:
        """The old broken app ID must not appear anywhere in the landing."""
        self.assertNotIn(
            self.BROKEN_ID,
            self.html,
            f"Broken iOS app ID {self.BROKEN_ID} must not appear in docs/index.html",
        )


# ---------------------------------------------------------------------------
# T357DomOrderTest — DOM order matches visual/semantic order
# ---------------------------------------------------------------------------

class T357DomOrderTest(unittest.TestCase):
    """Verify that the HTML DOM order of top-level sections within <main>
    matches the intended visual/semantic reading order (T-357)."""

    EXPECTED_ORDER = [
        "landing-hero",        # hero (identified by class)
        "pnx2-history-band",   # history band (identified by class)
        "pnx2-democracy-data", # democracy data (identified by class)
        "votes",               # votes section (identified by id)
        "download",            # download section (identified by id)
        "how",                 # how it works (identified by id)
        "demo",                # demo (identified by id)
        "features",            # features (identified by id)
        "forum",               # forum (identified by id)
        "wiki-section",        # wiki/docs (identified by id)
        "roadmap",             # roadmap (identified by id)
        "contact",             # contact (identified by id)
        "notice",              # disclaimer (identified by id)
        "newsletter",          # newsletter (identified by id, last before footer)
    ]

    @classmethod
    def setUpClass(cls) -> None:
        from html.parser import HTMLParser

        class _SectionCollector(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.in_main = False
                self.depth = 0
                self.sections: list[str] = []

            def handle_starttag(self, tag: str, attrs: list) -> None:
                ad = dict(attrs)
                if tag == "main" and ad.get("id") == "main":
                    self.in_main = True
                    return
                if self.in_main and tag == "section":
                    if self.depth == 0:
                        # Top-level section: identify by id or class
                        sid = ad.get("id", "")
                        cls_attr = ad.get("class", "")
                        if sid:
                            self.sections.append(sid)
                        elif "landing-hero" in cls_attr:
                            self.sections.append("landing-hero")
                        elif "pnx2-history-band" in cls_attr:
                            self.sections.append("pnx2-history-band")
                        elif "pnx2-democracy-data" in cls_attr:
                            self.sections.append("pnx2-democracy-data")
                        else:
                            self.sections.append(f"unknown-class:{cls_attr}")
                    self.depth += 1

            def handle_endtag(self, tag: str) -> None:
                if tag == "main" and self.in_main:
                    self.in_main = False
                if self.in_main and tag == "section" and self.depth > 0:
                    self.depth -= 1

        p = _SectionCollector()
        html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        p.feed(html)
        cls.actual_order = p.sections

    def test_section_count_matches(self) -> None:
        self.assertEqual(
            len(self.EXPECTED_ORDER),
            len(self.actual_order),
            f"Expected {len(self.EXPECTED_ORDER)} top-level sections, "
            f"found {len(self.actual_order)}: {self.actual_order}",
        )

    def test_dom_order_matches_semantic_order(self) -> None:
        self.assertEqual(
            self.EXPECTED_ORDER,
            self.actual_order,
            "DOM section order does not match the intended semantic/visual order (T-357)",
        )

    def test_no_css_order_on_top_level_sections(self) -> None:
        """CSS order properties for top-level sections should be removed
        now that DOM order matches visual order."""
        css = (
            r2_landing_check.DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"
        ).read_text(encoding="utf-8")
        # Check that main#main flex container for ordering is gone
        self.assertNotIn(
            "main#main",
            css,
            "main#main flex container should be removed (DOM order is canonical now)",
        )
        # Check no top-level section order properties remain
        for section_id in ["#how", "#demo", "#votes", "#download", "#forum",
                           "#wiki-section", "#roadmap", "#contact", "#notice",
                           "#newsletter"]:
            pattern = rf"^{re.escape(section_id)}\s*\{{\s*order\s*:"
            self.assertIsNone(
                re.search(pattern, css, re.MULTILINE),
                f"CSS order property for {section_id} should be removed",
            )

    def test_key_ids_preserved(self) -> None:
        """All functional IDs must survive the reorder."""
        html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        for key_id in [
            "main", "how", "demo", "features", "forum", "votes",
            "wiki-section", "roadmap", "contact", "download",
            "newsletter", "notice", "nlForm", "nlEmail", "nlBtn",
            "heroParliamentDecision", "heroLiveStatus",
            "heroCitizenDecision", "heroCitizenMeta",
            "historyTitle", "repSection", "chatPanel",
        ]:
            self.assertIn(
                f'id="{key_id}"',
                html,
                f"Functional ID '{key_id}' missing after DOM reorder (T-357)",
            )

    def test_newsletter_is_last_section_before_footer(self) -> None:
        """Newsletter must be the last section before footer."""
        html = (r2_landing_check.DOCS_DIR / "index.html").read_text(encoding="utf-8")
        # Find the closing </section> of the newsletter
        newsletter_start = html.index('id="newsletter"')
        newsletter_close = html.index("</section>", newsletter_start)
        main_end = html.index("</main>")
        between = html[newsletter_close + len("</section>"):main_end]
        self.assertNotIn(
            "<section",
            between,
            "No <section> should appear between newsletter and </main>",
        )


# ---------------------------------------------------------------------------
# T378ForumCardInsetTest — forum first-card left inset regression
# ---------------------------------------------------------------------------

class T378ForumCardInsetTest(unittest.TestCase):
    """T-378: All four Forum feature cards must have equal padding."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.css = (
            r2_landing_check.DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"
        ).read_text(encoding="utf-8")

    def _css_rule_bodies(self, selector: str) -> list[str]:
        source = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)
        pattern = rf"(?:^|}})[^{{}}]*{re.escape(selector)}[^{{}}]*\{{([^{{}}]*)\}}"
        return re.findall(pattern, source, flags=re.DOTALL | re.MULTILINE)

    def test_first_child_has_no_padding_left_zero(self) -> None:
        """The first forum card must not zero out its left padding."""
        bodies = self._css_rule_bodies("#forum .forum-feature:first-child")
        combined = "\n".join(bodies)
        self.assertNotIn("padding-left: 0", combined,
                         "T-378 regression: first forum card strips left padding")

    def test_last_child_has_no_padding_right_zero(self) -> None:
        """The last forum card must not zero out its right padding."""
        bodies = self._css_rule_bodies("#forum .forum-feature:last-child")
        combined = "\n".join(bodies)
        self.assertNotIn("padding-right: 0", combined,
                         "T-378 regression: last forum card strips right padding")

    def test_base_forum_card_has_uniform_padding(self) -> None:
        """The shared forum-feature rule must set equal padding on all sides."""
        bodies = self._css_rule_bodies("#forum .forum-feature")
        combined = "\n".join(bodies)
        self.assertIn("padding: 24px !important", combined,
                       "Forum cards must have uniform 24px padding")

    def test_last_child_still_removes_border_right(self) -> None:
        """The last card should still drop its right border."""
        bodies = self._css_rule_bodies("#forum .forum-feature:last-child")
        combined = "\n".join(bodies)
        self.assertIn("border-right: 0", combined,
                       "Last forum card should have no right border")


if __name__ == "__main__":
    unittest.main()

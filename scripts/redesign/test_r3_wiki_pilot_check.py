#!/usr/bin/env python3
"""Focused negative and real-tree tests for the R3 wiki pilot gate."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r3_wiki_pilot_check as r3

MINIMAL_HTML = """<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="../assets/redesign-v2/tokens.css"/>
<link rel="stylesheet" href="../assets/redesign-v2/foundation.css"/>
<link rel="stylesheet" href="../assets/redesign-v2/r3-wiki.css"/>
</head><body>
<a class="pnx2-skip" href="#main" data-el="Μετάβαση στο κύριο περιεχόμενο" data-en="Skip to main content">skip</a>
<nav class="pnx2-header"></nav>
<main id="main"><div class="hero">Wiki</div></main>
<footer class="pnx2-footer"></footer>
</body></html>"""

MINIMAL_CSS = """*,*::before,*::after {
  border-radius: 0 !important;
  box-shadow: none !important;
}
.pnx2-header { background: #fff; }
"""


class RealTreeTest(unittest.TestCase):
    def test_real_tree_passes(self) -> None:
        self.assertEqual([], r3.check_r3())


class PreservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        inv = json.loads(r3.R0_INVENTORY_FILE.read_text(encoding="utf-8"))
        cls.baseline = next(p for p in inv["pages"] if p["path"] == r3.PILOT_REL)
        cls.current = r3._inventory_page_at(r3.DOCS_DIR, r3.PILOT_REL)

    def test_real_contract_has_only_allowed_deltas(self) -> None:
        self.assertEqual([], r3.check_pilot_preservation(self.baseline, self.current))

    def test_external_host_change_fails(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["external_hosts"].append("example.invalid")
        self.assertTrue(any("external_hosts" in v for v in r3.check_pilot_preservation(self.baseline, changed)))

    def test_script_change_fails(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["scripts"]["inline"].pop()
        self.assertTrue(any("scripts" in v for v in r3.check_pilot_preservation(self.baseline, changed)))

    def test_bilingual_loss_fails(self) -> None:
        changed = copy.deepcopy(self.current)
        changed["bilingual"]["pairs"].pop()
        self.assertTrue(any("bilingual" in v for v in r3.check_pilot_preservation(self.baseline, changed)))


class StructureTest(unittest.TestCase):
    def test_minimal_structure_passes(self) -> None:
        self.assertEqual([], r3.check_structure(MINIMAL_HTML))

    def test_commented_header_does_not_pass(self) -> None:
        html = MINIMAL_HTML.replace(
            '<nav class="pnx2-header"></nav>',
            '<!-- <nav class="pnx2-header"></nav> --><nav></nav>',
        )
        self.assertTrue(any("pnx2-header" in v for v in r3.check_structure(html)))

    def test_main_id_on_div_does_not_pass(self) -> None:
        html = MINIMAL_HTML.replace('<main id="main">', '<main><div id="main"></div>')
        self.assertTrue(any("main#main" in v for v in r3.check_structure(html)))

    def test_hero_outside_main_fails(self) -> None:
        html = MINIMAL_HTML.replace(
            '<main id="main"><div class="hero">Wiki</div></main>',
            '<div class="hero">Wiki</div><main id="main"></main>',
        )
        self.assertTrue(any("hero" in v for v in r3.check_structure(html)))

    def test_wrong_skip_contract_fails(self) -> None:
        html = MINIMAL_HTML.replace('href="#main"', 'href="#content"')
        self.assertTrue(any("skip link contract" in v for v in r3.check_structure(html)))

    def test_missing_stylesheet_fails(self) -> None:
        html = MINIMAL_HTML.replace(
            '<link rel="stylesheet" href="../assets/redesign-v2/r3-wiki.css"/>', ""
        )
        self.assertTrue(any("r3-wiki.css" in v for v in r3.check_structure(html)))


class CssTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        css_dir = self.tmp / "assets/redesign-v2"
        css_dir.mkdir(parents=True)
        for rel in r3.R3_CSS_RELS:
            (self.tmp / rel).write_text(MINIMAL_CSS, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _violation(self, css: str) -> list[str]:
        (self.tmp / r3.R3_CSS_RELS[-1]).write_text(MINIMAL_CSS + css, encoding="utf-8")
        return r3.check_css_files(self.tmp)

    def test_minimal_css_passes(self) -> None:
        self.assertEqual([], r3.check_css_files(self.tmp))

    def test_gradient_fails(self) -> None:
        self.assertTrue(any("gradient" in v for v in self._violation(".x{background:linear-gradient(#fff,#000)}")))

    def test_shadow_fails(self) -> None:
        self.assertTrue(any("box-shadow" in v for v in self._violation(".x{box-shadow:0 2px 4px #000}")))

    def test_vw_inside_clamp_fails(self) -> None:
        self.assertTrue(any("viewport-scaled" in v for v in self._violation(".x{font-size:clamp(1rem,4vw,3rem)}")))

    def test_quoted_import_fails(self) -> None:
        self.assertTrue(any("external @import" in v for v in self._violation('@import "https://example.invalid/x.css";')))

    def test_protocol_relative_import_fails(self) -> None:
        self.assertTrue(any("external @import" in v for v in self._violation('@import url("//example.invalid/x.css");')))

    def test_external_url_fails(self) -> None:
        self.assertTrue(any("external url" in v for v in self._violation('.x{background:url("https://example.invalid/x.png")}')))

    def test_blur_fails(self) -> None:
        self.assertTrue(any("blur" in v for v in self._violation(".x{backdrop-filter:blur(8px)}")))


class ParityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "docs/wiki").mkdir(parents=True)
        (self.tmp / "docs/index.html").write_text("landing", encoding="utf-8")
        (self.tmp / "docs/wiki/index.html").write_text("pilot", encoding="utf-8")
        (self.tmp / "docs/other.html").write_text("stable", encoding="utf-8")
        self.inv = {"pages": [
            {"path": "docs/index.html", "sha256": "r2"},
            {"path": "docs/wiki/index.html", "sha256": "r0-pilot"},
            {"path": "docs/other.html", "sha256": hashlib.sha256(b"stable").hexdigest()},
        ]}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nonpilot_match_passes(self) -> None:
        self.assertEqual([], r3.check_nonpilot_parity(self.inv, self.tmp))

    def test_nonpilot_change_fails(self) -> None:
        (self.tmp / "docs/other.html").write_text("changed", encoding="utf-8")
        self.assertTrue(any("docs/other.html" in v for v in r3.check_nonpilot_parity(self.inv, self.tmp)))


if __name__ == "__main__":
    unittest.main()

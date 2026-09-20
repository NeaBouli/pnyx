#!/usr/bin/env python3
"""Focused tests for the R4 Community/header/chat gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r4_community_header_check as r4


class RealTreeTest(unittest.TestCase):
    def test_real_tree_passes(self) -> None:
        self.assertEqual([], r4.check_r4())


class StructureTest(unittest.TestCase):
    VALID = """<!doctype html><html><head>
<link rel="stylesheet" href="assets/redesign-v2/tokens.css">
<link rel="stylesheet" href="assets/redesign-v2/foundation.css">
<link rel="stylesheet" href="assets/redesign-v2/r4-community.css">
</head><body><a class="pnx2-skip" href="#main">skip</a>
<nav class="pnx2-header"></nav><main id="main"><div class="community-hero"></div></main>
<footer class="pnx2-footer"></footer></body></html>"""

    def test_valid_structure(self) -> None:
        self.assertEqual([], r4.check_structure(self.VALID))

    def test_footer_inside_main_fails(self) -> None:
        html = self.VALID.replace(
            '</main>\n<footer class="pnx2-footer">',
            '<footer class="pnx2-footer"></footer></main>\n<div',
        )
        self.assertTrue(any("footer" in item for item in r4.check_structure(html)))

    def test_missing_main_fails(self) -> None:
        self.assertTrue(any("main#main" in item for item in r4.check_structure(self.VALID.replace(' id="main"', ""))))


class ChatContractTest(unittest.TestCase):
    def test_display_override_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(
                "@media (max-width: 400px){#chatPanel{position: fixed !important;"
                "left: 16px !important;right: 16px !important;width: auto !important;display:block;}}",
                encoding="utf-8",
            )
            self.assertTrue(any("display" in item for item in r4.check_mobile_chat(docs)))

    def test_missing_inset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(
                "@media (max-width: 400px){#chatPanel{position: fixed !important;width: auto !important;}}",
                encoding="utf-8",
            )
            self.assertTrue(any("left" in item for item in r4.check_mobile_chat(docs)))


class HeaderContractTest(unittest.TestCase):
    def test_duplicate_page_nav_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nav = root / "apps/web/src/components/NavHeader.tsx"
            nav.parent.mkdir(parents=True)
            nav.write_text(
                "/bills /results /mp /municipal /analytics flex-nowrap overflow-x-auto min-w-0 whitespace-nowrap",
                encoding="utf-8",
            )
            legacy = root / "apps/web/src/components/PublicDataNav.tsx"
            legacy.write_text("retained", encoding="utf-8")
            for rel in r4.PUBLIC_DATA_PAGES:
                page = root / rel
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text("page", encoding="utf-8")
            (root / r4.PUBLIC_DATA_PAGES[0]).write_text("<PublicDataNav />", encoding="utf-8")
            self.assertTrue(any("duplicate" in item for item in r4.check_dynamic_header(root)))


if __name__ == "__main__":
    unittest.main()

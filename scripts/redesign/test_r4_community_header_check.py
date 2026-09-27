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
    HEADER = (
        "nav.pnx2-header{flex-wrap:nowrap !important;}"
        "nav.pnx2-header .nav-links{overflow-x:auto;scrollbar-width:none;}"
        "@media (max-width:640px){nav.pnx2-header .nav-logo{font-size:0 !important;}}"
    )

    @classmethod
    def _source(cls, chat: str) -> str:
        return cls.HEADER + "@media (max-width:400px){#chatPanel{" + chat + "}}"

    def test_display_override_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(self._source(
                "position:fixed !important;left:16px !important;right:16px !important;"
                "width:auto !important;overflow-y:auto !important;display:block;"
            ), encoding="utf-8")
            self.assertTrue(any("display" in item for item in r4.check_mobile_chat(docs)))

    def test_missing_inset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(self._source(
                "position:fixed !important;width:auto !important;overflow-y:auto !important;"
            ), encoding="utf-8")
            self.assertTrue(any("left" in item for item in r4.check_mobile_chat(docs)))

    def test_later_media_rule_cannot_satisfy_400px_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(
                self.HEADER
                + "@media (max-width:400px){.other{color:red;}}"
                + "@media (max-width:900px){#chatPanel{position:fixed !important;left:16px !important;"
                "right:16px !important;width:auto !important;overflow-y:auto !important;}}",
                encoding="utf-8",
            )
            self.assertTrue(any("#chatPanel" in item for item in r4.check_mobile_chat(docs)))

    def test_comment_decoys_do_not_satisfy_chat_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r2-landing.css"
            target.parent.mkdir(parents=True)
            target.write_text(
                self.HEADER
                + "/* @media (max-width:400px){#chatPanel{position:fixed !important;left:16px !important;"
                "right:16px !important;width:auto !important;overflow-y:auto !important;}} */",
                encoding="utf-8",
            )
            self.assertTrue(any("#chatPanel" in item for item in r4.check_mobile_chat(docs)))


class HeaderContractTest(unittest.TestCase):
    @staticmethod
    def _nav_source(classes: str = "flex min-w-0 flex-nowrap overflow-x-auto") -> str:
        return (
            "const navLinks = ["
            "{ href: `/${locale}/bills` },{ href: `/${locale}/results` },"
            "{ href: `/${locale}/mp` },{ href: `/${locale}/municipal` },"
            "{ href: `/${locale}/analytics` }];"
            f'<nav className="{classes}">{{navLinks.map(link => '
            '<a className="whitespace-nowrap">x</a>)}</nav>'
        )

    @staticmethod
    def _write_tree(root: Path, nav_source: str) -> None:
        nav = root / "apps/web/src/components/NavHeader.tsx"
        nav.parent.mkdir(parents=True)
        nav.write_text(nav_source, encoding="utf-8")
        (root / "apps/web/src/components/PublicDataNav.tsx").write_text("retained", encoding="utf-8")
        for rel in r4.PUBLIC_DATA_PAGES:
            page = root / rel
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text("page", encoding="utf-8")

    def test_duplicate_page_nav_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_tree(root, self._nav_source())
            (root / r4.PUBLIC_DATA_PAGES[0]).write_text("<PublicDataNav />", encoding="utf-8")
            self.assertTrue(any("duplicate" in item for item in r4.check_dynamic_header(root)))

    def test_missing_public_data_page_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_tree(root, self._nav_source())
            (root / r4.PUBLIC_DATA_PAGES[0]).unlink()
            self.assertTrue(any("missing public-data page" in item for item in r4.check_dynamic_header(root)))

    def test_decoy_routes_outside_nav_links_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._nav_source().replace("{ href: `/${locale}/analytics` }", "")
            self._write_tree(root, source + "// /analytics")
            self.assertTrue(any("/analytics" in item for item in r4.check_dynamic_header(root)))

    def test_unused_nav_links_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_tree(root, self._nav_source().replace("navLinks.map", "otherLinks.map"))
            self.assertTrue(any("does not consume navLinks" in item for item in r4.check_dynamic_header(root)))


class CssContractTest(unittest.TestCase):
    def test_unrelated_and_commented_declarations_do_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            target = docs / "assets/redesign-v2/r4-community.css"
            target.parent.mkdir(parents=True)
            target.write_text(
                "/* nav.pnx2-header{flex-wrap:nowrap !important;} */"
                ".decoy{overflow-x:auto;border-radius:0 !important;box-shadow:none !important;}"
                "@media (max-width:480px){.decoy{grid-template-columns:1fr !important;}}",
                encoding="utf-8",
            )
            for rel in r4.CSS_RELS[:-1]:
                path = docs / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            violations = r4.check_css(docs)
            self.assertTrue(any("nowrap" in item for item in violations))
            self.assertTrue(any("single-column" in item for item in violations))


if __name__ == "__main__":
    unittest.main()

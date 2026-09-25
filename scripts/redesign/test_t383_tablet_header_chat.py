"""T-383: tablet header clipping, chat-trigger collision, and scroll-margin tests.

Validates:
 1. Brand-copy hidden at <=960px so nav links are not clipped.
 2. Nav link padding tightened at <=820px for one-line fit.
 3. Chat widget repositioned to bottom-left at <=820px, preventing fold "+" overlap.
 4. Chat panel constrained to viewport width at narrow viewports.
 5. Scroll-margin-top still set on all anchor targets.
 6. landing-folds.js defers scrollIntoView via requestAnimationFrame after fold open.
 7. All 7 nav destinations plus lang-btn and CTA remain present in HTML.
 8. Forum card insets (text-align: left) and representative heading centering preserved.
"""

from __future__ import annotations

import re
import unittest

from r2_landing_check import DOCS_DIR


CSS_PATH = DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"
JS_PATH = DOCS_DIR / "assets/redesign-v2/landing-folds.js"
HTML_PATH = DOCS_DIR / "index.html"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _extract_media_block(css: str, max_width: int) -> str:
    """Return the concatenated content of all @media (max-width: Npx) blocks."""
    pattern = rf"@media\s*\(\s*max-width\s*:\s*{max_width}px\s*\)\s*\{{"
    blocks: list[str] = []
    for m in re.finditer(pattern, css):
        start = m.end()
        depth = 1
        pos = start
        while pos < len(css) and depth > 0:
            if css[pos] == "{":
                depth += 1
            elif css[pos] == "}":
                depth -= 1
            pos += 1
        blocks.append(css[start : pos - 1])
    return "\n".join(blocks)


class BrandCopyHiddenTest(unittest.TestCase):
    """At <=960px, .pnx2-brand-copy must be display:none so nav links fit."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_brand_copy_hidden_at_960(self) -> None:
        block = _extract_media_block(self.css, 960)
        self.assertRegex(
            block,
            r"\.pnx2-brand-copy\s*\{[^}]*display\s*:\s*none",
            ".pnx2-brand-copy must be display:none at <=960px",
        )


class NavPaddingTightenedTest(unittest.TestCase):
    """At <=820px, nav link padding must be reduced for one-line fit."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())
        self.block_820 = _extract_media_block(self.css, 820)

    def test_nav_link_padding_reduced(self) -> None:
        m = re.search(
            r"nav\.pnx2-header\s+\.nav-links\s+a\s*\{([^}]*)\}",
            self.block_820,
        )
        self.assertIsNotNone(m, "nav link rule not found in 820px block")
        rule = m.group(1)
        self.assertRegex(rule, r"padding\s*:\s*0\s+6px", "padding must be 0 6px at <=820px")
        self.assertRegex(rule, r"font-size\s*:\s*12px", "font-size must be 12px at <=820px")

    def test_cta_padding_reduced(self) -> None:
        m = re.search(
            r"nav\.pnx2-header\s+\.nav-links\s+\.pnx2-nav-cta\s*\{([^}]*)\}",
            self.block_820,
        )
        self.assertIsNotNone(m, "CTA rule not found in 820px block")
        rule = m.group(1)
        self.assertRegex(rule, r"padding\s*:\s*0\s+10px", "CTA padding must be 0 10px at <=820px")


class ChatWidgetRepositionedTest(unittest.TestCase):
    """At <=820px, chat widget must move to bottom-left to avoid fold overlap."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())
        self.block_820 = _extract_media_block(self.css, 820)

    def test_chat_widget_left_positioned(self) -> None:
        m = re.search(r"#chatWidget\s*\{([^}]*)\}", self.block_820)
        self.assertIsNotNone(m, "#chatWidget rule not found in 820px block")
        rule = m.group(1)
        self.assertRegex(rule, r"right\s*:\s*auto\s*!important", "right must be auto !important")
        self.assertRegex(rule, r"left\s*:\s*1\.5rem\s*!important", "left must be 1.5rem !important")

    def test_chat_panel_repositioned(self) -> None:
        m = re.search(r"#chatPanel\s*\{([^}]*)\}", self.block_820)
        self.assertIsNotNone(m, "#chatPanel rule not found in 820px block")
        rule = m.group(1)
        self.assertRegex(rule, r"right\s*:\s*auto\s*!important")
        self.assertRegex(rule, r"left\s*:\s*0\s*!important")
        self.assertRegex(
            rule,
            r"max-width\s*:\s*calc\(100vw\s*-\s*3rem\)\s*!important",
            "panel max-width must be viewport-constrained",
        )


class ScrollMarginTest(unittest.TestCase):
    """All anchor targets must have scroll-margin-top to clear the sticky header."""

    EXPECTED_IDS = [
        "how", "demo", "features", "wiki-section", "forum",
        "roadmap", "notice", "contact", "representative",
        "transparency", "votes", "download",
    ]

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_scroll_margin_top_set(self) -> None:
        m = re.search(r"scroll-margin-top\s*:\s*(\d+)px", self.css)
        self.assertIsNotNone(m, "scroll-margin-top rule not found")
        value = int(m.group(1))
        self.assertGreaterEqual(value, 80, "scroll-margin-top must be >= 80px")

    def test_all_anchor_ids_covered(self) -> None:
        # Find the selector list before the scroll-margin-top declaration
        m = re.search(r"((?:#[\w-]+[\s,]*)+)\s*\{[^}]*scroll-margin-top", self.css)
        self.assertIsNotNone(m, "scroll-margin-top selector block not found")
        selector = m.group(1)
        for eid in self.EXPECTED_IDS:
            self.assertIn(f"#{eid}", selector, f"#{eid} missing from scroll-margin-top selector")


class ScrollIntoViewDeferredTest(unittest.TestCase):
    """landing-folds.js must defer scrollIntoView via requestAnimationFrame."""

    def setUp(self) -> None:
        self.js = JS_PATH.read_text()

    def test_scroll_into_view_inside_raf(self) -> None:
        # The pattern: details.open = true → requestAnimationFrame → scrollIntoView
        pattern = r"details\.open\s*=\s*true;\s*(?://[^\n]*\n\s*)*requestAnimationFrame\s*\(\s*function"
        self.assertRegex(
            self.js, pattern,
            "scrollIntoView must be deferred via requestAnimationFrame after details.open",
        )

    def test_scroll_into_view_not_called_synchronously(self) -> None:
        # Ensure scrollIntoView does NOT appear right after details.open without rAF
        pattern = r"details\.open\s*=\s*true;\s*target\.scrollIntoView"
        self.assertNotRegex(
            self.js, pattern,
            "scrollIntoView must NOT be called synchronously after fold open",
        )


class NavDestinationsPreservedTest(unittest.TestCase):
    """All 7 nav links, the lang button, and CTA must remain in the HTML."""

    EXPECTED_HREFS = ["#main", "#votes", "#roadmap", "#wiki-section", "wiki/", "community.html", "#download"]

    def setUp(self) -> None:
        self.html = HTML_PATH.read_text()

    def test_all_nav_links_present(self) -> None:
        nav_section = re.search(r'<div class="nav-links">(.*?)</div>', self.html, re.DOTALL)
        self.assertIsNotNone(nav_section, ".nav-links container not found")
        nav_html = nav_section.group(1)
        for href in self.EXPECTED_HREFS:
            self.assertIn(
                f'href="{href}"',
                nav_html,
                f"nav link with href={href} missing from .nav-links",
            )

    def test_lang_button_present(self) -> None:
        nav_section = re.search(r'<div class="nav-links">(.*?)</div>', self.html, re.DOTALL)
        self.assertIsNotNone(nav_section)
        self.assertIn("lang-btn", nav_section.group(1), "language button missing")

    def test_cta_present(self) -> None:
        nav_section = re.search(r'<div class="nav-links">(.*?)</div>', self.html, re.DOTALL)
        self.assertIsNotNone(nav_section)
        self.assertIn("pnx2-nav-cta", nav_section.group(1), "CTA button missing")


class ForumInsetPreservedTest(unittest.TestCase):
    """Forum and representative layout rules from PR #362 must remain intact."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_forum_text_align_left(self) -> None:
        m = re.search(r"#forum\s+\.section-inner[^{]*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, "#forum .section-inner rule not found")
        self.assertRegex(m.group(1), r"text-align\s*:\s*left", "forum must be text-align: left")

    def test_representative_fold_centering_preserved(self) -> None:
        rules = [
            m.group(1)
            for m in re.finditer(
                r"\.pnx2-representative-fold\s*>\s*\.pnx2-fold-summary\s*\{([^}]*)\}",
                self.css,
            )
        ]
        self.assertTrue(rules, "representative fold summary rule not found")
        padding_rule = next((r for r in rules if "padding-top" in r), None)
        self.assertIsNotNone(padding_rule, "representative fold summary padding rule not found")
        self.assertRegex(padding_rule, r"padding-top\s*:\s*\d+px")
        self.assertRegex(padding_rule, r"padding-bottom\s*:\s*\d+px")


if __name__ == "__main__":
    unittest.main()

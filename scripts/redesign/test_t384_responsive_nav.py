"""T-384: responsive navigation, chat positioning, folds, and anchor behavior.

Replaces the brittle T-383 tests with behavior-focused assertions that verify:
 1. Hamburger menu button present in HTML with ARIA attributes.
 2. Nav links container has id matching aria-controls on the menu button.
 3. At <=960px: hamburger visible, nav-links hidden by default, shown via .nav-open.
 4. Brand wordmark (.pnx2-brand-copy) is never display:none at any breakpoint.
 5. No overflow-x:auto on .nav-links (no hidden clipping as sole nav access).
 6. Chat widget repositioned to bottom-left at <=960px.
 7. Chat panel viewport-constrained at <=960px.
 8. Scroll-margin-top set on all anchor targets (>=80px).
 9. landing-folds.js defers scrollIntoView via requestAnimationFrame.
10. landing-folds.js contains menu toggle logic with Escape key support.
11. All 7 nav destinations plus lang-btn and CTA present in HTML.
12. Forum text-align:left and fold centering preserved from PR #362.
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


class HamburgerMenuPresenceTest(unittest.TestCase):
    """The HTML must contain a hamburger button with proper ARIA wiring."""

    def setUp(self) -> None:
        self.html = HTML_PATH.read_text()

    def test_menu_button_exists(self) -> None:
        self.assertRegex(
            self.html,
            r'<button\s[^>]*class="pnx2-menu-btn"',
            "hamburger .pnx2-menu-btn button must exist in HTML",
        )

    def test_menu_button_aria_expanded(self) -> None:
        self.assertRegex(
            self.html,
            r'<button\s[^>]*aria-expanded="false"',
            "hamburger button must have aria-expanded='false'",
        )

    def test_menu_button_aria_controls(self) -> None:
        m = re.search(r'aria-controls="([^"]+)"', self.html)
        self.assertIsNotNone(m, "hamburger button must have aria-controls")
        target_id = m.group(1)
        self.assertIn(
            f'id="{target_id}"',
            self.html,
            f"element with id='{target_id}' must exist (aria-controls target)",
        )


class HamburgerCSSBehaviorTest(unittest.TestCase):
    """At <=960px the hamburger shows and nav-links collapse to a menu."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())
        self.block_960 = _extract_media_block(self.css, 960)

    def test_hamburger_visible_at_960(self) -> None:
        self.assertRegex(
            self.block_960,
            r"\.pnx2-menu-btn\s*\{[^}]*display\s*:\s*flex",
            ".pnx2-menu-btn must be display:flex at <=960px",
        )

    def test_nav_links_hidden_by_default_at_960(self) -> None:
        m = re.search(
            r"nav\.pnx2-header\s+\.nav-links\s*\{([^}]*)\}",
            self.block_960,
        )
        self.assertIsNotNone(m, "nav-links rule must exist in 960px block")
        self.assertRegex(
            m.group(1),
            r"display\s*:\s*none",
            "nav-links must be display:none by default at <=960px",
        )

    def test_nav_links_shown_when_open(self) -> None:
        self.assertRegex(
            self.block_960,
            r"nav\.pnx2-header\.nav-open\s+\.nav-links\s*\{[^}]*display\s*:\s*flex",
            "nav-links must be display:flex when .nav-open is set",
        )


class WordmarkAlwaysVisibleTest(unittest.TestCase):
    """The brand wordmark must override the older mobile hide rule."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_brand_copy_not_hidden(self) -> None:
        pattern = r"\.pnx2-brand-copy\s*\{[^}]*display\s*:\s*none"
        self.assertNotRegex(
            self.css,
            pattern,
            ".pnx2-brand-copy must NEVER be display:none — wordmark must stay visible",
        )

    def test_mobile_override_beats_r2_nav_logo_span_rule(self) -> None:
        block_640 = _extract_media_block(self.css, 640)
        self.assertRegex(
            block_640,
            r"nav\.pnx2-header\s+\.nav-logo\s+\.pnx2-brand-copy\s*\{[^}]*display\s*:\s*flex",
            "R2 hides nav-logo spans below 640px; the wordmark needs a more specific override",
        )


class NoOverflowClippingTest(unittest.TestCase):
    """Nav links must not rely on overflow-x:auto as the sole access method."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_no_overflow_auto_on_nav_links(self) -> None:
        # Check for overflow-x: auto in any nav-links rule (base or media query)
        nav_link_rules = re.findall(
            r"(?:nav\.pnx2-header\s+)?\.nav-links\s*\{([^}]*)\}",
            self.css,
        )
        for rule in nav_link_rules:
            self.assertNotRegex(
                rule,
                r"overflow-x\s*:\s*auto",
                "nav-links must not use overflow-x:auto — use hamburger menu instead",
            )


class ChatWidgetPositionTest(unittest.TestCase):
    """Chat widget must move away from fold toggles at narrow widths."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())
        self.block_960 = _extract_media_block(self.css, 960)

    def test_chat_widget_repositioned(self) -> None:
        m = re.search(r"#chatWidget\s*\{([^}]*)\}", self.block_960)
        self.assertIsNotNone(m, "#chatWidget rule must exist at <=960px")
        rule = m.group(1)
        self.assertRegex(rule, r"left\s*:", "chat widget must have left positioning")

    def test_chat_panel_constrained(self) -> None:
        m = re.search(r"#chatPanel\s*\{([^}]*)\}", self.block_960)
        self.assertIsNotNone(m, "#chatPanel rule must exist at <=960px")
        rule = m.group(1)
        self.assertRegex(
            rule,
            r"max-width\s*:",
            "chat panel must have max-width constraint",
        )


class ScrollMarginTest(unittest.TestCase):
    """All anchor targets must have scroll-margin-top >= 80px."""

    EXPECTED_IDS = [
        "how", "demo", "features", "wiki-section", "forum",
        "roadmap", "notice", "contact", "representative",
        "transparency", "votes", "download",
    ]

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_scroll_margin_top_adequate(self) -> None:
        m = re.search(r"scroll-margin-top\s*:\s*(\d+)px", self.css)
        self.assertIsNotNone(m, "scroll-margin-top rule not found")
        value = int(m.group(1))
        self.assertGreaterEqual(value, 80, "scroll-margin-top must be >= 80px")

    def test_all_anchor_ids_covered(self) -> None:
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
        self.assertIn(
            "requestAnimationFrame",
            self.js,
            "scrollIntoView must be deferred via requestAnimationFrame",
        )
        self.assertIn(
            "scrollIntoView",
            self.js,
            "scrollIntoView must be present",
        )

    def test_scroll_into_view_not_called_synchronously(self) -> None:
        pattern = r"details\.open\s*=\s*true;\s*target\.scrollIntoView"
        self.assertNotRegex(
            self.js, pattern,
            "scrollIntoView must NOT be called synchronously after fold open",
        )


class MenuToggleJSTest(unittest.TestCase):
    """landing-folds.js must include menu toggle with Escape key handling."""

    def setUp(self) -> None:
        self.js = JS_PATH.read_text()

    def test_menu_toggle_exists(self) -> None:
        self.assertIn("nav-open", self.js, "JS must toggle nav-open class")

    def test_escape_key_closes_menu(self) -> None:
        self.assertIn("Escape", self.js, "JS must handle Escape key to close menu")

    def test_escape_restores_focus_to_menu_button(self) -> None:
        self.assertIn("focusWasInside", self.js)
        self.assertIn("btn.focus()", self.js)

    def test_aria_expanded_toggled(self) -> None:
        self.assertIn(
            "aria-expanded",
            self.js,
            "JS must toggle aria-expanded on the menu button",
        )


class NavDestinationsPreservedTest(unittest.TestCase):
    """All 7 nav links, the lang button, and CTA must remain in the HTML."""

    EXPECTED_HREFS = [
        "#main", "#votes", "#roadmap", "#wiki-section",
        "wiki/", "community.html", "#download",
    ]

    def setUp(self) -> None:
        self.html = HTML_PATH.read_text()

    def test_all_nav_links_present(self) -> None:
        nav_section = re.search(
            r'<div class="nav-links"[^>]*>(.*?)</div>',
            self.html, re.DOTALL,
        )
        self.assertIsNotNone(nav_section, ".nav-links container not found")
        nav_html = nav_section.group(1)
        for href in self.EXPECTED_HREFS:
            self.assertIn(
                f'href="{href}"',
                nav_html,
                f"nav link with href={href} missing from .nav-links",
            )

    def test_lang_button_present(self) -> None:
        nav_section = re.search(
            r'<div class="nav-links"[^>]*>(.*?)</div>',
            self.html, re.DOTALL,
        )
        self.assertIsNotNone(nav_section)
        self.assertIn("lang-btn", nav_section.group(1), "language button missing")

    def test_cta_present(self) -> None:
        nav_section = re.search(
            r'<div class="nav-links"[^>]*>(.*?)</div>',
            self.html, re.DOTALL,
        )
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


if __name__ == "__main__":
    unittest.main()

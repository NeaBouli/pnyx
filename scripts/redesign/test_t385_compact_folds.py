"""T-385: compact closed-fold vertical-rhythm regression tests.

Validates that all closed disclosure bands use the same compact padding
as the reference features/representative folds (~108 px single-line,
~159 px two-line), with no extra outer section padding, and that
full-width separators exist between adjacent bands.

Checks (CSS-only, no browser):
 1. Base .pnx2-fold-summary has 30 px top/bottom padding.
 2. Fold-hosting sections (#how, #demo, #forum, #wiki-section, #roadmap,
    #contact, #notice) have padding-top: 0 and padding-bottom: 0.
 3. #transparency has padding-top: 0 and padding-bottom: 0.
 4. Adjacent sections keep a single separator; #notice has no top border
    and has a bottom border before the newsletter.
 5. Open-state padding: fold[open] rules restore 56 px bottom padding.
 6. Features/representative fold overrides are still intact.
 7. Fold summary border-bottom remains 0 (no title underline).
 8. Typography: fold heading font-size clamp is preserved.
"""

from __future__ import annotations

import re
import unittest

from r2_landing_check import DOCS_DIR


CSS_PATH = DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _find_rule(css: str, selector_pattern: str) -> str | None:
    m = re.search(selector_pattern + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


def _find_all_rules(css: str, selector_pattern: str) -> list[str]:
    return [m.group(1) for m in re.finditer(selector_pattern + r"\s*\{([^}]*)\}", css)]


def _last_value(css: str, selector_pattern: str, prop: str) -> str | None:
    """Return the last effective value for *prop* across all rules matching *selector_pattern*."""
    rules = _find_all_rules(css, selector_pattern)
    val = None
    for block in rules:
        m = re.search(rf"{prop}\s*:\s*([^;]+)", block)
        if m:
            val = m.group(1).strip().rstrip("!important").strip()
    return val


class BaseFoldSummaryPaddingTest(unittest.TestCase):
    """Base .pnx2-fold-summary must have 30 px symmetric padding."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_base_fold_summary_30px_padding(self) -> None:
        val = _last_value(self.css, r"(?:^|\n)\.pnx2-fold-summary(?![>\s]*h)", "padding")
        self.assertIsNotNone(val, ".pnx2-fold-summary padding not found")
        self.assertRegex(val, r"30px\s+0", "base fold summary padding must be 30px 0")


class SectionPaddingZeroTest(unittest.TestCase):
    """Fold-hosting sections must have zero vertical padding."""

    FOLD_SECTIONS = ["how", "demo", "forum", "wiki-section", "roadmap", "contact", "notice"]

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_section_padding_top_zero(self) -> None:
        for section_id in self.FOLD_SECTIONS:
            val = _last_value(self.css, rf"(?:^|\n|,\s*)#{re.escape(section_id)}\b", "padding-top")
            self.assertIsNotNone(val, f"#{section_id} padding-top not found")
            self.assertEqual(val, "0", f"#{section_id} must have padding-top: 0, got '{val}'")

    def test_section_padding_bottom_zero(self) -> None:
        for section_id in self.FOLD_SECTIONS:
            val = _last_value(self.css, rf"(?:^|\n|,\s*)#{re.escape(section_id)}\b", "padding-bottom")
            self.assertIsNotNone(val, f"#{section_id} padding-bottom not found")
            self.assertEqual(val, "0", f"#{section_id} must have padding-bottom: 0, got '{val}'")


class TransparencyPaddingZeroTest(unittest.TestCase):
    """#transparency must have zero vertical padding for compact fold band."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_transparency_padding_top_zero(self) -> None:
        val = _last_value(self.css, r"(?:^|\n)#transparency\b", "padding-top")
        self.assertIsNotNone(val, "#transparency padding-top not found")
        self.assertEqual(val, "0", f"#transparency must have padding-top: 0, got '{val}'")

    def test_transparency_padding_bottom_zero(self) -> None:
        val = _last_value(self.css, r"(?:^|\n)#transparency\b", "padding-bottom")
        self.assertIsNotNone(val, "#transparency padding-bottom not found")
        self.assertEqual(val, "0", f"#transparency must have padding-bottom: 0, got '{val}'")


class SeparatorBorderTest(unittest.TestCase):
    """Do not stack top borders onto the existing section bottom borders."""

    SECTIONS = ["how", "demo", "features", "forum", "roadmap", "contact"]

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_no_extra_top_borders(self) -> None:
        for section_id in self.SECTIONS:
            val = _last_value(self.css, rf"(?:^|\n|,\s*)#{re.escape(section_id)}\b", "border-top")
            self.assertNotEqual(val, "2px solid #0f172a", f"#{section_id} has a doubled separator")

    def test_notice_boundary(self) -> None:
        selector = r"(?:^|\n|,\s*)#notice\b"
        self.assertEqual(_last_value(self.css, selector, "border-top"), "0")
        self.assertEqual(_last_value(self.css, selector, "border-bottom"), "2px solid #0f172a")


class OpenStatePaddingTest(unittest.TestCase):
    """Open folds must restore bottom padding for content breathing room."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_section_fold_open_padding(self) -> None:
        rule = _find_rule(
            self.css,
            r"\.section\s*>\s*\.section-inner\s*>\s*\.pnx2-fold\[open\]",
        )
        self.assertIsNotNone(rule, ".section > .section-inner > .pnx2-fold[open] rule not found")
        self.assertRegex(rule, r"padding-bottom\s*:\s*56px", "open fold must have padding-bottom: 56px")

    def test_demo_fold_open_padding(self) -> None:
        rule = _find_rule(
            self.css,
            r"\.demo-section\s*>\s*\.pnx2-fold\[open\]",
        )
        self.assertIsNotNone(rule, ".demo-section > .pnx2-fold[open] rule not found")
        self.assertRegex(rule, r"padding-bottom\s*:\s*56px")

    def test_notice_fold_open_padding(self) -> None:
        rule = _find_rule(
            self.css,
            r"#notice\s*>\s*div\s*>\s*\.pnx2-fold\[open\]",
        )
        self.assertIsNotNone(rule, "#notice > div > .pnx2-fold[open] rule not found")
        self.assertRegex(rule, r"padding-bottom\s*:\s*56px")

    def test_transparency_fold_open_padding(self) -> None:
        rule = _find_rule(
            self.css,
            r"#transparency\s*>\s*\.pnx2-fold\[open\]",
        )
        self.assertIsNotNone(rule, "#transparency > .pnx2-fold[open] rule not found")
        self.assertRegex(rule, r"padding-bottom\s*:\s*56px")


class ReferenceOverridesIntactTest(unittest.TestCase):
    """Features and representative fold-summary overrides must still exist."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_features_fold_summary_override(self) -> None:
        rule = _find_rule(
            self.css,
            r"\.pnx2-features-fold\s*>\s*\.pnx2-fold-summary",
        )
        self.assertIsNotNone(rule, ".pnx2-features-fold > .pnx2-fold-summary rule not found")
        self.assertRegex(rule, r"padding-top\s*:\s*30px")
        self.assertRegex(rule, r"padding-bottom\s*:\s*30px")

    def test_representative_fold_summary_override(self) -> None:
        rules = _find_all_rules(
            self.css,
            r"\.pnx2-representative-fold\s*>\s*\.pnx2-fold-summary",
        )
        found = False
        for r in rules:
            if "padding-top" in r:
                found = True
                self.assertRegex(r, r"padding-top\s*:\s*30px")
                self.assertRegex(r, r"padding-bottom\s*:\s*3[02]px")
        self.assertTrue(found, "representative fold summary padding rule not found")


class NoTitleUnderlineTest(unittest.TestCase):
    """Fold summaries must not have a visible border-bottom (title underline)."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_fold_summary_no_underline(self) -> None:
        m = re.search(r"\.pnx2-fold-summary\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, ".pnx2-fold-summary rule not found")
        self.assertRegex(m.group(1), r"border-bottom\s*:\s*(0|none)", "fold summary must have border-bottom: 0")


class TypographyPreservedTest(unittest.TestCase):
    """Fold heading font-size clamp must be preserved."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_fold_heading_clamp(self) -> None:
        m = re.search(
            r"\.pnx2-fold-summary\s+h2[\s\S]*?\.pnx2-fold-summary\s+h3[\s\S]*?\{([^}]*)\}",
            self.css,
        )
        self.assertIsNotNone(m, "shared fold heading rule not found")
        self.assertRegex(
            m.group(1),
            r"font-size\s*:\s*clamp\(28px",
            "fold heading must use clamp(28px, ..., 42px)",
        )


if __name__ == "__main__":
    unittest.main()

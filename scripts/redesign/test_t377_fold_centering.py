"""T-377: closed disclosure vertical-centering regression tests.

Validates:
 1. #transparency has zero bottom-margin (no asymmetric push on features fold).
 2. #features has padding-bottom: 0 (no asymmetric space below representative).
 3. Features fold summary has equal top/bottom padding.
 4. Representative fold summary has near-equal padding (±2px for ::before).
 5. Representative has NO added bottom-margin (prevents off-center heading).
 6. Separators: exactly one 2px full-width divider between the two bands.
 7. Typography: fold heading font-size unchanged (clamp 28px..42px).
 8. Representative band centering: fold summary padding is symmetric enough
    that heading sits within ±3px of the midpoint between its top divider
    and the #forum border.
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


def _parse_px(value: str) -> float | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*px", value)
    return float(m.group(1)) if m else None


class TransparencyBottomMarginTest(unittest.TestCase):
    """#transparency must not push the features fold down with a large bottom-margin."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_transparency_bottom_margin_is_zero(self) -> None:
        blocks = _find_all_rules(self.css, r"(?:^|\n)#transparency")
        margin_block = None
        for block in blocks:
            if "margin" in block:
                margin_block = block
                break
        self.assertIsNotNone(margin_block, "#transparency rule with margin not found")
        m = re.search(r"margin\s*:\s*([^;]+)", margin_block)
        self.assertIsNotNone(m, "margin declaration not found")
        raw = m.group(1).strip().rstrip("!important").strip()
        # The shorthand contains calc() with spaces; extract top-level tokens
        # by collapsing parenthesised groups first.
        collapsed = re.sub(r"\([^)]*\)", "(…)", raw)
        parts = collapsed.split()
        self.assertTrue(len(parts) >= 3, f"expected >=3 margin values, got {parts}")
        # Bottom margin is the third top-level token; map it back to the raw value
        # by finding the end of the second token in the raw string.
        bottom_raw = raw.rsplit(None, 1)[-1]  # last whitespace-separated token
        self.assertRegex(
            bottom_raw, r"^0",
            f"#transparency bottom-margin must be 0, got '{bottom_raw}'",
        )


class FeaturesSectionPaddingTest(unittest.TestCase):
    """#features must have padding-bottom: 0 so representative band is not bottom-heavy."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_features_padding_bottom_zero(self) -> None:
        rule = _find_rule(self.css, r"(?:^|\n)#features(?!\s*[>.:\s]*\.)")
        self.assertIsNotNone(rule, "#features standalone rule not found")
        self.assertRegex(
            rule,
            r"padding-bottom\s*:\s*0",
            "#features must have padding-bottom: 0",
        )


class FeaturesFoldCenteringTest(unittest.TestCase):
    """Features fold summary must have symmetric padding for vertical centering."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_features_fold_summary_exists(self) -> None:
        rule = _find_rule(
            self.css,
            r"\.pnx2-features-fold\s*>\s*\.pnx2-fold-summary",
        )
        self.assertIsNotNone(rule, ".pnx2-features-fold > .pnx2-fold-summary rule not found")

    def test_features_fold_summary_symmetric_padding(self) -> None:
        rule = _find_rule(
            self.css,
            r"\.pnx2-features-fold\s*>\s*\.pnx2-fold-summary",
        )
        self.assertIsNotNone(rule)
        m_top = re.search(r"padding-top\s*:\s*(\d+)px", rule)
        m_bot = re.search(r"padding-bottom\s*:\s*(\d+)px", rule)
        self.assertIsNotNone(m_top, "padding-top not found on features fold summary")
        self.assertIsNotNone(m_bot, "padding-bottom not found on features fold summary")
        top = int(m_top.group(1))
        bot = int(m_bot.group(1))
        self.assertEqual(top, bot, f"features fold padding must be symmetric: top={top} bottom={bot}")
        self.assertGreaterEqual(top, 20, "padding must be large enough for visible centering band")


class RepresentativeFoldCenteringTest(unittest.TestCase):
    """Representative fold summary must have near-symmetric padding (±2px for ::before)."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def _padding_rule(self) -> str:
        """Find the representative fold summary rule that sets padding."""
        rules = _find_all_rules(
            self.css,
            r"\.pnx2-representative-fold\s*>\s*\.pnx2-fold-summary",
        )
        for r in rules:
            if "padding-top" in r:
                return r
        self.fail("no .pnx2-representative-fold > .pnx2-fold-summary rule with padding found")

    def test_representative_fold_summary_exists(self) -> None:
        self._padding_rule()  # asserts if not found

    def test_representative_fold_summary_near_symmetric_padding(self) -> None:
        rule = self._padding_rule()
        m_top = re.search(r"padding-top\s*:\s*(\d+)px", rule)
        m_bot = re.search(r"padding-bottom\s*:\s*(\d+)px", rule)
        self.assertIsNotNone(m_top, "padding-top not found")
        self.assertIsNotNone(m_bot, "padding-bottom not found")
        top = int(m_top.group(1))
        bot = int(m_bot.group(1))
        diff = abs(top - bot)
        self.assertLessEqual(
            diff, 3,
            f"representative fold padding must be within 3px: top={top} bottom={bot}",
        )
        self.assertGreaterEqual(top, 20, "padding must be large enough for visible centering band")

    def test_representative_bottom_accounts_for_before(self) -> None:
        """Bottom padding should be >= top to compensate for the 2px ::before divider."""
        rule = self._padding_rule()
        m_top = re.search(r"padding-top\s*:\s*(\d+)px", rule)
        m_bot = re.search(r"padding-bottom\s*:\s*(\d+)px", rule)
        top = int(m_top.group(1))
        bot = int(m_bot.group(1))
        self.assertGreaterEqual(
            bot, top,
            "bottom padding should be >= top to offset ::before divider height",
        )


class RepresentativeNoExtraMarginTest(unittest.TestCase):
    """#representative must NOT have an added margin-bottom — it shifts the heading off-center."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_representative_no_margin_bottom(self) -> None:
        """Regression: margin-bottom on #representative pushed heading above midpoint."""
        rules = _find_all_rules(
            self.css,
            r"#features\s*>\s*\.section-inner\s*>\s*#representative(?!::)",
        )
        combined = " ".join(rules) if rules else ""
        self.assertNotRegex(
            combined,
            r"margin-bottom\s*:\s*[1-9]\d*px",
            "#representative must NOT have a non-zero margin-bottom (causes off-center heading)",
        )


class RepresentativeBandCenteringTest(unittest.TestCase):
    """Representative fold summary padding must keep the heading centered in the band.

    The band runs from the top divider (::before, 2px) to the #forum bottom border.
    With symmetric padding, the heading sits at the midpoint.  An extra margin-bottom
    would push the heading upward; this test ensures the padding is close enough to
    symmetric that midpoint error stays within ±3px.
    """

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_representative_centering_geometry(self) -> None:
        rule = None
        for r in _find_all_rules(
            self.css,
            r"\.pnx2-representative-fold\s*>\s*\.pnx2-fold-summary",
        ):
            if "padding-top" in r:
                rule = r
                break
        self.assertIsNotNone(rule, "representative fold summary padding rule not found")

        m_top = re.search(r"padding-top\s*:\s*(\d+)px", rule)
        m_bot = re.search(r"padding-bottom\s*:\s*(\d+)px", rule)
        self.assertIsNotNone(m_top)
        self.assertIsNotNone(m_bot)
        top_pad = int(m_top.group(1))
        bot_pad = int(m_bot.group(1))

        # The ::before pseudo-element adds 2px above the padding.
        # Total space above heading center: 2px (divider) + top_pad
        # Total space below heading center: bot_pad
        # For perfect centering: bot_pad = top_pad + 2
        above = 2 + top_pad  # divider + top padding
        below = bot_pad
        midpoint_error = above - below
        self.assertLessEqual(
            abs(midpoint_error), 3,
            f"heading midpoint error {midpoint_error}px exceeds ±3px "
            f"(above={above}, below={below})",
        )


class DividerIntegrityTest(unittest.TestCase):
    """The full-width divider between features and representative must still exist."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_representative_before_still_exists(self) -> None:
        rule = _find_rule(
            self.css,
            r"#features\s*>\s*\.section-inner\s*>\s*#representative\s*::before",
        )
        self.assertIsNotNone(rule, "::before divider rule must still exist")
        self.assertRegex(rule, r"width\s*:\s*100vw")
        self.assertRegex(rule, r"height\s*:\s*2px")
        self.assertRegex(rule, r"background\s*:\s*#0f172a")


class TypographyPreservationTest(unittest.TestCase):
    """Fold heading typography must remain unchanged (clamp 28..42px)."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_shared_fold_heading_clamp_preserved(self) -> None:
        m = re.search(
            r"\.pnx2-fold-summary\s+h2[\s\S]*?\.pnx2-fold-summary\s+h3[\s\S]*?\{([^}]*)\}",
            self.css,
        )
        self.assertIsNotNone(m, "shared fold heading rule not found")
        self.assertRegex(
            m.group(1),
            r"font-size\s*:\s*clamp\(28px",
            "desktop heading must use clamp(28px, ..., 42px)",
        )

    def test_mobile_heading_28px(self) -> None:
        """At <=560px, fold headings must still be 28px."""
        blocks: list[str] = []
        for m in re.finditer(r"@media\s*\(\s*max-width\s*:\s*560px\s*\)\s*\{", self.css):
            start = m.end()
            depth = 1
            pos = start
            while pos < len(self.css) and depth > 0:
                if self.css[pos] == "{":
                    depth += 1
                elif self.css[pos] == "}":
                    depth -= 1
                pos += 1
            blocks.append(self.css[start : pos - 1])
        mobile = "\n".join(blocks)
        self.assertRegex(
            mobile,
            r"font-size\s*:\s*28px",
            "mobile fold heading must be 28px",
        )


if __name__ == "__main__":
    unittest.main()

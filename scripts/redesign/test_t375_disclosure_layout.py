"""T-375: landing disclosure layout defect regression tests.

Validates:
 1. #transparency divider spans full viewport (calc-based margins/padding).
 2. Exactly one full-width divider between features fold and representative.
 3. Representative heading uses the shared fold heading typography (clamp).
 4. No title underline on fold summaries.
 5. #features has overflow-x: clip to contain full-viewport children.
"""

from __future__ import annotations

import re
import unittest

from r2_landing_check import DOCS_DIR


CSS_PATH = DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _find_rule(css: str, selector_pattern: str) -> str | None:
    """Return the declaration block for the first rule matching *selector_pattern*."""
    m = re.search(selector_pattern + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


def _find_all_rules(css: str, selector_pattern: str) -> list[str]:
    """Return all declaration blocks for rules matching *selector_pattern*."""
    return [m.group(1) for m in re.finditer(selector_pattern + r"\s*\{([^}]*)\}", css)]


class TransparencyDividerTest(unittest.TestCase):
    """The verification (#transparency) divider must span full viewport."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def _standalone_transparency_rule(self) -> str:
        """Find the #transparency { ... } rule that is NOT inside a compound selector."""
        blocks = _find_all_rules(self.css, r"(?:^|\n)#transparency")
        self.assertTrue(len(blocks) > 0, "#transparency standalone rule not found")
        # The standalone rule has margin/padding — find it
        for block in blocks:
            if "margin" in block:
                return block
        self.fail("no #transparency rule with margin declaration found")

    def test_transparency_uses_viewport_calc_margins(self) -> None:
        rule = self._standalone_transparency_rule()
        self.assertRegex(
            rule,
            r"margin\s*:.*calc\(\s*-50vw\s*\+\s*50%\s*\)",
            "margin must use calc(-50vw + 50%) for full-viewport width",
        )

    def test_transparency_uses_viewport_calc_padding(self) -> None:
        rule = self._standalone_transparency_rule()
        self.assertRegex(
            rule,
            r"padding\s*:.*calc\(\s*50vw\s*-\s*50%\s*\)",
            "padding must use calc(50vw - 50%) to keep content aligned",
        )

    def test_transparency_has_dark_border_bottom(self) -> None:
        rule = self._standalone_transparency_rule()
        self.assertRegex(
            rule,
            r"border-bottom\s*:\s*2px\s+solid\s+#0f172a",
            "border-bottom must be 2px solid #0f172a",
        )

    def test_features_has_overflow_clip(self) -> None:
        rule = _find_rule(self.css, r"(?:^|\n)#features(?!\s*[>.:\s]*\.)(?!\s*>)")
        self.assertIsNotNone(rule, "#features standalone rule not found")
        self.assertRegex(
            rule,
            r"overflow-x\s*:\s*clip",
            "#features must have overflow-x: clip to contain full-viewport children",
        )


class FeatureRepresentativeDividerTest(unittest.TestCase):
    """Exactly one full-width divider between the features fold and representative."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_representative_before_pseudo_exists(self) -> None:
        rule = _find_rule(
            self.css,
            r"#features\s*>\s*\.section-inner\s*>\s*#representative\s*::before",
        )
        self.assertIsNotNone(rule, "::before pseudo-element rule for representative divider not found")
        self.assertRegex(rule, r"width\s*:\s*100vw")
        self.assertRegex(rule, r"height\s*:\s*2px")
        self.assertRegex(rule, r"background\s*:\s*#0f172a")

    def test_representative_before_uses_calc_margin(self) -> None:
        rule = _find_rule(
            self.css,
            r"#features\s*>\s*\.section-inner\s*>\s*#representative\s*::before",
        )
        self.assertIsNotNone(rule)
        self.assertRegex(
            rule,
            r"margin-left\s*:\s*calc\(\s*-50vw\s*\+\s*50%\s*\)",
            "pseudo-element must use calc(-50vw + 50%) to center across viewport",
        )

    def test_no_double_border_on_representative(self) -> None:
        """#representative itself must not also have a border-top (double divider)."""
        rule = _find_rule(self.css, r"(?:^|\n)#representative\b")
        self.assertIsNotNone(rule)
        self.assertNotRegex(
            rule,
            r"border-top\s*:\s*[1-9]",
            "representative must not have its own border-top (would create double divider)",
        )


class HeadingTypographyTest(unittest.TestCase):
    """Both feature and representative fold headings share the same clamp typography."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_shared_fold_heading_uses_clamp(self) -> None:
        """The shared .pnx2-fold-summary h2/h3 rule must use clamp for font-size."""
        # The rule is a multi-selector block; search for combined selector line
        m = re.search(
            r"\.pnx2-fold-summary\s+h2[\s\S]*?\.pnx2-fold-summary\s+h3[\s\S]*?\{([^}]*)\}",
            self.css,
        )
        self.assertIsNotNone(m, "shared fold heading multi-selector rule not found")
        self.assertRegex(
            m.group(1),
            r"font-size\s*:\s*clamp\(28px",
            "shared fold heading must use clamp(28px, ..., 42px)",
        )

    def test_representative_heading_no_fixed_font_size(self) -> None:
        rule = _find_rule(self.css, r"#representative\s+\.pnx2-fold-summary\s+h3")
        self.assertIsNotNone(rule, "#representative fold heading rule not found")
        self.assertNotRegex(
            rule,
            r"font-size\s*:",
            "representative heading must NOT override font-size (inherits shared clamp)",
        )

    def test_summary_no_underline(self) -> None:
        """Fold summaries must not have visible border-bottom (no underline)."""
        m = re.search(r"\.pnx2-fold-summary\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, ".pnx2-fold-summary rule not found")
        self.assertRegex(m.group(1), r"border-bottom\s*:\s*(0|none)\s*;")

    def test_no_open_state_underline(self) -> None:
        self.assertNotRegex(
            self.css,
            r"\.pnx2-fold\[open\]\s*>\s*\.pnx2-fold-summary\s*\{[^}]*border-bottom\s*:\s*[1-9]",
            "open fold summary must not gain a border-bottom underline",
        )


class MobileClippingRegressionTest(unittest.TestCase):
    """T-376: at ≤560px, #features must not clip full-width breakout children."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def _mobile_block(self) -> str:
        """Extract the @media (max-width: 560px) block content."""
        # Find the block; may appear multiple times — collect all
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
        self.assertTrue(blocks, "@media (max-width: 560px) block not found")
        return "\n".join(blocks)

    def test_features_no_horizontal_padding(self) -> None:
        mobile = self._mobile_block()
        rule = _find_rule(mobile, r"#features\b(?!\s*>)")
        self.assertIsNotNone(rule, "#features override not found in ≤560px media query")
        self.assertRegex(rule, r"padding-left\s*:\s*0", "#features must have padding-left: 0")
        self.assertRegex(rule, r"padding-right\s*:\s*0", "#features must have padding-right: 0")

    def test_features_section_inner_has_horizontal_padding(self) -> None:
        mobile = self._mobile_block()
        rule = _find_rule(mobile, r"#features\s*>\s*\.section-inner")
        self.assertIsNotNone(rule, "#features > .section-inner rule not found in ≤560px media query")
        self.assertRegex(rule, r"padding-left\s*:\s*20px", ".section-inner must have padding-left: 20px")
        self.assertRegex(rule, r"padding-right\s*:\s*20px", ".section-inner must have padding-right: 20px")


if __name__ == "__main__":
    unittest.main()

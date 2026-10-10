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


def _split_mobile_560(css: str) -> tuple[str, str]:
    """Separate the existing 560px blocks, not a CSS cascade/media-query parser."""
    outside: list[str] = []
    mobile: list[str] = []
    cursor = 0
    for match in re.finditer(r"@media\s*\(\s*max-width\s*:\s*560px\s*\)\s*\{", css):
        start = match.end()
        depth, pos = 1, start
        while pos < len(css) and depth:
            depth += (css[pos] == "{") - (css[pos] == "}")
            pos += 1
        assert depth == 0, "Unclosed 560px media block"
        outside.append(css[cursor:match.start()])
        mobile.append(css[start:pos - 1])
        cursor = pos
    outside.append(css[cursor:])
    return "".join(outside), "\n".join(mobile)


SHARED_HEADING_SELECTOR = (
    r"\.pnx2-fold-summary\s+h2\s*,\s*"
    r"\.pnx2-fold-summary\s+h3\s*,\s*"
    r"\.pnx2-fold-summary\s+\.demo-title"
)


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
        rules = _find_all_rules(
            self.css,
            r"#features\s*>\s*\.section-inner\s*>\s*#representative\s*::before",
        )
        self.assertTrue(rules, "::before pseudo-element rule for representative divider not found")
        widths = [value.strip() for rule in rules for value in re.findall(r"(?:^|;)\s*width\s*:\s*([^;]+)", rule)]
        self.assertTrue(widths, "divider width declaration not found")
        for width in widths:
            self.assertRegex(width, r"^100vw(?:\s*!important)?$", "every explicit divider width must remain 100vw")
        rule = rules[0]
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
        outside_mobile, _ = _split_mobile_560(self.css)
        rules = _find_all_rules(outside_mobile, SHARED_HEADING_SELECTOR)
        self.assertTrue(rules, "shared fold heading multi-selector rule not found")
        sizes = [value.strip() for rule in rules for value in re.findall(r"(?:^|;)\s*font-size\s*:\s*([^;]+)", rule)]
        self.assertTrue(sizes, "shared heading font-size declaration not found")
        for size in sizes:
            self.assertRegex(size, r"^clamp\(28px\s*,\s*3rem\s*,\s*42px\)(?:\s*!important)?$")

    def test_shared_mobile_heading_keeps_legitimate_28px_override(self) -> None:
        _, mobile = _split_mobile_560(self.css)
        rules = _find_all_rules(mobile, SHARED_HEADING_SELECTOR)
        self.assertTrue(rules, "shared mobile heading rule not found")
        sizes = [value.strip() for rule in rules for value in re.findall(r"(?:^|;)\s*font-size\s*:\s*([^;]+)", rule)]
        self.assertTrue(sizes)
        for size in sizes:
            self.assertRegex(size, r"^28px(?:\s*!important)?$")

    def test_representative_heading_no_fixed_font_size(self) -> None:
        rules = _find_all_rules(self.css, r"#representative\s+\.pnx2-fold-summary\s+h3")
        self.assertTrue(rules, "#representative fold heading rule not found")
        for rule in rules:
            self.assertNotRegex(rule, r"font-size\s*:", "individual representative heading must inherit shared desktop/mobile typography")

    def test_summary_no_underline(self) -> None:
        """Fold summaries must not have visible border-bottom (no underline)."""
        rules = _find_all_rules(self.css, r"\.pnx2-fold-summary")
        self.assertTrue(rules, ".pnx2-fold-summary rule not found")
        borders = [value.strip() for rule in rules for value in re.findall(r"(?:^|;)\s*border-bottom\s*:\s*([^;]+)", rule)]
        self.assertTrue(borders, "summary border-bottom declaration not found")
        for border in borders:
            self.assertRegex(border, r"^(?:0|none)(?:\s*!important)?$", "every explicit summary border-bottom must suppress the underline")

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
        _, mobile = _split_mobile_560(self.css)
        self.assertTrue(mobile, "@media (max-width: 560px) block not found")
        return mobile

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


class LateOverrideMutationTest(unittest.TestCase):
    """Negative source fixtures; no specificity engine or rendered-layout proof."""

    def setUp(self) -> None:
        self.css = _strip_comments(CSS_PATH.read_text())

    def test_late_individual_heading_override_is_rejected(self) -> None:
        for declaration in (
            "#representative .pnx2-fold-summary h3 { font-size: 20px !important; }",
            "@media (max-width: 560px) { #representative .pnx2-fold-summary h3 { font-size: 20px !important; } }",
        ):
            with self.subTest(declaration=declaration):
                contract = HeadingTypographyTest()
                contract.css = self.css + "\n" + declaration
                with self.assertRaises(AssertionError):
                    contract.test_representative_heading_no_fixed_font_size()

    def test_late_summary_underline_is_rejected(self) -> None:
        contract = HeadingTypographyTest()
        contract.css = self.css + "\n.pnx2-fold-summary { border-bottom: 2px solid #0f172a; }"
        with self.assertRaises(AssertionError):
            contract.test_summary_no_underline()

    def test_late_divider_width_override_is_rejected(self) -> None:
        contract = FeatureRepresentativeDividerTest()
        contract.css = self.css + "\n#features > .section-inner > #representative::before { width: 80%; }"
        with self.assertRaises(AssertionError):
            contract.test_representative_before_pseudo_exists()


if __name__ == "__main__":
    unittest.main()

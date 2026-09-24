"""Keep landing disclosure titles unlined in both states."""

from __future__ import annotations

import re
import unittest

from r2_landing_check import DOCS_DIR


class DisclosureUnderlineTest(unittest.TestCase):
    def test_summary_has_no_border_in_either_state(self) -> None:
        css = (DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css").read_text()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        summary = re.search(r"\.pnx2-fold-summary\s*\{([^}]*)\}", css)
        self.assertIsNotNone(summary)
        self.assertRegex(summary.group(1), r"border-bottom\s*:\s*(0|none)\s*;")
        self.assertNotRegex(
            css,
            r"\.pnx2-fold(?:\[open\])?\s*>\s*\.pnx2-fold-summary\s*\{[^}]*border-bottom",
        )

    def test_section_divider_remains(self) -> None:
        css = (DOCS_DIR / "assets/redesign-v2/r2-landing.css").read_text()
        section = re.search(r"\.section\s*\{([^}]*)\}", css)
        self.assertIsNotNone(section)
        self.assertRegex(section.group(1), r"border-bottom\s*:\s*[1-9]\d*px\s+solid\b")

    def test_verification_band_matches_white_landing_with_dark_divider(self) -> None:
        css = (DOCS_DIR / "assets/redesign-v2/r5-landing-fidelity.css").read_text()
        verification = re.search(
            r"#features\s*>\s*\.section-inner\s*>\s*#transparency\s*\{([^}]*)\}",
            css,
        )
        self.assertIsNotNone(verification)
        self.assertRegex(verification.group(1), r"background\s*:\s*#fff\s*!important")
        self.assertRegex(
            verification.group(1),
            r"border-bottom\s*:\s*2px\s+solid\s+#0f172a\s*!important",
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Focused tests for scripts/redesign/r1_foundation_check.py.

Violation fixtures are built in temporary directories; the real foundation
directory is never modified. Run with:
python3 -m unittest scripts/redesign/test_r1_foundation_check.py
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import r1_foundation_check  # noqa: E402  (same-directory import)

REAL_FOUNDATION = r1_foundation_check.FOUNDATION_DIR

MINIMAL_TOKENS = """:root {
  --pnx2-accent: #2563eb;
  --pnx2-accent-dark: #1d4ed8;
  --pnx2-ink: #0f172a;
  --pnx2-body: #334155;
  --pnx2-muted: #64748b;
  --pnx2-border-mid: #e2e8f0;
  --pnx2-border-weak: #f1f5f9;
  --pnx2-bg: #ffffff;
  --pnx2-bg-tinted: #f8fafc;
  --pnx2-on-accent: #eff6ff;
  --pnx2-on-ink: #cbd5e1;
  --pnx2-selection: #dbeafe;
  --pnx2-target-min: 44px;
}
"""

MINIMAL_CSS = """a:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.pnx2-container { max-width: var(--pnx2-content-max); }
.pnx2-btn { min-height: 48px; }
.pnx2-nav a { min-height: var(--pnx2-target-min); }
.pnx2-loading { color: gray; }
.pnx2-error { color: red; }
.pnx2-empty { color: gray; }
@media (max-width: 640px) { .pnx2-nav { justify-content: flex-start; } }
"""

MINIMAL_HTML = """<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>fixture</title>
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="foundation.css">
</head>
<body>
<p class="pnx2-loading" role="status" aria-live="polite">load</p>
<p class="pnx2-error" role="alert">err</p>
<p class="pnx2-empty" role="status">empty</p>
</body>
</html>
"""

MINIMAL_README = """# fixture
Isolation notes. CSP posture. Documented fallback. Unresolved gate list.
"""


def build_fixture(root: Path, overrides: dict[str, str] | None = None) -> None:
    files = {
        "tokens.css": MINIMAL_TOKENS,
        "foundation.css": MINIMAL_CSS,
        "index.html": MINIMAL_HTML,
        "README.md": MINIMAL_README,
    }
    if overrides:
        files.update(overrides)
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")


class RealFoundationTest(unittest.TestCase):
    def test_real_foundation_passes(self) -> None:
        self.assertEqual([], r1_foundation_check.check_foundation(REAL_FOUNDATION))


class FixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def violations_for(self, overrides: dict[str, str]) -> list[str]:
        build_fixture(self.tmp, overrides)
        return r1_foundation_check.check_foundation(self.tmp)

    def test_minimal_valid_fixture_passes(self) -> None:
        build_fixture(self.tmp)
        self.assertEqual([], r1_foundation_check.check_foundation(self.tmp))

    def test_missing_file_fails(self) -> None:
        build_fixture(self.tmp)
        (self.tmp / "tokens.css").unlink()
        violations = r1_foundation_check.check_foundation(self.tmp)
        self.assertTrue(any("missing required file: tokens.css" in v for v in violations))

    def test_external_http_reference_fails(self) -> None:
        violations = self.violations_for({"tokens.css": MINIMAL_TOKENS + '\n@import url("https://fonts.example.com/x.css");\n'})
        self.assertTrue(any("http(s)" in v for v in violations))

    def test_script_tag_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace("</body>", "<script src=\"x.js\"></script>\n</body>")})
        self.assertTrue(any("<script>" in v for v in violations))

    def test_inline_event_handler_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace("<body>", '<body onload="go()">')})
        self.assertTrue(any("inline event handler" in v for v in violations))

    def test_inline_style_attribute_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace("<body>", '<body style="margin:0">')})
        self.assertTrue(any("inline style" in v for v in violations))

    def test_support_js_reference_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace("</body>", "<p>loads support.js</p>\n</body>")})
        self.assertTrue(any("support.js" in v for v in violations))

    def test_support_js_allowed_in_comments_only(self) -> None:
        # comments may document the exclusion; they must not trip the check
        build_fixture(self.tmp, {"index.html": MINIMAL_HTML.replace("</body>", "<!-- no support.js here -->\n</body>")})
        self.assertEqual([], r1_foundation_check.check_foundation(self.tmp))

    def test_missing_viewport_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace('<meta name="viewport" content="width=device-width,initial-scale=1.0">\n', "")})
        self.assertTrue(any("viewport" in v for v in violations))

    def test_missing_lang_el_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace('lang="el"', 'lang="en"')})
        self.assertTrue(any('lang="el"' in v for v in violations))

    def test_missing_focus_hook_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS.replace("a:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }\n", "")})
        self.assertTrue(any("focus-visible" in v for v in violations))

    def test_missing_state_hook_fails(self) -> None:
        violations = self.violations_for({"index.html": MINIMAL_HTML.replace('<p class="pnx2-error" role="alert">err</p>\n', "")})
        self.assertTrue(any("pnx2-error" in v for v in violations))

    def test_missing_aria_semantics_fails(self) -> None:
        stripped = MINIMAL_HTML.replace(' role="status" aria-live="polite"', "").replace(' role="alert"', "").replace(' role="status"', "")
        violations = self.violations_for({"index.html": stripped})
        self.assertTrue(any("aria-live/role" in v for v in violations))

    def test_fixed_width_trap_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\n.box { width: 960px; }\n"})
        self.assertTrue(any("960px" in v for v in violations))

    def test_overflow_x_hidden_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\nhtml { overflow-x: hidden; }\n"})
        self.assertTrue(any("overflow-x: hidden" in v for v in violations))

    def test_nonzero_border_radius_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\n.card { border-radius: 8px; }\n"})
        self.assertTrue(any("border-radius" in v for v in violations))

    def test_gradient_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\n.band { background: linear-gradient(#fff, #eee); }\n"})
        self.assertTrue(any("gradient" in v for v in violations))

    def test_negative_letter_spacing_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\nh1 { letter-spacing: -0.02em; }\n"})
        self.assertTrue(any("negative letter-spacing" in v for v in violations))

    def test_viewport_scaled_font_size_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\nh1 { font-size: 6vw; }\n"})
        self.assertTrue(any("viewport-scaled font size" in v for v in violations))

    def test_shadow_fails(self) -> None:
        violations = self.violations_for({"foundation.css": MINIMAL_CSS + "\n.card { box-shadow: 0 2px 8px #000; }\n"})
        self.assertTrue(any("box-shadow" in v for v in violations))

    def test_missing_token_value_fails(self) -> None:
        violations = self.violations_for({"tokens.css": MINIMAL_TOKENS.replace("#2563eb", "#0000ff")})
        self.assertTrue(any("--pnx2-accent" in v for v in violations))

    def test_readme_keywords_required(self) -> None:
        violations = self.violations_for({"README.md": "# empty\n"})
        self.assertTrue(any("README.md" in v for v in violations))


if __name__ == "__main__":
    unittest.main()

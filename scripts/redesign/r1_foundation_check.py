#!/usr/bin/env python3
"""R1 foundation validator for design/redesign-v2/foundation/.

Stdlib-only, deterministic, same family as scripts/redesign/r0_inventory.py.
Fails (exit 1) if the isolated foundation violates any of its documented
constraints:

- no http(s) references, no scripts, no inline event handlers, no support.js
- viewport meta and lang="el" present on the demo
- visible keyboard focus hook (:focus-visible with outline)
- loading/error/empty state hooks with ARIA live semantics
- no horizontal fixed-width traps (no width > 360px, no 100vw, no
  overflow-x: hidden), sub-44px targets, nonzero border-radius, gradients
  or shadows
- required handoff token values present

Run: python3 scripts/redesign/r1_foundation_check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FOUNDATION_DIR = REPO_ROOT / "design" / "redesign-v2" / "foundation"

REQUIRED_FILES = ("tokens.css", "foundation.css", "index.html", "README.md")

REQUIRED_TOKENS = {
    "--pnx2-accent": "#2563eb",
    "--pnx2-accent-dark": "#1d4ed8",
    "--pnx2-ink": "#0f172a",
    "--pnx2-body": "#334155",
    "--pnx2-muted": "#64748b",
    "--pnx2-border-mid": "#e2e8f0",
    "--pnx2-border-weak": "#f1f5f9",
    "--pnx2-bg": "#ffffff",
    "--pnx2-bg-tinted": "#f8fafc",
    "--pnx2-on-accent": "#eff6ff",
    "--pnx2-on-ink": "#cbd5e1",
    "--pnx2-selection": "#dbeafe",
}

HTTP_RE = re.compile(r"https?://", re.I)
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
INLINE_HANDLER_RE = re.compile(r"<[^>]+\son[a-zA-Z]+\s*=")
INLINE_STYLE_RE = re.compile(r"<[^>]+\sstyle\s*=", re.I)
VIEWPORT_RE = re.compile(r'<meta[^>]+name="viewport"[^>]+width=device-width', re.I)
LANG_EL_RE = re.compile(r'<html[^>]+\blang="el"', re.I)
FOCUS_RE = re.compile(r":focus-visible[^{]*\{[^}]*outline")
PX_WIDTH_RE = re.compile(r"(?<![-\w])width\s*:\s*(\d+)px")
RADIUS_RE = re.compile(r"border-radius\s*:\s*([^;]+);")
SHADOW_RE = re.compile(r"box-shadow\s*:\s*([^;]+);")
MIN_HEIGHT_RE = re.compile(r"min-height\s*:\s*(\d+)px")


def check_foundation(root: Path) -> list[str]:
    violations: list[str] = []

    texts: dict[str, str] = {}
    for name in REQUIRED_FILES:
        path = root / name
        if not path.is_file():
            violations.append(f"missing required file: {name}")
        else:
            texts[name] = path.read_text(encoding="utf-8")
    if violations:
        return violations

    code_files = {k: v for k, v in texts.items() if k.endswith((".css", ".html"))}
    # comments may legitimately name forbidden patterns (e.g. "no support.js")
    stripped_files = {
        name: HTML_COMMENT_RE.sub("", CSS_COMMENT_RE.sub("", content))
        for name, content in code_files.items()
    }

    for name, content in stripped_files.items():
        if HTTP_RE.search(content):
            violations.append(f"{name}: external http(s) reference found")
        if "support.js" in content:
            violations.append(f"{name}: reference to prototype support.js")
        if "<script" in content.lower():
            violations.append(f"{name}: <script> tag is not allowed in the foundation")
        if INLINE_HANDLER_RE.search(content):
            violations.append(f"{name}: inline event handler attribute found")
        if name.endswith(".html") and INLINE_STYLE_RE.search(content):
            violations.append(f"{name}: inline style attribute found")

    html = texts["index.html"]
    css = texts["foundation.css"]
    tokens = texts["tokens.css"]
    readme = texts["README.md"]

    if not VIEWPORT_RE.search(html):
        violations.append("index.html: missing viewport meta with width=device-width")
    if not LANG_EL_RE.search(html):
        violations.append('index.html: root element must carry lang="el"')
    for stylesheet in ("tokens.css", "foundation.css"):
        if f'href="{stylesheet}"' not in html:
            violations.append(f"index.html: does not reference {stylesheet}")

    if not FOCUS_RE.search(css):
        violations.append("foundation.css: missing :focus-visible rule with an outline")

    for state_class in ("pnx2-loading", "pnx2-error", "pnx2-empty"):
        if state_class not in html or state_class not in css:
            violations.append(f"state hook {state_class} missing from index.html or foundation.css")
    if not re.search(r'aria-live|role="status"|role="alert"', html):
        violations.append("index.html: states lack aria-live/role semantics")

    for name, content in stripped_files.items():
        if re.search(r"overflow-x\s*:\s*hidden", content):
            violations.append(f"{name}: overflow-x: hidden is forbidden (breaks sticky header; use clip)")
        if re.search(r"(?<![-\w])width\s*:\s*100vw", content):
            violations.append(f"{name}: width: 100vw is a horizontal-scroll trap")
        for match in PX_WIDTH_RE.finditer(content):
            if int(match.group(1)) > 360:
                violations.append(f"{name}: fixed width {match.group(1)}px exceeds the 360px viewport budget")
        for match in RADIUS_RE.finditer(content):
            if match.group(1).strip() not in ("0", "var(--pnx2-radius)"):
                violations.append(f"{name}: nonzero border-radius {match.group(1).strip()!r} (handoff mandates 0)")
        if "linear-gradient" in content:
            violations.append(f"{name}: gradients are forbidden by the handoff")
        if re.search(r"letter-spacing\s*:\s*-", content):
            violations.append(f"{name}: negative letter-spacing is forbidden")
        if re.search(r"font-size\s*:[^;]*(?:\d|\.)vw", content):
            violations.append(f"{name}: viewport-scaled font size is forbidden")
        for match in SHADOW_RE.finditer(content):
            if match.group(1).strip() != "none":
                violations.append(f"{name}: box-shadow is forbidden by the handoff")

    min_heights = [int(m.group(1)) for m in MIN_HEIGHT_RE.finditer(css)]
    if not any(h >= 44 for h in min_heights):
        violations.append("foundation.css: no min-height >= 44px interaction target declared")
    if 48 not in min_heights and "var(--pnx2-button-height)" not in css:
        violations.append("foundation.css: buttons must keep the 48px minimum height")
    if "--pnx2-target-min: 44px" not in tokens:
        violations.append("tokens.css: --pnx2-target-min must be 44px")
    if "var(--pnx2-target-min)" not in css:
        violations.append("foundation.css: interaction targets must use var(--pnx2-target-min)")

    for token, value in REQUIRED_TOKENS.items():
        if f"{token}: {value}" not in tokens:
            violations.append(f"tokens.css: required token {token}: {value} missing or changed")
    if "max-width: var(--pnx2-content-max)" not in css:
        violations.append("foundation.css: content container must use the token-based max-width")
    if "@media" not in css:
        violations.append("foundation.css: no responsive media query present")

    for keyword in ("Isolation", "CSP", "fallback", "gate"):
        if keyword.lower() not in readme.lower():
            violations.append(f"README.md: required section keyword {keyword!r} missing")

    return violations


def main() -> int:
    violations = check_foundation(FOUNDATION_DIR)
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        return 1
    print(f"R1 foundation check passed ({FOUNDATION_DIR.relative_to(REPO_ROOT)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

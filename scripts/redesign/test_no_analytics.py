#!/usr/bin/env python3
"""Regression test: no analytics scripts in public HTML pages.

Ensures the Plausible analytics script and any preconnect/dns-prefetch
to analytics.ekklesia.gr are permanently absent from every allowlisted
public HTML page (EKA-33 resolution).

Run with: python3 -m pytest scripts/redesign/test_no_analytics.py -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = REPO_ROOT / "docs/planning/r0/PUBLIC_HTML_ALLOWLIST.txt"

# Patterns that must never appear in public pages
_ANALYTICS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Plausible script loader", re.compile(r"analytics\.ekklesia\.gr/js/script\.js", re.IGNORECASE)),
    ("analytics preconnect", re.compile(r'rel=["\'](?:preconnect|dns-prefetch)["\'].*analytics\.ekklesia\.gr', re.IGNORECASE)),
    ("Plausible data-domain", re.compile(r'data-domain=["\']ekklesia\.gr["\']', re.IGNORECASE)),
]


class TestNoAnalyticsInPublicHTML(unittest.TestCase):
    """Every allowlisted public HTML page must be free of analytics scripts."""

    def test_no_plausible_references_in_any_public_page(self) -> None:
        self.assertTrue(ALLOWLIST.is_file(), "PUBLIC_HTML_ALLOWLIST.txt missing")
        paths = [
            line.strip()
            for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        paths.append("docs/wiki/audit.html")
        self.assertGreater(len(paths), 0, "allowlist is empty")

        violations: list[str] = []
        for rel_path in paths:
            html_file = REPO_ROOT / rel_path
            if not html_file.is_file():
                continue  # missing files are caught by r0_inventory
            content = html_file.read_text(encoding="utf-8")
            for label, pattern in _ANALYTICS_PATTERNS:
                if pattern.search(content):
                    violations.append(f"{rel_path}: {label}")

        self.assertEqual(
            [],
            violations,
            "Analytics references found in public HTML — these must stay removed (EKA-33):\n"
            + "\n".join(f"  - {v}" for v in violations),
        )


if __name__ == "__main__":
    unittest.main()

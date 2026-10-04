"""T-473 (#365): the FAQ language toggle must keep ``<html lang>`` in sync.

Runs the page's own inline ``toggleLang`` in Node against a minimal DOM stub:
first toggle -> English copy and ``lang="en"``, second toggle -> Greek and
``lang="el"``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FAQ = REPO / "docs/wiki/faq.html"

HARNESS = r"""
const src = require("fs").readFileSync(0, "utf8");
const html = { lang: "el" };
const btn = { textContent: "EN" };
const item = {
  innerHTML: "ΕΛ",
  attrs: { "data-el": "ΕΛ", "data-en": "EN" },
  getAttribute(name) { return this.attrs[name] || null; },
};
global.document = {
  documentElement: html,
  getElementById: (id) => (id === "langBtn" ? btn : null),
  querySelectorAll: (sel) => (sel === "[data-el]" ? [item] : []),
};
global.IntersectionObserver = function () { this.observe = function () {}; };
eval(src);
const out = [];
toggleLang();
out.push({ lang: html.lang, text: item.innerHTML, button: btn.textContent });
toggleLang();
out.push({ lang: html.lang, text: item.innerHTML, button: btn.textContent });
process.stdout.write(JSON.stringify(out));
"""


def toggle_script() -> str:
    html = FAQ.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    matches = [b for b in blocks if "function toggleLang" in b]
    if len(matches) != 1:
        raise AssertionError(f"expected one inline toggleLang script, found {len(matches)}")
    return matches[0]


@unittest.skipUnless(shutil.which("node"), "node is required to execute the inline script")
class FaqToggleLangTest(unittest.TestCase):
    def test_toggle_updates_document_lang_both_ways(self) -> None:
        run = subprocess.run(
            ["node", "-e", HARNESS], input=toggle_script(),
            capture_output=True, text=True, check=True, timeout=30,
        )
        first, second = json.loads(run.stdout)
        self.assertEqual(first, {"lang": "en", "text": "EN", "button": "ΕΛ"})
        self.assertEqual(second, {"lang": "el", "text": "ΕΛ", "button": "EN"})


if __name__ == "__main__":
    unittest.main()

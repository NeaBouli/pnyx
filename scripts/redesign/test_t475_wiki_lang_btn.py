"""T-475: the R3 wiki language switch is reachable in the initial 390px nav view.

At <=920px ``r3-wiki.css`` turns ``.nav-links`` into a nowrap horizontal
scroller and ``#langBtn`` is its last child, so without a pin it starts far
off-screen (x=1460 at 390px, T-474). The fix pins only ``.lang-btn`` to the
scroller's inline end inside the existing 920px block; DOM and focus order
stay unchanged. The static tests pin the narrowest rule; the optional browser
test (Playwright, local file:// only, all other requests aborted) proves the
button is hit-testable before any scroll on every bilingual R3 wiki page.

T-479 (review F1): while pinned, the button's right edge is the scroller's
overflow clip edge, so the foundation focus ring (2px outline, +2px offset) was
cut off on reverse keyboard entry. The pinned button draws its ring inside;
the browser test checks the computed ring lies within the nav clip rectangle.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSS = REPO / "docs/assets/redesign-v2/r3-wiki.css"
TOKENS = REPO / "docs/assets/redesign-v2/tokens.css"
WIKI = REPO / "docs/wiki"
PAGES = [
    "api", "architecture", "audit", "broadcasting", "contributing", "database",
    "delete-account", "faq", "index", "modules", "privacy", "roadmap",
    "security", "whitepaper", "zk-voting",
]
PIN = ".pnx2-header .nav-links > .lang-btn"
RAISE = ".pnx2-header .nav-links > a:focus-visible"
PIN_FOCUS = f"{PIN}:focus-visible"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _split_media(css: str, max_width: int) -> tuple[str, str]:
    """Return (inside, outside) of the single ``@media (max-width: Npx)`` block."""
    matches = list(re.finditer(rf"@media\s*\(\s*max-width\s*:\s*{max_width}px\s*\)\s*\{{", css))
    if len(matches) != 1:
        raise AssertionError(f"expected one {max_width}px block, found {len(matches)}")
    start = pos = matches[0].end()
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(css[pos], 0)
        pos += 1
    return css[start:pos - 1], css[:matches[0].start()] + css[pos:]


def _rules(css: str) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = dict(
            (k.strip(), v.strip())
            for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d)
        )
        for s in sel.split(","):
            rules.setdefault(" ".join(s.split()), {}).update(decls)
    return rules


class LangButtonPinTest(unittest.TestCase):
    def setUp(self) -> None:
        css = _strip_comments(CSS.read_text(encoding="utf-8"))
        inside, self.outside = _split_media(css, 920)
        self.rules = _rules(inside)

    def test_scroller_still_exists_so_pin_is_required(self) -> None:
        nav = self.rules[".pnx2-header .nav-links"]
        self.assertEqual(nav.get("flex-wrap"), "nowrap")
        self.assertEqual(nav.get("overflow-x"), "auto")

    def test_button_is_pinned_to_inline_end(self) -> None:
        pin = self.rules.get(PIN)
        self.assertIsNotNone(pin, f"{PIN} rule missing from the 920px block")
        self.assertEqual(pin.get("position"), "sticky")
        end = pin.get("inset-inline-end") or pin.get("right")
        self.assertIsNotNone(end, "sticky pin needs an inline-end offset")
        self.assertNotIn("left", pin)
        self.assertNotIn("inset-inline-start", pin)
        self.assertGreater(int(pin.get("z-index", "0")), 0)

    def test_no_reordering_or_desktop_change(self) -> None:
        for sel, decls in self.rules.items():
            if "nav-links" in sel:
                self.assertNotIn("order", decls, sel)
        self.assertNotIn("sticky", self.outside, "pin must stay inside the 920px block")

    def test_links_scroll_clear_of_pin_and_focus_is_not_obscured(self) -> None:
        pad = self.rules[".pnx2-header .nav-links"].get("scroll-padding-inline-end", "")
        self.assertIn("--pnx2-target-min", pad)
        raise_rule = self.rules.get(RAISE, {})
        self.assertEqual(raise_rule.get("position"), "relative")
        self.assertGreater(int(raise_rule.get("z-index", "0")), int(self.rules[PIN]["z-index"]))

    def test_button_background_is_opaque(self) -> None:
        base = _rules(self.outside)[".pnx2-header .lang-btn"]
        self.assertEqual(base.get("background"), "var(--pnx2-bg)")
        token = re.search(r"--pnx2-bg:\s*([^;]+);", TOKENS.read_text(encoding="utf-8"))
        self.assertRegex(token.group(1).strip(), r"^#[0-9a-fA-F]{6}$")

    def test_pinned_focus_ring_is_drawn_inside_the_button(self) -> None:
        offset = self.rules.get(PIN_FOCUS, {}).get("outline-offset", "")
        m = re.fullmatch(r"calc\(-(\d+) \* var\(--pnx2-focus-offset\)\)", offset)
        self.assertIsNotNone(m, f"{PIN_FOCUS} needs a token-bound inset outline-offset")
        tokens = TOKENS.read_text(encoding="utf-8")
        width = int(re.search(r"--pnx2-focus-outline:\s*(\d+)px", tokens).group(1))
        token = int(re.search(r"--pnx2-focus-offset:\s*(\d+)px", tokens).group(1))
        # Outer ring edge = width + offset; it must not reach past the border box.
        self.assertLessEqual(width - int(m.group(1)) * token, 0)
        self.assertNotIn("focus-visible", _rules(self.outside).get(PIN_FOCUS, {}))

    def test_lang_button_is_last_direct_child_on_every_page(self) -> None:
        for name in PAGES:
            html = (WIKI / f"{name}.html").read_text(encoding="utf-8")
            nav = re.search(r'<div class="nav-links">(.*?)</div>', html, re.S)
            self.assertIsNotNone(nav, name)
            tail = nav.group(1).strip()
            self.assertRegex(
                tail, r'<button class="lang-btn"[^>]*id="langBtn"[^>]*>[^<]*</button>$', name
            )


BROWSER = r"""
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const b = await chromium.launch();
  const out = {};
  for (const url of JSON.parse(process.argv[1])) {
    const page = await b.newPage({ viewport: { width: 390, height: 844 } });
    await page.route("**/*", r => r.request().url().startsWith("file:") ? r.continue() : r.abort());
    await page.goto(url, { waitUntil: "load" });
    out[path.basename(url)] = await page.evaluate(() => {
      const nav = document.querySelector(".pnx2-header .nav-links");
      const btn = document.getElementById("langBtn");
      const n = nav.getBoundingClientRect(), r = btn.getBoundingClientRect();
      const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
      return { scrollLeft: nav.scrollLeft, left: r.left, right: r.right, navRight: n.right,
               vw: innerWidth, hit: hit === btn,
               overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
    });
    await page.close();
  }
  await b.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(2); });
"""


def _playwright_available() -> bool:
    if not shutil.which("node"):
        return False
    probe = subprocess.run(
        ["node", "-e", "require(process.env.PLAYWRIGHT_MODULE || 'playwright')"],
        capture_output=True, cwd=REPO,
    )
    return probe.returncode == 0


# Reverse keyboard entry (Shift+Tab from the first focusable after the nav) on a
# fresh page keeps the pin engaged; forward Tab reaches the button at scroll end.
FOCUS = r"""
const { chromium, webkit } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const [url, engines] = JSON.parse(process.argv[1]);
const ring = () => {
  const nav = document.querySelector(".pnx2-header .nav-links");
  const btn = document.getElementById("langBtn");
  const cs = getComputedStyle(btn), b = btn.getBoundingClientRect(), n = nav.getBoundingClientRect();
  const e = parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset);
  const left = n.left + nav.clientLeft, top = n.top + nav.clientTop;
  return { focused: document.activeElement === btn, visible: btn.matches(":focus-visible"),
           style: cs.outlineStyle, position: cs.position, scrollLeft: nav.scrollLeft,
           ring: [b.left - e, b.top - e, b.right + e, b.bottom + e],
           clip: [left, top, left + nav.clientWidth, top + nav.clientHeight] };
};
(async () => {
  const out = {};
  for (const name of engines) {
    const b = await { chromium, webkit }[name].launch();
    const mod = name === "webkit" ? "Alt+" : "";
    for (const width of [390, 840]) {
      for (const dir of ["reverse", "forward"]) {
        const page = await b.newPage({ viewport: { width, height: 844 } });
        await page.route("**/*", r => r.request().url().startsWith("file:") ? r.continue() : r.abort());
        await page.goto(url, { waitUntil: "load" });
        if (dir === "reverse") {
          await page.evaluate(() => {
            const all = [...document.querySelectorAll("a[href], button, input, select, textarea, [tabindex]")];
            all[all.indexOf(document.getElementById("langBtn")) + 1].focus();
          });
          await page.keyboard.press(mod + "Shift+Tab");
        } else {
          for (let i = 0; i < 60 && !(await page.evaluate(() => document.activeElement.id === "langBtn")); i++)
            await page.keyboard.press(mod + "Tab");
        }
        // Page CSS has `.lang-btn { transition: all 0.2s }`: measure the settled ring.
        await page.evaluate(() => Promise.all(document.getElementById("langBtn").getAnimations().map(a => a.finished)));
        out[`${name}/${width}/${dir}`] = await page.evaluate(ring);
        await page.close();
      }
    }
    await b.close();
  }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(2); });
"""


@unittest.skipUnless(_playwright_available(), "node + playwright (PLAYWRIGHT_MODULE) required")
class LangButtonInitialViewBrowserTest(unittest.TestCase):
    def test_button_visible_and_hit_before_any_scroll_at_390(self) -> None:
        urls = [(WIKI / f"{name}.html").as_uri() for name in PAGES]
        run = subprocess.run(
            ["node", "-e", BROWSER, json.dumps(urls)],
            capture_output=True, text=True, timeout=300, cwd=REPO,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        for page, m in json.loads(run.stdout).items():
            with self.subTest(page=page):
                self.assertEqual(m["scrollLeft"], 0)
                self.assertGreaterEqual(m["left"], 0)
                self.assertLessEqual(m["right"], min(m["vw"], m["navRight"]) + 0.5)
                self.assertTrue(m["hit"], "elementFromPoint must hit #langBtn")
                self.assertEqual(m["overflow"], 0)

    def test_focus_ring_inside_nav_clip_forward_and_reverse(self) -> None:
        run = subprocess.run(
            ["node", "-e", FOCUS, json.dumps([(WIKI / "faq.html").as_uri(), ["chromium", "webkit"]])],
            capture_output=True, text=True, timeout=300, cwd=REPO,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        results = json.loads(run.stdout)
        self.assertEqual(len(results), 8)
        for key, m in results.items():
            with self.subTest(case=key):
                self.assertTrue(m["focused"] and m["visible"], "button must hold :focus-visible")
                self.assertEqual(m["style"], "solid")
                self.assertEqual(m["position"], "sticky")
                (rl, rt, rr, rb), (cl, ct, cr, cb) = m["ring"], m["clip"]
                self.assertGreaterEqual(rl, cl - 0.01)
                self.assertGreaterEqual(rt, ct - 0.01)
                self.assertLessEqual(rr, cr + 0.01)
                self.assertLessEqual(rb, cb + 0.01)


if __name__ == "__main__":
    unittest.main()

// T-420 (EKA-50/51/52) browser gate for the module/database wiki pages and the
// navigation pages touched by the footer/nav fixes.
// Serves the static docs/ tree locally and drives it in Chromium and WebKit at
// 1440px and 390px. Every non-local request is aborted, so nothing reaches
// production.
//
// Usage: node scripts/redesign/t420_wiki_facts.browser.cjs [outDir]
//   PLAYWRIGHT_MODULE=/path/to/playwright overrides the module lookup.
// Exit code 0 only when every check passes; results.json lists each check.
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, "playwright", path.join(require("os").homedir(), "node_modules/playwright")];
  for (const c of candidates) {
    if (!c) continue;
    try { return require(c); } catch (_) { /* try next */ }
  }
  throw new Error("playwright not found; set PLAYWRIGHT_MODULE");
}
const { chromium, webkit } = loadPlaywright();

const DOCS = path.resolve(__dirname, "../../docs");
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "../../.fleet/reports/T-420"));
fs.mkdirSync(OUT, { recursive: true });

const ENGINES = { chromium, webkit };
const VIEWPORTS = [{ w: 1440, h: 900 }, { w: 390, h: 844 }];
const PAGES = [
  "wiki/modules.html",
  "wiki/database.html",
  "wiki/api.html",
  "wiki/index.html",
  "community.html",
  "govgr-dimos.html",
];

const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
  ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json", ".woff2": "font/woff2" };

function serve() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
      if (p.endsWith("/")) p += "index.html";
      const file = path.join(DOCS, p);
      if (!file.startsWith(DOCS) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404); res.end(); return;
      }
      res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

async function inspect(page) {
  return page.evaluate(() => {
    const ids = {};
    document.querySelectorAll("[id]").forEach((el) => { ids[el.id] = (ids[el.id] || 0) + 1; });
    const duplicateIds = Object.keys(ids).filter((k) => ids[k] > 1);

    const navDupes = [];
    document.querySelectorAll("nav").forEach((nav) => {
      const seen = {};
      nav.querySelectorAll("a[href]").forEach((a) => {
        const href = a.getAttribute("href");
        if (href.startsWith("#")) return;
        // Logo + "Home" share a target by design; a duplicate is same target + same label.
        const key = `${href} ${(a.textContent || "").trim()}`;
        seen[key] = (seen[key] || 0) + 1;
      });
      Object.keys(seen).filter((k) => seen[k] > 1).forEach((k) => navDupes.push(k));
    });

    const footer24h = [...document.querySelectorAll("a[data-el='24 Ώρες']")].map((a) => a.getAttribute("href"));

    const brokenFragments = [...document.querySelectorAll("a[href^='#']")]
      .map((a) => a.getAttribute("href"))
      .filter((h) => h.length > 1 && !document.getElementById(h.slice(1)));

    const docW = document.documentElement.clientWidth;
    const pageOverflow = document.documentElement.scrollWidth - docW;

    // Tables and code blocks must stay inside their scroll container / the viewport.
    const escapes = [];
    document.querySelectorAll("table, .code-block, pre, code").forEach((el) => {
      if (el.closest("#legalModal")) return;
      const r = el.getBoundingClientRect();
      if (r.width === 0) return;
      const wrap = el.closest(".table-wrap, .code-block, pre");
      const container = wrap && wrap !== el ? wrap.getBoundingClientRect() : { left: 0, right: docW };
      const scrolls = wrap && wrap !== el && ["auto", "scroll"].includes(getComputedStyle(wrap).overflowX);
      if (!scrolls && (r.right > container.right + 1 || r.left < container.left - 1)) {
        escapes.push(`${el.tagName.toLowerCase()}:${(el.textContent || "").trim().slice(0, 40)}`);
      }
      if (wrap && wrap !== el) {
        const wr = wrap.getBoundingClientRect();
        if (wr.right > docW + 1) escapes.push(`wrap-beyond-viewport:${el.tagName.toLowerCase()}`);
      }
    });

    const moduleIds = [...document.querySelectorAll("td")]
      .map((td) => (td.textContent || "").trim())
      .filter((t) => /^MOD-\d+b?$/.test(t));
    const tableNames = [...document.querySelectorAll("tr > td:first-child")].map((td) => td.textContent.trim());
    return { duplicateIds, navDupes, footer24h, brokenFragments, pageOverflow, escapes, moduleIds, tableNames };
  });
}

(async () => {
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}/`;
  const results = [];
  let failures = 0;
  const check = (name, ok, detail) => {
    results.push({ name, ok, detail });
    if (!ok) { failures += 1; console.log(`FAIL ${name} ${JSON.stringify(detail)}`); }
  };

  for (const [engineName, engine] of Object.entries(ENGINES)) {
    const browser = await engine.launch();
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
      await ctx.route("**/*", (route) => {
        const u = route.request().url();
        return u.startsWith(base) ? route.continue() : route.abort();
      });
      for (const rel of PAGES) {
        const page = await ctx.newPage();
        const errors = [];
        page.on("pageerror", (e) => errors.push(String(e)));
        const resp = await page.goto(base + rel, { waitUntil: "load" });
        const tag = `${engineName}@${vp.w} ${rel}`;
        check(`${tag} status`, resp && resp.status() === 200, resp && resp.status());
        const r = await inspect(page);
        check(`${tag} no duplicate ids`, r.duplicateIds.length === 0, r.duplicateIds);
        check(`${tag} no duplicate nav links`, r.navDupes.length === 0, r.navDupes);
        check(`${tag} 24h footer -> WINDOW_24H`,
          r.footer24h.length > 0 && r.footer24h.every((h) => h.endsWith("/bills?status=WINDOW_24H")), r.footer24h);
        check(`${tag} fragments resolve`, r.brokenFragments.length === 0, r.brokenFragments);
        check(`${tag} no horizontal page overflow`, r.pageOverflow <= 1, r.pageOverflow);
        check(`${tag} code/table containment`, r.escapes.length === 0, r.escapes);
        check(`${tag} no page errors`, errors.length === 0, errors);
        if (rel === "wiki/modules.html") {
          check(`${tag} no MOD-13/MOD-17`, !r.moduleIds.includes("MOD-13") && !r.moduleIds.includes("MOD-17"), r.moduleIds);
          check(`${tag} MOD-25 listed`, r.moduleIds.includes("MOD-25"), r.moduleIds);
        }
        if (rel === "wiki/database.html") {
          const phantom = ["representative_consent", "representative_profile", "citizen_evaluation"];
          check(`${tag} no phantom tables`, !phantom.some((t) => r.tableNames.includes(t)), r.tableNames);
          check(`${tag} MOD-25 tables listed`,
            ["politician_evaluations", "evaluation_questions"].every((t) => r.tableNames.includes(t)), r.tableNames);
        }
        const shot = path.join(OUT, `${engineName}-${vp.w}-${rel.replace(/\//g, "_")}.png`);
        await page.screenshot({ path: shot, fullPage: true });
        await page.close();
      }
      await ctx.close();
    }
    await browser.close();
  }
  srv.close();
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify({ failures, results }, null, 2));
  console.log(`${results.length - failures}/${results.length} checks passed`);
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });

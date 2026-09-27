// T-421 (EKA-48/49) browser gate for head metadata on every sitemap page.
// Serves the current docs/ tree and a base docs/ tree (default: origin/main via
// `git archive`) locally and drives both in Chromium and WebKit at 1440px and
// 390px. Every non-local request is aborted and recorded, so nothing reaches
// production. Head-only changes must leave layout, navigation and the set of
// attempted external hosts identical to the base.
//
// Usage: node scripts/redesign/t421_seo_metadata.browser.cjs [outDir] [baseRef]
//   PLAYWRIGHT_MODULE=/path/to/playwright overrides the module lookup.
// Exit code 0 only when every check passes; results.json lists each check.
"use strict";
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, "playwright", path.join(os.homedir(), "node_modules/playwright")];
  for (const c of candidates) {
    if (!c) continue;
    try { return require(c); } catch (_) { /* try next */ }
  }
  throw new Error("playwright not found; set PLAYWRIGHT_MODULE");
}
const { chromium, webkit } = loadPlaywright();

const ROOT = path.resolve(__dirname, "../..");
const OUT = path.resolve(process.argv[2] || path.join(ROOT, ".fleet/reports/T-421"));
const BASE_REF = process.argv[3] || "origin/main";
fs.mkdirSync(OUT, { recursive: true });

const sources = JSON.parse(fs.readFileSync(path.join(ROOT, "scripts/sitemap.sources.json"), "utf8"));
const PAGES = sources.entries.filter((e) => e.source).map((e) => ({ rel: e.source.slice("docs/".length), url: sources.base + e.loc }));

const ENGINES = { chromium, webkit };
const VIEWPORTS = [{ w: 1440, h: 900 }, { w: 390, h: 844 }];
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
  ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json", ".woff2": "font/woff2" };

function baseDocs() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t421-base-"));
  const tar = execFileSync("git", ["archive", BASE_REF, "docs"], { cwd: ROOT, maxBuffer: 1 << 30 });
  execFileSync("tar", ["-x", "-C", dir], { input: tar });
  return path.join(dir, "docs");
}

function serve(docs) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
      if (p.endsWith("/")) p += "index.html";
      const file = path.join(docs, p);
      if (!file.startsWith(docs) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
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
    const attr = (sel, a) => [...document.querySelectorAll(sel)].map((el) => el.getAttribute(a));
    const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map((s) => {
      try { JSON.parse(s.textContent); return true; } catch (_) { return false; }
    });
    const nav = document.querySelector("nav, header");
    const navRect = nav ? nav.getBoundingClientRect() : null;
    const navLinks = nav ? [...nav.querySelectorAll("a[href]")].filter((a) => {
      const r = a.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }).length : 0;
    return {
      canonical: attr('link[rel="canonical"]', "href"),
      ogUrl: attr('meta[property="og:url"]', "content"),
      twitterCard: attr('meta[name="twitter:card"]', "content"),
      hreflang: [...document.querySelectorAll("link[hreflang]")].map((l) => `${l.hreflang}=${l.getAttribute("href")}`),
      ld,
      navRect: navRect && { x: Math.round(navRect.x), w: Math.round(navRect.width), h: Math.round(navRect.height) },
      navLinks,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      height: document.documentElement.scrollHeight,
    };
  });
}

async function run(engine, vp, base, rel, external) {
  const ctx = await engine.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: "reduce" });
  await ctx.route("**/*", (route) => {
    const u = route.request().url();
    if (u.startsWith(base)) return route.continue();
    try { external.add(new URL(u).host); } catch (_) { external.add(u.slice(0, 40)); }
    return route.abort();
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const resp = await page.goto(base + rel, { waitUntil: "load" });
  await page.waitForTimeout(300);
  const r = await inspect(page);
  r.status = resp && resp.status();
  r.errors = errors;
  return { ctx, page, r };
}

(async () => {
  const baseSrv = await serve(baseDocs());
  const headSrv = await serve(path.join(ROOT, "docs"));
  const baseUrl = `http://127.0.0.1:${baseSrv.address().port}/`;
  const headUrl = `http://127.0.0.1:${headSrv.address().port}/`;
  const results = [];
  const externalByPage = {};
  let failures = 0;
  const check = (name, ok, detail) => {
    results.push({ name, ok, detail });
    if (!ok) { failures += 1; console.log(`FAIL ${name} ${JSON.stringify(detail)}`); }
  };

  for (const [engineName, engineType] of Object.entries(ENGINES)) {
    const browser = await engineType.launch();
    for (const vp of VIEWPORTS) {
      for (const { rel, url } of PAGES) {
        const tag = `${engineName}@${vp.w} ${rel}`;
        const extBase = new Set();
        const extHead = new Set();
        const b = await run(browser, vp, baseUrl, rel, extBase);
        const h = await run(browser, vp, headUrl, rel, extHead);
        const r = h.r;
        check(`${tag} status`, r.status === 200, r.status);
        check(`${tag} canonical`, r.canonical.length === 1 && r.canonical[0] === url, r.canonical);
        check(`${tag} og:url = canonical`, r.ogUrl.length === 1 && r.ogUrl[0] === url, r.ogUrl);
        check(`${tag} twitter:card`, r.twitterCard.length === 1 && !!r.twitterCard[0], r.twitterCard);
        check(`${tag} hreflang el+x-default self only`,
          JSON.stringify(r.hreflang) === JSON.stringify([`el=${url}`, `x-default=${url}`]), r.hreflang);
        check(`${tag} JSON-LD parses`, r.ld.length >= 1 && r.ld.every(Boolean), r.ld);
        check(`${tag} navigation visible`, !!r.navRect && r.navLinks > 0, { navRect: r.navRect, navLinks: r.navLinks });
        check(`${tag} navigation unchanged vs base`,
          JSON.stringify(r.navRect) === JSON.stringify(b.r.navRect) && r.navLinks === b.r.navLinks,
          { head: [r.navRect, r.navLinks], base: [b.r.navRect, b.r.navLinks] });
        check(`${tag} no new horizontal overflow`, r.overflow <= Math.max(1, b.r.overflow), { head: r.overflow, base: b.r.overflow });
        check(`${tag} page height unchanged vs base`, Math.abs(r.height - b.r.height) <= 2, { head: r.height, base: b.r.height });
        check(`${tag} no new page errors`, r.errors.length <= b.r.errors.length, { head: r.errors, base: b.r.errors });
        check(`${tag} no new external hosts`, [...extHead].every((x) => extBase.has(x)),
          { head: [...extHead], base: [...extBase] });
        externalByPage[rel] = [...new Set([...(externalByPage[rel] || []), ...extHead])].sort();
        await h.page.screenshot({ path: path.join(OUT, `${engineName}-${vp.w}-${rel.replace(/\//g, "_")}.png`) });
        await b.ctx.close();
        await h.ctx.close();
      }
    }
    await browser.close();
  }
  baseSrv.close();
  headSrv.close();
  fs.writeFileSync(path.join(OUT, "results.json"),
    JSON.stringify({ baseRef: BASE_REF, failures, externalAttemptsBlocked: externalByPage, results }, null, 2));
  console.log(`${results.length - failures}/${results.length} checks passed`);
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });

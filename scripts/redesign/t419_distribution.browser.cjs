// T-419 / EKA-38 + EKA-51 browser matrix: download cards, links, navigation, overflow.
// Chromium + WebKit at 1440px and 390px against a local static server for docs/.
// Every non-local request is aborted; external links are inspected, never followed.
//   node scripts/redesign/t419_distribution.browser.cjs [outDir]
//   PLAYWRIGHT_MODULE=/path/to/playwright overrides the module lookup.
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
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "../../.fleet/reports/T-419"));
fs.mkdirSync(OUT, { recursive: true });

const ENGINES = { chromium, webkit };
const VIEWPORTS = [{ w: 1440, h: 900 }, { w: 390, h: 844 }];
const CANONICAL_APK = "https://github.com/NeaBouli/pnyx/releases/download/v1.0.32/ekklesia-v1.0.32-vC61-DIRECT.apk";
const FDROID = "https://f-droid.org/packages/ekklesia.gr/";
const PLAY = "https://play.google.com/apps/testing/ekklesia.gr";

const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json", ".webp": "image/webp", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8" };
function serve() {
  const server = http.createServer((req, res) => {
    let rel = decodeURIComponent(req.url.split("?")[0].split("#")[0]);
    if (rel.endsWith("/")) rel += "index.html";
    const file = path.join(DOCS, rel);
    if (!file.startsWith(DOCS) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

const results = [];
function check(caseName, name, ok, detail) {
  results.push({ case: caseName, check: name, ok: !!ok, detail });
  if (!ok) console.log(`FAIL ${caseName} :: ${name} :: ${JSON.stringify(detail)}`);
}

async function open(browser, base, vp, rel) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, hasTouch: vp.w < 1000, serviceWorkers: "block", locale: "el-GR" });
  const page = await ctx.newPage();
  const errors = [];
  const external = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith(base)) return route.continue();
    external.push(url);
    return route.abort("blockedbyclient");
  });
  await page.goto(base + rel, { waitUntil: "load" });
  return { ctx, page, errors, external };
}

async function overflow(page) {
  return page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth }));
}

async function landing(browser, base, engine, vp) {
  const tag = `${engine}@${vp.w} index`;
  const { ctx, page, errors } = await open(browser, base, vp, "/index.html");

  // Navigation: the header CTA must reach #download (menu button first on narrow viewports).
  const menuBtn = page.locator(".pnx2-menu-btn");
  if (await menuBtn.isVisible()) await menuBtn.click();
  const cta = page.locator('nav a.pnx2-nav-cta[href="#download"]');
  check(tag, "download CTA visible", await cta.isVisible(), null);
  await cta.click();
  await page.waitForTimeout(900);
  const section = await page.locator("#download").boundingBox();
  check(tag, "CTA scrolls to #download", section && section.y < vp.h && section.y + section.height > 0, section);
  check(tag, "hash is #download", (await page.evaluate(() => location.hash)) === "#download", null);

  await page.locator("#download .download-channel-card").first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  const cards = await page.evaluate(() => Array.from(document.querySelectorAll("#download .download-channel-card")).map((c) => {
    const r = c.getBoundingClientRect();
    const svg = c.querySelector("svg");
    const sr = svg.getBoundingClientRect();
    return {
      tag: c.tagName, href: c.getAttribute("href"), target: c.getAttribute("target"), rel: c.getAttribute("rel"),
      text: c.innerText.replace(/\s+/g, " ").trim(),
      left: r.left, right: r.right, width: r.width, height: r.height,
      svgFill: getComputedStyle(svg).fill, svgW: sr.width, svgH: sr.height,
      cardBg: getComputedStyle(c).backgroundColor,
    };
  }));
  check(tag, "four download cards", cards.length === 4, cards.length);
  const vw = (await overflow(page)).innerWidth;
  for (const c of cards) {
    const name = c.text.split(" ").slice(0, 3).join(" ");
    check(tag, `card in viewport: ${name}`, c.left >= 0 && c.right <= vw + 0.5 && c.width > 0 && c.height > 0, c);
    check(tag, `icon rendered: ${name}`, c.svgW >= 20 && c.svgH >= 20, { w: c.svgW, h: c.svgH });
    check(tag, `icon not white-on-white: ${name}`, c.svgFill !== c.cardBg && !/rgb\(255, 255, 255\)/.test(c.svgFill), { fill: c.svgFill, bg: c.cardBg });
  }
  const byHref = Object.fromEntries(cards.filter((c) => c.href).map((c) => [c.href, c]));
  check(tag, "direct card -> canonical APK", !!byHref[CANONICAL_APK], Object.keys(byHref));
  check(tag, "F-Droid card -> package page", !!byHref[FDROID], Object.keys(byHref));
  check(tag, "Play card -> testing page", !!byHref[PLAY], Object.keys(byHref));
  for (const c of cards.filter((x) => x.href)) check(tag, `external link opens safely: ${c.href}`, c.target === "_blank" && /noopener/.test(c.rel || ""), c);
  const appStore = cards.find((c) => /App Store/.test(c.text));
  check(tag, "App Store card is not a link", appStore && appStore.tag !== "A" && !appStore.href, appStore);
  const fdroid = byHref[FDROID];
  check(tag, "F-Droid says available, unversioned (el)", fdroid && /Διαθέσιμο/.test(fdroid.text) && !/v\d+\.\d+|vC\d+/.test(fdroid.text), fdroid && fdroid.text);
  check(tag, "Play says under review (el)", byHref[PLAY] && /Υπό έλεγχο/.test(byHref[PLAY].text), byHref[PLAY] && byHref[PLAY].text);

  // Language toggle keeps the same status wording in English.
  await page.evaluate(() => toggleLang());
  const fdEn = await page.locator(`#download a[href="${FDROID}"]`).innerText();
  check(tag, "F-Droid says available (en)", /Available/.test(fdEn) && /Independent F-Droid build/.test(fdEn), fdEn);
  const playEn = await page.locator(`#download a[href="${PLAY}"]`).innerText();
  check(tag, "Play says under review (en)", /Under review/.test(playEn), playEn);

  const ov = await overflow(page);
  check(tag, "no horizontal overflow", ov.scrollWidth <= ov.innerWidth, ov);
  check(tag, "no page errors", errors.length === 0, errors);
  await page.locator("#download").screenshot({ path: path.join(OUT, `${engine}-${vp.w}-index-download.png`) });
  await ctx.close();
}

async function simplePage(browser, base, engine, vp, rel, fn) {
  const tag = `${engine}@${vp.w} ${rel}`;
  const { ctx, page, errors } = await open(browser, base, vp, rel);
  await fn(tag, page);
  const ov = await overflow(page);
  check(tag, "no horizontal overflow", ov.scrollWidth <= ov.innerWidth, ov);
  check(tag, "no page errors", errors.length === 0, errors);
  await ctx.close();
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    for (const [engine, type] of Object.entries(ENGINES)) {
      const browser = await type.launch();
      try {
        for (const vp of VIEWPORTS) {
          await landing(browser, base, engine, vp);
          await simplePage(browser, base, engine, vp, "/representative.html#download", async (tag, page) => {
            const box = page.locator("#download");
            await box.scrollIntoViewIfNeeded();
            check(tag, "availability block visible", await box.isVisible(), null);
            const hrefs = await box.locator("a").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
            check(tag, "no ekprosopos APK link", !hrefs.some((h) => /ekprosopos-latest\.apk/.test(h || "")), hrefs);
            check(tag, "APK shown in development", /Σε ανάπτυξη/.test(await box.innerText()), null);
            await box.screenshot({ path: path.join(OUT, `${engine}-${vp.w}-representative-download.png`) });
          });
          await simplePage(browser, base, engine, vp, "/sso-verify.html", async (tag, page) => {
            const links = await page.locator(".download-grid a").evaluateAll((as) => as.map((a) => {
              const r = a.getBoundingClientRect();
              return { href: a.getAttribute("href"), text: a.innerText.replace(/\s+/g, " "), right: r.right, left: r.left };
            }));
            const vw = await page.evaluate(() => window.innerWidth);
            check(tag, "three download links", links.length === 3, links);
            for (const l of links) check(tag, `link in viewport: ${l.href}`, l.left >= 0 && l.right <= vw + 0.5, l);
            check(tag, "links are canonical", links.every((l) => [CANONICAL_APK, FDROID, PLAY].includes(l.href)), links);
          });
          for (const rel of ["/wiki/faq.html", "/wiki/roadmap.html"]) {
            await simplePage(browser, base, engine, vp, rel, async (tag, page) => {
              const html = await page.content();
              check(tag, "F-Droid availability sentence present", html.includes("Η εφαρμογή είναι διαθέσιμη και στο F-Droid"), null);
              check(tag, "no stale F-Droid hedge", !/παλαιότερη έκδοση|older version/.test(html), null);
            });
          }
        }
      } finally {
        await browser.close();
      }
    }
  } finally {
    server.close();
  }
  const failed = results.filter((r) => !r.ok);
  fs.writeFileSync(path.join(OUT, "browser-results.json"), JSON.stringify({ total: results.length, failed: failed.length, results }, null, 2));
  console.log(`${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });

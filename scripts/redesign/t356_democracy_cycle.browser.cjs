// #356 browser gate for the landing democracy cycle (#demo).
// Serves the static docs/ tree locally and drives it in Chromium and WebKit.
// All api.ekklesia.gr requests are answered by page.route mocks; every other
// non-local request is aborted, so nothing reaches production.
//
// Usage: node scripts/redesign/t356_democracy_cycle.browser.cjs [outDir]
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
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "../../.fleet/reports/T-356"));
fs.mkdirSync(OUT, { recursive: true });

const ENGINES = { chromium, webkit };
const VIEWPORTS = [
  { w: 1440, h: 900, cols: 6, dataCols: 2 },
  { w: 840, h: 900, cols: 3, dataCols: 2 },
  { w: 390, h: 844, cols: 1, dataCols: 1 },
  { w: 360, h: 800, cols: 1, dataCols: 1 },
];

const LIVE = {
  bill_id: "GR-T356", title_el: "Νομοσχέδιο δοκιμής", title_en: "Test bill", status: "PARLIAMENT_VOTED",
  total_votes: 1234, yes_pct: 60, no_pct: 35, abstain_pct: 5, unknown_pct: 0,
};
const STATES = {
  live: (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(LIVE) }),
  empty: (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
  none: (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ bill_id: null, total_votes: 0 }) }),
  http503: (route) => route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"unavailable"}' }),
  abort: (route) => route.abort("failed"),
};

const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json", ".webp": "image/webp", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2" };
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

async function newPage(browser, base, vp, state, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, hasTouch: vp.w < 1000, reducedMotion: opts.reducedMotion || "no-preference", serviceWorkers: "block", locale: "el-GR" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  // Record every change of the active phase from page start (hash-open check).
  await page.addInitScript(() => {
    window.__t356Seq = [];
    document.addEventListener("DOMContentLoaded", () => {
      const grid = document.getElementById("cyclePhases");
      if (!grid) return;
      let last = null;
      new MutationObserver(() => {
        const cells = Array.from(grid.children);
        const a = cells.findIndex((c) => c.classList.contains("active"));
        if (a !== last) { window.__t356Seq.push(a); last = a; }
      }).observe(grid, { subtree: true, attributes: true, attributeFilter: ["class"] });
    });
  });
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith(base)) return route.continue();
    if (url.includes("api.ekklesia.gr/api/v1/vote/results/latest")) return STATES[state](route);
    if (url.includes("api.ekklesia.gr")) return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    return route.abort("blockedbyclient");
  });
  await page.goto(base + (opts.hash || ""), { waitUntil: "load" });
  await page.waitForTimeout(600);
  return { ctx, page, errors };
}

const activeIndex = (page) => page.evaluate(() => {
  const cells = Array.from(document.querySelectorAll("#cyclePhases > .demo-box"));
  const on = cells.map((c, i) => (c.classList.contains("active") ? i : -1)).filter((i) => i >= 0);
  return on.length === 1 ? on[0] : on.length === 0 ? -1 : "multi:" + on.join(",");
});

async function openFoldByKeyboard(page) {
  const summary = page.locator("#demo summary");
  await summary.focus();
  await page.keyboard.press("Enter");
}

async function layoutChecks(page, name, vp) {
  const m = await page.evaluate(() => {
    const grid = document.getElementById("cyclePhases");
    const cols = getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length;
    const cells = Array.from(grid.children).map((c) => ({
      id: c.id, sw: c.scrollWidth, cw: c.clientWidth, sh: c.scrollHeight, ch: c.clientHeight,
      kids: Array.from(c.querySelectorAll("*")).filter((k) => { const r = k.getBoundingClientRect(), p = c.getBoundingClientRect(); return r.width && (r.right > p.right + 1 || r.left < p.left - 1); }).map((k) => k.className || k.tagName),
    }));
    const data = document.querySelector("#demo .pnx2-democracy-data");
    const dataCols = getComputedStyle(data).gridTemplateColumns.split(" ").filter(Boolean).length;
    const dr = data.getBoundingClientRect();
    const dataOverflow = Array.from(data.querySelectorAll("*")).filter((k) => { const r = k.getBoundingClientRect(); return r.width && (r.right > dr.right + 1 || r.left < dr.left - 1); }).map((k) => k.id || k.tagName).slice(0, 8);
    const de = document.documentElement;
    const tileOverflow = Array.from(document.querySelectorAll("#dBox6 *")).filter((k) => { const r = k.getBoundingClientRect(); return r.width && r.right > de.clientWidth + 1; }).map((k) => k.id || k.className).slice(0, 8);
    const rep = document.getElementById("repSection").getBoundingClientRect();
    const cplm = document.getElementById("cplmSection").getBoundingClientRect();
    const tile = document.getElementById("dBox6").getBoundingClientRect();
    return { cols, cells, dataCols, dataOverflow, tileOverflow, docOverflowX: de.scrollWidth - de.clientWidth,
      order: { gridBottom: Math.round(grid.getBoundingClientRect().bottom), tileTop: Math.round(tile.top), tileBottom: Math.round(tile.bottom), dataTop: Math.round(dr.top) },
      repCplmSideBySide: Math.abs(rep.top - cplm.top) < 2 && cplm.left > rep.left };
  });
  check(name, `phase grid has ${vp.cols} columns`, m.cols === vp.cols, m.cols);
  const bad = m.cells.filter((c) => c.sw > c.cw + 1 || c.sh > c.ch + 1 || c.kids.length);
  check(name, "no phase cell overflow", bad.length === 0, bad);
  check(name, "no document horizontal overflow", m.docOverflowX === 0, m.docOverflowX);
  check(name, "no result tile overflow", m.tileOverflow.length === 0, m.tileOverflow);
  check(name, `Rep/CPLM has ${vp.dataCols} column(s)`, m.dataCols === vp.dataCols && m.repCplmSideBySide === (vp.dataCols === 2), { cols: m.dataCols, sideBySide: m.repCplmSideBySide });
  check(name, "no Rep/CPLM overflow", m.dataOverflow.length === 0, m.dataOverflow);
  check(name, "order: cycle → result → Rep/CPLM", m.order.gridBottom <= m.order.tileTop + 1 && m.order.tileBottom <= m.order.dataTop + 1, m.order);
}

async function contrastChecks(page, name) {
  const r = await page.evaluate(() => {
    const parse = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
    const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
    const blend = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
    const bgOf = (el) => {
      const layers = [];
      for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
      let bg = { r: 255, g: 255, b: 255, a: 1 };
      for (let i = layers.length - 1; i >= 0; i--) bg = blend(layers[i], bg);
      return bg;
    };
    const fails = []; let min = 99, count = 0;
    const walker = document.createTreeWalker(document.getElementById("demo"), NodeFilter.SHOW_TEXT);
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      if (!t.textContent.trim()) continue;
      const el = t.parentElement;
      if (el.closest("summary")) continue;
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height || cs.visibility === "hidden" || el.closest("[hidden]")) continue;
      let op = 1; for (let n = el; n && n.nodeType === 1; n = n.parentElement) op *= Number(getComputedStyle(n).opacity);
      if (op < 0.1) continue;
      const bg = bgOf(el);
      let fg = parse(el.namespaceURI === "http://www.w3.org/2000/svg" ? cs.fill : cs.color);
      if (!fg) continue;
      fg = blend({ ...fg, a: fg.a * op }, bg);
      const L1 = lum(fg), L2 = lum(bg);
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      count++; min = Math.min(min, ratio);
      if (ratio < 4.5) fails.push({ text: t.textContent.trim().slice(0, 40), ratio: Math.round(ratio * 100) / 100, color: cs.color });
    }
    return { count, min: Math.round(min * 100) / 100, fails: fails.slice(0, 12) };
  });
  check(name, `visible text contrast >= 4.5:1 (${r.count} nodes, min ${r.min})`, r.fails.length === 0, r.fails);
  return r;
}

async function interactionChecks(page, name, shot) {
  // Close and reopen by keyboard so sampling starts exactly at phase 01, then
  // expect 01..06 exactly once in order, followed by 01 again.
  await openFoldByKeyboard(page);
  await page.waitForTimeout(300);
  await openFoldByKeyboard(page);
  const t0 = Date.now();
  const seen = [];
  let last = null, phase6Style = null;
  while (Date.now() - t0 < 14500) {
    const a = await activeIndex(page);
    if (a !== last) {
      seen.push({ t: Date.now() - t0, a });
      last = a;
      if (a === 5 && !phase6Style) {
        await page.waitForTimeout(450); // let the 0.3 s highlight transition settle
        phase6Style = await page.evaluate(() => {
          const cells = document.querySelectorAll("#cyclePhases > .demo-box");
          const on = getComputedStyle(cells[5]), off = getComputedStyle(cells[0]);
          const r = cells[5].getBoundingClientRect();
          return { onBg: on.backgroundColor, offBg: off.backgroundColor, onTop: on.borderTopColor, offTop: off.borderTopColor, visible: r.width > 0 && r.height > 0, current: cells[5].getAttribute("aria-current") };
        });
        await page.locator("#dBoxArchive").scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(OUT, `${shot}-phase6.png`) });
      }
      if (a === 0 && seen.length > 6) break;
    }
    await page.waitForTimeout(80);
  }
  // The native <details> toggle event is async; ignore the idle state before it.
  const seq = seen.map((s) => s.a).filter((a, i, all) => !(a === -1 && all.slice(0, i).every((x) => x === -1)));
  check(name, "phases 01..06 each active once in order, then 01", JSON.stringify(seq.slice(0, 7)) === "[0,1,2,3,4,5,0]", seen);
  check(name, "phase 06 visibly highlighted", phase6Style && phase6Style.visible && phase6Style.onBg !== phase6Style.offBg && phase6Style.onTop !== phase6Style.offTop && phase6Style.current === "step", phase6Style);

  // Pause via keyboard (Space on the focused button): no change for 5 s.
  await page.locator("#cycleToggle").focus();
  await page.keyboard.press("Space");
  const pausedAt = await activeIndex(page);
  const pausedLabel = await page.locator("#cycleToggleText").textContent();
  await page.waitForTimeout(5000);
  const afterPause = await activeIndex(page);
  check(name, "pause stops the cycle (5 s)", afterPause === pausedAt && pausedAt >= 0 && /Αναπαραγωγή/.test(pausedLabel), { pausedAt, afterPause, pausedLabel });

  // Play via Enter continues from the paused phase.
  await page.keyboard.press("Enter");
  await page.waitForTimeout(pausedAt === 5 ? 3400 : 2400); // phase 06 holds 3 s
  const afterPlay = await activeIndex(page);
  const expected = pausedAt === 5 ? 0 : pausedAt + 1;
  const playLabel = await page.locator("#cycleToggleText").textContent();
  check(name, "play resumes from the paused phase", afterPlay === expected && /Παύση/.test(playLabel), { pausedAt, afterPlay, expected, playLabel });

  // Closing stops and clears; reopening restarts at phase 01.
  await openFoldByKeyboard(page);
  await page.waitForTimeout(100);
  const closedOpen = await page.evaluate(() => document.querySelector("#demo details").open);
  const closedSamples = [];
  for (let i = 0; i < 8; i++) { closedSamples.push(await activeIndex(page)); await page.waitForTimeout(500); }
  check(name, "closing the fold stops the cycle", closedOpen === false && closedSamples.every((a) => a === -1), closedSamples);
  await openFoldByKeyboard(page);
  await page.waitForTimeout(150);
  const reopen = await activeIndex(page);
  await page.waitForTimeout(2200);
  const reopen2 = await activeIndex(page);
  check(name, "reopening restarts at phase 01", reopen === 0 && reopen2 === 1, { reopen, reopen2 });
}

async function runCase(browser, base, engine, vp) {
  const name = `${engine}-${vp.w}x${vp.h}`;
  const { ctx, page, errors } = await newPage(browser, base, vp, "live");
  const closed = await page.evaluate(() => ({ open: document.querySelector("#demo details").open }));
  check(name, "fold collapsed on load", closed.open === false, closed);
  check(name, "no active phase while collapsed", (await activeIndex(page)) === -1, await activeIndex(page));
  await page.locator("#demo").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(OUT, `${name}-closed.png`) });
  const focusRing = await page.locator("#demo summary").evaluate((s) => { s.focus(); const c = getComputedStyle(s); return c.outlineStyle + " " + c.outlineWidth; });
  await openFoldByKeyboard(page);
  await page.waitForTimeout(150);
  check(name, "keyboard Enter opens the fold", await page.evaluate(() => document.querySelector("#demo details").open), focusRing);
  await page.locator("#cyclePhases").scrollIntoViewIfNeeded();
  await layoutChecks(page, name, vp);
  const dataVisible = [];
  for (const id of ["repSection", "cplmSection"]) {
    await page.locator(`#${id}`).scrollIntoViewIfNeeded();
    await page.waitForTimeout(600);
    const visible = await page.locator(`#${id}`).evaluate((el) => {
      const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      return { id: el.id, opacity: Number(cs.opacity), visibility: cs.visibility, width: r.width, height: r.height };
    });
    dataVisible.push(visible);
    await page.screenshot({ path: path.join(OUT, `${name}-${id}.png`) });
  }
  check(name, "Rep/CPLM become visibly rendered on scroll", dataVisible.every((x) => x.opacity >= 0.99 && x.visibility === "visible" && x.width > 0 && x.height > 0), dataVisible);
  await contrastChecks(page, name);
  await page.locator("#demo").screenshot({ path: path.join(OUT, `${name}-open-full.png`) });
  const btn = await page.locator("#cycleToggle").evaluate((b) => { const r = b.getBoundingClientRect(); return { w: r.width, h: r.height, tab: b.tabIndex, type: b.type }; });
  check(name, "pause/play button visible and focusable (>=44px)", btn.h >= 44 && btn.w >= 44 && btn.tab === 0 && btn.type === "button", btn);
  await page.locator("#cyclePhases").scrollIntoViewIfNeeded();
  await interactionChecks(page, name, name);
  check(name, "no page errors", errors.length === 0, errors);
  await ctx.close();

  // Hash navigation opens the fold below the sticky header.
  const h = await newPage(browser, base, vp, "live", { hash: "#demo" });
  await h.page.waitForTimeout(500);
  const hash = await h.page.evaluate(() => { const nav = document.querySelector("nav.pnx2-header"); const d = document.getElementById("demo"); return { open: d.querySelector("details").open, navBottom: Math.round(nav.getBoundingClientRect().bottom), demoTop: Math.round(d.getBoundingClientRect().top) }; });
  check(name, "#demo hash opens fold below sticky header", hash.open && hash.demoTop >= hash.navBottom - 1, hash);
  await h.page.screenshot({ path: path.join(OUT, `${name}-hash-demo.png`) });
  const hashSeq = await h.page.evaluate(() => window.__t356Seq);
  check(name, "hash-opened fold starts at phase 01", hashSeq[0] === 0, hashSeq);
  await h.ctx.close();
}

const TEXT_IDS = ["latestBillTitle", "latestBillStatus", "resultTotal", "resultParticipation", "resultYesLabel", "resultNoLabel", "resultMajority", "demoYesLabel", "demoNoLabel"];
const readState = (page) => page.evaluate((ids) => {
  const o = {};
  ids.forEach((id) => { o[id] = document.getElementById(id).textContent.trim(); });
  o.yesBar = document.getElementById("yesBar").style.width || "0";
  o.resultYes = document.getElementById("resultYes").style.width || "0";
  o.repScore = document.getElementById("repScore").textContent.trim();
  o.cplmX = document.getElementById("cplmX").textContent.trim();
  return o;
}, TEXT_IDS);

async function stateChecks(browser, base, engine, vp) {
  for (const state of Object.keys(STATES)) {
    const name = `${engine}-${vp.w}x${vp.h}-state-${state}`;
    const { ctx, page, errors } = await newPage(browser, base, vp, state, { hash: "#demo" });
    await page.waitForTimeout(400);
    const el = await readState(page);
    await page.evaluate(() => toggleLang());
    const en = await readState(page);
    const phasesEn = await page.evaluate(() => Array.from(document.querySelectorAll("#cyclePhases .demo-label")).map((n) => n.textContent.trim()));
    await page.evaluate(() => toggleLang());
    await page.locator("#dBox6").scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(OUT, `${name}.png`) });
    const numbers = (o) => TEXT_IDS.filter((id) => /\d/.test(o[id]) && id !== "latestBillTitle");
    if (state === "live") {
      check(name, "EL live values + status label + participation", el.latestBillStatus === "Κατάσταση νομοσχεδίου · Ψηφίστηκε στη Βουλή" && el.resultTotal === "1.234 ψήφοι" && /^Συμμετοχή στην πλατφόρμα: 0\.0126% \(1\.234 \/ 9\.810\.040\)$/.test(el.resultParticipation) && el.demoYesLabel === "60% Υπέρ" && el.yesBar === "60%" && el.resultYes === "60%", el);
      check(name, "EN parity for live values", en.latestBillStatus === "Bill status · Voted in Parliament" && en.resultTotal === "1,234 votes" && /^Platform participation: 0\.0126% \(1,234 \/ 9,810,040\)$/.test(en.resultParticipation) && en.resultMajority === "Majority: YES" && en.latestBillTitle === "Test bill", en);
      check(name, "EN phase labels", JSON.stringify(phasesEn) === JSON.stringify(["Announced", "Active", "Citizens", "24h", "Parliament", "Archive"]), phasesEn);
    } else {
      check(name, "no fake numbers in empty/error state", numbers(el).length === 0 && numbers(en).length === 0 && el.yesBar === "0" && el.resultYes === "0" && el.repScore === "—" && el.cplmX === "—", { el, en });
      if (state === "empty" || state === "none") check(name, "empty state says waiting", el.latestBillStatus === "Δεν υπάρχει ακόμη αποτέλεσμα με ψήφους" && en.latestBillStatus === "No voted result is available yet", el.latestBillStatus);
      else check(name, "error state says unavailable (EL/EN)", el.latestBillStatus === "Τα ζωντανά δεδομένα δεν είναι διαθέσιμα αυτή τη στιγμή." && en.latestBillStatus === "Live data is currently unavailable.", { el: el.latestBillStatus, en: en.latestBillStatus });
    }
    check(name, "no page errors", errors.length === 0, errors);
    await ctx.close();
  }
}

async function reducedMotionCheck(browser, base, engine, vp) {
  const name = `${engine}-${vp.w}x${vp.h}-reduced-motion`;
  const { ctx, page } = await newPage(browser, base, vp, "live", { reducedMotion: "reduce" });
  await openFoldByKeyboard(page);
  const samples = [];
  const t0 = Date.now();
  while (Date.now() - t0 < 10000) { samples.push(await activeIndex(page)); await page.waitForTimeout(250); }
  const label = await page.locator("#cycleToggleText").textContent();
  check(name, "reduced motion: no phase change for 10 s", new Set(samples).size === 1, { distinct: [...new Set(samples)], n: samples.length });
  check(name, "reduced motion: control offers Play", /Αναπαραγωγή/.test(label), label);
  await page.locator("#cyclePhases").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(OUT, `${name}.png`) });
  await ctx.close();
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const meta = { base, docs: DOCS, startedAt: new Date().toISOString(), engines: {} };
  try {
    for (const [engine, type] of Object.entries(ENGINES)) {
      const browser = await type.launch();
      meta.engines[engine] = browser.version();
      for (const vp of VIEWPORTS) await runCase(browser, base, engine, vp);
      await reducedMotionCheck(browser, base, engine, VIEWPORTS[0]);
      await reducedMotionCheck(browser, base, engine, VIEWPORTS[2]);
      await stateChecks(browser, base, engine, engine === "webkit" ? VIEWPORTS[2] : VIEWPORTS[0]);
      await browser.close();
    }
  } finally {
    server.close();
  }
  const failed = results.filter((r) => !r.ok);
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify({ meta, total: results.length, failed: failed.length, results }, null, 2));
  console.log(`${results.length - failed.length}/${results.length} checks passed; evidence in ${OUT}`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });

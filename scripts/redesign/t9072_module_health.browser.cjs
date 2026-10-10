// T-9072 offline browser gate for docs/wiki/modules.html health dots.
// Serves docs/ locally; the health endpoint is fulfilled from local fixtures,
// every other non-local request is aborted. No production calls.
// Usage: node scripts/redesign/t9072_module_health.browser.cjs [outDir]
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
function loadPlaywright() {
  for (const c of [process.env.PLAYWRIGHT_MODULE, "playwright", path.join(require("os").homedir(), "node_modules/playwright")]) {
    if (!c) continue;
    try { return require(c); } catch (_) { /* next */ }
  }
  throw new Error("playwright not found; set PLAYWRIGHT_MODULE");
}
const { chromium } = loadPlaywright();
const DOCS = path.resolve(__dirname, "../../docs");
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "../../.fleet/reports/T-9072"));
fs.mkdirSync(OUT, { recursive: true });
const HEALTH = "/api/v1/health/modules";
const all = (st) => Object.fromEntries(["01","02","03","04","05","06","07","08","10","11","12","14","15","16","19","20","21","22","25"].map((n) => [`MOD-${n}`, { status: st }]));
const FIX = {
  base: { status: 200, body: { modules: { ...all("ok"), "MOD-09": { status: "deferred" }, "MOD-21": { status: "unknown" }, "MOD-23": { status: "disabled" }, "MOD-24": { status: "ok" }, "MOD-25": { status: "unknown" } } } },
  next: { status: 200, body: { modules: { ...all("ok"), "MOD-25": undefined, "MOD-01": { status: "error" }, "MOD-02": { status: "degraded" }, "MOD-09": { status: "deferred" }, "MOD-23": { status: "disabled" }, "MOD-24": { status: "ok" } } } },
  heal: { status: 200, body: { modules: { ...all("ok"), "MOD-09": { status: "deferred" }, "MOD-23": { status: "disabled" }, "MOD-03": { status: "bogus" }, "MOD-04": "x" } } },
  non2xx: { status: 503, body: { modules: all("ok") } },
  malformed: { status: 200, body: { modules: [] } },
  invalid: { status: 200, raw: "not json" },
  fail: { abort: true },
};
const checks = [];
const ok = (name, cond, detail) => { checks.push({ name, pass: !!cond, detail }); };
const server = http.createServer((req, res) => {
  const p = path.join(DOCS, decodeURIComponent(req.url.split("?")[0]));
  if (!p.startsWith(DOCS) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  const ext = path.extname(p);
  res.writeHead(200, { "content-type": { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".svg": "image/svg+xml" }[ext] || "application/octet-stream" });
  fs.createReadStream(p).pipe(res);
});
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  const externals = [];
  const dot = (page, id) => page.evaluate((i) => { const e = document.getElementById(i); const r = e.closest("tr"); return { cls: e.className, h: e.getAttribute("data-health"), aria: e.getAttribute("aria-label"), title: e.getAttribute("title"), text: e.textContent, rowBg: r.style.background, rowBorder: r.style.borderLeft }; }, id);
  for (const vp of [{ w: 1280, h: 900 }, { w: 390, h: 844 }]) {
    const tag = `${vp.w}`;
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
    const page = await ctx.newPage();
    const errors = []; const failed = [];
    page.on("console", (m) => { if (m.type() === "error" && !(m.location().url || "").includes(HEALTH)) errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("requestfailed", (r) => { if (r.url().startsWith(origin)) failed.push(r.url()); });
    let fixture = "base"; let gate = null;
    await page.route("**/*", async (route) => {
      const u = route.request().url();
      if (u.startsWith(origin)) return route.continue();
      if (u.includes(HEALTH)) {
        if (gate) await gate;
        const f = FIX[fixture];
        if (f.abort) return route.abort();
        return route.fulfill({ status: f.status, contentType: "application/json", body: f.raw || JSON.stringify(f.body) });
      }
      externals.push(u); return route.abort();
    });
    await page.clock.install();
    await page.goto(`${origin}/wiki/modules.html`);
    await page.waitForFunction(() => document.getElementById("dot-mod01").getAttribute("data-health") === "ok");
    let d = await dot(page, "dot-mod21"); ok(`${tag} MOD21 unknown neutral`, d.cls.includes("dot-unknown") && !d.cls.includes("dot-active") && d.aria === "Κατάσταση: άγνωστη", d);
    d = await dot(page, "dot-mod25"); ok(`${tag} MOD25 unknown`, d.cls.includes("dot-unknown"), d);
    d = await dot(page, "dot-mod23"); ok(`${tag} MOD23 disabled`, d.cls.includes("dot-planned") && d.h === "disabled", d);
    d = await dot(page, "dot-mod24"); ok(`${tag} MOD24 CPLM stays neutral despite Forum ok`, d.cls.includes("dot-unknown") && !d.cls.includes("dot-active"), d);
    d = await dot(page, "dot-mod02b"); ok(`${tag} MOD02b neutral`, d.cls.includes("dot-unknown"), d);
    d = await dot(page, "dot-mod09"); ok(`${tag} MOD09 deferred`, d.cls.includes("dot-planned"), d);
    d = await dot(page, "dot-mod18"); ok(`${tag} MOD18 paused unchanged`, d.cls === "status-dot dot-planned" && d.h === null, d);
    ok(`${tag} no text inside dot`, d.text === "", d);
    const bw = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(`${tag} no horizontal overflow`, bw <= 0, { overflow: bw });
    await page.screenshot({ path: path.join(OUT, `modules-${tag}-el-base.png`), fullPage: true });
    // EL -> EN -> EL via real button click
    await page.click("#langBtn");
    d = await dot(page, "dot-mod21"); ok(`${tag} EN label after click`, d.aria === "Status: unknown" && d.title === "Status: unknown", d);
    d = await dot(page, "dot-mod24"); ok(`${tag} EN label unmapped`, d.aria === "Status: unknown", d);
    await page.click("#langBtn");
    d = await dot(page, "dot-mod23"); ok(`${tag} EL label back`, d.aria === "Κατάσταση: απενεργοποιημένο", d);
    await page.click("#langBtn");
    // delayed reply arrives after language switched -> uses current language (EN)
    fixture = "next"; let release; gate = new Promise((r) => { release = r; });
    await page.clock.runFor(30000);
    await page.click("#langBtn"); await page.click("#langBtn"); // EN->EL->EN while pending
    release(); gate = null;
    await page.waitForFunction(() => document.getElementById("dot-mod01").getAttribute("data-health") === "error");
    d = await dot(page, "dot-mod01"); ok(`${tag} error + EN delayed label`, d.cls.includes("dot-error") && d.aria === "Status: error" && d.rowBorder.includes("solid"), d);
    d = await dot(page, "dot-mod02"); ok(`${tag} degraded`, d.cls.includes("dot-degraded") && d.aria === "Status: degraded", d);
    d = await dot(page, "dot-mod25"); ok(`${tag} MOD25 absent -> unknown`, d.cls.includes("dot-unknown"), d);
    await page.screenshot({ path: path.join(OUT, `modules-${tag}-en-transition.png`), fullPage: true });
    fixture = "heal"; await page.clock.runFor(30000);
    await page.waitForFunction(() => document.getElementById("dot-mod01").getAttribute("data-health") === "ok");
    d = await dot(page, "dot-mod01"); ok(`${tag} stale classes/highlight cleared`, d.cls === "status-dot dot-active" && d.rowBg === "" && d.rowBorder === "", d);
    d = await dot(page, "dot-mod03"); ok(`${tag} unrecognized status -> unknown`, d.cls.includes("dot-unknown"), d);
    d = await dot(page, "dot-mod04"); ok(`${tag} malformed entry -> unknown`, d.cls.includes("dot-unknown"), d);
    for (const f of ["non2xx", "malformed", "invalid", "fail"]) {
      fixture = "heal"; await page.clock.runFor(30000);
      await page.waitForFunction(() => document.getElementById("dot-mod05").getAttribute("data-health") === "ok");
      fixture = f; await page.clock.runFor(30000);
      await page.waitForFunction(() => document.getElementById("dot-mod05").getAttribute("data-health") === "unknown");
      d = await dot(page, "dot-mod05"); ok(`${tag} ${f} -> unknown, not green`, d.cls.includes("dot-unknown") && !d.cls.includes("dot-active"), d);
      d = await dot(page, "dot-mod09"); ok(`${tag} ${f} keeps MOD09 deferred`, d.cls.includes("dot-planned"), d);
    }
    await page.screenshot({ path: path.join(OUT, `modules-${tag}-en-fail.png`), fullPage: true });
    ok(`${tag} no console errors`, errors.length === 0, errors);
    ok(`${tag} no failed local requests`, failed.length === 0, failed);
    await ctx.close();
  }
  ok("no external requests beyond fixture", externals.every((u) => !u.includes("ekklesia.gr") || u.includes(HEALTH)), externals);
  const receipt = { task: "T-9072", commit: require("child_process").execSync("git rev-parse HEAD").toString().trim(), node: process.version, browser: `chromium ${browser.version()}`, playwright: require(require.resolve("playwright/package.json", { paths: [require("os").homedir()] })).version, fixtures: Object.keys(FIX), abortedExternal: externals, checks, pass: checks.every((c) => c.pass) };
  await browser.close(); server.close();
  fs.writeFileSync(path.join(OUT, "receipt.json"), JSON.stringify(receipt, null, 2));
  checks.filter((c) => !c.pass).forEach((c) => console.error("FAIL", c.name, JSON.stringify(c.detail)));
  console.log(`${checks.filter((c) => c.pass).length}/${checks.length} checks passed`);
  process.exit(receipt.pass ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(1); });

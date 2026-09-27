// T-415 (EKA-62) browser gate for the landing chat widget (#chatWidget).
// Serves the static docs/ tree locally and drives it in Chromium and WebKit.
// POST api.ekklesia.gr/api/v1/agent/ask is answered by page.route mocks; every
// other api.ekklesia.gr call gets 503 and every other non-local request is
// aborted, so nothing reaches production or a model provider.
//
// Usage: node scripts/redesign/t415_chat_widget.browser.cjs [outDir]
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

const DOCS = path.resolve(process.env.T415_DOCS || path.join(__dirname, "../../docs"));
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "../../.fleet/reports/T-415"));
fs.mkdirSync(OUT, { recursive: true });

const ENGINES = { chromium, webkit };
const VIEWPORTS = [
  { w: 1440, h: 900 },
  { w: 390, h: 844 },
  { w: 360, h: 640 },
];

const HOSTILE_Q = '<img src=x onerror="window.__pwned=1"><b>bold</b> & "q" \'x\'';
const HOSTILE_ANSWER = '<script>window.__pwned=2</script><img src=x onerror="window.__pwned=3"> 5 < 6 && a > b ' +
  "UNBROKEN" + "x".repeat(120) + "\n\n---\n⚠️ Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία.";
const HOSTILE_SOURCES = [
  { type: "knowledge_base", id: 7, category: "faq", title: '<i onmouseover="window.__pwned=4">KB</i> τίτλος' },
  { type: "parliament_bill", bill_id: "GR-2026-0002", title: '<svg onload="window.__pwned=5">' },
  { type: "knowledge_base", topic: "private_key" },
  "not-an-object",
];
const RATE_EL = "Πάρα πολλές ερωτήσεις σε σύντομο χρόνο";
const RATE_EN = "Too many questions in a short time";
const ERR_EL = "Ο βοηθός δεν μπόρεσε να απαντήσει";
const OFFLINE_EN = "Connection error.";

const json = (status, body) => (route) => route.fulfill({
  status, contentType: "application/json", body: JSON.stringify(body),
  headers: { "access-control-allow-origin": "*" },
});

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

async function newPage(browser, base, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, hasTouch: vp.w < 1000, serviceWorkers: "block", locale: "el-GR" });
  const page = await ctx.newPage();
  const errors = [];
  const dialogs = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("dialog", (d) => { dialogs.push(d.message()); d.dismiss(); });
  const api = { queue: [], requests: [] };
  await page.route("**/*", async (route) => {
    const req = route.request();
    const url = req.url();
    if (url.startsWith(base)) return route.continue();
    if (url.includes("api.ekklesia.gr/api/v1/agent/ask")) {
      if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type", "access-control-allow-methods": "POST" } });
      api.requests.push(JSON.parse(req.postData() || "{}"));
      const next = api.queue.shift() || json(500, { detail: "no mock queued" });
      return next(route);
    }
    if (url.includes("api.ekklesia.gr")) return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    return route.abort("blockedbyclient");
  });
  await page.goto(base, { waitUntil: "load" });
  await page.waitForTimeout(400);
  return { ctx, page, errors, dialogs, api };
}

const state = (page) => page.evaluate(() => {
  const msgs = document.getElementById("chatMessages");
  const nodes = Array.from(msgs.querySelectorAll(".chat-msg"));
  const last = nodes[nodes.length - 1] || null;
  return {
    panel: getComputedStyle(document.getElementById("chatPanel")).display,
    expanded: document.getElementById("chatToggle").getAttribute("aria-expanded"),
    active: document.activeElement && (document.activeElement.id || document.activeElement.tagName),
    kinds: nodes.map((n) => n.getAttribute("data-chat-kind")),
    lastKind: last && last.getAttribute("data-chat-kind"),
    lastText: last && last.firstChild && last.firstChild.nodeType === 3 ? last.firstChild.nodeValue : null,
    lastRole: last && last.getAttribute("role"),
    retry: !!(last && last.querySelector("[data-chat-retry]")),
    injected: msgs.querySelectorAll("img,script,svg,b,i,iframe,[onerror],[onload],[onmouseover]").length,
    pwned: window.__pwned || null,
    busy: msgs.getAttribute("aria-busy"),
  };
});
const waitSettled = (page) => page.waitForFunction(() => !document.querySelector('#chatMessages [data-chat-kind="loading"]'), null, { timeout: 5000 });

async function ask(page, text) {
  await page.locator("#chatInput").fill(text);
  await page.locator("#chatInput").press("Enter");
  await waitSettled(page);
}

async function layoutChecks(page, name, vp) {
  const m = await page.evaluate(() => {
    const p = document.getElementById("chatPanel").getBoundingClientRect();
    const de = document.documentElement;
    const msgs = document.getElementById("chatMessages");
    const bubbles = Array.from(msgs.querySelectorAll(".chat-msg")).filter((b) => b.scrollWidth > b.clientWidth + 1).length;
    const inp = document.getElementById("chatInput").getBoundingClientRect();
    const send = document.querySelector('#chatPanel button[data-en="Send"]').getBoundingClientRect();
    return { left: p.left, right: p.right, top: p.top, bottom: p.bottom, vw: de.clientWidth, vh: window.innerHeight,
      docOverflowX: de.scrollWidth - de.clientWidth, msgsOverflowX: msgs.scrollWidth - msgs.clientWidth, bubbles,
      sendInside: send.right <= p.right + 0.5 && inp.left >= p.left - 0.5 };
  });
  check(name, "panel fully inside viewport", m.left >= 0 && m.right <= m.vw && m.top >= 0 && m.bottom <= m.vh, m);
  check(name, "no document horizontal overflow", m.docOverflowX === 0, m.docOverflowX);
  check(name, "no chat horizontal overflow (long unbroken answer wraps)", m.msgsOverflowX <= 0 && m.bubbles === 0, m);
  check(name, "input and send button inside panel", m.sendInside, m);
}

async function runCase(engineName, browser, base, vp) {
  const name = `${engineName}-${vp.w}x${vp.h}`;
  const { ctx, page, errors, dialogs, api } = await newPage(browser, base, vp);

  // Keyboard open: focus toggle, Enter.
  await page.locator("#chatToggle").focus();
  await page.keyboard.press("Enter");
  let s = await state(page);
  check(name, "keyboard Enter opens panel, focuses input, aria-expanded", s.panel === "flex" && s.expanded === "true" && s.active === "chatInput", s);

  // Markup characters in question, answer and sources are rendered as text.
  api.queue.push(json(200, { question: HOSTILE_Q, answer: HOSTILE_ANSWER, model: "ollama", sources: HOSTILE_SOURCES, lang: "el" }));
  await ask(page, HOSTILE_Q);
  s = await state(page);
  const texts = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll("#chatMessages .chat-msg"));
    const user = nodes.filter((n) => n.getAttribute("data-chat-kind") === "user").pop();
    const bot = nodes.filter((n) => n.getAttribute("data-chat-kind") === "bot").pop();
    return { user: user && user.textContent, bot: bot && bot.firstChild.nodeValue,
      sources: bot ? Array.from(bot.querySelectorAll("[data-chat-sources] li")).map((li) => li.textContent) : [],
      sourcesHead: bot && bot.querySelector("[data-chat-sources] > div") && bot.querySelector("[data-chat-sources] > div").textContent };
  });
  check(name, "request carries exact question and lang=el", api.requests[0] && api.requests[0].question === HOSTILE_Q && api.requests[0].lang === "el", api.requests[0]);
  check(name, "question markup shown as literal text", texts.user === HOSTILE_Q, texts.user);
  check(name, "answer markup shown as literal text (incl. newlines)", texts.bot === HOSTILE_ANSWER, texts.bot);
  check(name, "sources rendered as text, invalid entries skipped", JSON.stringify(texts.sources) === JSON.stringify(['<i onmouseover="window.__pwned=4">KB</i> τίτλος', 'GR-2026-0002 — <svg onload="window.__pwned=5">']) && texts.sourcesHead === "Πηγές:", texts);
  check(name, "no element injected, no handler executed", s.injected === 0 && s.pwned === null && dialogs.length === 0, { injected: s.injected, pwned: s.pwned, dialogs });
  await page.mouse.move(vp.w - 60, vp.h - 200);
  await layoutChecks(page, name, vp);
  await page.screenshot({ path: path.join(OUT, `${name}-markup.png`) });

  // Normal EL answer.
  api.queue.push(json(200, { answer: "Η ψηφοφορία γίνεται στην εφαρμογή.", model: "ollama", sources: [], lang: "el" }));
  await ask(page, "Πώς ψηφίζω;");
  s = await state(page);
  check(name, "normal EL answer rendered as bot message", s.lastKind === "bot" && s.lastText === "Η ψηφοφορία γίνεται στην εφαρμογή." && api.requests[1].lang === "el", s);

  // 429 (EL): distinct state, bilingual copy, retry by keyboard.
  api.queue.push(json(429, { error: "Rate limit exceeded: 5 per 1 minute" }));
  await ask(page, "Ερώτηση έξι");
  s = await state(page);
  check(name, "429 shows distinct rate-limited state (EL)", s.lastKind === "rate-limited" && s.lastText.includes(RATE_EL) && s.lastRole === "alert" && s.retry, s);
  await page.screenshot({ path: path.join(OUT, `${name}-429-el.png`) });
  const before = api.requests.length;
  api.queue.push(json(200, { answer: "Απάντηση μετά την αναμονή.", model: "ollama", sources: [{ type: "knowledge_base", id: 1, category: "faq", title: "Συχνές ερωτήσεις" }], lang: "el" }));
  await page.locator('#chatMessages [data-chat-kind="rate-limited"] [data-chat-retry]').focus();
  await page.keyboard.press("Enter");
  await waitSettled(page);
  s = await state(page);
  const kinds = s.kinds.filter((k) => k !== "loading");
  check(name, "retry resends same question once and replaces 429 message", api.requests.length === before + 1 && api.requests[before].question === "Ερώτηση έξι" && s.lastKind === "bot" && !kinds.includes("rate-limited"), { n: api.requests.length - before, s });

  // Generic HTTP error is not the rate-limit message.
  api.queue.push(json(500, { detail: "boom" }));
  await ask(page, "Σφάλμα;");
  s = await state(page);
  check(name, "500 shows generic error, not rate-limit copy", s.lastKind === "error" && s.lastText.includes(ERR_EL) && !s.lastText.includes(RATE_EL) && s.retry, s);

  // Double Enter while a request is pending sends only once.
  const n0 = api.requests.length;
  api.queue.push(async (route) => { await new Promise((r) => setTimeout(r, 400)); return json(200, { answer: "Αργή απάντηση.", sources: [] })(route); });
  await page.locator("#chatInput").fill("Πρώτη");
  await page.locator("#chatInput").press("Enter");
  await page.locator("#chatInput").fill("Δεύτερη");
  await page.locator("#chatInput").press("Enter");
  const busy = (await state(page)).busy;
  await waitSettled(page);
  check(name, "pending request blocks a second send", api.requests.length === n0 + 1 && busy === "true", { sent: api.requests.length - n0, busy });

  // Switch to EN: normal answer, 429 and network failure in English.
  await page.evaluate(() => toggleLang());
  api.queue.push(json(200, { answer: "Voting happens in the app.", model: "ollama", sources: [{ type: "parliament_bill", bill_id: "GR-2026-0003", title: "Test bill" }], lang: "en" }));
  await ask(page, "How do I vote?");
  s = await state(page);
  const enSources = await page.evaluate(() => Array.from(document.querySelectorAll("#chatMessages .chat-msg")).pop().querySelector("[data-chat-sources]").textContent);
  check(name, "normal EN answer with lang=en and EN sources label", s.lastKind === "bot" && s.lastText === "Voting happens in the app." && api.requests[api.requests.length - 1].lang === "en" && enSources === "Sources:GR-2026-0003 — Test bill", { s, enSources });
  api.queue.push(json(429, { error: "Rate limit exceeded: 5 per 1 minute" }));
  await ask(page, "Sixth question");
  s = await state(page);
  const retryLabel = await page.locator('#chatMessages [data-chat-kind="rate-limited"] [data-chat-retry]').last().textContent();
  check(name, "429 shows distinct rate-limited state (EN)", s.lastKind === "rate-limited" && s.lastText.includes(RATE_EN) && retryLabel === "Try again", { s, retryLabel });
  await page.screenshot({ path: path.join(OUT, `${name}-429-en.png`) });
  api.queue.push((route) => route.abort("failed"));
  await ask(page, "Offline?");
  s = await state(page);
  check(name, "network failure shows connection error (EN)", s.lastKind === "error" && s.lastText.includes(OFFLINE_EN) && !s.lastText.includes(RATE_EN), s);
  await layoutChecks(page, `${name}-after`, vp);

  // Close via Escape (focus returns to toggle), reopen, close via ✕ button.
  await page.locator("#chatInput").focus();
  await page.keyboard.press("Escape");
  s = await state(page);
  check(name, "Escape closes panel and returns focus to toggle", s.panel === "none" && s.expanded === "false" && s.active === "chatToggle", s);
  await page.keyboard.press("Enter");
  s = await state(page);
  check(name, "reopen by keyboard keeps history", s.panel === "flex" && s.kinds.length > 5, s);
  await page.locator('#chatPanel button[aria-label="Κλείσιμο / Close"]').click();
  s = await state(page);
  check(name, "close button hides panel", s.panel === "none" && s.expanded === "false", s);

  check(name, "no page errors or dialogs", errors.length === 0 && dialogs.length === 0, { errors, dialogs });
  check(name, "every chat request was mocked (no unmocked call)", api.queue.length === 0, api.queue.length);
  await ctx.close();
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const versions = {};
  try {
    for (const [engineName, engine] of Object.entries(ENGINES)) {
      const browser = await engine.launch();
      versions[engineName] = browser.version();
      try {
        for (const vp of VIEWPORTS) await runCase(engineName, browser, base, vp);
      } finally {
        await browser.close();
      }
    }
  } finally {
    server.close();
  }
  const failed = results.filter((r) => !r.ok);
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify({ versions, total: results.length, failed: failed.length, results }, null, 2));
  console.log(`T-415 chat widget: ${results.length - failed.length}/${results.length} checks passed (${JSON.stringify(versions)})`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });

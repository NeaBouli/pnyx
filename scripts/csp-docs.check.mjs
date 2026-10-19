// Offline regressions for the real CSP listeners and optional browser policy checks.
// PLAYWRIGHT_MODULE points to an existing installation; nothing is downloaded.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';
const root = fileURLToPath(new URL('../', import.meta.url));
const source = readFileSync(resolve(root, 'docs/assets/js/events.js'), 'utf8');
function harness(extra = {}) {
  const listeners = new Map();
  const context = vm.createContext({ document: { addEventListener(type, fn) { listeners.set(type, fn); } }, ...extra });
  vm.runInContext(source, context);
  const node = (attrs, parentElement = null) => ({ dataset: {}, style: {}, parentElement, getAttribute: name => attrs[name] ?? null });
  const emit = (type, target, detail = {}) => {
    const event = { type, target, cancelBubble: false, defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.cancelBubble = true; }, ...detail };
    listeners.get(type)(event);
    return event;
  };
  return { node, emit };
}
test('literal and translated/dynamically inserted controls keep this, bubbling and return-false behavior', () => {
  const calls = [];
  const { node, emit } = harness({ openLegalModal: value => calls.push(value), filterByCat: (el, value) => calls.push([el, value]) });
  const parent = node({ 'data-csp-click': 'open-legal-modal-privacy-link' });
  assert.equal(emit('click', node({}, parent)).defaultPrevented, true);
  assert.deepEqual(calls, ['privacy']);
  const dynamic = node({ 'data-csp-click': 'filter-category' }); dynamic.dataset.value = 'category:bug';
  emit('click', dynamic);
  assert.deepEqual(calls[1], [dynamic, 'category:bug']);
});
test('generated ticket vote stops propagation to the surrounding ticket card', () => {
  const calls = [];
  const { node, emit } = harness({ toggleVote: n => calls.push(['vote', n]), selectTicket: n => calls.push(['select', n]) });
  const card = node({ 'data-csp-click': 'select-ticket' }); card.dataset.number = '42';
  const button = node({ 'data-csp-click': 'toggle-vote-stop' }, card); button.dataset.number = '42';
  emit('click', node({}, button));
  assert.deepEqual(calls, [['vote', 42]]);
  emit('click', card);
  assert.deepEqual(calls[1], ['select', 42]);
});
test('data values cannot introduce code and Enter triggers the chat listener', () => {
  let sent = 0;
  const { node, emit } = harness({ sendChat: () => sent++ });
  emit('click', node({ 'data-csp-click': 'sendChat()' }));
  emit('keydown', node({ 'data-csp-keydown': 'chat-enter' }), { key: 'Escape' });
  assert.equal(sent, 0);
  emit('keydown', node({ 'data-csp-keydown': 'chat-enter' }), { key: 'Enter' });
  assert.equal(sent, 1);
});

const browserModule = process.env.PLAYWRIGHT_MODULE;
test('Chromium/WebKit: JSON-LD, language, FAQ and generated demo controls under Report-Only then enforced CSP (no network)', { skip: !browserModule }, async () => {
  const require = createRequire(import.meta.url);
  const { chromium, webkit } = require(browserModule);
  const target = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const header of ['Content-Security-Policy-Report-Only', 'Content-Security-Policy']) {
        const context = await browser.newContext({ serviceWorkers: 'block' });
        await context.route('**/*', async route => {
          // Every request is fulfilled from disk or aborted; no HTTP/DNS fetch is made.
          const url = new URL(route.request().url());
          if (url.origin !== 'https://csp.invalid') return route.abort();
          const path = resolve(root, 'docs', '.' + decodeURIComponent(url.pathname));
          if (!path.startsWith(resolve(root, 'docs') + '/') || !existsSync(path)) return route.fulfill({ status: 404, body: '' });
          const type = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css' }[extname(path)] ?? 'application/octet-stream';
          return route.fulfill({ status: 200, headers: { [header]: target }, contentType: type, body: readFileSync(path) });
        });
        const page = await context.newPage();
        await page.addInitScript(() => {
          window.cspScriptViolations = [];
          document.addEventListener('securitypolicyviolation', e => {
            if (e.effectiveDirective.startsWith('script-src')) window.cspScriptViolations.push(e.effectiveDirective);
          });
        });
        await page.goto('https://csp.invalid/wiki/faq.html');
        const json = await page.locator('script[type="application/ld+json"]').allTextContents();
        assert.ok(json.length); json.forEach(body => JSON.parse(body));
        await page.locator('#langBtn').click();
        assert.equal(await page.locator('html').getAttribute('lang'), 'en');
        await page.locator('#langBtn').click();
        assert.equal(await page.locator('html').getAttribute('lang'), 'el');
        const faq = page.locator('[data-csp-click="toggle-parent"]').first();
        await faq.click();
        assert.ok(await faq.evaluate(el => el.parentElement.classList.contains('open')));
        assert.deepEqual(await page.evaluate(() => window.cspScriptViolations), []);
        await page.goto('https://csp.invalid/demo/bills.html');
        await page.locator('[data-csp-click="demo-filter"][data-value="ACTIVE"]').click();
        assert.equal(await page.evaluate(() => currentFilter), 'ACTIVE');
        const vote = page.locator('[data-csp-click="demo-vote"]').first();
        const bill = await vote.getAttribute('data-bill');
        await vote.click();
        assert.equal(await page.evaluate(id => demoGetVote(id), bill), 'YES');
        assert.deepEqual(await page.evaluate(() => window.cspScriptViolations), []);
        await context.close();
      }
    } finally { await browser.close(); }
  }
});

test('new-ticket listener preserves GitHub/QR guards and opens only after both checks', () => {
  for (const state of ['none', 'github', 'both']) {
    const calls = [];
    const storage = new Map(state === 'none' ? [] : state === 'github' ? [['polis_token', 'token']] : [['polis_token', 'token'], ['polis_nullifier', 'verified']]);
    const ctx = vm.createContext({
      document: { addEventListener() {} },
      sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
      login: () => calls.push('github'), openQRLogin: () => calls.push('qr'), openNewTicketModal: () => calls.push('open'),
    });
    vm.runInContext(readFileSync(resolve(root, 'docs/assets/js/tickets-auth-guard.js'), 'utf8'), ctx);
    const { node, emit } = harness({ requestNewTicket: event => ctx.requestNewTicket(event) });
    const event = emit('click', node({ 'data-csp-click': 'open-new-ticket-modal' }));
    assert.deepEqual(calls, [state === 'none' ? 'github' : state === 'github' ? 'qr' : 'open']);
    assert.equal(event.defaultPrevented, state !== 'both');
    if (state === 'github') assert.equal(storage.get('polis_pending_action'), 'new-ticket');
  }
});

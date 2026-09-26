// EKA-14 / EKA-15 regressions. Dependency-free: node --test scripts/static-docs-remote-sinks.check.mjs
// Executes the real patched functions against a minimal fake DOM that records every
// innerHTML write, so hostile remote strings can be traced to text vs. HTML sinks.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

const HOSTILE_LOGIN = '<img src=x onerror=alert(1)>';
const HOSTILE_ERROR = '<svg onload=alert(document.domain)>"\'&';
const HOSTILE_AVATARS = [
  'javascript:alert(1)',
  'data:image/svg+xml,<svg onload=alert(1)>',
  'http://avatars.githubusercontent.com/u/1?v=4',
  'https://evil.example/u/1?v=4',
  'https://avatars.githubusercontent.com.evil.example/u/1',
  '" onerror="alert(1)',
  '',
  null,
];
const GOOD_AVATAR = 'https://avatars.githubusercontent.com/u/12345?v=4';

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.style = { cssText: '', display: '' };
    this.listeners = {};
    this.htmlWrites = [];
    this.className = '';
    this._text = '';
    this._html = null;
  }
  set textContent(v) { this._text = String(v); this._html = null; this.children = []; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set innerHTML(v) { this.htmlWrites.push(String(v)); this._html = String(v); this._text = ''; this.children = []; }
  get innerHTML() {
    if (this._html !== null) return this._html;
    return this._text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  appendChild(c) { this.children.push(c); return c; }
  replaceChildren(...nodes) { this.children = nodes; this._html = null; this._text = ''; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  setAttribute(k, v) { this[k] = String(v); }
}

function fakeDocument() {
  const byId = new Map();
  return {
    byId,
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, new FakeElement('div'));
      return byId.get(id);
    },
    createElement: (tag) => new FakeElement(tag),
    querySelectorAll: () => [],
  };
}

function walk(el, out = []) {
  out.push(el);
  el.children.forEach((c) => walk(c, out));
  return out;
}

// Asserts a DOM-built subtree carries no HTML parsing and only safe element/attribute shapes.
function assertInertTree(container, allowedTags) {
  assert.deepEqual(container.htmlWrites, [], 'remote data must not be routed through innerHTML');
  for (const el of walk(container).slice(1)) {
    assert.ok(allowedTags.includes(el.tagName), `unexpected element ${el.tagName}`);
    assert.equal(el._html, null, `${el.tagName} must not receive innerHTML`);
    for (const key of Object.keys(el)) {
      if (/^on/i.test(key)) assert.equal(typeof el[key], 'function', `string handler ${key} set`);
    }
    if (el.tagName === 'IMG') {
      assert.match(el.src, /^https:\/\/avatars\.githubusercontent\.com\//, 'avatar src must be a GitHub https URL');
    }
  }
}

// Extracts a top-level function declaration (optionally async) by brace matching.
function extractFunction(source, name) {
  const m = new RegExp(`(async\\s+)?function ${name}\\(`).exec(source);
  assert.ok(m, `function ${name} not found`);
  let depth = 0;
  for (let i = source.indexOf('{', m.index); i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}' && --depth === 0) return source.slice(m.index, i + 1);
  }
  throw new Error(`unterminated function ${name}`);
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

// ─── docs/tickets/polis.js ──────────────────────────────────────────────────

function loadPolis() {
  const document = fakeDocument();
  const ctx = vm.createContext({
    document,
    URL,
    POLIS_CONFIG: { i18n: { el: {}, en: {} } },
    sessionStorage: { getItem: () => null, removeItem() {} },
    window: { location: { origin: 'https://ekklesia.gr' } },
  });
  vm.runInContext(read('docs/tickets/polis.js'), ctx, { filename: 'polis.js' });
  return { ctx, document };
}

test('polis.js: hostile GitHub login renders as text only', () => {
  const { ctx, document } = loadPolis();
  ctx.polisUser = { login: HOSTILE_LOGIN, avatar_url: GOOD_AVATAR };
  ctx.renderAuthStatus();
  const container = document.byId.get('authStatus');
  assertInertTree(container, ['DIV', 'IMG', 'SPAN', 'BUTTON']);
  const wrap = container.children[0];
  assert.equal(wrap.className, 'auth-status');
  const [img, name, btn] = wrap.children;
  assert.equal(img.src, 'https://avatars.githubusercontent.com/u/12345?v=4&s=56');
  assert.equal(img.className, 'auth-avatar');
  assert.equal(name.textContent, HOSTILE_LOGIN);
  assert.equal(btn.className, 'btn-logout');
  assert.equal(btn.listeners.click.length, 1);
});

test('polis.js: non-GitHub or non-https avatar URLs are dropped', () => {
  for (const avatar of HOSTILE_AVATARS) {
    const { ctx, document } = loadPolis();
    ctx.polisUser = { login: 'octocat', avatar_url: avatar };
    ctx.renderAuthStatus();
    const container = document.byId.get('authStatus');
    assertInertTree(container, ['DIV', 'IMG', 'SPAN', 'BUTTON']);
    const tags = container.children[0].children.map((c) => c.tagName);
    assert.deepEqual(tags, ['SPAN', 'BUTTON'], `avatar ${String(avatar)} must not render`);
    assert.equal(container.children[0].children[0].textContent, 'octocat');
  }
});

test('polis.js: GitHub API error message is escaped before innerHTML', async () => {
  const { ctx, document } = loadPolis();
  ctx.loadTickets = async () => { throw new Error(HOSTILE_ERROR); };
  await ctx.loadAndRender();
  const html = document.byId.get('ticketList').innerHTML;
  assert.ok(!html.includes('<svg'), 'raw error markup reached innerHTML');
  assert.ok(html.includes('&lt;svg onload=alert(document.domain)&gt;'), 'escaped error text missing');
  assert.ok(html.includes('class="empty-state"'), 'error presentation changed');
});

test('polis.js: comment author login is escaped', () => {
  const src = read('docs/tickets/polis.js');
  assert.ok(!/\+\s*c\.user\.login\s*\+/.test(src), 'raw comment login interpolation remains');
  assert.ok(src.includes('escapeHtml(c.user && c.user.login)'), 'escaped comment login missing');
  assert.ok(!/\+\s*e\.message\s*\+/.test(src), 'raw error message interpolation remains');
  assert.ok(!/\+\s*polisUser\.(login|avatar_url)\s*\+/.test(src), 'raw polisUser interpolation remains');
});

// ─── docs/index.html (ticket landing) ───────────────────────────────────────

async function runCheckTicketAuth(user) {
  const html = read('docs/index.html');
  const document = fakeDocument();
  const ctx = vm.createContext({
    document,
    URL,
    sessionStorage: { getItem: () => 'token', removeItem() {} },
    fetch: async () => ({ json: async () => user }),
  });
  vm.runInContext(`${extractFunction(html, 'ticketAvatarUrl')}\n${extractFunction(html, 'checkTicketAuth')}`, ctx);
  ctx.checkTicketAuth();
  await flush();
  return document.byId.get('ticketUserInfo');
}

test('index.html: hostile GitHub login renders as text only', async () => {
  const info = await runCheckTicketAuth({ login: HOSTILE_LOGIN, avatar_url: GOOD_AVATAR });
  assertInertTree(info, ['IMG', 'SPAN', 'BUTTON']);
  const [img, name, btn] = info.children;
  assert.equal(img.src, 'https://avatars.githubusercontent.com/u/12345?v=4&s=40');
  assert.equal(name.textContent, HOSTILE_LOGIN);
  assert.equal(btn.textContent, 'Logout');
  assert.equal(typeof btn.onclick, 'function');
});

test('index.html: non-GitHub or non-https avatar URLs are dropped', async () => {
  for (const avatar of HOSTILE_AVATARS) {
    const info = await runCheckTicketAuth({ login: 'octocat', avatar_url: avatar });
    assertInertTree(info, ['IMG', 'SPAN', 'BUTTON']);
    assert.deepEqual(info.children.map((c) => c.tagName), ['SPAN', 'BUTTON'], `avatar ${String(avatar)} must not render`);
  }
});

test('index.html: no raw GitHub user interpolation remains', () => {
  const html = read('docs/index.html');
  assert.ok(!/\+\s*u\.(login|avatar_url)\s*\+/.test(html), 'raw GitHub user interpolation remains');
});

// ─── docs/embed/qr-login.html ───────────────────────────────────────────────

async function runStartSessionError(status, body) {
  const html = read('docs/embed/qr-login.html');
  const document = fakeDocument();
  const ctx = vm.createContext({
    document,
    API: '',
    hide() {},
    show() {},
    getParams: () => ({ purpose: 'login' }),
    fetch: async () => ({ ok: false, status, json: async () => body }),
  });
  vm.runInContext(extractFunction(html, 'startSession'), ctx);
  await ctx.startSession();
  return document.byId.get('qr-container');
}

test('qr-login.html: hostile API detail renders as text only', async () => {
  const box = await runStartSessionError(400, { detail: HOSTILE_ERROR });
  assert.deepEqual(box.htmlWrites, [''], 'only the constant reset may use innerHTML');
  assert.equal(box.children.length, 1);
  const [p] = box.children;
  assert.equal(p.tagName, 'P');
  assert.equal(p._html, null);
  assert.equal(p.textContent, HOSTILE_ERROR);
  assert.equal(p.style.cssText, 'color:#dc2626;font-size:0.85rem');
});

test('qr-login.html: missing or non-string detail falls back to status text', async () => {
  assert.equal((await runStartSessionError(500, {})).children[0].textContent, 'API Error 500');
  const structured = await runStartSessionError(422, { detail: [{ msg: '<b>x</b>' }] });
  assert.equal(structured.children[0].textContent, 'API Error 422');
});

// ─── EKA-15: apps/web admin_key helpers ─────────────────────────────────────

function listFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? listFiles(p) : [p];
  });
}

test('apps/web/src ships no adminApi or admin_key query constructors', () => {
  const files = listFiles(join(root, 'apps/web/src')).filter((f) => /\.(ts|tsx|js|mjs)$/.test(f));
  assert.ok(files.length > 0);
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    assert.ok(!src.includes('admin_key'), `${f} still references admin_key`);
    assert.ok(!/\badminApi\b/.test(src), `${f} still references adminApi`);
  }
});

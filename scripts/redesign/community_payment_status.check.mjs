// Copyright (c) 2026 Vendetta Labs — MIT License
// Run with: node --test scripts/redesign/community_payment_status.check.mjs
// Real inline page behavior; all DOM, network and timers are memory-only fakes.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../../docs/community.html', import.meta.url), 'utf8');
const inline = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
  .map((match) => match[1])
  .find((source) => source.includes('@ai-anchor INVOICE_AMPEL_TIMER'));
assert.ok(inline, 'Community financial-status script must exist');

function harness(lang = 'el') {
  const elements = new Map();
  for (const match of html.matchAll(/<[^!\/][^>]*\bid="([^"]+)"[^>]*>/g)) {
    const opening = match[0];
    const attrs = new Map([...opening.matchAll(/([\w-]+)="([^"]*)"/g)]
      .map((attribute) => [attribute[1], attribute[2]]));
    const style = Object.fromEntries((attrs.get('style') || '').split(';')
      .filter((part) => part.includes(':'))
      .map((part) => part.split(':').map((value) => value.trim())));
    let content = html.slice(match.index + opening.length).split('</', 1)[0]
      .replace(/<[^>]*>/g, '');
    const element = {
      id: match[1], style, className: attrs.get('class') || '',
      getAttribute: (name) => attrs.get(name) ?? null,
      setAttribute: (name, value) => attrs.set(name, String(value)),
      classList: { add() {}, remove() {}, toggle() {} },
      get textContent() { return content; },
      set textContent(value) { content = String(value); },
      get innerHTML() { return content; },
      set innerHTML(value) { content = String(value).replace(/<[^>]*>/g, ''); },
    };
    elements.set(element.id, element);
  }
  const requests = [];
  const intervals = [];
  const context = vm.createContext({
    currentLang: lang,
    document: {
      getElementById: (id) => elements.get(id) ?? null,
      querySelectorAll: () => [],
      addEventListener() {},
    },
    window: {},
    console: { log() {}, warn() {}, error() {} },
    fetch: (url) => {
      if (url === 'https://api.ekklesia.gr/api/v1/payments/status') {
        return new Promise((resolve, reject) => requests.push({ resolve, reject }));
      }
      return Promise.reject(new Error('Unrelated endpoint is offline in this fixture'));
    },
    setInterval: (callback, ms) => { intervals.push({ callback, ms }); return intervals.length; },
    setTimeout: () => 0,
    clearTimeout() {},
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : ['2026-10-10T00:00:00Z'])); }
      static now() { return Date.parse('2026-10-10T00:00:00Z'); }
    },
  });
  vm.runInContext(inline, context, { timeout: 5000, filename: 'community.html:inline-finance' });
  const flush = async () => { for (let index = 0; index < 20; index += 1) await Promise.resolve(); };
  return {
    text(id) { assert.ok(elements.has(id), `Missing DOM element ${id}`); return elements.get(id).textContent; },
    element(id) { assert.ok(elements.has(id), `Missing DOM element ${id}`); return elements.get(id); },
    language(value) { context.currentLang = value; this.tick(); },
    tick() {
      const timer = intervals.find(({ callback, ms }) => callback.name === 'tick' && ms === 1000);
      assert.ok(timer, 'Real financial tick must be registered');
      timer.callback();
    },
    async respond(status, body) {
      const request = requests.shift();
      assert.ok(request, 'A financial-status request must be pending');
      request.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) });
      await flush();
    },
    async refresh(status, body) {
      const timer = intervals.find(({ callback }) => callback.name === 'fetchPaymentStatus');
      assert.ok(timer, 'Real financial refresh must be registered');
      timer.callback();
      await this.respond(status, body);
    },
    async failRefresh() {
      const timer = intervals.find(({ callback }) => callback.name === 'fetchPaymentStatus');
      assert.ok(timer, 'Real financial refresh must be registered');
      timer.callback();
      const request = requests.shift();
      assert.ok(request, 'A financial-status request must be pending');
      request.reject(new Error('Synthetic network failure'));
      await flush();
    },
  };
}

const snapshot = () => ({
  server: { received: 100, cost_total: 75, balance: 25, cost_monthly: 25, months_elapsed: 3 },
  domain: { received: 9.3, cost_total: 9.3, balance: 0, cost_yearly: 9.3, expires: '2028-03-29' },
  reserve: 5,
});

function assertUnknown(page) {
  for (const id of ['sReceived', 'sCost', 'sBalanceVal', 'dReceived', 'dCost', 'dBalanceVal', 'rReserveVal']) {
    assert.equal(page.text(id), '—', `${id} must not invent a zero or debit`);
  }
  assert.doesNotMatch(page.text('sBadge'), /NEEDS FUNDING|ΧΡΕΙΑΖΕΤΑΙ ΧΡΗΜΑΤΟΔΟΤΗΣΗ/);
  assert.doesNotMatch(page.element('sCard').className, /pulse-red/);
  assert.doesNotMatch(page.element('dCard').className, /pulse-red/);
}

function assertKnown(page, reserve = '5,00€') {
  assert.equal(page.text('sReceived'), '100,00€');
  assert.equal(page.text('sCost'), '-75,00€');
  assert.equal(page.text('sBalanceVal'), '25,00€');
  assert.equal(page.text('dReceived'), '9,30€');
  assert.equal(page.text('dCost'), '-9,30€');
  assert.equal(page.text('dBalanceVal'), '0,00€');
  assert.equal(page.text('rReserveVal'), reserve);
}

for (const lang of ['el', 'en']) {
  test(`initial pending request shows unknown accounting, not funding debt (${lang})`, () => {
    const page = harness(lang);
    assertUnknown(page);
    page.tick();
    assertUnknown(page);
  });

  test(`initial 503 stays neutral and reports unavailable (${lang})`, async () => {
    const page = harness(lang);
    await page.respond(503, { detail: 'Temporarily unavailable' });
    assertUnknown(page);
    for (const id of ['sDataHint', 'dDataHint', 'rUnavailable']) {
      assert.notEqual(page.element(id).style.display, 'none');
    }
  });
}

test('valid snapshot reaches every financial balance and hides unavailable hints', async () => {
  const page = harness();
  await page.respond(200, snapshot());
  assertKnown(page);
  for (const id of ['sDataHint', 'dDataHint', 'rUnavailable']) {
    assert.equal(page.element(id).style.display, 'none');
  }
});

test('later 503 preserves last-known balances, flags stale data, and recovers', async () => {
  const page = harness('en');
  await page.respond(200, snapshot());
  await page.refresh(503, { detail: 'Temporarily unavailable' });
  assertKnown(page);
  assert.notEqual(page.element('rUnavailable').style.display, 'none');
  for (const id of ['sDataHint', 'dDataHint']) {
    assert.notEqual(page.element(id).style.display, 'none');
    assert.match(page.text(id), /unavailable|last|stale/i);
  }
  page.language('el');
  assertKnown(page);
  assert.match(page.text('sDataHint'), /διαθέσι|Τελευτα|παλαι/i);
  page.language('en');
  assertKnown(page);
  assert.match(page.text('sDataHint'), /unavailable|last|stale/i);
  await page.refresh(200, snapshot());
  assertKnown(page);
  for (const id of ['sDataHint', 'dDataHint', 'rUnavailable']) {
    assert.equal(page.element(id).style.display, 'none');
  }
});

for (const body of [null, {}, { detail: 'Unavailable' }, { server: {}, domain: {} },
  { available: false, server: snapshot().server, domain: snapshot().domain }]) {
  test(`malformed 200 never fabricates fallback accounting: ${JSON.stringify(body)}`, async () => {
    const page = harness();
    await page.respond(200, body);
    assertUnknown(page);
  });
}

test('malformed server does not suppress a valid domain or reserve', async () => {
  const page = harness();
  const body = snapshot();
  body.server.received = '100';
  await page.respond(200, body);
  assert.equal(page.text('sReceived'), '—');
  assert.equal(page.text('sBalanceVal'), '—');
  assert.equal(page.text('dReceived'), '9,30€');
  assert.equal(page.text('dBalanceVal'), '0,00€');
  assert.equal(page.text('rReserveVal'), '5,00€');
  assert.notEqual(page.element('sDataHint').style.display, 'none');
  assert.equal(page.element('dDataHint').style.display, 'none');
});

test('malformed domain does not suppress a valid server or reserve', async () => {
  const page = harness();
  const body = snapshot();
  body.domain.balance = null;
  await page.respond(200, body);
  assert.equal(page.text('sReceived'), '100,00€');
  assert.equal(page.text('sBalanceVal'), '25,00€');
  assert.equal(page.text('dReceived'), '—');
  assert.equal(page.text('dBalanceVal'), '—');
  assert.equal(page.text('rReserveVal'), '5,00€');
  assert.equal(page.element('sDataHint').style.display, 'none');
  assert.notEqual(page.element('dDataHint').style.display, 'none');
});

test('legitimate zero balances are received data, not unavailable placeholders', async () => {
  const page = harness();
  const zero = snapshot();
  zero.server = { ...zero.server, received: 0, cost_total: 0, balance: 0 };
  zero.domain = { ...zero.domain, received: 0, cost_total: 0, balance: 0 };
  zero.reserve = 0;
  await page.respond(200, zero);
  for (const id of ['sReceived', 'sBalanceVal', 'dReceived', 'dBalanceVal', 'rReserveVal']) {
    assert.equal(page.text(id), '0,00€');
  }
  for (const id of ['sDataHint', 'dDataHint', 'rUnavailable']) {
    assert.equal(page.element(id).style.display, 'none');
  }
  page.language('en');
  assert.equal(page.text('sBalanceVal'), '0,00€');
  page.language('el');
  assert.equal(page.text('rReserveVal'), '0,00€');
});

function assertStaleReserve(page, value = '5,00€', lang = 'en') {
  assert.equal(page.text('rReserveVal'), value);
  assert.notEqual(page.element('rUnavailable').style.display, 'none');
  assert.match(page.text('rUnavailable'), lang === 'en'
    ? /last valid|stale/i
    : /Τελευταία έγκυρα|παλαι/i);
}

const invalidReserveResponses = [
  { name: '503', status: 503, body: { detail: 'Temporarily unavailable' } },
  { name: 'numeric string', status: 200, body: { ...snapshot(), reserve: '5' } },
  { name: 'null reserve', status: 200, body: { ...snapshot(), reserve: null } },
  { name: 'missing reserve', status: 200, body: { server: snapshot().server, domain: snapshot().domain } },
  { name: 'NaN reserve', status: 200, body: { ...snapshot(), reserve: NaN } },
  { name: 'infinite reserve', status: 200, body: { ...snapshot(), reserve: Infinity } },
  { name: 'object reserve', status: 200, body: { ...snapshot(), reserve: {} } },
  { name: 'null payload', status: 200, body: null },
  { name: 'unavailable with numeric reserve', status: 200, body: { ...snapshot(), available: false, reserve: 99 } },
];

for (const { name, status, body } of invalidReserveResponses) {
  test(`last valid reserve is retained and marked stale after ${name}`, async () => {
    const page = harness('en');
    await page.respond(200, snapshot());
    await page.refresh(status, body);
    assertKnown(page);
    assertStaleReserve(page);
    page.tick();
    assertStaleReserve(page);
  });
}

test('reserve survives a network failure without suppressing cached server/domain balances', async () => {
  const page = harness('en');
  await page.respond(200, snapshot());
  await page.failRefresh();
  assertKnown(page);
  assertStaleReserve(page);
});

test('zero is a valid cached reserve and remains zero after a failed refresh', async () => {
  const page = harness('en');
  await page.respond(200, { ...snapshot(), reserve: 0 });
  assert.equal(page.text('rReserveVal'), '0,00€');
  assert.equal(page.element('rUnavailable').style.display, 'none');
  await page.refresh(503, { detail: 'Temporarily unavailable' });
  assertStaleReserve(page, '0,00€');
});

test('stale reserve rerenders EL/EN and a new valid value or zero clears the notice', async () => {
  const page = harness('el');
  await page.respond(200, snapshot());
  await page.refresh(503, { detail: 'Temporarily unavailable' });
  assertStaleReserve(page, '5,00€', 'el');
  page.language('en');
  assertStaleReserve(page);
  page.language('el');
  assertStaleReserve(page, '5,00€', 'el');
  await page.refresh(200, { ...snapshot(), reserve: 11.25 });
  assert.equal(page.text('rReserveVal'), '11,25€');
  assert.equal(page.element('rUnavailable').style.display, 'none');
  await page.refresh(503, { detail: 'Temporarily unavailable' });
  assertStaleReserve(page, '11,25€', 'el');
  await page.refresh(200, { ...snapshot(), reserve: 0 });
  assert.equal(page.text('rReserveVal'), '0,00€');
  assert.equal(page.element('rUnavailable').style.display, 'none');
});

test('an invalid reserve does not suppress independently valid server and domain updates', async () => {
  const page = harness('en');
  await page.respond(200, snapshot());
  const updated = snapshot();
  updated.server.received = 200;
  updated.server.balance = 125;
  updated.domain.received = 10.3;
  updated.domain.balance = 1;
  updated.reserve = 'invalid';
  await page.refresh(200, updated);
  assert.equal(page.text('sReceived'), '200,00€');
  assert.equal(page.text('sBalanceVal'), '125,00€');
  assert.equal(page.text('dReceived'), '10,30€');
  assert.equal(page.text('dBalanceVal'), '1,00€');
  assert.equal(page.element('sDataHint').style.display, 'none');
  assert.equal(page.element('dDataHint').style.display, 'none');
  assertStaleReserve(page);
});

for (const body of [{ ...snapshot(), reserve: null }, { ...snapshot(), reserve: '5' },
  { ...snapshot(), available: false, reserve: 99 }]) {
  test(`without a prior valid reserve unavailable does not invent cached money: ${JSON.stringify(body)}`, async () => {
    const page = harness('en');
    await page.respond(200, body);
    assert.equal(page.text('rReserveVal'), '—');
    assert.notEqual(page.element('rUnavailable').style.display, 'none');
    assert.match(page.text('rUnavailable'), /unavailable/i);
    assert.doesNotMatch(page.text('rUnavailable'), /last valid|stale/i);
    page.language('el');
    assert.equal(page.text('rReserveVal'), '—');
    assert.match(page.text('rUnavailable'), /διαθέσι/i);
  });
}

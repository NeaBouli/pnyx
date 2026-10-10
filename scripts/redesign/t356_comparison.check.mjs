// Same-bill comparison behavior: actual Landing IIFE, memory-only DOM/fetch/timers.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../../docs/index.html', import.meta.url), 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
  .map((match) => match[1]).find((source) => source.includes('function fetchRepresentation()'));
assert.ok(script, 'Real Representation IIFE must exist');
const REP = 'https://api.ekklesia.gr/api/v1/analytics/representation';
const resultsURL = (id) => `https://api.ekklesia.gr/api/v1/public/bills/${encodeURIComponent(id)}/results`;
const representation = (id = 'GR-T356', score = 73) => ({
  cumulative_representation: score, cumulative_divergence: score === null ? null : 100 - score,
  total_citizen_votes: 1234, bills_analyzed: 2,
  last_bill: id === null ? null : { bill_id: id, title_el: 'Synthetic bill', citizen_votes: 100, divergence: 40, representation: score },
});
const result = (id = 'GR-T356') => ({
  bill_id: id, status: 'PARLIAMENT_VOTED', results_hidden: false,
  citizen_votes: { yes: 60, no: 35, abstain: 5, unknown: 0, total: 100 },
  parliament_votes: { A: 'YES', B: 'NO', C: 'ABSTAIN' },
});

function harness(lang = 'el') {
  const elements = new Map(), requests = [], history = [], intervals = [];
  for (const match of html.matchAll(/<[^!\/][^>]*\bid="([^"]+)"[^>]*>/g)) {
    const attrs = new Map([...match[0].matchAll(/([\w-]+)="([^"]*)"/g)].map((item) => [item[1], item[2]]));
    const style = Object.fromEntries((attrs.get('style') || '').split(';').filter((part) => part.includes(':'))
      .map((part) => { const colon = part.indexOf(':'); return [part.slice(0, colon).trim(), part.slice(colon + 1).trim()]; }));
    let text = html.slice(match.index + match[0].length).split('</', 1)[0].replace(/<[^>]*>/g, '');
    elements.set(match[1], {
      style, className: attrs.get('class') || '',
      getAttribute: (key) => attrs.get(key) ?? null,
      setAttribute: (key, value) => attrs.set(key, String(value)),
      get textContent() { return text; }, set textContent(value) { text = String(value); },
      set innerHTML(_value) { assert.fail('Dynamic comparison data must not use innerHTML'); },
    });
  }
  const context = vm.createContext({
    currentLang: lang, console: { log() {}, warn() {}, error() {} },
    document: { getElementById: (id) => elements.get(id) ?? null }, window: {},
    fetch: (url) => {
      history.push(url);
      assert.ok(url === REP || /^https:\/\/api\.ekklesia\.gr\/api\/v1\/public\/bills\/[^/]+\/results$/.test(url), 'Only existing public mocked reads are allowed');
      return new Promise((resolve, reject) => requests.push({ url, resolve, reject }));
    },
    setInterval: (callback, ms) => { intervals.push({ callback, ms }); return intervals.length; },
  });
  vm.runInContext(script, context, { timeout: 5000, filename: 'index.html:representation' });
  const flush = async () => { for (let i = 0; i < 25; i++) await Promise.resolve(); };
  const take = (url) => {
    const index = requests.findIndex((request) => request.url === url);
    assert.notEqual(index, -1, `Expected pending request ${url}`);
    return requests.splice(index, 1)[0];
  };
  return {
    history, requests, take,
    element(id) { assert.ok(elements.has(id), `Missing DOM ${id}`); return elements.get(id); },
    text(id) { return this.element(id).textContent; },
    async deliver(request, body, status = 200) {
      request.resolve({ ok: status >= 200 && status < 300, status, json: async () => body });
      await flush();
    },
    async respond(url, body, status = 200) { await this.deliver(take(url), body, status); },
    async fail(url) { take(url).reject(new Error('Synthetic offline fixture')); await flush(); },
    refresh() {
      const timer = intervals.find(({ callback }) => callback.name === 'fetchRepresentation');
      assert.ok(timer, 'Real Representation refresh must be registered'); timer.callback();
    },
    language(value) {
      context.currentLang = value;
      // Same data-el/en DOM update performed by the page's existing toggleLang.
      for (const element of elements.values()) {
        const translated = element.getAttribute(`data-${value}`);
        if (translated !== null) element.textContent = translated;
      }
    },
  };
}

function neutral(page, lang = 'el') {
  for (const id of ['repParliamentValue', 'repCitizenValue']) assert.equal(page.text(id), '—');
  for (const id of ['repParliamentFill', 'repCitizenFill']) assert.equal(page.element(id).style.width, '0%');
  assert.match(page.text('repComparisonNote'), lang === 'el' ? /Δεν υπάρχουν διαθέσιμα έγκυρα/ : /unavailable/);
}

function comparison(page, lang = 'el', parliament = 100 / 3, citizen = 60) {
  const label = (n) => n.toFixed(2).replace('.', lang === 'el' ? ',' : '.') + (lang === 'el' ? '% Υπέρ' : '% YES');
  assert.equal(page.text('repParliamentValue'), label(parliament));
  assert.equal(page.text('repCitizenValue'), label(citizen));
  assert.ok(Math.abs(parseFloat(page.element('repParliamentFill').style.width) - parliament) < 0.02);
  assert.ok(Math.abs(parseFloat(page.element('repCitizenFill').style.width) - citizen) < 0.02);
  assert.match(page.text('repComparisonNote'), lang === 'el' ? /Ίδιο νομοσχέδιο:/ : /Same bill:/);
  assert.match(page.text('repComparisonNote'), lang === 'el' ? /Όχι ποσοστό βουλευτών/ : /Not MP percentages/);
}

for (const lang of ['el', 'en']) {
  test(`same bill: 33.33% reported parties vs 60% citizens, not cumulative score (${lang})`, async () => {
    const page = harness(lang); neutral(page, lang);
    await page.respond(REP, representation());
    await page.respond(resultsURL('GR-T356'), result());
    comparison(page, lang); assert.equal(page.text('repScore'), '73%');
    page.language(lang === 'el' ? 'en' : 'el'); comparison(page, lang === 'el' ? 'en' : 'el');
    page.language(lang); comparison(page, lang);
    assert.deepEqual(page.history, [REP, resultsURL('GR-T356')]);
  });
  test(`zero YES is real data, never neutral (${lang})`, async () => {
    const page = harness(lang), data = result();
    data.citizen_votes = { yes: 0, no: 100, abstain: 0, unknown: 0, total: 100 };
    data.parliament_votes = { A: 'NO', B: 'ABSTAIN' };
    await page.respond(REP, representation()); await page.respond(resultsURL('GR-T356'), data);
    comparison(page, lang, 0, 0);
  });
}

const invalid = [
  ['hidden', (d) => { d.results_hidden = true; }],
  ['missing hidden flag', (d) => { delete d.results_hidden; }],
  ['active', (d) => { d.status = 'ACTIVE'; }],
  ['24-hour window', (d) => { d.status = 'WINDOW_24H'; }],
  ['wrong bill', (d) => { d.bill_id = 'GR-OTHER'; }],
  ['missing citizen counts', (d) => { delete d.citizen_votes; }],
  ['numeric string', (d) => { d.citizen_votes.yes = '60'; }],
  ['negative count', (d) => { d.citizen_votes.yes = -1; }],
  ['fractional count', (d) => { d.citizen_votes.yes = 59.5; }],
  ['unsafe total', (d) => { d.citizen_votes = { yes: Number.MAX_SAFE_INTEGER + 1, no: 0, abstain: 0, unknown: 0, total: Number.MAX_SAFE_INTEGER + 1 }; }],
  ['sum mismatch', (d) => { d.citizen_votes.total = 101; }],
  ['empty citizen total', (d) => { d.citizen_votes = { yes: 0, no: 0, abstain: 0, unknown: 0, total: 0 }; }],
  ['empty parties', (d) => { d.parliament_votes = {}; }],
  ['missing parties', (d) => { delete d.parliament_votes; }],
  ['array parties', (d) => { d.parliament_votes = ['YES']; }],
  ['unknown party', (d) => { d.parliament_votes.B = 'UNKNOWN'; }],
  ['null party', (d) => { d.parliament_votes.B = null; }],
  ['non-string party', (d) => { d.parliament_votes.B = 1; }],
  ['blank party name', (d) => { d.parliament_votes[' '] = 'YES'; }],
];
for (const [name, mutate] of invalid) {
  test(`${name} makes both comparison bars neutral, including after prior valid data`, async () => {
    const page = harness();
    await page.respond(REP, representation()); await page.respond(resultsURL('GR-T356'), result());
    comparison(page); page.refresh(); neutral(page);
    await page.respond(REP, representation()); const data = result(); mutate(data);
    await page.respond(resultsURL('GR-T356'), data); neutral(page);
    page.language('en'); neutral(page, 'en');
  });
}

test('OPEN_END and all recognized Greek positions preserve the denominator', async () => {
  const page = harness(), data = result();
  data.status = 'OPEN_END'; data.parliament_votes = { A: 'ΝΑΙ', B: 'ΟΧΙ', C: 'ΠΑΡΩΝ', D: 'ΑΠΟΧΗ' };
  await page.respond(REP, representation()); await page.respond(resultsURL('GR-T356'), data);
  comparison(page, 'el', 25, 60);
});

test('valid last-bill comparison is independent of an absent cumulative score', async () => {
  const page = harness(); await page.respond(REP, representation('GR-T356', null));
  await page.respond(resultsURL('GR-T356'), result()); comparison(page); assert.equal(page.text('repScore'), '—');
});

test('missing last bill performs no substitute request', async () => {
  const page = harness(); await page.respond(REP, representation(null)); neutral(page);
  assert.deepEqual(page.history, [REP]);
});

test('bill IDs are safely encoded, not appended as endpoint syntax', async () => {
  const page = harness(), id = 'GR/A ?'; await page.respond(REP, representation(id));
  assert.equal(page.history[1], resultsURL(id)); await page.respond(resultsURL(id), result(id)); comparison(page);
});

for (const status of [404, 503]) {
  test(`public results HTTP ${status} stays neutral`, async () => {
    const page = harness(); await page.respond(REP, representation());
    await page.respond(resultsURL('GR-T356'), result(), status); neutral(page);
  });
}

test('public results network failure stays neutral', async () => {
  const page = harness(); await page.respond(REP, representation());
  await page.fail(resultsURL('GR-T356')); neutral(page);
});

test('late result after actual language state changed renders EN, then EL', async () => {
  const page = harness(); await page.respond(REP, representation());
  page.language('en'); await page.respond(resultsURL('GR-T356'), result());
  comparison(page, 'en'); page.language('el'); comparison(page);
});

test('older bill response cannot overwrite the newer selected bill', async () => {
  const page = harness(); await page.respond(REP, representation('GR-A'));
  const old = page.take(resultsURL('GR-A')); page.refresh();
  await page.respond(REP, representation('GR-B'));
  const data = result('GR-B'); data.citizen_votes = { yes: 20, no: 80, abstain: 0, unknown: 0, total: 100 };
  await page.respond(resultsURL('GR-B'), data); comparison(page, 'el', 100 / 3, 20);
  await page.deliver(old, result('GR-A')); comparison(page, 'el', 100 / 3, 20);
  assert.match(page.text('repComparisonNote'), /GR-B/);
});

test('refresh with no selected bill invalidates an older pending result', async () => {
  const page = harness(); await page.respond(REP, representation());
  const old = page.take(resultsURL('GR-T356')); page.refresh();
  await page.respond(REP, representation(null)); await page.deliver(old, result()); neutral(page);
});

test('out-of-order Representation responses cannot initiate stale bill lookup', async () => {
  const page = harness(), old = page.take(REP); page.refresh();
  await page.respond(REP, representation('GR-B')); await page.respond(resultsURL('GR-B'), result('GR-B'));
  await page.deliver(old, representation('GR-A')); comparison(page);
  assert.ok(!page.history.includes(resultsURL('GR-A'))); assert.match(page.text('repComparisonNote'), /GR-B/);
});

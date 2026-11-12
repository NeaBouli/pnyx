import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { scriptBodies } from '../../../scripts/docs-scripts.mjs';

const page = new URL('./index.html', import.meta.url);
const html = readFileSync(page, 'utf8');
const code = scriptBodies(page, new URL('../../../docs/representative/index.html', import.meta.url)).join('\n');

async function renderResults(payload) {
  const billsList = { innerHTML: '', addEventListener() {} };
  const context = {
    window: {},
    localStorage: { getItem: () => '' },
    document: {
      getElementById: (id) => id === 'billsList' ? billsList : null,
      addEventListener() {},
    },
    fetch: async () => ({ json: async () => payload }),
    setTimeout,
  };
  vm.runInNewContext(code, context);
  await context.loadResults('REP-1');
  return billsList.innerHTML;
}

test('suppressed or null vote results render the Greek small-cell state', async () => {
  const cases = [
    { suppressed: true, total: null, yes_pct: null, no_pct: null },
    { suppressed: false, total: null, yes_pct: null, no_pct: null },
  ];
  for (const result of cases) {
    const output = await renderResults({
      title_el: '<script>alert(1)</script>',
      ...result,
      party_votes: null,
      consensus_count: 0,
    });
    assert.match(output, /Δεν υπάρχουν αρκετές ψήφοι για εμφάνιση αποτελεσμάτων/);
    assert.match(output, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.doesNotMatch(output, /<script>alert/);
    assert.doesNotMatch(output, /NaN|100%|0%|bar-wrap/);
  }
});

test('the representative page stays Greek-first and does not interpolate API data unsafely', () => {
  assert.match(html, /lang="el"/);
  assert.match(code, /esc\(d\.title_el\)/);
});

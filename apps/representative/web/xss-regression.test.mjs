import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'index.html'), 'utf8');

test('esc() and num() helpers are defined before first use', () => {
  const escAt = html.indexOf('function esc(');
  const numAt = html.indexOf('function num(');
  assert.ok(escAt > -1 && numAt > -1, 'helpers missing');
  assert.ok(escAt < html.indexOf('async function loadBills'), 'helpers must precede loadBills');
});

test('no raw scraper/API strings are interpolated into innerHTML', () => {
  for (const raw of ['+b.title_el+', '+d.title_el+', '+q.question_el+', '+q.category+', "'+(sl[b.status]||b.status)+'"]) {
    assert.equal(html.includes(raw), false, `unescaped interpolation still present: ${raw}`);
  }
});

test('bill ids are not interpolated into inline event-handler attributes', () => {
  assert.equal(html.includes('onclick="loadResults('), false, 'dynamic onclick handler still present');
  assert.match(html, /data-billid="'\+esc\(b\.id\)\+'/, 'data-billid binding missing');
  assert.match(html, /addEventListener\('click'/, 'delegated click listener missing');
});

test('bill ids are URL-encoded before hitting the API path', () => {
  assert.match(html, /\/rep\/results\/'\+encodeURIComponent\(billId\)/, 'billId must be encodeURIComponent-wrapped');
});

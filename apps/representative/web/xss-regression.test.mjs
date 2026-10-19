import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { scriptBodies } from '../../../scripts/docs-scripts.mjs';

const page = new URL('./index.html', import.meta.url);
const html = readFileSync(page, 'utf8');
// apps/web/Dockerfile copies this page to public/representative/index.html.
const scripts = scriptBodies(page, new URL('../../../docs/representative/index.html', import.meta.url));
const code = scripts.join('\n');
const source = html + '\n' + code;

test('esc() and num() helpers are defined before first use', () => {
  // Deferred classic scripts execute in tag order after parsing.
  for (const [, attrs] of html.matchAll(/<script\b([^>]*)>/gi)) {
    assert.match(attrs, /\bdefer\b/);
    assert.doesNotMatch(attrs, /\basync\b|\btype\s*=\s*["']module["']/i);
  }
  const escAt = code.indexOf('function esc(');
  const numAt = code.indexOf('function num(');
  const loadBillsAt = code.indexOf('async function loadBills');
  assert.ok(escAt > -1 && numAt > -1, 'helpers missing');
  assert.ok(loadBillsAt > -1, 'loadBills missing');
  assert.ok(escAt < loadBillsAt && numAt < loadBillsAt, 'helpers must precede loadBills in script load order');
});

test('no raw scraper/API strings are interpolated into innerHTML', () => {
  for (const raw of ['+b.title_el+', '+d.title_el+', '+q.question_el+', '+q.category+', "'+(sl[b.status]||b.status)+'"]) {
    assert.equal(source.includes(raw), false, `unescaped interpolation still present: ${raw}`);
  }
});

test('bill ids are not interpolated into inline event-handler attributes', () => {
  assert.equal(source.includes('onclick="loadResults('), false, 'dynamic onclick handler still present');
  assert.match(code, /data-billid="'\+esc\(b\.id\)\+'/, 'data-billid binding missing');
  assert.match(code, /addEventListener\('click'/, 'delegated click listener missing');
  assert.match(code, /loadResults\(card\.getAttribute\('data-billid'\)\)/, 'delegated bill id missing');
});

test('bill ids are URL-encoded before hitting the API path', () => {
  assert.match(code, /\/rep\/results\/'\+encodeURIComponent\(billId\)/, 'billId must be encodeURIComponent-wrapped');
});

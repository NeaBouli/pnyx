// node --test scripts/npm-audit-gate.check.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evaluate } from './npm-audit-gate.mjs';

const ADV = (id, sev = 'high', name = 'node-forge') => ({ source: 1, name, severity: sev, url: `https://github.com/advisories/${id}` });
const report = (extra = {}) => ({ vulnerabilities: {
  'node-forge': { severity: 'high', via: [ADV('GHSA-86w9-cpqp-85rv')] },
  '@expo/cli': { severity: 'high', via: ['node-forge'] },
  expo: { severity: 'high', via: ['@expo/cli'] },
  ...extra,
} });
const allow = { entries: [{ id: 'GHSA-86w9-cpqp-85rv', workspaces: ['apps/mobile'], review_by: '2026-11-01' }] };

test('allowlisted advisory and its dependents pass in the listed workspace', () => {
  const r = evaluate(report(), 'apps/mobile', allow, '2026-10-02');
  assert.deepEqual(r.blocking, []);
  assert.deepEqual(r.waived, ['GHSA-86w9-cpqp-85rv (node-forge)']);
});

test('the same advisory blocks in a workspace that is not listed', () => {
  assert.deepEqual(evaluate(report(), 'apps/web', allow, '2026-10-02').blocking, ['GHSA-86w9-cpqp-85rv (node-forge)']);
});

test('an expired entry fails the gate', () => {
  const r = evaluate(report(), 'apps/mobile', allow, '2026-11-02');
  assert.deepEqual(r.expired, ['GHSA-86w9-cpqp-85rv expired on 2026-11-01']);
  assert.ok(r.blocking.length > 0);
});

test('any other high advisory still blocks, even through an allowlisted package chain', () => {
  const r = evaluate(report({ undici: { severity: 'high', via: [ADV('GHSA-aaaa-bbbb-cccc', 'high', 'undici')] },
    expo: { severity: 'high', via: ['@expo/cli', 'undici'] } }), 'apps/mobile', allow, '2026-10-02');
  assert.deepEqual(r.blocking, ['GHSA-aaaa-bbbb-cccc (undici)']);
});

test('moderate advisories are ignored like npm audit --audit-level=high', () => {
  assert.deepEqual(evaluate({ vulnerabilities: { x: { severity: 'moderate', via: [ADV('GHSA-xxxx-yyyy-zzzz', 'moderate', 'x')] } } }, 'apps/mobile', allow, '2026-10-02').blocking, []);
});

test('an errored or empty audit report fails closed', () => {
  assert.equal(evaluate(null, 'apps/mobile', allow, '2026-10-02').blocking.length, 1);
  assert.equal(evaluate({ error: { code: 'ENOTFOUND' } }, 'apps/mobile', allow, '2026-10-02').blocking.length, 1);
  assert.equal(evaluate({}, 'apps/mobile', allow, '2026-10-02').blocking.length, 1);
});

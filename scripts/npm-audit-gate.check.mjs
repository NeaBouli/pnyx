// node --test scripts/npm-audit-gate.check.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evaluate, entryProblems, parseDate } from './npm-audit-gate.mjs';

const TODAY = '2026-10-02';
const ADV = (id, sev = 'high', name = 'node-forge') => ({ source: 1, name, severity: sev, url: `https://github.com/advisories/${id}` });
const report = (extra = {}) => ({ vulnerabilities: {
  'node-forge': { severity: 'high', via: [ADV('GHSA-86w9-cpqp-85rv')] },
  '@expo/cli': { severity: 'high', via: ['node-forge'] },
  expo: { severity: 'high', via: ['@expo/cli'] },
  ...extra,
} });
const ENTRY = {
  id: 'GHSA-86w9-cpqp-85rv', package: 'node-forge', workspaces: ['apps/mobile'], reason: 'tooling only',
  approved_by: 'Gio', approved_on: '2026-10-02', approval_source: 'session 2026-10-02', review_by: '2026-11-01',
};
const allow = (over = {}) => ({ entries: [{ ...ENTRY, ...over }] });
const run = (r, ws = 'apps/mobile', a = allow(), today = TODAY) => evaluate(r, ws, a, today);
const fails = (res) => res.blocking.length > 0 || res.invalid.length > 0;

test('approved allowlisted advisory and its dependents pass in the listed workspace', () => {
  const r = run(report());
  assert.deepEqual(r.blocking, []);
  assert.deepEqual(r.invalid, []);
  assert.deepEqual(r.waived, ['GHSA-86w9-cpqp-85rv (node-forge)']);
});

test('the same advisory blocks in a workspace that is not listed', () => {
  assert.deepEqual(run(report(), 'apps/web').blocking, ['GHSA-86w9-cpqp-85rv (node-forge)']);
});

test('an expired entry fails the gate', () => {
  const r = run(report(), 'apps/mobile', allow(), '2026-11-02');
  assert.ok(r.invalid.some((e) => e.includes('expired on 2026-11-01')));
  assert.ok(r.blocking.length > 0);
});

test('any other high advisory still blocks, even through an allowlisted package chain', () => {
  const r = run(report({ undici: { severity: 'high', via: [ADV('GHSA-aaaa-bbbb-cccc', 'high', 'undici')] },
    expo: { severity: 'high', via: ['@expo/cli', 'undici'] } }));
  assert.deepEqual(r.blocking, ['GHSA-aaaa-bbbb-cccc (undici)']);
});

test('moderate advisories are ignored like npm audit --audit-level=high', () => {
  assert.equal(fails(run({ vulnerabilities: { x: { severity: 'moderate', via: [ADV('GHSA-xxxx-yyyy-zzzz', 'moderate', 'x')] } } })), false);
});

test('an errored or empty audit report fails closed', () => {
  for (const r of [null, { error: { code: 'ENOTFOUND' } }, {}]) assert.equal(run(r).blocking.length, 1);
});

test('1: missing, empty or PENDING approval fails closed', () => {
  for (const over of [{ approved_by: '' }, { approved_by: 'PENDING (Gio)' }, { approved_by: undefined },
    { approval_source: '' }, { approved_on: undefined }]) {
    const r = run(report(), 'apps/mobile', allow(over));
    assert.ok(fails(r), JSON.stringify(over));
    assert.deepEqual(r.waived, []);
  }
});

test('1b: an unapproved entry for another workspace still fails every workspace', () => {
  assert.ok(fails(run({ vulnerabilities: {} }, 'apps/web', allow({ approved_by: 'PENDING' }))));
});

test('2: review_by and approved_on must be real dates within the 60-day window', () => {
  for (const s of ['2026-11-1', '2026-02-30', 'soon', '2026-13-01', '']) assert.equal(parseDate(s), null, s);
  assert.notEqual(parseDate('2026-11-01'), null);
  for (const over of [{ review_by: '2026-02-30' }, { review_by: 'next month' }, { review_by: '2026-12-02' },
    { approved_on: '2026-10-03' }, { approved_on: '2026-08-01', review_by: '2026-10-05' }]) {
    assert.ok(entryProblems({ ...ENTRY, ...over }, TODAY).length > 0, JSON.stringify(over));
  }
  assert.deepEqual(entryProblems({ ...ENTRY, review_by: '2026-12-01', approved_on: '2026-10-02' }, TODAY), []);
});

test('3: unknown or missing severity and unresolvable via chains block', () => {
  assert.ok(fails(run(report({ x: { severity: 'severe', via: [ADV('GHSA-aaaa-bbbb-cccc', 'high', 'x')] } }))));
  assert.ok(fails(run(report({ x: { via: [ADV('GHSA-aaaa-bbbb-cccc', 'high', 'x')] } }))));
  assert.ok(fails(run(report({ x: { severity: 'high', via: [ADV('GHSA-aaaa-bbbb-cccc', undefined, 'x')] } }))));
  assert.ok(fails(run(report({ x: { severity: 'high', via: ['not-in-report'] } }))));
  assert.ok(fails(run(report({ x: { severity: 'high', via: [] } }))));
  assert.ok(fails(run(report({ a: { severity: 'high', via: ['b'] }, b: { severity: 'high', via: ['a'] } }))));
});

test('4: the allowlist matches the exact (GHSA, package, workspace) tuple', () => {
  const other = { vulnerabilities: { 'other-pkg': { severity: 'high', via: [ADV('GHSA-86w9-cpqp-85rv', 'high', 'other-pkg')] } } };
  assert.deepEqual(run(other).blocking, ['GHSA-86w9-cpqp-85rv (other-pkg)']);
  assert.ok(fails(run(report(), 'apps/mobile', allow({ package: 'node-forge-fork' }))));
});

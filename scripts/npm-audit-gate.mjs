#!/usr/bin/env node
// npm audit gate with scoped, expiring, approved exceptions (.github/npm-audit-allowlist.json).
// usage (inside a workspace): npm audit --json | node ../../scripts/npm-audit-gate.mjs <workspace> [today]
// Fails (exit 1) on any high/critical advisory that is not covered by a valid allowlist entry for
// the exact tuple (GHSA id, package, workspace). Fail closed: invalid/unapproved/expired entries,
// unknown severities, unresolvable via chains and errored audit reports all block.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const SEVERE = new Set(['high', 'critical']);
const KNOWN = new Set(['info', 'low', 'moderate', 'high', 'critical']);
export const MAX_WINDOW_DAYS = 60;
const GHSA_RE = /^GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$/;
const DAY = 86400000;

// Strict YYYY-MM-DD that is a real calendar date; returns UTC ms or null.
export function parseDate(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const t = Date.parse(`${s}T00:00:00Z`);
  return Number.isNaN(t) || new Date(t).toISOString().slice(0, 10) !== s ? null : t;
}

// Returns a list of problems; an entry with any problem is ignored and fails the gate.
export function entryProblems(e, today) {
  const p = [];
  const now = parseDate(today);
  if (!GHSA_RE.test(e?.id ?? '')) p.push('id is not a GHSA id');
  if (typeof e?.package !== 'string' || !e.package) p.push('package missing');
  if (!Array.isArray(e?.workspaces) || !e.workspaces.length || e.workspaces.some((w) => typeof w !== 'string' || !w)) p.push('workspaces missing');
  if (typeof e?.reason !== 'string' || !e.reason.trim()) p.push('reason missing');
  const by = typeof e?.approved_by === 'string' ? e.approved_by.trim() : '';
  if (!by || /pending/i.test(by)) p.push('not approved (approved_by empty or PENDING)');
  if (typeof e?.approval_source !== 'string' || !e.approval_source.trim()) p.push('approval_source missing');
  const on = parseDate(e?.approved_on);
  const review = parseDate(e?.review_by);
  if (on === null) p.push('approved_on is not a valid YYYY-MM-DD date');
  if (review === null) p.push('review_by is not a valid YYYY-MM-DD date');
  if (now === null) p.push(`today "${today}" is not a valid date`);
  if (on !== null && now !== null && on > now) p.push('approved_on is in the future');
  if (review !== null && now !== null) {
    if (review < now) p.push(`expired on ${e.review_by}`);
    if (review - now > MAX_WINDOW_DAYS * DAY) p.push(`review_by more than ${MAX_WINDOW_DAYS} days ahead`);
  }
  if (review !== null && on !== null && review - on > MAX_WINDOW_DAYS * DAY) p.push(`review_by more than ${MAX_WINDOW_DAYS} days after approved_on`);
  return p;
}

export function ghsaOf(via) {
  const m = /GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}/.exec(via.url || '');
  return m ? m[0] : `unidentified advisory ${String(via.source ?? via.title ?? '?')}`;
}

export function evaluate(report, workspace, allowlist, today) {
  // Fail closed: an audit that errored (registry down, bad lockfile) or produced no report is not a pass.
  if (!report || report.error || typeof report.vulnerabilities !== 'object' || report.vulnerabilities === null) {
    return { blocking: [`npm audit produced no usable report${report?.error ? `: ${report.error.code || report.error.summary || 'error'}` : ''}`], waived: [], invalid: [] };
  }
  const entries = Array.isArray(allowlist?.entries) ? allowlist.entries : null;
  const invalid = [];
  if (!entries) invalid.push('allowlist has no entries array');
  const allowed = new Set();
  for (const e of entries ?? []) {
    if (!Array.isArray(e?.workspaces) || !e.workspaces.includes(workspace)) {
      // Entries for other workspaces are still validated, so a broken file fails everywhere.
      const p = entryProblems(e, today);
      if (p.length) invalid.push(`${e?.id ?? '?'}: ${p.join('; ')}`);
      continue;
    }
    const p = entryProblems(e, today);
    if (p.length) invalid.push(`${e.id}: ${p.join('; ')}`);
    else allowed.add(`${e.id}|${e.package}`);
  }

  const vulns = report.vulnerabilities;
  const blocking = new Set();
  const waived = new Set();
  // Resolve a package to its root advisories; unresolvable names or unknown severities block.
  const roots = (name, seen) => {
    if (!vulns[name]) return [{ problem: `via chain references unknown package ${name}` }];
    if (seen.has(name)) return [];
    seen.add(name);
    const via = Array.isArray(vulns[name].via) ? vulns[name].via : [];
    if (!via.length) return [{ problem: `${name} has no via entries` }];
    return via.flatMap((v) => {
      if (typeof v === 'string') return roots(v, seen);
      if (!v || typeof v !== 'object') return [{ problem: `${name} has a malformed via entry` }];
      if (!KNOWN.has(v.severity)) return [{ problem: `${ghsaOf(v)} (${v.name ?? name}) has unknown severity ${JSON.stringify(v.severity)}` }];
      return [{ id: ghsaOf(v), severity: v.severity, pkg: v.name }];
    });
  };
  for (const [name, v] of Object.entries(vulns)) {
    if (!KNOWN.has(v?.severity)) {
      blocking.add(`${name} has unknown severity ${JSON.stringify(v?.severity)}`);
      continue;
    }
    if (!SEVERE.has(v.severity)) continue;
    const found = roots(name, new Set());
    let severeRoots = 0;
    for (const r of found) {
      if (r.problem) { blocking.add(r.problem); continue; }
      if (!SEVERE.has(r.severity)) continue;
      severeRoots += 1;
      (allowed.has(`${r.id}|${r.pkg}`) ? waived : blocking).add(`${r.id} (${r.pkg})`);
    }
    if (!severeRoots && !found.some((r) => r.problem)) blocking.add(`${name} is ${v.severity} but no high/critical root advisory was resolved`);
  }
  return { blocking: [...blocking].sort(), waived: [...waived].sort(), invalid };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const workspace = process.argv[2];
  const today = process.argv[3] || new Date().toISOString().slice(0, 10);
  let allowlist = null;
  try { allowlist = JSON.parse(readFileSync(join(root, '.github/npm-audit-allowlist.json'), 'utf8')); } catch { allowlist = null; }
  let report = null;
  try { report = JSON.parse(readFileSync(0, 'utf8')); } catch { report = null; }
  const { blocking, waived, invalid } = evaluate(report, workspace, allowlist, today);
  for (const w of waived) console.log(`waived (allowlist): ${w}`);
  for (const e of invalid) console.error(`::error::allowlist entry ${e}`);
  for (const b of blocking) console.error(`::error::high/critical advisory: ${b}`);
  process.exit(blocking.length || invalid.length ? 1 : 0);
}

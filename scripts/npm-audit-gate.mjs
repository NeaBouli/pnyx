#!/usr/bin/env node
// npm audit gate with scoped, expiring exceptions (.github/npm-audit-allowlist.json).
// usage (inside a workspace): npm audit --json | node ../../scripts/npm-audit-gate.mjs <workspace> [today]
// Fails (exit 1) on any high/critical advisory that is not covered by an unexpired allowlist
// entry for this workspace. A package flagged only through allowlisted advisories passes.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const SEVERE = new Set(['high', 'critical']);

export function ghsaOf(via) {
  const m = /GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}/.exec(via.url || '');
  return m ? m[0] : String(via.source ?? via.title ?? 'unknown');
}

export function evaluate(report, workspace, allowlist, today) {
  // Fail closed: an audit that errored (registry down, bad lockfile) or produced no report is not a pass.
  if (!report || report.error || typeof report.vulnerabilities !== 'object' || report.vulnerabilities === null) {
    return { blocking: [`npm audit produced no usable report${report?.error ? `: ${report.error.code || report.error.summary || 'error'}` : ''}`], waived: [], expired: [] };
  }
  const active = allowlist.entries.filter((e) => e.workspaces.includes(workspace));
  const expired = active.filter((e) => e.review_by < today).map((e) => `${e.id} expired on ${e.review_by}`);
  const allowed = new Set(active.filter((e) => e.review_by >= today).map((e) => e.id));
  const vulns = report.vulnerabilities || {};
  const roots = (name, seen = new Set()) => {
    if (seen.has(name) || !vulns[name]) return [];
    seen.add(name);
    return vulns[name].via.flatMap((v) => (typeof v === 'string' ? roots(v, seen) : [{ id: ghsaOf(v), severity: v.severity, pkg: v.name }]));
  };
  const blocking = new Set();
  const waived = new Set();
  for (const [name, v] of Object.entries(vulns)) {
    if (!SEVERE.has(v.severity)) continue;
    for (const r of roots(name)) {
      if (!SEVERE.has(r.severity)) continue;
      (allowed.has(r.id) ? waived : blocking).add(`${r.id} (${r.pkg})`);
    }
  }
  return { blocking: [...blocking].sort(), waived: [...waived].sort(), expired };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const workspace = process.argv[2];
  const today = process.argv[3] || new Date().toISOString().slice(0, 10);
  const allowlist = JSON.parse(readFileSync(join(root, '.github/npm-audit-allowlist.json'), 'utf8'));
  let report = null;
  try { report = JSON.parse(readFileSync(0, 'utf8')); } catch { report = null; }
  const { blocking, waived, expired } = evaluate(report, workspace, allowlist, today);
  for (const w of waived) console.log(`waived (allowlist): ${w}`);
  for (const e of expired) console.error(`::error::allowlist entry ${e}`);
  for (const b of blocking) console.error(`::error::high/critical advisory: ${b}`);
  process.exit(blocking.length || expired.length ? 1 : 0);
}

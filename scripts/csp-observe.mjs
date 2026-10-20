#!/usr/bin/env node
// T-9141. Importing this module and --list never load Playwright or use the network.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

export const ORIGIN = 'https://ekklesia.gr';
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MATRIX = ['chromium', 'webkit'].flatMap((browser) =>
  [390, 1280].map((width) => ({ browser, width })));
const PRIVATE_PATH = /\/(?:auth|login|logout|sso(?:-verify)?|admin|account|profile|oauth|vote|voting|session|sessions)(?:[/.\-]|$)/i;

function asURL(value, base = ORIGIN) {
  try { return new URL(String(value), base); } catch { return null; }
}

export function pathOnly(value, base = ORIGIN) {
  if (!value) return '';
  const url = asURL(value, base);
  return url && /^https?:$/.test(url.protocol) ? url.pathname : '';
}

export function blockedOrigin(value, base = ORIGIN) {
  if (!value) return '';
  if (value === 'inline' || value === 'eval') return value;
  const url = asURL(value, base);
  if (!url) return '';
  if (/^https?:$/.test(url.protocol) || url.protocol === 'blob:') {
    return url.origin === 'null' ? '' : url.origin;
  }
  // Never retain data:, javascript:, extension URLs or their payloads.
  return '';
}

function scriptSample(value) {
  // Only code from a public, anonymous document is eligible. Redact literals
  // (including an unfinished final literal), URLs and email addresses first.
  return String(value || '')
    .replace(/"(?:\\.|[^"\\])*(?:"|$)|'(?:\\.|[^'\\])*(?:'|$)|`(?:\\.|[^`\\])*(?:`|$)/g, '[redacted]')
    .replace(/https?:\/\/[^\s<>]+/gi, '[url]')
    .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[redacted]')
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .slice(0, 40);
}

const directive = (value) => /^[a-z][a-z-]*$/.test(String(value || '')) ? value : '';

export function normalizeViolation(event, pagePath, evidence = 'event') {
  const base = asURL(pagePath)?.href || ORIGIN;
  return {
    pagePath: pathOnly(pagePath),
    evidence,
    violatedDirective: directive(event.violatedDirective),
    effectiveDirective: directive(event.effectiveDirective),
    blockedURI: blockedOrigin(event.blockedURI, base),
    sourceFile: pathOnly(event.sourceFile, base),
    line: Number.isSafeInteger(event.lineNumber) && event.lineNumber > 0 ? event.lineNumber : 0,
    sample: scriptSample(event.sample),
    disposition: ['report', 'enforce'].includes(event.disposition) ? event.disposition : null,
  };
}

export function aggregateViolation(groups, event, pagePath, run, evidence = 'event') {
  const normalized = normalizeViolation(event, pagePath, evidence);
  const key = JSON.stringify(normalized);
  let group = groups.get(key);
  if (!group) {
    group = { ...normalized, count: 0, runs: [] };
    groups.set(key, group);
  }
  group.count += 1;
  let occurrence = group.runs.find((item) => item.browser === run.browser && item.width === run.width);
  if (!occurrence) {
    occurrence = { ...run, count: 0 };
    group.runs.push(occurrence);
  }
  occurrence.count += 1;
  return group;
}

export function consoleViolation(message, location = {}) {
  if (!/content[- ]security[- ]policy/i.test(message)) return null;
  // Chromium warns about Report-Only policies without a reporting endpoint.
  // That configuration diagnostic is not a resource/execution violation. The
  // observer deliberately collects events locally and has no report receiver.
  if (/report[- ]only/i.test(message) && /does not specify[^;]*report-(?:uri|to)/i.test(message)
      && /(?:no effect|no reports)/i.test(message)) return null;
  // Console wording differs by engine. Keep only recognizable fields, never
  // the raw message, policy, nonce, hash or console arguments.
  const name = message.match(/\b(?:default-src|[a-z]+-src(?:-elem|-attr)?|base-uri|frame-ancestors|form-action|sandbox)\b/i)?.[0].toLowerCase();
  const resource = message.match(/(?:load(?:ing)?|connect(?:ing)? to|fram(?:e|ing))[^'"\n]*['"](https?:\/\/[^'"\s]+)['"]/i)?.[1];
  return {
    violatedDirective: name,
    effectiveDirective: '', // Console text does not reliably distinguish elem/attr fallback.
    blockedURI: resource || (/(?:^|[\s"'(])(?:eval|evaluating|evaluation)(?:[\s"'(]|$)/i.test(message) ? 'eval'
      : /\binline (?:script|event|style)/i.test(message) ? 'inline' : ''),
    sourceFile: location.url,
    lineNumber: Number.isInteger(location.lineNumber) ? location.lineNumber + 1 : 0,
    disposition: /report[- ]only|\[report only\]/i.test(message) ? 'report'
      : /refused|blocked|violat/i.test(message) ? 'enforce' : null,
  };
}

export function allowedRequest(value, method = 'GET') {
  const url = asURL(value);
  if (!url || url.origin !== ORIGIN || url.username || url.password || method !== 'GET') return false;
  let pathname;
  try { pathname = decodeURIComponent(url.pathname); } catch { return false; }
  return !PRIVATE_PATH.test(pathname);
}

export function collectPagePaths(xml, wikiFiles, billPath) {
  const decodeXML = (value) => value.replace(/&amp;/g, '&').replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
  const urls = [...xml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/g)].map((match) => decodeXML(match[1]));
  if (!urls.length) throw new Error('Local sitemap has no page URLs.');
  // Include public language alternates, even when they have no separate <loc>.
  urls.push(...[...xml.matchAll(/<xhtml:link\b[^>]*\bhref="([^"]+)"/g)].map((match) => decodeXML(match[1])));
  urls.push('/el', '/en', '/el/bills', '/el/results', '/en/analytics', '/tickets/');
  urls.push(...wikiFiles.filter((file) => /^[^/]+\.html$/.test(file)).map((file) => `/wiki/${file}`));
  if (billPath) {
    if (!/^\/(?:el|en)\/bills\/[^/?#]+$/.test(billPath) || !allowedRequest(billPath)) {
      throw new Error('--bill-path must be a public /el/bills/<id> or /en/bills/<id> path without query or fragment.');
    }
    urls.push(billPath);
  }
  for (const value of urls) {
    if (!allowedRequest(value)) throw new Error('Page list contains a non-public or off-origin URL.');
  }
  return [...new Set(urls.map((url) => pathOnly(url)))].sort();
}

// Use fetch without automatic redirects so no redirected request can escape
// the allowlist. Fulfill the final response at the requested URL; see the docs
// for the effect this has on relative assets after a path-changing redirect.
export async function routeReadOnly(route, counts) {
  const request = route.request();
  if (!allowedRequest(request.url(), request.method())) {
    counts.blockedRequests += 1;
    return route.abort();
  }
  const headers = Object.fromEntries(Object.entries(request.headers())
    .filter(([name]) => !/^(?:cookie|authorization|proxy-authorization|referer)$/i.test(name)));
  // Empty values also override cookies managed internally by route.fetch.
  headers.cookie = '';
  headers.authorization = '';
  let url = request.url();
  try {
    for (let redirects = 0; redirects <= 5; redirects += 1) {
      if (!allowedRequest(url)) break;
      const response = await route.fetch({ url, method: 'GET', headers, maxRedirects: 0, timeout: 15000 });
      const responseHeaders = response.headers();
      const status = response.status();
      if ([301, 302, 303, 307, 308].includes(status) && responseHeaders.location) {
        url = asURL(responseHeaders.location, url)?.href;
        counts.redirects += 1;
        await response.dispose();
        continue;
      }
      delete responseHeaders['set-cookie'];
      await route.fulfill({ response, headers: responseHeaders });
      await response.dispose();
      return;
    }
    counts.blockedRequests += 1;
  } catch {
    counts.failedRequests += 1; // Never log errors containing URLs or response data.
  }
  await route.abort();
}

function markdown(report) {
  const cell = (value) => String(value ?? 'unknown').replace(/[&<>|`\r\n]/g, (char) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '|': '&#124;', '`': '&#96;', '\r': ' ', '\n': ' ' })[char]);
  const lines = ['# CSP observation', '',
    `${report.coverage.length} page/browser/width visits. ${report.complete ? 'Coverage complete.' : 'INCOMPLETE coverage; inspect the visit table.'}`,
    '', 'Counts are observations, not unique bugs. Console diagnostics can duplicate DOM events.',
    'Unknown console fields are empty/null; console counts never imply a DOM violation.',
    '', '## By directive and source', '',
    '| Directive | Source path:line | Evidence | Disposition | Count | Pages |',
    '| --- | --- | --- | --- | ---: | --- |'];
  const groups = new Map();
  for (const row of report.observations) {
    const fields = [row.effectiveDirective || row.violatedDirective || 'unknown',
      `${row.sourceFile || '(unavailable)'}:${row.line}`, row.evidence, row.disposition];
    const key = JSON.stringify(fields);
    if (!groups.has(key)) groups.set(key, { fields, count: 0, pages: new Set() });
    const group = groups.get(key);
    group.count += row.count;
    group.pages.add(row.pagePath);
  }
  for (const [, group] of [...groups].sort(([a], [b]) => a.localeCompare(b))) {
    lines.push(`| ${group.fields.map(cell).join(' | ')} | ${group.count} | ${[...group.pages].sort().map(cell).join(', ')} |`);
  }
  if (!groups.size) lines.push('| No observations | — | — | — | 0 | — |');
  lines.push('', '## Coverage', '',
    '| Page | Browser | Width | HTTP | Result | Report-Only header | Enforced header | Blocked / failed requests | Redirects |',
    '| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |');
  for (const row of report.coverage) {
    lines.push(`| ${[row.pagePath, row.browser, row.width, row.status ?? '—', row.result,
      row.reportOnlyHeader, row.enforcedHeader, `${row.blockedRequests} / ${row.failedRequests}`, row.redirects].map(cell).join(' | ')} |`);
  }
  lines.push('', report.billPath ? `Bill detail: ${cell(report.billPath)}.` : 'Bill detail: NOT FOUND; rerun with --bill-path.',
    '', 'See docs/security/CSP_OBSERVATION.md for privacy, coverage limits and inventory mapping.', '');
  return lines.join('\n');
}

async function visit(browser, pagePath, run, groups, settleMs, discoverBill) {
  const row = { pagePath, ...run, status: null, result: 'navigation-error',
    reportOnlyHeader: false, enforcedHeader: false, blockedRequests: 0, failedRequests: 0, redirects: 0 };
  const context = await browser.newContext({
    viewport: { width: run.width, height: run.width === 390 ? 844 : 900 },
    serviceWorkers: 'block', acceptDownloads: false,
  });
  let billPath = null;
  try {
    await context.route('**/*', (route) => routeReadOnly(route, row));
    await context.routeWebSocket('**/*', (socket) => { row.blockedRequests += 1; socket.close(); });
    await context.exposeBinding('__cspObserve', (source, event) => {
      // Attribute iframe events to the visited top-level page; sourceFile still
      // identifies their source. Do not retain frame URLs or binding arguments.
      aggregateViolation(groups, event, pagePath, run);
    });
    await context.addInitScript(() => {
      // In-memory binding only: no report endpoint or page-side network sender.
      document.addEventListener('securitypolicyviolation', (event) => {
        void window.__cspObserve({
          violatedDirective: event.violatedDirective,
          effectiveDirective: event.effectiveDirective,
          blockedURI: event.blockedURI,
          sourceFile: event.sourceFile,
          lineNumber: event.lineNumber,
          sample: event.sample,
          disposition: event.disposition,
        }).catch(() => {});
      });
      // Prevent scripts from persisting or reading cookies in this fresh context.
      Object.defineProperty(document, 'cookie', { get: () => '', set: () => {}, configurable: false });
    });
    const page = await context.newPage();
    page.on('console', (message) => {
      const event = consoleViolation(message.text(), message.location());
      if (event) aggregateViolation(groups, event, pagePath, run, 'console');
    });
    page.on('dialog', (dialog) => { void dialog.dismiss(); });
    const response = await page.goto(ORIGIN + pagePath, { waitUntil: 'load', timeout: 30000 });
    if (response) {
      row.status = response.status();
      const headers = response.headers();
      row.reportOnlyHeader = Boolean(headers['content-security-policy-report-only']);
      row.enforcedHeader = Boolean(headers['content-security-policy']);
      row.result = response.ok() ? 'ok' : 'http-error';
    }
    await page.waitForTimeout(settleMs);
    if (discoverBill) {
      const links = await page.locator('a[href]').evaluateAll((anchors) => anchors.map((anchor) => anchor.href));
      billPath = links.filter((href) => allowedRequest(href))
        .map((href) => pathOnly(href)).find((path) => /^\/el\/bills\/[^/]+$/.test(path)) || null;
    }
    // Drain events queued by the page before destroying its context.
    await page.evaluate(() => new Promise((done) => setTimeout(done, 0)));
  } catch {
    row.result = 'navigation-error';
  } finally {
    await context.close();
  }
  return { row, billPath };
}

async function observe(paths, options) {
  const require = createRequire(import.meta.url);
  const playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
  if (MATRIX.some(({ browser }) => typeof playwright[browser]?.launch !== 'function')) {
    throw new Error('Chromium and WebKit are required.');
  }
  const groups = new Map();
  const report = { schemaVersion: 1, origin: ORIGIN, matrix: MATRIX, pagePaths: paths,
    billPath: options.billPath || null, complete: false, coverage: [], observations: [] };
  let browser;
  let currentEngine;
  const useBrowser = async (engine) => {
    if (currentEngine === engine) return;
    if (browser) await browser.close();
    browser = null;
    browser = await playwright[engine].launch({ headless: true });
    currentEngine = engine;
  };
  const recordVisit = async (pagePath, run) => {
    const result = await visit(browser, pagePath, run, groups, options.settleMs,
      pagePath === '/el/bills' && !report.billPath);
    report.coverage.push(result.row);
    if (result.billPath && !report.billPath) {
      report.billPath = result.billPath;
      if (!paths.includes(result.billPath)) paths.push(result.billPath);
    }
    process.stderr.write(`${run.browser} ${run.width} ${pagePath}: ${result.row.result}\n`);
  };
  try {
    for (const run of MATRIX) {
      await useBrowser(run.browser);
      // Array iteration includes the detail path discovered during /el/bills.
      for (const pagePath of paths) await recordVisit(pagePath, run);
    }
    // Discovery may succeed only in a later engine/width. Fill missing detail
    // visits without reloading the rest of the sitemap.
    if (report.billPath) {
      for (const run of MATRIX) {
        if (report.coverage.some((row) => row.pagePath === report.billPath
          && row.browser === run.browser && row.width === run.width)) continue;
        await useBrowser(run.browser);
        await recordVisit(report.billPath, run);
      }
    }
  } finally {
    if (browser) await browser.close();
    report.observations = [...groups.values()].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
    report.complete = coverageComplete(report);
    mkdirSync(options.outDir, { recursive: true });
    writeFileSync(join(options.outDir, 'csp-observation.json'), `${JSON.stringify(report, null, 2)}\n`);
    writeFileSync(join(options.outDir, 'csp-observation.md'), markdown(report));
  }
  return report;
}

export function coverageComplete(report) {
  return Boolean(report.billPath) && report.coverage.length === report.pagePaths.length * MATRIX.length
    && report.coverage.every((row) => row.result === 'ok' && row.enforcedHeader && !row.reportOnlyHeader);
}

async function main() {
  const { values } = parseArgs({ options: {
    observe: { type: 'boolean' }, list: { type: 'boolean' }, help: { type: 'boolean', short: 'h' },
    'bill-path': { type: 'string' }, 'out-dir': { type: 'string', default: '/tmp/csp-observation' },
    'settle-ms': { type: 'string', default: '3000' },
  } });
  if (values.help) {
    process.stdout.write('Usage: node scripts/csp-observe.mjs [--list | --observe] [--bill-path /el/bills/<id>] [--out-dir /tmp/csp-observation] [--settle-ms 3000]\n\nDefault: list local paths without network. Only gio-dd may run --observe against production.\n');
    return;
  }
  if (values.list && values.observe) throw new Error('Choose --list or --observe.');
  const settleMs = Number(values['settle-ms']);
  if (!Number.isSafeInteger(settleMs) || settleMs < 0 || settleMs > 60000) {
    throw new Error('--settle-ms must be an integer from 0 through 60000.');
  }
  const paths = collectPagePaths(readFileSync(join(ROOT, 'docs/sitemap.xml'), 'utf8'),
    readdirSync(join(ROOT, 'docs/wiki')), values['bill-path']);
  if (!values.observe) {
    process.stdout.write(`${JSON.stringify({ origin: ORIGIN, matrix: MATRIX, pagePaths: paths,
      billDetail: values['bill-path'] || 'Discover from public /el/bills links during --observe.' }, null, 2)}\n`);
    return;
  }
  const report = await observe(paths, { billPath: values['bill-path'], settleMs, outDir: resolve(values['out-dir']) });
  process.stdout.write('Wrote csp-observation.json and csp-observation.md.\n');
  if (!report.complete) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(() => {
    // Playwright errors can contain raw console/URL data and local user paths.
    process.stderr.write('CSP observation failed. Check arguments, local sitemap and Playwright/browser installation; see docs/security/CSP_OBSERVATION.md.\n');
    process.exitCode = 1;
  });
}

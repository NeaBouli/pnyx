// Offline only: node --test scripts/csp-observe.check.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  ORIGIN, aggregateViolation, allowedRequest, blockedOrigin, collectPagePaths,
  consoleViolation, normalizeViolation, routeReadOnly,
} from './csp-observe.mjs';

test('aggregation strips queries/fragments and credentials; blocked resources retain only origins', () => {
  const groups = new Map();
  const event = { violatedDirective: 'script-src-elem', effectiveDirective: 'script-src-elem',
    blockedURI: 'https://user:secret@cdn.example/assets/a.js?token=private#fragment',
    sourceFile: `${ORIGIN}/wiki/faq.html?email=private#section`, lineNumber: 12,
    sample: 'function toggleLanguage() { return true; } trailing', disposition: 'report' };
  aggregateViolation(groups, event, '/wiki/faq.html?secret=private#faq', { browser: 'chromium', width: 390 });
  aggregateViolation(groups, { ...event, blockedURI: 'https://cdn.example/other.js?different=private' },
    '/wiki/faq.html', { browser: 'chromium', width: 390 });
  aggregateViolation(groups, event, '/wiki/faq.html', { browser: 'webkit', width: 1280 });
  assert.equal(groups.size, 1);
  const [row] = groups.values();
  assert.equal(row.pagePath, '/wiki/faq.html');
  assert.equal(row.sourceFile, '/wiki/faq.html');
  assert.equal(row.blockedURI, 'https://cdn.example');
  assert.equal(row.count, 3);
  assert.deepEqual(row.runs.map((run) => run.count), [2, 1]);
  assert.equal(row.sample, event.sample.slice(0, 40));
  assert.equal(row.line, 12);
  assert.equal(row.disposition, 'report');
  assert.doesNotMatch(JSON.stringify(row), /private|secret|\?|#|user:/);
  for (const value of ['inline', 'eval']) assert.equal(blockedOrigin(value), value);
  assert.equal(blockedOrigin('data:text/javascript,private'), '');
  assert.equal(blockedOrigin('blob:https://cdn.example/private'), 'https://cdn.example');
  assert.equal(normalizeViolation({ sample: 'const email = "person@example.org";' }, '/').sample, 'const email = [redacted];');
  aggregateViolation(groups, { ...event, disposition: 'enforce' }, '/wiki/faq.html', { browser: 'webkit', width: 1280 });
  assert.equal(groups.size, 2, 'enforced and report-only violations remain separate');
});

test('console diagnostics have sanitized fields and stay separate from DOM events', () => {
  assert.equal(consoleViolation('ordinary application message'), null);
  const event = consoleViolation('[Report Only] Loading the script "https://cdn.example/a.js?secret=private" violates the Content Security Policy directive "script-src \'unsafe-inline\'".',
    { url: `${ORIGIN}/app.js?secret=private`, lineNumber: 3 });
  const row = normalizeViolation(event, '/en', 'console');
  assert.equal(row.blockedURI, 'https://cdn.example');
  assert.equal(row.sourceFile, '/app.js');
  assert.equal(row.line, 4);
  assert.equal(row.disposition, 'report');
  assert.equal(row.effectiveDirective, '');
  assert.doesNotMatch(JSON.stringify(row), /private|unsafe-inline/);
});

test('page list includes alternates and wiki files; rejects unsafe paths and requests', () => {
  const paths = collectPagePaths(`<urlset><loc>${ORIGIN}/?drop=yes</loc><xhtml:link href="${ORIGIN}/en/results"/></urlset>`,
    ['faq.html', 'extra.html', 'image.png'], '/el/bills/GR-123');
  for (const path of ['/', '/el', '/en', '/el/bills', '/el/bills/GR-123', '/el/results', '/en/results', '/en/analytics', '/tickets/', '/wiki/extra.html']) {
    assert.ok(paths.includes(path), path);
  }
  assert.ok(!paths.some((path) => path.includes('?')));
  assert.ok(allowedRequest(`${ORIGIN}/api/v1/bills?limit=5`));
  for (const url of ['https://other.example/', 'https://ekklesia.gr.evil.example/', 'http://ekklesia.gr/', `${ORIGIN}/tickets/auth/callback.html`, `${ORIGIN}/el/%6cogin`]) {
    assert.ok(!allowedRequest(url), url);
  }
  assert.ok(!allowedRequest(`${ORIGIN}/api/v1/bills`, 'POST'));
  assert.throws(() => collectPagePaths('<loc>https://other.example/</loc>', []));
});

test('routing strips cookies and auth and refuses an external redirect without following it', async () => {
  const fetched = [];
  let aborted = false;
  const counts = { blockedRequests: 0, failedRequests: 0, redirects: 0 };
  await routeReadOnly({
    request: () => ({ url: () => ORIGIN + '/', method: () => 'GET',
      headers: () => ({ cookie: 'private', authorization: 'private', referer: 'private' }) }),
    fetch: async (options) => {
      fetched.push(options);
      return { status: () => 302, headers: () => ({ location: 'https://other.example/?private' }), dispose: async () => {} };
    },
    abort: async () => { aborted = true; },
  }, counts);
  assert.equal(fetched.length, 1);
  assert.equal(fetched[0].maxRedirects, 0);
  assert.equal(fetched[0].headers.cookie, '');
  assert.equal(fetched[0].headers.authorization, '');
  assert.equal(fetched[0].headers.referer, undefined);
  assert.ok(aborted);
  assert.equal(counts.blockedRequests, 1);
  let fulfilled;
  await routeReadOnly({
    request: () => ({ url: () => ORIGIN + '/', method: () => 'GET', headers: () => ({}) }),
    fetch: async () => ({ status: () => 200, dispose: async () => {},
      headers: () => ({ 'set-cookie': 'private', 'content-security-policy-report-only': "script-src 'self'" }) }),
    fulfill: async (response) => { fulfilled = response; },
  }, counts);
  assert.equal(fulfilled.headers['set-cookie'], undefined);
  assert.equal(fulfilled.headers['content-security-policy-report-only'], "script-src 'self'");
});

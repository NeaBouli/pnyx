// Offline production-render proof. Run after apps/web's build, with its installed deps.
// Next's request/response mocks render in process: no server, socket or HTTP client.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { LEGACY_CSP } from '../apps/web/csp.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const app = resolve(root, 'apps/web');
const require = createRequire(resolve(app, 'package.json'));
const { version: nextVersion } = JSON.parse(readFileSync(require.resolve('next/package.json'), 'utf8'));
const { default: NextServer } = require('next/dist/server/next-server');
const { createRequestResponseMocks } = require('next/dist/server/lib/mock-request');
const { setupFsCheck } = require('next/dist/server/lib/router-utils/filesystem');
const { getResolveRoutes } = require('next/dist/server/lib/router-utils/resolve-routes');
const { removeRequestMeta } = require('next/dist/server/request-meta');
const { getScriptNonceFromHeader } = require('next/dist/server/app-render/get-script-nonce-from-header');
const compiledProxy = require(resolve(app, '.next/server/middleware.js'));
const proxy = request => compiledProxy.handler(request, { waitUntil() {}, requestMeta: {
  relativeProjectDir: relative(process.cwd(), app), distDir: resolve(app, '.next'),
} });

function createRouteOptions(resolveRoutes, version, assetPrefix = '') {
  const unsupported = detail => {
    throw new Error(`Unsupported Next.js ${version} resolveRoutes internal API: ${detail}. Update scripts/csp-render.check.mjs for this option shape.`);
  };
  if (typeof resolveRoutes !== 'function') unsupported('getResolveRoutes must return a function');
  const source = Function.prototype.toString.call(resolveRoutes);
  const signature = source.match(/^(?:async\s+)?function(?:\s+[\w$]+)?\s*\(\s*\{([^{}]*)\}\s*\)\s*\{/)
    ?? source.match(/^(?:async\s*)?\(\s*\{([^{}]*)\}\s*\)\s*=>/);
  if (!signature) unsupported('expected a single destructured options parameter');
  const names = signature[1].trim().replace(/,\s*$/, '').split(',').map(name => name.trim());
  const supported = new Set(['req', 'res', 'isUpgradeReq', 'invokedOutputs', 'signal', 'getAssetPrefix']);
  const unknown = names.filter(name => !supported.has(name));
  if (unknown.length) unsupported(`unrecognized options: ${unknown.join(', ')}`);
  if (!names.includes('req') || !names.includes('res')) unsupported('missing req/res options');
  // 16.3.8 ignores the extra fields; CI's 16.4.1 also calls getAssetPrefix.
  // Validate before routing so future required callbacks cannot fail obscurely.
  return (req, res) => ({
    req, res, isUpgradeReq: false, invokedOutputs: new Set(),
    signal: new AbortController().signal, getAssetPrefix: () => assetPrefix,
  });
}

test('router options support 16.3.8 and the CI-evidenced getAssetPrefix callback', async () => {
  const req = { url: '/el/bills' };
  const res = {};
  async function oldResolveRoutes({ req, res, isUpgradeReq, invokedOutputs }) {
    assert.equal(req.url, '/el/bills');
    assert.ok(res);
    assert.equal(isUpgradeReq, false);
    assert.ok(invokedOutputs instanceof Set);
  }
  // CI evidence establishes this additional callback, not the full 16.4.1 signature.
  async function resolveRoutesWithAssetPrefix({ req, res, isUpgradeReq, invokedOutputs, signal, getAssetPrefix }) {
    await oldResolveRoutes({ req, res, isUpgradeReq, invokedOutputs });
    assert.ok(signal instanceof AbortSignal);
    assert.equal(signal.aborted, false);
    return getAssetPrefix();
  }
  const oldOptions = createRouteOptions(oldResolveRoutes, '16.3.8');
  await oldResolveRoutes(oldOptions(req, res));
  const options = createRouteOptions(resolveRoutesWithAssetPrefix, '16.4.1');
  assert.equal(await resolveRoutesWithAssetPrefix(options(req, res)), '');
  assert.notEqual(options(req, res).invokedOutputs, options(req, res).invokedOutputs);
  assert.equal(await resolveRoutesWithAssetPrefix(createRouteOptions(resolveRoutesWithAssetPrefix, '16.4.1', '/assets')(req, res)), '/assets');
});

test('unknown router option shapes fail with the Next version and an actionable diagnostic', () => {
  assert.throws(() => createRouteOptions(async function resolveRoutes({ req, res, newCallback }) {}, '16.4.1'),
    /Unsupported Next\.js 16\.4\.1 resolveRoutes internal API: unrecognized options: newCallback.*Update scripts\/csp-render\.check\.mjs/);
  assert.throws(() => createRouteOptions(async function resolveRoutes(options) {}, 'future'),
    /Next\.js future.*expected a single destructured options parameter/);
  assert.throws(() => createRouteOptions(async function resolveRoutes({ signal }) {}, 'future'),
    /Next\.js future.*missing req\/res options/);
  assert.throws(() => createRouteOptions(undefined, 'future'),
    /Next\.js future.*getResolveRoutes must return a function/);
});

test('production router and renders retain fresh nonces and preserve observation/enforcement response policies', async () => {
  const conf = JSON.parse(readFileSync(resolve(app, '.next/required-server-files.json'), 'utf8')).config;
  const manifest = JSON.parse(readFileSync(resolve(app, '.next/prerender-manifest.json'), 'utf8'));
  for (const path of Object.keys(manifest.routes)) assert.ok(!/^\/(el|en)(\/|$)/.test(path), `localized page prerendered: ${path}`);
  const server = new NextServer({ dir: app, dev: false, conf });
  const originalEnforce = process.env.CSP_ENFORCE;
  try {
    await server.prepare();
    const fsChecker = await setupFsCheck({ dir: app, dev: false, config: conf });
    // Run Next's real router header processing. Reconstructing only the request
    // overrides misses middleware response headers overwriting those overrides.
    // Next >=16.4 inserts getAssetPrefix as the third positional parameter of getResolveRoutes.
    const leading = /^function getResolveRoutes\(fsChecker, config, getAssetPrefix\b/.test(getResolveRoutes.toString())
      ? [fsChecker, conf, () => conf.assetPrefix ?? ''] : [fsChecker, conf];
    const resolveRoutes = getResolveRoutes(...leading, { dir: app, dev: false, hostname: 'ekklesia.gr', port: 443 }, {
      async initialize() {
        return { async requestHandler(req) {
          const response = await proxy(new Request('https://ekklesia.gr' + req.url, { headers: req.headers }));
          throw { result: { response } };
        } };
      },
    }, {});
    const routeOptions = createRouteOptions(resolveRoutes, nextVersion, conf.assetPrefix ?? '');
    for (const enforce of [false, true]) {
      process.env.CSP_ENFORCE = String(enforce);
      for (const path of ['/el/bills', '/en/sso-verify', '/el/analytics', '/el/unknown']) {
        const nonces = [];
        const cacheHeaders = [];
        for (let i = 0; i < 2; i++) {
          const chunks = [];
          const { req, res } = createRequestResponseMocks({ url: path, headers: {
            host: 'ekklesia.gr', 'x-nonce': 'attacker',
            'content-security-policy': "script-src 'nonce-attacker'",
            'content-security-policy-report-only': "script-src 'nonce-attacker'",
          }, resWriter(chunk) { chunks.push(Buffer.from(chunk)); return true; } });
          const { resHeaders } = await resolveRoutes(routeOptions(req, res));
          for (const [key, value] of Object.entries(resHeaders)) res.setHeader(key, value);
          removeRequestMeta(req, 'middlewareInvoke');
          const nonce = req.headers['x-nonce'];
          assert.ok(nonce && nonce !== 'attacker');
          const target = res.getHeader('content-security-policy-report-only');
          assert.equal(req.headers['content-security-policy'], target, 'router must retain the nonce CSP for rendering');
          assert.equal(getScriptNonceFromHeader(target), nonce);
          const result = await server.renderToHTML(req, res, path, {});
          const html = result ?? Buffer.concat(chunks).toString('utf8');
          assert.equal(res.statusCode, path === '/el/unknown' ? 404 : 200);
          assert.ok(html?.includes('self.__next_f'), 'actual Flight HTML is required');
          assert.ok(html.includes('self.__next_f.push'), 'streamed Flight payload is required');
          const scripts = [...html.matchAll(/<script\b([^>]*)>/g)];
          assert.ok(scripts.length > 1);
          for (const [, attrs] of scripts) assert.ok(attrs.includes(`nonce="${nonce}"`), `rendered script nonce mismatches proxy: ${attrs}`);
          assert.equal(res.getHeader('content-security-policy'), enforce ? target : LEGACY_CSP);
          assert.equal(res.getHeader('content-security-policy-report-only'), target);
          assert.match(res.getHeader('cache-control'), /private/);
          assert.match(res.getHeader('cache-control'), /no-store/);
          const nextCache = res.getHeader('x-nextjs-cache');
          assert.ok(!['HIT', 'STALE'].includes(nextCache));
          nonces.push(nonce); cacheHeaders.push(nextCache ?? '(absent)');
        }
        assert.notEqual(nonces[0], nonces[1]);
        process.stdout.write(`${enforce ? 'enforce' : 'observe'} ${path}: two fresh matching HTML/Flight nonces; x-nextjs-cache=${cacheHeaders.join(', ')}\n`);
      }
    }
  } finally {
    if (originalEnforce === undefined) delete process.env.CSP_ENFORCE;
    else process.env.CSP_ENFORCE = originalEnforce;
    await server.close();
  }
});

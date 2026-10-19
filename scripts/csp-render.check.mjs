// Offline production-render proof. Run after apps/web's build, with its installed deps.
// Next's request/response mocks render in process: no server, socket or HTTP client.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));
const app = resolve(root, 'apps/web');
const require = createRequire(resolve(app, 'package.json'));
const { default: NextServer } = require('next/dist/server/next-server');
const { createRequestResponseMocks } = require('next/dist/server/lib/mock-request');
const compiledProxy = require(resolve(app, '.next/server/middleware.js'));
const proxy = request => compiledProxy.handler(request, { waitUntil() {}, requestMeta: {
  relativeProjectDir: relative(process.cwd(), app), distDir: resolve(app, '.next'),
} });

test('two sequential production renders retain fresh proxy nonces and bypass the Next page cache', async () => {
  const conf = JSON.parse(readFileSync(resolve(app, '.next/required-server-files.json'), 'utf8')).config;
  const manifest = JSON.parse(readFileSync(resolve(app, '.next/prerender-manifest.json'), 'utf8'));
  for (const path of Object.keys(manifest.routes)) assert.ok(!/^\/(el|en)(\/|$)/.test(path), `localized page prerendered: ${path}`);
  const server = new NextServer({ dir: app, dev: false, conf });
  await server.prepare();
  try {
    for (const path of ['/en/sso-verify', '/el/analytics', '/el/unknown']) {
      const nonces = [];
      const cacheHeaders = [];
      for (let i = 0; i < 2; i++) {
        const response = await proxy(new Request('https://ekklesia.gr' + path));
        const headers = { host: 'ekklesia.gr' };
        for (const [key, value] of response.headers) {
          if (key.startsWith('x-middleware-request-')) headers[key.slice('x-middleware-request-'.length)] = value;
        }
        const nonce = headers['x-nonce'];
        assert.ok(nonce);
        const chunks = [];
        const { req, res } = createRequestResponseMocks({ url: path, headers, resWriter(chunk) { chunks.push(Buffer.from(chunk)); return true; } });
        res.setHeader('Content-Security-Policy', response.headers.get('Content-Security-Policy'));
        const result = await server.renderToHTML(req, res, path, {});
        const html = result ?? Buffer.concat(chunks).toString('utf8');
        assert.equal(res.statusCode, path === '/el/unknown' ? 404 : 200);
        assert.ok(html?.includes('self.__next_f'), 'actual Flight HTML is required');
        const scripts = [...html.matchAll(/<script\b([^>]*)>/g)];
        assert.ok(scripts.length > 1);
        for (const [, attrs] of scripts) assert.ok(attrs.includes(`nonce="${nonce}"`), 'rendered script nonce mismatches proxy');
        assert.match(res.getHeader('cache-control'), /(?:private|no-store)/);
        const nextCache = res.getHeader('x-nextjs-cache');
        assert.ok(!['HIT', 'STALE'].includes(nextCache));
        nonces.push(nonce); cacheHeaders.push(nextCache ?? '(absent)');
      }
      assert.notEqual(nonces[0], nonces[1]);
      process.stdout.write(`${path}: two fresh matching HTML/Flight nonces; x-nextjs-cache=${cacheHeaders.join(', ')}\n`);
    }
  } finally { await server.close(); }
});

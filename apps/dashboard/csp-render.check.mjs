// Run after next build. Mirror scripts/csp-render.check.mjs using Next's real
// production router and renderer, with a local signed session and no network.
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const app = fileURLToPath(new URL('./', import.meta.url))
const require = createRequire(import.meta.url)
const { version } = require('next/package.json')
const { default: NextServer } = require('next/dist/server/next-server')
const { createRequestResponseMocks } = require('next/dist/server/lib/mock-request')
const { setupFsCheck } = require('next/dist/server/lib/router-utils/filesystem')
const { getResolveRoutes } = require('next/dist/server/lib/router-utils/resolve-routes')
const { removeRequestMeta } = require('next/dist/server/request-meta')
const { getScriptNonceFromHeader } = require('next/dist/server/app-render/get-script-nonce-from-header')
const { encode } = await import(require.resolve('@auth/core/jwt'))

test('production login, authenticated HTML, errors and assets have one fresh matching CSP in both modes', async () => {
  const env = { ...process.env }
  const originalFetch = globalThis.fetch
  const secret = 'dashboard-csp-render-local-session-fixture-secret'
  const cookieName = '__Secure-authjs.session-token'
  process.env.AUTH_SECRET = secret
  process.env.AUTH_TRUST_HOST = 'true'
  process.env.AUTH_URL = 'https://dashboard.ekklesia.gr'
  const proxyFile = resolve(app, '.next/server/proxy.js')
  const { handler } = require(existsSync(proxyFile) ? proxyFile : resolve(app, '.next/server/middleware.js'))
  const proxy = request => handler(request, { waitUntil() {}, requestMeta: {
    relativeProjectDir: relative(process.cwd(), app), distDir: resolve(app, '.next'),
  } })
  const conf = JSON.parse(readFileSync(resolve(app, '.next/required-server-files.json'), 'utf8')).config
  const manifest = JSON.parse(readFileSync(resolve(app, '.next/prerender-manifest.json'), 'utf8'))
  assert.deepEqual(Object.keys(manifest.routes).filter(path => path !== '/_global-error'), [],
    'nonce-bearing application pages must not be prerendered')
  const server = new NextServer({ dir: app, dev: false, conf })
  globalThis.fetch = async () => { throw new Error('dashboard CSP render check is offline') }
  try {
    const session = role => encode({ secret, salt: cookieName, token: {
      sub: 'csp-fixture', name: 'CSP fixture', githubUsername: 'fixture', role,
      picture: 'https://avatars.githubusercontent.com/u/1',
    } })
    const admin = await session('SUPER_ADMIN')
    const support = await session('SUPPORT')
    await server.prepare()
    const fsChecker = await setupFsCheck({ dir: app, dev: false, config: conf })
    const leading = /^function getResolveRoutes\(fsChecker, config, getAssetPrefix\b/.test(getResolveRoutes.toString())
      ? [fsChecker, conf, () => conf.assetPrefix ?? ''] : [fsChecker, conf]
    const resolveRoutes = getResolveRoutes(...leading, { dir: app, dev: false, hostname: 'dashboard.ekklesia.gr', port: 443 }, {
      async initialize() {
        return { async requestHandler(req) {
          const response = await proxy(new Request('https://dashboard.ekklesia.gr' + req.url, { headers: req.headers }))
          throw { result: { response } }
        } }
      },
    }, {})
    // Fail explicitly when Next changes its internal routing contract.
    const signature = resolveRoutes.toString().match(/^(?:async\s+)?function(?:\s+[\w$]+)?\s*\(\s*\{([^{}]*)\}/)
    assert.ok(signature, `Unsupported Next.js ${version} resolveRoutes signature`)
    const names = signature[1].trim().replace(/,\s*$/, '').split(',').map(name => name.trim())
    const supported = ['req', 'res', 'isUpgradeReq', 'invokedOutputs', 'signal', 'getAssetPrefix']
    assert.ok(names.includes('req') && names.includes('res') && names.every(name => supported.includes(name)),
      `Unsupported Next.js ${version} router options: ${names.join(', ')}`)

    async function route(path, token, extraHeaders = {}) {
      const chunks = []
      const { req, res } = createRequestResponseMocks({ url: path, headers: {
        host: 'dashboard.ekklesia.gr', ...(token ? { cookie: `${cookieName}=${token}` } : {}),
        'x-nonce': 'attacker', 'content-security-policy': "script-src 'nonce-attacker'",
        'content-security-policy-report-only': "script-src 'nonce-attacker'", ...extraHeaders,
      }, resWriter(chunk) { chunks.push(Buffer.from(chunk)); return true } })
      const result = await resolveRoutes({ req, res, isUpgradeReq: false, invokedOutputs: new Set(),
        signal: new AbortController().signal, getAssetPrefix: () => conf.assetPrefix ?? '',
      })
      for (const [key, value] of Object.entries(result.resHeaders ?? {})) res.setHeader(key, value)
      if (result.statusCode) res.statusCode = result.statusCode
      removeRequestMeta(req, 'middlewareInvoke')
      return { req, res, chunks, result }
    }

    function checkHeaders(res, enforce) {
      const name = enforce === 'false' ? 'content-security-policy-report-only' : 'content-security-policy'
      assert.deepEqual(res.getHeaderNames().filter(key => /^content-security-policy(?:-report-only)?$/i.test(key)), [name])
      const policy = res.getHeader(name)
      assert.equal(typeof policy, 'string')
      assert.doesNotMatch(policy, /attacker|unsafe-eval|strict-dynamic|,|\*/)
      assert.match(policy, /style-src 'self' 'unsafe-inline'/)
      assert.match(policy, /img-src 'self' data: https:\/\/avatars\.githubusercontent\.com;/)
      assert.equal(res.getHeader('x-content-type-options'), 'nosniff')
      assert.equal(res.getHeader('referrer-policy'), 'strict-origin-when-cross-origin')
      return policy
    }

    for (const enforce of [undefined, 'true', 'false']) {
      if (enforce === undefined) delete process.env.CSP_ENFORCE
      else process.env.CSP_ENFORCE = enforce
      const mode = enforce === 'false' ? 'report-only' : enforce === 'true' ? 'enforced' : 'default'
      for (const [path, token, status] of [
        ['/login', null, 200], ['/', admin, 200], ['/analytics', admin, 200], ['/csp-missing', admin, 404],
      ]) {
        const nonces = []
        for (let i = 0; i < 2; i++) {
          const { req, res, chunks } = await route(path, token)
          const nonce = req.headers['x-nonce']
          assert.match(nonce, /^[A-Za-z0-9+/]{43}=$/)
          assert.equal(getScriptNonceFromHeader(req.headers['content-security-policy']), nonce)
          const rendered = await server.renderToHTML(req, res, path, {})
          const html = rendered ?? Buffer.concat(chunks).toString('utf8')
          assert.equal(res.statusCode, status, `${mode} ${path}: ${html?.slice(0, 200)}`)
          assert.match(html, /self\.__next_f\.push/)
          if (path === '/login') assert.match(html, /Sign in with GitHub/)
          if (token) assert.doesNotMatch(html, /NEXT_REDIRECT/)
          const scripts = [...html.matchAll(/<script\b([^>]*)>/g)]
          assert.ok(scripts.length > 1, 'real bootstrap and Flight scripts are required')
          for (const [, attrs] of scripts) {
            assert.ok(attrs.includes(`nonce="${nonce}"`), `${mode} ${path}: script nonce mismatch: ${attrs}`)
          }
          assert.equal(getScriptNonceFromHeader(checkHeaders(res, enforce)), nonce)
          assert.match(res.getHeader('cache-control'), /private/)
          assert.match(res.getHeader('cache-control'), /no-store/)
          assert.ok(!['HIT', 'STALE'].includes(res.getHeader('x-nextjs-cache')))
          nonces.push(nonce)
        }
        assert.notEqual(nonces[0], nonces[1])
        process.stdout.write(`${mode} ${path}: two fresh HTML/Flight nonces; one CSP; status ${status}\n`)
      }

      const files = JSON.parse(readFileSync(resolve(app, '.next/build-manifest.json'), 'utf8'))
      const asset = '/_next/' + files.rootMainFiles[0]
      for (const [path, token, status] of [
        ['/analytics', null, 307], ['/api/proxy/admin/stats', null, 401], ['/users', support, 403],
        ['/login/?callbackUrl=%2Fanalytics', null, 308],
        [asset, null, 200], ['/favicon.ico', null, 200],
      ]) {
        const { res, result } = await route(path, token)
        checkHeaders(res, enforce)
        assert.equal(result.statusCode ?? res.statusCode, status, path)
        if (status === 307) assert.match(res.getHeader('location'), /\/login\?callbackUrl=%2Fanalytics$/)
        if (status === 308) assert.match(res.getHeader('location'), /\/login\?callbackUrl=%2Fanalytics$/)
      }
      // RSC and prefetch requests must also pass through the nonce proxy.
      const nonces = []
      for (const extraHeaders of [{ rsc: '1' }, { 'next-router-prefetch': '1' }]) {
        const { req, res } = await route('/analytics', admin, extraHeaders)
        assert.equal(getScriptNonceFromHeader(checkHeaders(res, enforce)), req.headers['x-nonce'])
        nonces.push(req.headers['x-nonce'])
      }
      assert.notEqual(nonces[0], nonces[1])
      process.stdout.write(`${mode}: login redirect, 401, 403, assets, RSC and prefetch retain one CSP\n`)
    }
  } finally {
    await server.close()
    globalThis.fetch = originalFetch
    for (const key of ['AUTH_SECRET', 'AUTH_TRUST_HOST', 'AUTH_URL', 'CSP_ENFORCE']) {
      if (env[key] === undefined) delete process.env[key]
      else process.env[key] = env[key]
    }
  }
})

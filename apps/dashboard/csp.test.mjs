import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const { NextRequest, NextResponse } = require('next/server')
const { getScriptNonceFromHeader } = require('next/dist/server/app-render/get-script-nonce-from-header')
const { createInlinedDataReadableStream } = require('next/dist/server/app-render/use-flight-response')
const testing = require('next/experimental/testing/server')

// Use the dashboard's existing TypeScript/VM test pattern without another runner.
function load(file, imports = {}, env = process.env) {
  const context = { exports: {}, require: name => {
    assert.ok(name in imports, `unexpected import: ${name}`)
    return imports[name]
  }, process: { env }, crypto, btoa, URL, Headers, Uint8Array }
  const source = ts.transpileModule(readFileSync(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  vm.runInNewContext(source, context, { filename: file })
  return context.exports
}

function fixture(enforce, session = null) {
  let authCalls = 0
  const auth = load('./src/lib/auth.ts', {
    'next-auth': { default: () => ({ auth: callback => async request => {
      authCalls++
      request.auth = session
      const response = await callback(request)
      response.headers.append('set-cookie', 'session-fixture=preserved; HttpOnly')
      return response
    } }) },
    'next-auth/providers/github': { default: () => ({}) },
  })
  const csp = load('./src/lib/csp.ts')
  const { proxy, config } = load('./src/proxy.ts', {
    'next/server': { NextRequest, NextResponse }, '@/lib/auth': auth, '@/lib/csp': csp,
  }, { ...process.env, CSP_ENFORCE: enforce })
  return { proxy, config, authCalls: () => authCalls }
}

const admin = { user: { role: 'SUPER_ADMIN', githubUsername: 'fixture' } }
const hostile = {
  'x-nonce': 'attacker', 'content-security-policy': "script-src 'nonce-attacker'",
  'content-security-policy-report-only': "script-src 'nonce-attacker'",
}

test('policy has only the required browser origins and directives', () => {
  const csp = load('./src/lib/csp.ts', {}, {})
  assert.equal(csp.noncePolicy('fixture'), [
    "default-src 'self'", "script-src 'self' 'nonce-fixture'",
    "style-src 'self' 'unsafe-inline'", "img-src 'self' data: https://avatars.githubusercontent.com https://ekklesia.gr/pnx.png",
    "connect-src 'self' https://api.ekklesia.gr", "font-src 'self'", "frame-ancestors 'none'",
    "object-src 'none'", "base-uri 'self'", "form-action 'self'",
  ].join('; '))
  assert.equal(load('./src/lib/csp.ts', {}, { NEXT_PUBLIC_API_URL: 'https://api.example.test:8443/v1/' })
    .noncePolicy('fixture').match(/connect-src[^;]+/)[0], "connect-src 'self' https://api.example.test:8443")
})

test('newsletter previews allow the exact template logo URL without allowing its whole origin', () => {
  const { noncePolicy } = load('./src/lib/csp.ts')
  const imageSources = noncePolicy('fixture').match(/img-src ([^;]+)/)[1].split(' ')
  const logo = 'https://ekklesia.gr/pnx.png'
  assert.deepEqual(imageSources.filter(source => source.startsWith(new URL(logo).origin)), [logo])
  for (const template of ['weekly-digest.html', 'monthly-digest.html']) {
    const html = readFileSync(new URL(`../../newsletter/templates/${template}`, import.meta.url), 'utf8')
    const images = [...html.matchAll(/<img\b[^>]*\bsrc="([^"]+)"/g)].map(match => match[1])
    assert.ok(images.includes(logo), `${template} must use the permitted logo URL`)
  }
})

test('Web Crypto generates independent 256-bit base64 nonces', () => {
  const { createNonce } = load('./src/lib/csp.ts')
  const nonces = Array.from({ length: 16 }, createNonce)
  assert.equal(new Set(nonces).size, nonces.length)
  for (const nonce of nonces) {
    assert.match(nonce, /^[A-Za-z0-9+/]{43}=$/)
    assert.equal(Buffer.from(nonce, 'base64').byteLength, 32)
  }
})

for (const enforce of [undefined, 'true', 'false']) {
  test(`single policy and matching render nonce with CSP_ENFORCE=${enforce}`, async () => {
    const { proxy } = fixture(enforce, admin)
    const nonces = []
    for (const [path, headers] of [
      ['/login', hostile], ['/', hostile], ['/analytics', { ...hostile, rsc: '1' }],
      ['/analytics', { ...hostile, 'next-router-prefetch': '1' }], ['/api/auth/session', hostile],
    ]) {
      const response = await proxy(new NextRequest(`https://dashboard.ekklesia.gr${path}`, { headers }))
      const nonce = response.headers.get('x-middleware-request-x-nonce')
      assert.match(nonce, /^[A-Za-z0-9+/]{43}=$/)
      const policy = response.headers.get('x-middleware-request-content-security-policy')
      assert.equal(getScriptNonceFromHeader(policy), nonce)
      assert.equal(response.headers.get('x-middleware-request-content-security-policy-report-only'), null)
      const name = enforce === 'false' ? 'content-security-policy-report-only' : 'content-security-policy'
      assert.deepEqual([...response.headers.keys()].filter(key => /^content-security-policy/.test(key)), [name])
      assert.equal(response.headers.get(name), policy)
      assert.doesNotMatch(policy.match(/script-src[^;]+/)[0], /unsafe-inline|unsafe-eval|strict-dynamic|attacker/)
      assert.match(response.headers.get('cache-control'), /private, no-store/)
      assert.match(response.headers.get('set-cookie'), /session-fixture=preserved/)
      nonces.push(nonce)
    }
    assert.equal(new Set(nonces).size, nonces.length)
  })
}

test('Next nonces every bootstrap and streamed Flight inline script', async () => {
  const { proxy } = fixture(undefined)
  const response = await proxy(new NextRequest('https://dashboard.ekklesia.gr/login'))
  const nonce = getScriptNonceFromHeader(response.headers.get('x-middleware-request-content-security-policy'))
  const flight = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode('0:"dashboard fixture"\n'))
    controller.close()
  } })
  const html = await new Response(createInlinedDataReadableStream(flight, nonce, null)).text()
  assert.match(html, /self\.__next_f/)
  const scripts = [...html.matchAll(/<script\b([^>]*)>/g)]
  assert.ok(scripts.length >= 2)
  for (const [, attrs] of scripts) assert.equal(attrs, ` nonce="${nonce}"`)
})

test('login redirects, unauthenticated API errors and role denials keep their behavior and CSP', async () => {
  const cases = [
    ['/analytics', null, 307, '/login?callbackUrl=%2Fanalytics'],
    ['/api/proxy/admin/stats', null, 401, null],
    ['/users', { user: { role: 'SUPPORT' } }, 403, null],
    ['/analytics', admin, 200, null], ['/login', null, 200, null], ['/api/auth/csrf', null, 200, null],
  ]
  for (const enforce of [undefined, 'false']) {
    for (const [path, session, status, location] of cases) {
      const { proxy } = fixture(enforce, session)
      const response = await proxy(new NextRequest(`https://dashboard.ekklesia.gr${path}`))
      assert.equal(response.status, status, path)
      assert.equal(response.headers.get('location'), location && `https://dashboard.ekklesia.gr${location}`)
      const name = enforce === 'false' ? 'content-security-policy-report-only' : 'content-security-policy'
      assert.match(response.headers.get(name), /script-src 'self' 'nonce-/)
      if (status === 401 || status === 403) {
        assert.deepEqual(await response.json(), { error: status === 401 ? 'Unauthorized' : 'Forbidden' })
      }
    }
  }
})

test('assets gain a nonce policy without invoking auth or disabling asset caching', async () => {
  const { proxy, config, authCalls } = fixture(undefined)
  const matches = testing.unstable_doesProxyMatch ?? testing.unstable_doesMiddlewareMatch
  for (const path of ['/login', '/api/auth/session', '/analytics', '/missing.path', '/_next/static/chunk.js', '/_next/image', '/favicon.ico']) {
    assert.equal(matches({ config, nextConfig: {}, url: path }), true, path)
  }
  for (const path of ['/_next/static/chunk.js', '/_next/image?url=local', '/favicon.ico']) {
    const response = await proxy(new NextRequest(`https://dashboard.ekklesia.gr${path}`))
    assert.match(response.headers.get('content-security-policy'), /nonce-/)
    assert.equal(response.headers.get('cache-control'), null)
  }
  assert.equal(authCalls(), 0)
})

test('canonical trailing-slash redirects preserve status and query before auth, with CSP', async () => {
  const { proxy, authCalls } = fixture(undefined)
  const response = await proxy(new NextRequest('https://dashboard.ekklesia.gr/login/?callbackUrl=%2Fanalytics'))
  assert.equal(response.status, 308)
  assert.equal(response.headers.get('location'), 'https://dashboard.ekklesia.gr/login?callbackUrl=%2Fanalytics')
  assert.match(response.headers.get('content-security-policy'), /nonce-/)
  assert.equal(authCalls(), 0)
})

test('Next config supplies companion headers and leaves CSP to the proxy', async () => {
  const config = require('./next.config.js')
  assert.equal(config.skipTrailingSlashRedirect, true)
  assert.equal(config.env.NEXT_PUBLIC_API_URL, process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr')
  const rules = await config.headers()
  assert.equal(rules[0].source, '/:path*')
  assert.deepEqual(rules[0].headers, [
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  ])
  assert.ok(!rules.some(rule => rule.headers.some(header => /content-security-policy/i.test(header.key))))
})

test('login and authenticated pages inherit request rendering without static or ISR overrides', () => {
  const app = new URL('./src/app/', import.meta.url)
  const layout = readFileSync(new URL('layout.tsx', app), 'utf8')
  assert.match(layout, /export const dynamic = 'force-dynamic'/)
  assert.match(layout, /await headers\(\)/)
  function check(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = resolve(dir, entry.name)
      if (entry.isDirectory()) check(path)
      else if (/(page|layout)\.tsx$/.test(path)) {
        assert.doesNotMatch(readFileSync(path, 'utf8'), /export\s+(?:const\s+(?:dynamic\s*=\s*['"]force-static|revalidate\s*=\s*(?:[1-9]|false\b|Infinity\b)|fetchCache\s*=\s*['"]force-cache|generateStaticParams\b)|(?:async\s+)?function\s+generateStaticParams\b)/, path)
      }
    }
  }
  check(app.pathname)
})

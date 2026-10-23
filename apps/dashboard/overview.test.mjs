import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createRequire } from 'node:module'
import { setMaxListeners } from 'node:events'
const require = createRequire(import.meta.url)
const source = ts.transpileModule(fs.readFileSync(new URL('./src/lib/overview.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText

function load(fetch) {
  let timeout
  let cleared = false
  let nextTimer = 0
  const timers = new Map()
  class BrowserAbortController extends AbortController {
    constructor() { super(); setMaxListeners(0, this.signal) }
  }
  const context = { exports: {}, AbortController: BrowserAbortController, fetch,
    setTimeout: (fn, ms) => { timeout = fn; timers.set(++nextTimer, { fn, ms }); return nextTimer },
    clearTimeout: id => { cleared = true; timers.delete(id) },
  }
  vm.runInNewContext(source, context)
  return { ...context.exports, timers, expire: () => timeout(), cleared: () => cleared }
}

test('HLR uses initial, not an invented total; invalid data stays unavailable', () => {
  const { hlrEstimate } = load()
  assert.equal(hlrEstimate({ initial: 2499, remaining: 2435 }).percent, 97)
  assert.equal(hlrEstimate({ remaining: 2435 }).percent, null)
  assert.equal(hlrEstimate({ initial: 0, remaining: 0 }).percent, null)
  assert.equal(hlrEstimate({ initial: 2499, remaining: 0 }).percent, 0)
  assert.equal(hlrEstimate({ remaining: NaN }).remaining, null)
  for (const initial of [0, -1, NaN, Infinity, '2499', undefined]) {
    assert.equal(hlrEstimate({ initial, remaining: 1 }).initial, null)
  }
  assert.equal(hlrEstimate({ initial: 2499, remaining: 2435 }).initial, 2499)
})

test('successful response releases timeout', async () => {
  const api = load(async () => ({ ok: true, json: async () => ({ ok: true }) }))
  assert.equal((await api.fetchOverviewJSON('/test')).ok, true)
  assert.equal(api.cleared(), true)
})

test('failure and malformed JSON are unavailable, not false zero data', async () => {
  for (const response of [{ ok: false }, { ok: true, json: async () => { throw Error('bad') } }]) {
    const api = load(async () => response)
    assert.equal(await api.fetchOverviewJSON('/test'), null)
    assert.equal(api.cleared(), true)
  }
})

test('hanging response body is aborted and other cards can finish', async () => {
  let bodyStarted
  const started = new Promise(resolve => { bodyStarted = resolve })
  const api = load(async (_url, { signal }) => ({ ok: true,
    json: () => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(Error('timeout')))
      bodyStarted()
    }),
  }))
  const pending = api.fetchOverviewJSON('/test')
  await started
  api.expire()
  assert.equal(await pending, null)
  assert.equal(api.cleared(), true)
})

const flush = () => new Promise(setImmediate)

function deferredRequests() {
  const requests = new Map()
  const api = load((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(Error('aborted')), { once: true })
    requests.set(url, {
      signal,
      resolve: body => resolve({ ok: true, json: async () => body }),
      fail: () => reject(Error('unavailable')),
    })
  }))
  return { api, requests }
}

test('each widget publishes independently; failures and the 12s timeout settle only their widget', async () => {
  const { api, requests } = deferredRequests()
  const results = new Map()
  const cancel = api.loadOverviewWidgets('https://api.test', (key, value) => results.set(key, value))
  assert.equal(requests.size, 16)
  assert.ok(requests.has('/api/proxy/admin/hlr/credits'))
  assert.ok(requests.has('/api/discourse'))
  assert.ok([...api.timers.values()].every(timer => timer.ms === 12000))
  requests.get('https://api.test/health').resolve({ status: 'ok' })
  requests.get('https://api.test/api/v1/bills?limit=5').resolve({ bills: [{ id: 'fast-bill' }] })
  await flush()
  assert.deepEqual([...results.keys()].sort(), ['bills', 'health'])
  assert.equal(results.has('representation'), false)
  requests.get('/api/proxy/admin/hlr/credits').fail()
  await flush()
  assert.equal(results.get('hlr'), null)
  api.expire()
  await flush()
  assert.equal(results.get('deepl'), null)
  assert.equal(results.has('representation'), false)
  assert.equal(results.get('health').status, 'ok')
  cancel()
  await flush()
  assert.equal(api.timers.size, 0)
})

test('cancelled refreshes cannot publish late results and release every timer', async () => {
  const { api, requests } = deferredRequests()
  const results = []
  const cancel = api.loadOverviewWidgets('https://api.test', (...entry) => results.push(entry))
  requests.get('https://api.test/health').resolve({ status: 'old' })
  cancel()
  await flush()
  assert.deepEqual(results, [])
  assert.ok([...requests.values()].every(request => request.signal.aborted))
  assert.equal(api.timers.size, 0)
})

// Execute the real page with a small hook host and render its JSX with React.
function pageHost(api) {
  const state = []
  const effects = []
  const cleanups = []
  let cursor = 0
  const hooks = {
    useState(initial) {
      const index = cursor++
      if (!(index in state)) state[index] = typeof initial === 'function' ? initial() : initial
      return [state[index], value => { state[index] = typeof value === 'function' ? value(state[index]) : value }]
    },
    useRef(initial) { return state[cursor++] ??= { current: initial } },
    useCallback(fn) { return state[cursor++] ??= fn },
    useEffect(fn) {
      const index = cursor++
      if (!(index in state)) { state[index] = true; effects.push(fn) }
    },
  }
  const response = { exports: {} }
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./src/lib/response.ts', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText, response)
  const context = {
    exports: {}, process: { env: { NEXT_PUBLIC_API_URL: 'https://api.test' } },
    setInterval: () => 1, clearInterval: () => {},
    require: name => name === 'react' ? hooks
      : name === '@/lib/overview' ? api
        : name === '@/lib/response' ? response.exports
          : name === 'recharts' ? new Proxy({}, { get: () => ({ children }) => React.createElement('div', null, children) })
            : require(name),
  }
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./src/app/(dashboard)/page.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, context)
  return {
    render() { cursor = 0; return renderToStaticMarkup(context.exports.default()) },
    mount() { for (const effect of effects.splice(0)) cleanups.push(effect()) },
    tab(value) { state[0] = value },
    unmount() { for (const cleanup of cleanups) cleanup?.() },
  }
}

test('real overview renders fast cards and recent bills while representation remains pending', async () => {
  const { api, requests } = deferredRequests()
  const page = pageHost(api)
  const initial = page.render()
  assert.doesNotMatch(initial, /Κατάσταση API/)
  assert.doesNotMatch(initial, /Δεν βρέθηκαν νομοσχέδια/)
  page.mount()
  requests.get('https://api.test/health').resolve({ status: 'ok' })
  requests.get('https://api.test/api/v1/bills?limit=5').resolve({ bills: [
    { id: 42, title_el: 'Fast recent bill', status: 'OPEN_END', created_at: '2026-10-23' },
  ] })
  requests.get('https://api.test/api/v1/analytics/overview').resolve({ bills: { active: 17 }, votes: { total: 1234 } })
  await flush()
  const html = page.render()
  assert.match(html, /Κατάσταση API/)
  assert.match(html, /Ενεργό/)
  assert.match(html, /Fast recent bill/)
  assert.match(html, /Ενεργά Νομοσχέδια/)
  assert.match(html, />17</)
  assert.doesNotMatch(html, /Newsletter/)
  assert.equal(requests.get('https://api.test/api/v1/analytics/representation').signal.aborted, false)
  page.tab('analytics')
  let analytics = page.render()
  assert.doesNotMatch(analytics, /Δεν υπάρχουν δεδομένα/)
  requests.get('https://api.test/api/v1/analytics/top-divergence?limit=5').resolve({ data: [
    { bill_id: 23, title_el: 'Fast analytics bill', divergence_score: 0.4 },
  ] })
  await flush()
  analytics = page.render()
  assert.match(analytics, /Fast analytics bill/)
  assert.doesNotMatch(analytics, />0\.0%</)
  page.tab('finance')
  assert.doesNotMatch(page.render(), /Μη διαθέσιμο/)
  requests.get('https://api.test/api/v1/arweave/status').resolve({ balance_ar: 1.2345 })
  await flush()
  assert.match(page.render(), /1\.2345 AR/)
  page.unmount()
  await flush()
  assert.equal(api.timers.size, 0)
})

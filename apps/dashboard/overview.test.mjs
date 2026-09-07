import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const source = ts.transpileModule(fs.readFileSync(new URL('./src/lib/overview.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText

function load(fetch) {
  let timeout
  let cleared = false
  const context = { exports: {}, AbortController, fetch,
    setTimeout: fn => { timeout = fn; return 1 },
    clearTimeout: () => { cleared = true },
  }
  vm.runInNewContext(source, context)
  return { ...context.exports, expire: () => timeout(), cleared: () => cleared }
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

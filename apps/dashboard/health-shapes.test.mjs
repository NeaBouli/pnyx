import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

function transpile(file) {
  return ts.transpileModule(fs.readFileSync(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText
}

const response = { exports: {} }
vm.runInNewContext(transpile('./src/lib/response.ts'), response)
const context = { exports: {}, require: () => response.exports }
vm.runInNewContext(transpile('./src/lib/health-shapes.ts'), context)
const plain = value => JSON.parse(JSON.stringify(value))
const scraperJobsFrom = payload => plain(context.exports.scraperJobsFrom(payload))
const { forumSyncStatusFrom } = context.exports

const parliament = {
  name: 'parliament', last_run: '2026-10-04T07:38:29Z', last_success: '2026-10-04T07:38:31Z',
  last_error: null, error_count: 0, status: 'ok',
}

test('scraper jobs: current {scrapers: [...]} payload yields the real jobs', () => {
  const jobs = scraperJobsFrom({ scrapers: [parliament, { ...parliament, name: 'forum_sync', error_count: 420, status: 'circuit_open', last_error: '422' }] })
  assert.deepEqual(jobs.map(j => [j.name, j.error_count, j.status]), [['parliament', 0, 'ok'], ['forum_sync', 420, 'circuit_open']])
})

test('scraper jobs: legacy shapes still work and the wrapper never becomes a pseudo job', () => {
  assert.equal(scraperJobsFrom({ jobs: [parliament] })[0].name, 'parliament')
  assert.equal(scraperJobsFrom([parliament])[0].name, 'parliament')
  assert.deepEqual(scraperJobsFrom({ diavgeia: { error_count: 2 } }).map(j => [j.name, j.error_count]), [['diavgeia', 2]])
  assert.deepEqual(scraperJobsFrom({ scrapers: 'broken' }), [])
  assert.deepEqual(scraperJobsFrom(null), [])
  assert.equal(scraperJobsFrom({ scrapers: [{ error_count: 1 }] }).length, 0)
})

test('forum sync status comes from MOD-24 in /api/v1/health/modules', () => {
  assert.equal(forumSyncStatusFrom({ overall: 'error', modules: { 'MOD-24': { name: 'Discourse Forum Sync', status: 'error' } } }), 'error')
  assert.equal(forumSyncStatusFrom({ modules: { 'MOD-24': { status: 'ok' } } }), 'ok')
  assert.equal(forumSyncStatusFrom({ modules: ['MOD-24 Discourse Forum Sync'] }), null)
  assert.equal(forumSyncStatusFrom({}), null)
})

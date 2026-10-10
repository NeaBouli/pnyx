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
const healthModulesFrom = payload => plain(context.exports.healthModulesFrom(payload))

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

test('health modules: rows come from the modules map, never from overall/total', () => {
  const rows = healthModulesFrom({ overall: 'ok', total: 23, modules: { 'MOD-01': { name: 'HLR Identity', status: 'ok' }, 'MOD-09': { name: 'gov.gr OAuth', status: 'deferred' } } })
  assert.deepEqual(rows, [{ name: 'MOD-01 HLR Identity', status: 'ok' }, { name: 'MOD-09 gov.gr OAuth', status: 'deferred' }])
  assert.deepEqual(healthModulesFrom({ modules: [{ name: 'api', status: 'ok' }] }), [{ name: 'api', status: 'ok' }])
  assert.deepEqual(healthModulesFrom(null), [])
})

const { jobHealth, jobOutcomeLabel } = context.exports
const job = extra => scraperJobsFrom({ scrapers: [{ ...parliament, ...extra }] })[0]

test('job outcome: safe enums/count/time are kept, malformed values become unknown', () => {
  const ok = job({ last_outcome: 'degraded', last_outcome_reason: 'scrape_errors', last_outcome_count: 0, last_outcome_time: '2026-10-10T08:00:00+00:00' })
  assert.deepEqual([ok.last_outcome, ok.last_outcome_reason, ok.last_outcome_count, ok.last_outcome_time], ['degraded', 'scrape_errors', 0, '2026-10-10T08:00:00+00:00'])
  const bad = job({ last_outcome: '<b>x</b>', last_outcome_reason: 'Traceback', last_outcome_count: 10001, last_outcome_time: '2026-10-10 08:00' })
  assert.deepEqual([bad.last_outcome, bad.last_outcome_reason, bad.last_outcome_count, bad.last_outcome_time], [null, null, null, null])
  assert.equal(job({ last_outcome_count: -1 }).last_outcome_count, null)
  assert.equal(job({ last_outcome_count: 1.5 }).last_outcome_count, null)
  assert.equal(job({ last_outcome_time: '2026-13-40T99:00:00Z' }).last_outcome_time, null)
  assert.equal(job({}).last_outcome, null)
})

test('job health: degraded/failed outcome with error_count 0 is never green', () => {
  assert.equal(jobHealth(job({ status: undefined, last_outcome: 'degraded', last_outcome_count: 0 })), 'degraded')
  assert.equal(jobHealth(job({ status: 'ok', last_outcome: 'degraded' })), 'degraded')
  assert.equal(jobHealth(job({ status: 'ok', last_outcome: 'failed' })), 'error')
  assert.equal(jobHealth(job({ status: undefined, last_outcome: 'clean', last_outcome_count: 0 })), 'ok')
})

test('job health: circuit/error/counter precedence and unknown without positive evidence', () => {
  assert.equal(jobHealth(job({ status: 'circuit_open', last_outcome: 'clean' })), 'error')
  assert.equal(jobHealth(job({ status: 'error', last_outcome: 'clean' })), 'error')
  assert.equal(jobHealth(job({ status: 'warning' })), 'degraded')
  assert.equal(jobHealth(job({ status: undefined, error_count: 5, last_outcome: 'clean' })), 'error')
  assert.equal(jobHealth(job({ status: undefined, error_count: 1 })), 'degraded')
  assert.equal(jobHealth(job({ status: undefined })), 'unknown')
  assert.equal(jobHealth(job({ status: 'expired', last_outcome: 'bogus' })), 'unknown')
  assert.equal(jobHealth(scraperJobsFrom({ diavgeia: { error_count: 0 } })[0]), 'unknown')
})

test('job outcome label uses fixed text and placeholders only', () => {
  assert.equal(jobOutcomeLabel(job({ last_outcome: 'failed', last_outcome_reason: 'exception', last_outcome_count: 3 })), 'latest: failed · exception · 3 items')
  assert.equal(jobOutcomeLabel(job({ last_outcome: 'clean', last_outcome_reason: 'none', last_outcome_count: 0 })), 'latest: clean · no errors · 0 items')
  assert.equal(jobOutcomeLabel(job({ last_outcome: 'degraded', last_outcome_reason: '<img src=x>' })), 'latest: degraded · reason ? · ? items')
  assert.equal(jobOutcomeLabel(job({})), 'latest: unknown')
})

test('views wire the shared helpers instead of a local error_count rule', () => {
  const monitor = fs.readFileSync(new URL('./src/app/(dashboard)/monitor/page.tsx', import.meta.url), 'utf8')
  const logs = fs.readFileSync(new URL('./src/app/(dashboard)/logs/page.tsx', import.meta.url), 'utf8')
  for (const src of [monitor, logs]) {
    assert.match(src, /jobHealth\(/)
    assert.match(src, /jobOutcomeLabel\(/)
    assert.doesNotMatch(src, /dangerouslySetInnerHTML/)
  }
  assert.doesNotMatch(monitor, /errCount > 0 \? 'degraded' : 'ok'/)
  assert.doesNotMatch(monitor, />Last OK</)
})

import { asRecord, numberFrom } from './response'

export interface ScraperJob {
  name: string
  last_run: string | null
  last_success: string | null
  error_count: number
  last_error: string | null
  status?: string
  last_outcome: JobOutcome | null
  last_outcome_reason: JobOutcomeReason | null
  last_outcome_count: number | null
  last_outcome_time: string | null
}

export type JobOutcome = 'clean' | 'degraded' | 'failed'
export type JobOutcomeReason = 'none' | 'scrape_errors' | 'conversion_failed' | 'exception'
export type JobHealth = 'ok' | 'degraded' | 'error' | 'unknown'

const OUTCOMES: readonly string[] = ['clean', 'degraded', 'failed']
const REASONS: readonly string[] = ['none', 'scrape_errors', 'conversion_failed', 'exception']
const OUTCOME_COUNT_MAX = 10000
// Timezone-bearing ISO 8601 only (Z or ±hh:mm); anything else is treated as unknown.
const ISO_TZ = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/

function enumFrom<T extends string>(value: unknown, allowed: readonly string[]): T | null {
  return typeof value === 'string' && allowed.includes(value) ? (value as T) : null
}

function outcomeCountFrom(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= OUTCOME_COUNT_MAX ? value : null
}

function isoTimeFrom(value: unknown): string | null {
  return typeof value === 'string' && ISO_TZ.test(value) && !Number.isNaN(Date.parse(value)) ? value : null
}

/**
 * Health of one scraper job. Circuit/error status and the legacy error counter win; a degraded or
 * failed latest outcome qualifies the row even with error_count 0; ok needs positive evidence
 * (server status ok/healthy or a clean outcome). Missing status/outcome with zero errors is unknown.
 */
export function jobHealth(job: ScraperJob): JobHealth {
  const status = job.status?.toLowerCase()
  if (status === 'circuit_open' || status === 'error' || status === 'failed' || job.error_count >= 3) return 'error'
  if (job.last_outcome === 'failed') return 'error'
  if (status === 'warning' || status === 'degraded' || job.error_count > 0 || job.last_outcome === 'degraded') return 'degraded'
  if (status === 'ok' || status === 'healthy' || job.last_outcome === 'clean') return 'ok'
  return 'unknown'
}

const REASON_LABELS: Record<JobOutcomeReason, string> = {
  none: 'no errors',
  scrape_errors: 'scrape errors',
  conversion_failed: 'conversion failed',
  exception: 'exception',
}

/** Compact fixed-label summary of the latest outcome; never echoes server strings. */
export function jobOutcomeLabel(job: ScraperJob): string {
  if (!job.last_outcome) return 'latest: unknown'
  const reason = job.last_outcome_reason ? REASON_LABELS[job.last_outcome_reason] : 'reason ?'
  const count = job.last_outcome_count === null ? '? items' : `${job.last_outcome_count} items`
  return `latest: ${job.last_outcome} · ${reason} · ${count}`
}

function toJob(value: unknown, fallbackName = ''): ScraperJob | null {
  const job = asRecord(value)
  if (!job) return null
  const name = typeof job.name === 'string' && job.name ? job.name : fallbackName
  if (!name) return null
  return {
    name,
    last_run: typeof job.last_run === 'string' ? job.last_run : null,
    last_success: typeof job.last_success === 'string' ? job.last_success : null,
    error_count: numberFrom(job.error_count, 0) ?? 0,
    last_error: typeof job.last_error === 'string' ? job.last_error : null,
    ...(typeof job.status === 'string' ? { status: job.status } : {}),
    last_outcome: enumFrom<JobOutcome>(job.last_outcome, OUTCOMES),
    last_outcome_reason: enumFrom<JobOutcomeReason>(job.last_outcome_reason, REASONS),
    last_outcome_count: outcomeCountFrom(job.last_outcome_count),
    last_outcome_time: isoTimeFrom(job.last_outcome_time),
  }
}

/**
 * Jobs from GET /api/v1/scraper/jobs. The API returns {scrapers: [...]}; older builds returned
 * {jobs: [...]}, a bare array or a name → job map, which are still accepted.
 */
export function scraperJobsFrom(payload: unknown): ScraperJob[] {
  const record = asRecord(payload)
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(record?.scrapers)
      ? record.scrapers
      : Array.isArray(record?.jobs)
        ? record.jobs
        : null
  if (list) return list.map(item => toJob(item)).filter((job): job is ScraperJob => job !== null)
  if (!record || 'scrapers' in record || 'jobs' in record) return []
  return Object.entries(record)
    .map(([name, value]) => toJob(value, name))
    .filter((job): job is ScraperJob => job !== null)
}

export const FORUM_SYNC_MODULE = 'MOD-24'

/** Status of the Discourse bill sync (MOD-24) from GET /api/v1/health/modules, or null if absent. */
export function forumSyncStatusFrom(payload: unknown): string | null {
  const modules = asRecord(asRecord(payload)?.modules)
  const forum = asRecord(modules?.[FORUM_SYNC_MODULE])
  return typeof forum?.status === 'string' ? forum.status : null
}


export interface HealthModuleRow {
  name: string
  status: string
}

/**
 * Module rows from GET /api/v1/health/modules ({overall, modules: {"MOD-01": {name, status}, ...}}).
 * An array or {modules: [...]} is still accepted; top-level keys like overall/total are never rows.
 */
export function healthModulesFrom(payload: unknown): HealthModuleRow[] {
  const record = asRecord(payload)
  const modules = Array.isArray(payload) ? payload : record?.modules
  if (Array.isArray(modules)) {
    return modules
      .map(item => asRecord(item))
      .filter((item): item is Record<string, unknown> => item !== null && typeof item.name === 'string')
      .map(item => ({ name: item.name as string, status: String(item.status ?? 'unknown') }))
  }
  const map = asRecord(modules)
  if (!map) return []
  return Object.entries(map).map(([key, value]) => {
    const item = asRecord(value)
    const name = typeof item?.name === 'string' && item.name ? `${key} ${item.name}` : key
    return { name, status: String(item?.status ?? value ?? 'unknown') }
  })
}

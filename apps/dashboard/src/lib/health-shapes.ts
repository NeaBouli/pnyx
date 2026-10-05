import { asRecord, numberFrom } from './response'

export interface ScraperJob {
  name: string
  last_run: string | null
  last_success: string | null
  error_count: number
  last_error: string | null
  status?: string
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

export async function fetchOverviewJSON(url: string, signal?: AbortSignal): Promise<unknown> {
  if (signal?.aborted) return null
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetch(url, { signal: controller.signal })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}

export const overviewPaths = {
  health: '/health',
  hlr: '/api/proxy/admin/hlr/credits',
  bills: '/api/v1/bills?limit=5',
  cplm: '/api/v1/cplm/aggregate',
  analytics: '/api/v1/analytics/overview',
  scraperJobs: '/api/v1/scraper/jobs',
  discourse: '/api/discourse',
  claude: '/api/v1/claude/budget',
  newsletter: '/api/v1/newsletter/stats',
  divergence: '/api/v1/analytics/divergence-trends?days=90',
  votesTimeline: '/api/v1/analytics/votes-timeline?days=30',
  topDiv: '/api/v1/analytics/top-divergence?limit=5',
  representation: '/api/v1/analytics/representation',
  payments: '/api/v1/payments/status',
  arweave: '/api/v1/arweave/status',
  deepl: '/api/v1/public/deepl/usage',
} as const

export type OverviewWidget = keyof typeof overviewPaths

export function overviewLoading(): Record<OverviewWidget, boolean> {
  return Object.fromEntries(Object.keys(overviewPaths).map(key => [key, true])) as Record<OverviewWidget, boolean>
}

export function loadOverviewWidgets(
  api: string,
  onResult: (key: OverviewWidget, value: unknown) => void,
): () => void {
  const controller = new AbortController()
  for (const key of Object.keys(overviewPaths) as OverviewWidget[]) {
    const path = overviewPaths[key]
    const url = key === 'hlr' || key === 'discourse' ? path : `${api}${path}`
    void fetchOverviewJSON(url, controller.signal).then(value => {
      if (!controller.signal.aborted) onResult(key, value)
    })
  }
  return () => controller.abort()
}

export function hlrEstimate(primary: Record<string, unknown> | null | undefined) {
  const remaining = typeof primary?.remaining === 'number' && Number.isFinite(primary.remaining) && primary.remaining >= 0
    ? primary.remaining : null
  const initial = typeof primary?.initial === 'number' && Number.isFinite(primary.initial) && primary.initial > 0
    ? primary.initial : null
  return { remaining, initial, percent: remaining !== null && initial !== null
    ? Math.min(100, Math.round(remaining / initial * 100)) : null }
}

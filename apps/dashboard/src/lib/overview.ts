export async function fetchOverviewJSON(url: string): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetch(url, { signal: controller.signal })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

export function hlrEstimate(primary: Record<string, unknown> | null | undefined) {
  const remaining = typeof primary?.remaining === 'number' && Number.isFinite(primary.remaining) && primary.remaining >= 0
    ? primary.remaining : null
  const initial = typeof primary?.initial === 'number' && Number.isFinite(primary.initial) && primary.initial > 0
    ? primary.initial : null
  return { remaining, percent: remaining !== null && initial !== null
    ? Math.min(100, Math.round(remaining / initial * 100)) : null }
}

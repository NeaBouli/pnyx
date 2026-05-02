const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.EKKLESIA_API || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || process.env.EKKLESIA_ADMIN_KEY || ''

async function fetchAPI(path: string, options?: RequestInit) {
  try {
    const url = path.startsWith('http') ? path : `${API_BASE}${path}`
    const r = await fetch(url, {
      next: { revalidate: 60 },
      ...options,
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  } catch (err) {
    console.error(`[fetchAPI] ${path}:`, err)
    return null
  }
}

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}admin_key=${ADMIN_KEY}`
}

// --- Health ---
export async function fetchHealth() { return fetchAPI('/health') }
export async function fetchHealthModules() { return fetchAPI('/api/v1/health/modules') }

// --- HLR ---
export async function fetchHlrCredits() { return fetchAPI('/api/v1/identity/hlr/credits') }

// --- Bills ---
export async function fetchBills(limit = 5) { return fetchAPI(`/api/v1/bills?limit=${limit}`) }
export async function fetchAdminBills(limit = 100) { return fetchAPI(`/api/v1/admin/bills?limit=${limit}`) }
export async function fetchAdminStats() { return fetchAPI('/api/v1/admin/stats') }

export async function createBill(data: {
  title_el: string
  title_en?: string
  summary_short_el: string
  governance_level: string
  source_url?: string
}) {
  return fetchAPI(adminURL('/api/v1/admin/bills'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

// --- CPLM ---
export async function fetchCPLM() { return fetchAPI('/api/v1/cplm/aggregate') }
export async function fetchCPLMHistory() { return fetchAPI('/api/v1/cplm/history') }

// --- Analytics ---
export async function fetchAnalyticsOverview() { return fetchAPI('/api/v1/analytics/overview') }
export async function fetchDivergenceTrends(days = 90) { return fetchAPI(`/api/v1/analytics/divergence-trends?days=${days}`) }
export async function fetchVotesTimeline(days = 30) { return fetchAPI(`/api/v1/analytics/votes-timeline?days=${days}`) }
export async function fetchTopDivergence(limit = 10) { return fetchAPI(`/api/v1/analytics/top-divergence?limit=${limit}`) }
export async function fetchRepresentation() { return fetchAPI('/api/v1/analytics/representation') }

// --- Scraper & Jobs ---
export async function fetchScraperJobs() { return fetchAPI('/api/v1/scraper/jobs') }
export async function fetchScraperStatus() { return fetchAPI('/api/v1/scraper/status') }

// --- AI Budget ---
export async function fetchClaudeBudget() { return fetchAPI('/api/v1/claude/budget') }
export async function fetchDeepLUsage() { return fetchAPI('/api/v1/admin/deepl/usage') }

// --- Payments ---
export async function fetchPaymentStatus() { return fetchAPI('/api/v1/payments/status') }

// --- Arweave ---
export async function fetchArweaveStatus() { return fetchAPI('/api/v1/arweave/status') }

// --- Notifications ---
export async function fetchNotificationStatus() { return fetchAPI('/api/v1/notifications/status') }

// --- Newsletter ---
export async function fetchNewsletterStats() { return fetchAPI('/api/v1/newsletter/stats') }

// --- App Version ---
export async function fetchAppVersion() { return fetchAPI('/api/v1/app/version') }

// --- gov.gr Gates ---
export async function fetchGovGrStatus() { return fetchAPI('/api/v1/auth/govgr/status') }

// --- MP Ranking ---
export async function fetchMPRanking() { return fetchAPI('/api/v1/mp/ranking') }

// --- Admin Dashboard ---
export async function fetchAdminDashboard(adminKey: string) {
  return fetchAPI(`/api/v1/admin/dashboard?admin_key=${adminKey}`)
}

// --- Admin Actions (client-side, need ADMIN_KEY) ---
export async function adminReviewBill(billId: number) {
  return fetchAPI(adminURL(`/api/v1/admin/bills/${billId}/review`), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminFetchBillText(billId: number) {
  return fetchAPI(adminURL(`/api/v1/admin/bills/${billId}/fetch-text`), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminTransitionBill(billId: number, status: string) {
  return fetchAPI(adminURL(`/api/v1/bills/${billId}/transition`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminSetPartyVotes(billId: number, votes: Record<string, string>) {
  return fetchAPI(adminURL(`/api/v1/admin/bills/${billId}/party-votes`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(votes),
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminHealScraper() {
  return fetchAPI(adminURL('/api/v1/admin/scraper/heal-status'), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminGenerateCompassQuestions() {
  return fetchAPI(adminURL('/api/v1/admin/compass/generate-questions'), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function fetchCompassPending() {
  return fetchAPI(adminURL('/api/v1/admin/compass/pending-review'))
}

export async function adminApproveCompass(questionId: number) {
  return fetchAPI(adminURL(`/api/v1/admin/compass/approve/${questionId}`), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

export async function adminRejectCompass(questionId: number) {
  return fetchAPI(adminURL(`/api/v1/admin/compass/reject/${questionId}`), {
    method: 'POST',
    cache: 'no-store',
    next: undefined,
  } as RequestInit)
}

// --- Forum (Discourse) --- via server-side proxy to avoid CORS
export async function fetchDiscourseStats() {
  try {
    const r = await fetch('/api/discourse', { next: { revalidate: 300 } })
    return r.json()
  } catch {
    return null
  }
}

export async function fetchDiscourseVersion(): Promise<string> {
  try {
    const data = await fetchDiscourseStats()
    return data?.about?.version || 'unknown'
  } catch {
    return 'offline'
  }
}

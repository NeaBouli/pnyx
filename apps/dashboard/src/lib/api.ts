const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

// Public endpoints (no auth needed) — direct to API
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

// Admin endpoints — through server-side proxy (no key in browser)
async function adminFetch(path: string) {
  try {
    const proxyPath = path.replace(/^\/api\/v1\//, '')
    const r = await fetch(`/api/proxy/${proxyPath}`, { cache: 'no-store' })
    if (!r.ok) return null
    return r.json()
  } catch { return null }
}

async function adminPost(path: string, body?: unknown) {
  try {
    const proxyPath = path.replace(/^\/api\/v1\//, '')
    const r = await fetch(`/api/proxy/${proxyPath}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return r.json()
  } catch { return null }
}

async function adminPatch(path: string, body?: unknown) {
  try {
    const proxyPath = path.replace(/^\/api\/v1\//, '')
    const r = await fetch(`/api/proxy/${proxyPath}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return r.json()
  } catch { return null }
}

// --- Health ---
export async function fetchHealth() { return fetchAPI('/health') }
export async function fetchHealthModules() { return fetchAPI('/api/v1/health/modules') }

// --- HLR ---
export async function fetchHlrCredits() { return fetchAPI('/api/v1/identity/hlr/credits') }

// --- Bills ---
export async function fetchBills(limit = 5) { return fetchAPI(`/api/v1/bills?limit=${limit}`) }
export async function fetchAdminBills(limit = 100) { return adminFetch(`/api/v1/admin/bills?limit=${limit}`) }
export async function fetchAdminStats() { return adminFetch('/api/v1/admin/stats') }

export async function createBill(data: {
  title_el: string
  title_en?: string
  summary_short_el: string
  governance_level: string
  source_url?: string
}) {
  return adminPost('/api/v1/admin/bills', data)
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
export async function fetchDeepLUsage() { return adminFetch('/api/v1/admin/deepl/usage') }

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
export async function fetchAdminDashboard() {
  return adminFetch('/api/v1/admin/dashboard')
}

// --- Admin Actions ---
export async function adminReviewBill(billId: number) {
  return adminPost(`/api/v1/admin/bills/${billId}/review`)
}

export async function adminFetchBillText(billId: number) {
  return adminPost(`/api/v1/admin/bills/${billId}/fetch-text`)
}

export async function adminSetBillText(billId: number, text: string) {
  return adminPost(`/api/v1/admin/bills/${billId}/set-text`, { text_el: text })
}

export async function adminPatchBill(billId: number, data: Record<string, unknown>) {
  return adminPatch(`/api/v1/admin/bills/${billId}`, data)
}

export async function adminTransitionBill(billId: number, newStatus: string) {
  return adminPost(`/api/v1/bills/${billId}/transition`, { new_status: newStatus })
}

export async function adminSetPartyVotes(billId: number, votes: Record<string, string>) {
  return adminPost(`/api/v1/admin/bills/${billId}/party-votes`, { votes })
}

export async function fetchMPCompare(partyAbbr: string) {
  return fetchAPI(`/api/v1/mp/compare/${partyAbbr}`)
}

export async function adminHealScraper() {
  return adminPost('/api/v1/admin/scraper/heal-status')
}

export async function adminGenerateCompassQuestions() {
  return adminPost('/api/v1/admin/compass/generate-questions')
}

export async function fetchCompassPending() {
  return adminFetch('/api/v1/admin/compass/pending-review')
}

export async function adminApproveCompass(questionId: number) {
  return adminPost(`/api/v1/admin/compass/approve/${questionId}`)
}

export async function adminRejectCompass(questionId: number) {
  return adminPost(`/api/v1/admin/compass/reject/${questionId}`)
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

// --- Push Notifications --- via proxy
export async function sendPushNotification(title: string, body: string) {
  return adminPost('/api/v1/notify/send', {
    title_el: title, body_el: body, title_en: title, body_en: body,
  })
}

// --- VAA ---
export async function fetchVAAStatements() { return fetchAPI('/api/v1/vaa/statements') }
export async function fetchVAAParties() { return fetchAPI('/api/v1/vaa/parties') }

// --- Diavgeia Admin ---
export async function adminDiavgeiaScrape() {
  return adminPost('/api/v1/admin/diavgeia/scrape')
}
export async function adminRefreshOrgsCache() {
  return adminPost('/api/v1/admin/diavgeia/refresh-orgs-cache')
}

export async function fetchNewsletterLists() { return fetchAPI('/api/v1/newsletter/lists') }
export async function adminScraperTest() {
  try {
    const r = await fetch(`${API_BASE}/api/v1/scraper/test`, { cache: 'no-store' })
    return r.json()
  } catch { return null }
}

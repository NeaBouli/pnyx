const API = process.env.EKKLESIA_API || 'https://api.ekklesia.gr'

export async function fetchHealth() {
  const r = await fetch(`${API}/health`, { next: { revalidate: 30 } })
  return r.json()
}

export async function fetchHlrCredits() {
  const r = await fetch(`${API}/api/v1/identity/hlr/credits`, {
    next: { revalidate: 30 },
  })
  return r.json()
}

export async function fetchBills(limit = 5) {
  const r = await fetch(`${API}/api/v1/bills?limit=${limit}`, {
    next: { revalidate: 60 },
  })
  return r.json()
}

export async function fetchCPLM() {
  const r = await fetch(`${API}/api/v1/public/cplm`, {
    next: { revalidate: 60 },
  })
  return r.json()
}

export async function fetchRepresentation() {
  const r = await fetch(`${API}/api/v1/public/representation`, {
    next: { revalidate: 60 },
  })
  return r.json()
}

export async function fetchAdminStats() {
  const r = await fetch(`${API}/api/v1/admin/stats`, { next: { revalidate: 60 } })
  return r.json()
}

export async function fetchAdminBills(limit = 100) {
  const r = await fetch(`${API}/api/v1/admin/bills?limit=${limit}`, {
    next: { revalidate: 30 },
  })
  return r.json()
}

export async function createBill(data: {
  title_el: string
  title_en?: string
  summary_short_el: string
  governance_level: string
  source_url?: string
}) {
  const adminKey = process.env.EKKLESIA_ADMIN_KEY || ''
  const r = await fetch(`${API}/api/v1/admin/bills?admin_key=${adminKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  })
  if (!r.ok) throw new Error(`createBill: HTTP ${r.status}`)
  return r.json()
}

export async function fetchDiscourseVersion(): Promise<string> {
  try {
    const r = await fetch('https://pnyx.ekklesia.gr/about.json', {
      next: { revalidate: 300 },
    })
    const d = await r.json()
    return d.about?.version || 'unknown'
  } catch {
    return 'offline'
  }
}

'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type Tab = 'overview' | 'analytics' | 'finance'

// ─── Helpers ───

async function apiFetch(path: string) {
  try {
    const url = path.startsWith('http') ? path : `${API}${path}`
    const r = await fetch(url)
    if (!r.ok) return null
    return r.json()
  } catch { return null }
}

// ─── StatCard ───

interface StatCardProps {
  title: string
  value: string | number
  sub?: string
  color?: string
  badge?: { label: string; color: 'green' | 'red' | 'yellow' | 'gray' }
  progress?: number
}

function StatCard({ title, value, sub, color = 'text-blue-600', badge, progress }: StatCardProps) {
  const badgeColors: Record<string, string> = {
    green: 'bg-green-100 text-green-700',
    red: 'bg-red-100 text-red-700',
    yellow: 'bg-yellow-100 text-yellow-800',
    gray: 'bg-gray-100 text-gray-600',
  }
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between mb-1">
        <div className="text-sm font-medium text-gray-500">{title}</div>
        {badge && (
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeColors[badge.color]}`}>
            {badge.label}
          </span>
        )}
      </div>
      <div className={`text-3xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
      {progress != null && (
        <div className="mt-2">
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Status labels ───

type BillStatus = 'ANNOUNCED' | 'ACTIVE' | 'WINDOW_24H' | 'PARLIAMENT_VOTED' | 'OPEN_END'

const STATUS_LABELS: Record<BillStatus, string> = {
  ANNOUNCED: 'Ανακοινώθηκε',
  ACTIVE: 'Ενεργό',
  WINDOW_24H: 'Παράθυρο 24ω',
  PARLIAMENT_VOTED: 'Ψηφίστηκε',
  OPEN_END: 'Ανοιχτό',
}

const STATUS_COLORS: Record<BillStatus, string> = {
  ANNOUNCED: 'bg-gray-100 text-gray-700',
  ACTIVE: 'bg-green-100 text-green-700',
  WINDOW_24H: 'bg-yellow-100 text-yellow-800',
  PARLIAMENT_VOTED: 'bg-blue-100 text-blue-700',
  OPEN_END: 'bg-purple-100 text-purple-700',
}

// ─── Skeleton ───

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
}

// ─── Main ───

export default function OverviewPage() {
  const [tab, setTab] = useState<Tab>('overview')
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<Record<string, unknown>>({})

  const loadData = useCallback(async () => {
    setLoading(true)
    const [
      health, hlr, bills, cplm, analytics, scraperJobs, discourse,
      claude, newsletter, divergence, votesTimeline, topDiv, representation,
      payments, arweave, deepl,
    ] = await Promise.allSettled([
      apiFetch('/health'),
      apiFetch('/api/v1/identity/hlr/credits'),
      apiFetch('/api/v1/bills?limit=5'),
      apiFetch('/api/v1/cplm/aggregate'),
      apiFetch('/api/v1/analytics/overview'),
      apiFetch('/api/v1/scraper/jobs'),
      fetch('https://pnyx.ekklesia.gr/about.json').then(r => r.json()).catch(() => null),
      apiFetch('/api/v1/claude/budget'),
      apiFetch('/api/v1/newsletter/stats'),
      apiFetch('/api/v1/analytics/divergence-trends?days=90'),
      apiFetch('/api/v1/analytics/votes-timeline?days=30'),
      apiFetch('/api/v1/analytics/top-divergence?limit=5'),
      apiFetch('/api/v1/analytics/representation'),
      apiFetch('/api/v1/payments/status'),
      apiFetch('/api/v1/arweave/status'),
      apiFetch('/api/v1/admin/deepl/usage'),
    ])

    const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
    setData({
      health: v(health), hlr: v(hlr), bills: v(bills), cplm: v(cplm),
      analytics: v(analytics), scraperJobs: v(scraperJobs), discourse: v(discourse),
      claude: v(claude), newsletter: v(newsletter),
      divergence: v(divergence), votesTimeline: v(votesTimeline),
      topDiv: v(topDiv), representation: v(representation),
      payments: v(payments), arweave: v(arweave), deepl: v(deepl),
    })
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  const healthData = data.health as Record<string, unknown> | null
  const hlrData = data.hlr as Record<string, unknown> | null
  const cplmData = data.cplm as Record<string, unknown> | null
  const analyticsData = data.analytics as Record<string, unknown> | null
  const scraperJobs = data.scraperJobs as unknown[] | null
  const discourseData = data.discourse as Record<string, unknown> | null
  const claudeData = data.claude as Record<string, unknown> | null
  const newsletterData = data.newsletter as Record<string, unknown> | null
  const billsRaw = data.bills
  const bills = Array.isArray(billsRaw) ? billsRaw : (billsRaw as Record<string, unknown>)?.bills ?? []
  const divergenceData = data.divergence as unknown[] | null
  const votesTimelineData = data.votesTimeline as unknown[] | null
  const topDivData = data.topDiv as unknown[] | null
  const representationData = data.representation as Record<string, unknown> | null
  const paymentsData = data.payments as Record<string, unknown> | null
  const arweaveData = data.arweave as Record<string, unknown> | null
  const deeplData = data.deepl as Record<string, unknown> | null

  // Derived
  const apiOk = healthData?.status === 'ok'
  const moduleCount = healthData?.modules ? Object.keys(healthData.modules as object).length : 0
  const primary = hlrData?.primary as Record<string, unknown> | null
  const primaryCredits = primary?.remaining as number | null
  const primaryTotal = (primary?.total as number) ?? 1000
  const primaryPct = primaryCredits != null ? Math.round((primaryCredits / primaryTotal) * 100) : null
  const primaryProvider = primary?.provider as string | null
  const activeBills = Array.isArray(bills) ? bills.filter((b: Record<string, unknown>) => b.status === 'ACTIVE').length : 0
  const windowBills = Array.isArray(bills) ? bills.filter((b: Record<string, unknown>) => b.status === 'WINDOW_24H').length : 0
  const totalVotes = analyticsData?.total_votes as number | null
  const cplmX = cplmData?.x != null ? (cplmData.x as number).toFixed(1) : null
  const cplmY = cplmData?.y != null ? (cplmData.y as number).toFixed(1) : null
  const discourseVersion = (discourseData?.about as Record<string, unknown>)?.version as string | null
  const discourseTopics = (discourseData?.about as Record<string, unknown>)?.topic_count as number | null
  const claudeUsed = claudeData?.used_eur as number | null
  const claudeTotal = claudeData?.budget_eur as number | null
  const ollamaStatus = claudeData?.ollama_status as string | null
  const subscriberCount = newsletterData?.subscriber_count as number | null
  const sentMonth = newsletterData?.sent_month as number | null

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Επισκόπηση' },
    { key: 'analytics', label: 'Αναλυτικά' },
    { key: 'finance', label: 'Οικονομικά' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Επισκόπηση Dashboard</h1>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Ανανέωση...' : 'Ανανέωση'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* TAB: Overview */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* 8 tiles */}
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Κατάσταση API"
                value={apiOk ? 'Ενεργό' : 'Σφάλμα'}
                sub={moduleCount > 0 ? `${moduleCount} ενεργά modules` : undefined}
                color={apiOk ? 'text-green-600' : 'text-red-600'}
                badge={{ label: apiOk ? 'OK' : 'ERROR', color: apiOk ? 'green' : 'red' }}
              />
              <StatCard
                title="HLR Credits (Κύρια)"
                value={primaryCredits != null ? primaryCredits : '—'}
                sub={primaryProvider ? `Provider: ${primaryProvider}` : 'Μη διαθέσιμο'}
                color={primaryCredits != null ? 'text-blue-600' : 'text-gray-400'}
                progress={primaryPct ?? undefined}
              />
              <StatCard
                title="Ενεργά Νομοσχέδια"
                value={activeBills}
                sub={windowBills > 0 ? `${windowBills} σε WINDOW_24H` : 'Κανένα σε 24ω παράθυρο'}
                color="text-blue-600"
              />
              <StatCard
                title="Συνολικές Ψηφοφορίες"
                value={totalVotes != null ? totalVotes.toLocaleString('el-GR') : '—'}
                sub="Από analytics/overview"
                color="text-blue-600"
              />
              <StatCard
                title="CPLM Θέση"
                value={cplmX && cplmY ? `(${cplmX}, ${cplmY})` : '—'}
                sub="X = Οικονομία, Y = Κοινωνία"
                color={cplmData ? 'text-purple-600' : 'text-gray-400'}
              />
              <StatCard
                title="Discourse Forum"
                value={discourseVersion ?? 'offline'}
                sub={discourseTopics != null ? `${discourseTopics} θέματα` : 'pnyx.ekklesia.gr'}
                color={discourseVersion ? 'text-blue-600' : 'text-red-600'}
                badge={{ label: discourseVersion ? 'Live' : 'Offline', color: discourseVersion ? 'green' : 'red' }}
              />
              <StatCard
                title="AI Budget"
                value={claudeUsed != null && claudeTotal != null ? `${claudeUsed.toFixed(2)}/${claudeTotal}` : '—'}
                sub={ollamaStatus ? `Ollama: ${ollamaStatus}` : 'Claude EUR'}
                color="text-blue-600"
              />
              <StatCard
                title="Newsletter"
                value={subscriberCount != null ? subscriberCount : '—'}
                sub={sentMonth != null ? `${sentMonth} αποστολές/μήνα` : 'Συνδρομητές'}
                color="text-blue-600"
              />
            </div>
          )}

          {/* Recent bills */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">Τελευταία Νομοσχέδια</h2>
              <a href="/bills" className="text-sm text-blue-600 hover:underline">Όλα →</a>
            </div>
            {!Array.isArray(bills) || bills.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">Δεν βρέθηκαν νομοσχέδια</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">ID</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Τίτλος</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Κατάσταση</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Ημερομηνία</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(bills as Record<string, unknown>[]).slice(0, 5).map((bill) => (
                    <tr key={bill.id as number} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">#{bill.id as number}</td>
                      <td className="px-4 py-2.5 font-medium text-gray-900 truncate max-w-xs">{bill.title_el as string}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[bill.status as BillStatus] ?? 'bg-gray-100 text-gray-600'}`}>
                          {STATUS_LABELS[bill.status as BillStatus] ?? bill.status as string}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-xs">
                        {new Date(bill.created_at as string).toLocaleDateString('el-GR')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Scraper jobs */}
          <div>
            <h2 className="font-semibold text-gray-800 mb-3">Scheduler Jobs</h2>
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
              </div>
            ) : Array.isArray(scraperJobs) && scraperJobs.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {(scraperJobs as Record<string, unknown>[]).map((job, i) => {
                  const ok = job.status === 'ok' || job.status === 'success' || job.healthy === true
                  return (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-800 truncate">{job.name as string ?? job.job_id as string ?? `Job ${i + 1}`}</span>
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                      </div>
                      {job.interval && <div className="text-xs text-gray-400">{job.interval as string}</div>}
                      {job.last_run && <div className="text-xs text-gray-400 mt-0.5">Τελ.: {new Date(job.last_run as string).toLocaleString('el-GR')}</div>}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl p-6 text-center text-sm text-gray-400">
                Δεν βρέθηκαν δεδομένα scheduler jobs
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: Analytics */}
      {tab === 'analytics' && (
        <div className="space-y-6">
          {/* Divergence trends */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Divergence Trends (90 ημέρες)</h2>
            {Array.isArray(divergenceData) && divergenceData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={divergenceData as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v?.slice(5) ?? ''} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="divergence" stroke="#dc2626" dot={false} strokeWidth={2} name="Divergence" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-40 flex items-center justify-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Votes timeline */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Ψήφοι ανά Ημέρα (30 ημέρες)</h2>
            {Array.isArray(votesTimelineData) && votesTimelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={votesTimelineData as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v?.slice(5) ?? ''} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="votes" fill="#2563eb" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-40 flex items-center justify-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Top 5 divergence */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Top 5 Bills κατά Divergence</h2>
            </div>
            {Array.isArray(topDivData) && topDivData.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Bill</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-500">Divergence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(topDivData as Record<string, unknown>[]).slice(0, 5).map((item, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 text-gray-800 truncate max-w-xs">
                        #{item.bill_id as number} — {item.title_el as string ?? item.title as string ?? ''}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-red-600">
                        {((item.divergence_score as number ?? item.divergence as number ?? 0) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Representation Score */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Representation Score</h2>
            {representationData ? (
              <div>
                <div className="text-3xl font-bold text-purple-600 mb-2">
                  {((representationData.score as number ?? 0) * 100).toFixed(1)}%
                </div>
                <div className="w-full bg-gray-100 rounded-full h-3">
                  <div
                    className="bg-purple-500 h-3 rounded-full transition-all"
                    style={{ width: `${Math.min(100, (representationData.score as number ?? 0) * 100)}%` }}
                  />
                </div>
                <div className="text-xs text-gray-400 mt-2">Πόσο αντιπροσωπεύει η Βουλή τους πολίτες</div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>
        </div>
      )}

      {/* TAB: Finance */}
      {tab === 'finance' && (
        <div className="space-y-6">
          {/* Payment status */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Κατάσταση Πληρωμών</h2>
            {paymentsData ? (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {['server', 'domain', 'reserve'].map(key => {
                  const val = paymentsData[key]
                  return (
                    <div key={key} className="bg-gray-50 rounded-lg p-4">
                      <div className="text-xs text-gray-500 mb-1 capitalize">{key === 'server' ? 'Διακομιστής' : key === 'domain' ? 'Domain' : 'Αποθεματικό'}</div>
                      <div className="text-xl font-bold text-gray-800">
                        {val != null ? (typeof val === 'object' ? JSON.stringify(val) : String(val)) : '—'}
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Δεν υπάρχουν δεδομένα πληρωμών</div>
            )}
          </div>

          {/* HLR Credits */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">HLR Credits</h2>
            {hlrData ? (
              <div className="space-y-4">
                {(['primary', 'fallback'] as const).map(key => {
                  const prov = hlrData[key] as Record<string, unknown> | null
                  if (!prov) return null
                  const rem = prov.remaining as number | null
                  const tot = (prov.total as number) ?? 1000
                  const pct = rem != null ? Math.round((rem / tot) * 100) : 0
                  return (
                    <div key={key}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">{key === 'primary' ? 'Κύρια' : 'Εφεδρική'} ({prov.provider as string ?? '—'})</span>
                        <span className="font-medium text-gray-800">{rem ?? '—'} / {tot}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className={`h-2 rounded-full transition-all ${pct > 20 ? 'bg-blue-500' : 'bg-red-500'}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Μη διαθέσιμο</div>
            )}
          </div>

          {/* Arweave */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Arweave Balance</h2>
            {arweaveData ? (
              <div>
                <div className="text-3xl font-bold text-blue-600">
                  {arweaveData.balance != null ? `${(arweaveData.balance as number).toFixed(4)} AR` : '—'}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {arweaveData.address ? `Wallet: ${(arweaveData.address as string).slice(0, 12)}...` : ''}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">Μη διαθέσιμο</div>
            )}
          </div>

          {/* Claude AI Budget */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Claude AI Budget</h2>
            {claudeData ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">Ημερήσιο</div>
                  <div className="text-xl font-bold text-gray-800">
                    {(claudeData as Record<string, unknown>).daily_used != null
                      ? `${((claudeData as Record<string, unknown>).daily_used as number).toFixed(2)} EUR`
                      : '—'}
                  </div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">Μηνιαίο</div>
                  <div className="text-xl font-bold text-gray-800">
                    {claudeUsed != null && claudeTotal != null
                      ? `${claudeUsed.toFixed(2)} / ${claudeTotal} EUR`
                      : '—'}
                  </div>
                  {claudeUsed != null && claudeTotal != null && claudeTotal > 0 && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${Math.min(100, (claudeUsed / claudeTotal) * 100)}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">Μη διαθέσιμο</div>
            )}
          </div>

          {/* DeepL */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">DeepL Κατανάλωση</h2>
            {deeplData ? (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Χαρακτήρες</span>
                  <span className="font-medium text-gray-800">
                    {(deeplData as Record<string, unknown>).character_count != null
                      ? `${((deeplData as Record<string, unknown>).character_count as number).toLocaleString('el-GR')} / 500.000`
                      : '—'}
                  </span>
                </div>
                {(deeplData as Record<string, unknown>).character_count != null && (
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-green-500 h-2 rounded-full transition-all"
                      style={{ width: `${Math.min(100, ((deeplData as Record<string, unknown>).character_count as number / 500000) * 100)}%` }}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Μη διαθέσιμο</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

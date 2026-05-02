'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface ModuleBadgeProps {
  name: string
  status: string
}

function ModuleBadge({ name, status }: ModuleBadgeProps) {
  const isOk = status === 'ok' || status === 'up' || status === 'healthy' || status === 'true'
  const isDegraded = status === 'degraded'
  const isDisabled = status === 'disabled'
  return (
    <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
      <span className="text-sm font-medium text-gray-700">{name}</span>
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
        isOk ? 'bg-green-100 text-green-700' :
        isDegraded ? 'bg-yellow-100 text-yellow-700' :
        isDisabled ? 'bg-gray-100 text-gray-500' :
        'bg-red-100 text-red-700'
      }`}>
        {isOk ? 'Ενεργό' : isDegraded ? 'Υποβαθμισμένο' : isDisabled ? 'Απενεργ.' : status}
      </span>
    </div>
  )
}

export default function SystemPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [modules, setModules] = useState<Record<string, unknown> | null>(null)
  const [hlr, setHlr] = useState<Record<string, unknown> | null>(null)
  const [govGr, setGovGr] = useState<Record<string, unknown> | null>(null)
  const [arweave, setArweave] = useState<Record<string, unknown> | null>(null)
  const [notifications, setNotifications] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    const [hRes, mRes, hlrRes, govRes, arRes, notifRes] = await Promise.allSettled([
      fetch(`${API}/health`).then(r => r.json()),
      fetch(`${API}/api/v1/health/modules`).then(r => r.json()),
      fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
      fetch(`${API}/api/v1/auth/govgr/status`).then(r => r.json()),
      fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
      fetch(`${API}/api/v1/notifications/status`).then(r => r.json()),
    ])
    const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
    setHealth(v(hRes) as Record<string, unknown> | null)
    setModules(v(mRes) as Record<string, unknown> | null)
    setHlr(v(hlrRes) as Record<string, unknown> | null)
    setGovGr(v(govRes) as Record<string, unknown> | null)
    setArweave(v(arRes) as Record<string, unknown> | null)
    setNotifications(v(notifRes) as Record<string, unknown> | null)
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  const healthStatus = health?.status as string | null
  const isOk = healthStatus === 'ok'
  const moduleMap: Record<string, string> = (modules?.modules ?? modules ?? {}) as Record<string, string>
  const moduleEntries = Object.entries(moduleMap).filter(([k]) => k !== 'status' && k !== 'timestamp')

  const hlrPrimary = hlr?.primary as Record<string, unknown> | undefined
  const hlrFallback = hlr?.fallback as Record<string, unknown> | undefined

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Κατάσταση Συστήματος</h1>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Ανανέωση...' : 'Ανανέωση'}
        </button>
      </div>

      {/* Health Overview */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800">Κατάσταση API</h2>
          {health ? (
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${isOk ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {isOk ? 'Λειτουργικό' : 'Σφάλμα'}
            </span>
          ) : (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Μη διαθέσιμο</span>
          )}
        </div>
        <div className="p-4">
          {moduleEntries.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {moduleEntries.map(([name, status]) => (
                <ModuleBadge key={name} name={name} status={String(status)} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-4">Δεν υπάρχουν διαθέσιμα δεδομένα modules</p>
          )}
        </div>
      </div>

      {/* HLR Credits */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">HLR Credits</h2>
          <p className="text-xs text-gray-400 mt-0.5">Credits επαλήθευσης αριθμών τηλεφώνου</p>
        </div>
        <div className="px-6 py-4 space-y-3">
          {[
            { label: 'Κύρια πηγή (Primary)', data: hlrPrimary },
            { label: 'Εφεδρική πηγή (Fallback)', data: hlrFallback },
          ].map(({ label, data }) => (
            <div key={label} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
              <span className="text-sm text-gray-600">{label}</span>
              {data ? (
                <div className="text-right">
                  <div className="text-sm font-semibold text-gray-800">
                    {data.remaining != null ? `${data.remaining} credits` : '—'}
                  </div>
                  {data.provider && <div className="text-xs text-gray-400">{data.provider as string}</div>}
                </div>
              ) : (
                <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">Μη διαθέσιμο</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Grid: Arweave + Notifications + gov.gr */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">Arweave Balance</div>
          <div className="text-2xl font-bold text-blue-600">
            {arweave?.balance != null ? `${(arweave.balance as number).toFixed(4)} AR` : '—'}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            {arweave?.address ? `${(arweave.address as string).slice(0, 10)}...` : 'Wallet'}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">Push Notifications</div>
          <div className="text-2xl font-bold text-blue-600">
            {notifications?.subscriber_count ?? notifications?.device_count ?? '—'}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">Εγγεγραμμένες συσκευές</div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">gov.gr OAuth Gates</div>
          <div className="text-2xl font-bold text-gray-800">
            {govGr?.gates_fulfilled ?? govGr?.fulfilled ?? '0'}/{govGr?.gates_total ?? govGr?.total ?? '4'}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            {govGr?.status === 'active' ? 'Ενεργό' : 'Αναμονή πλήρωσης'}
          </div>
        </div>
      </div>
    </div>
  )
}

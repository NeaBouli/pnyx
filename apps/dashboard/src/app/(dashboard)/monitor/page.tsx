'use client'

import { useCallback, useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface ModuleHealth {
  name: string
  status: string
  error?: string
  last_success?: string
  error_count?: number
}

interface ScraperJob {
  name: string
  last_run: string | null
  last_success: string | null
  error_count: number
  last_error: string | null
}

export default function MonitorPage() {
  const [modules, setModules] = useState<Record<string, ModuleHealth>>({})
  const [overall, setOverall] = useState('')
  const [jobs, setJobs] = useState<ScraperJob[]>([])
  const [loading, setLoading] = useState(true)
  const [actionResult, setActionResult] = useState<Record<string, { status: string; data?: string }>>({})
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})

  const loadData = useCallback(async () => {
    try {
      const [mods, jobsResp] = await Promise.allSettled([
        fetch(`${API}/api/v1/health/modules`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/jobs`).then(r => r.json()),
      ])
      if (mods.status === 'fulfilled') {
        setModules(mods.value.modules || {})
        setOverall(mods.value.overall || 'unknown')
      }
      if (jobsResp.status === 'fulfilled') {
        const raw = jobsResp.value.jobs || jobsResp.value
        if (Array.isArray(raw)) setJobs(raw)
        else if (typeof raw === 'object') {
          setJobs(Object.entries(raw).map(([name, v]: [string, any]) => ({ name, ...v })))
        }
      }
    } catch { /* */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  async function triggerAction(key: string, endpoint: string) {
    setActionLoading(prev => ({ ...prev, [key]: true }))
    setActionResult(prev => ({ ...prev, [key]: { status: 'loading' } }))
    try {
      const r = await fetch(`/api/proxy/${endpoint}`, { method: 'POST' })
      const data = await r.json()
      if (r.ok) {
        setActionResult(prev => ({ ...prev, [key]: { status: 'ok', data: JSON.stringify(data) } }))
      } else {
        setActionResult(prev => ({ ...prev, [key]: { status: 'error', data: data.detail || `HTTP ${r.status}` } }))
      }
    } catch (e: any) {
      setActionResult(prev => ({ ...prev, [key]: { status: 'error', data: e.message } }))
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }))
    }
  }

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      ok: 'bg-green-100 text-green-700',
      degraded: 'bg-yellow-100 text-yellow-700',
      error: 'bg-red-100 text-red-700',
      disabled: 'bg-gray-100 text-gray-500',
      deferred: 'bg-gray-100 text-gray-400',
    }
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-500'}`}>
        {status}
      </span>
    )
  }

  const formatAge = (iso: string | null) => {
    if (!iso) return '—'
    const age = (Date.now() - new Date(iso).getTime()) / 3600000
    if (age < 1) return `${Math.round(age * 60)}m`
    if (age < 48) return `${Math.round(age)}h`
    return `${Math.round(age / 24)}d`
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Monitor — Self-Healing</h1>
          <p className="text-sm text-gray-500 mt-1">NEA-241: 3-Tier Auto-Recovery (T1 API / T2 Docker / T3 Telegram)</p>
        </div>
        <div className="flex items-center gap-3">
          {overall && statusBadge(overall)}
          <button
            onClick={() => { setLoading(true); loadData() }}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Aktualisieren
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1,2,3].map(i => <div key={i} className="animate-pulse bg-gray-200 rounded h-28" />)}
        </div>
      ) : (
        <>
          {/* Module Health Grid */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Module Status ({Object.keys(modules).length})</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {Object.entries(modules).map(([key, mod]) => (
                <div key={key} className="border border-gray-100 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-gray-400">{key}</span>
                    {statusBadge(mod.status)}
                  </div>
                  <div className="text-sm font-medium text-gray-800 truncate">{mod.name}</div>
                  {mod.error && <div className="text-xs text-red-500 mt-1 truncate">{mod.error}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Scraper Jobs */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-base font-semibold text-gray-800">Scraper Jobs</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Job</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Last Run</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Last OK</th>
                    <th className="text-right px-4 py-3 font-medium text-gray-600">Errors</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {jobs.map(j => {
                    const errCount = j.error_count || 0
                    const status = errCount >= 3 ? 'error' : errCount > 0 ? 'degraded' : 'ok'
                    return (
                      <tr key={j.name} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-gray-900">{j.name}</td>
                        <td className="px-4 py-3 text-gray-500">{formatAge(j.last_run)}</td>
                        <td className="px-4 py-3 text-gray-500">{formatAge(j.last_success)}</td>
                        <td className="px-4 py-3 text-right">{errCount > 0 ? <span className="text-red-600 font-bold">{errCount}</span> : <span className="text-gray-400">0</span>}</td>
                        <td className="px-4 py-3">{statusBadge(status)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Admin Actions */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Admin Actions</h2>
            <div className="flex flex-wrap gap-3">
              {[
                { key: 'catchup', label: 'Scraper Catch-up', endpoint: 'admin/scraper/catch-up' },
                { key: 'resync', label: 'Forum Resync', endpoint: 'admin/forum/resync-all' },
              ].map(btn => (
                <div key={btn.key}>
                  <button
                    onClick={() => triggerAction(btn.key, btn.endpoint)}
                    disabled={!!actionLoading[btn.key]}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    {actionLoading[btn.key] ? 'Wird ausgeführt...' : btn.label}
                  </button>
                  {actionResult[btn.key] && (
                    <div className={`mt-2 p-2 rounded text-xs ${actionResult[btn.key].status === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                      {actionResult[btn.key].data}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

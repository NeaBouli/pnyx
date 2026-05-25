'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type TabKey = 'system' | 'hlr' | 'scheduler' | 'api'

interface HealthModule {
  name: string
  status: string
}

interface HealthData {
  status: string
  version?: string
  uptime?: number
  timestamp?: string
}

interface HlrCredits {
  primary_credits?: number
  fallback_credits?: number
  primary_status?: string
  fallback_status?: string
  failover_active?: boolean
}

interface ScraperJob {
  name: string
  last_run?: string
  status?: string
  error?: string
  error_count?: number
  next_run?: string
}

interface ScraperStatus {
  ollama?: string
  ollama_model?: string
  ollama_status?: string
  status?: string
}

function StatusBadge({ status }: { status: string | undefined }) {
  const s = (status ?? 'unknown').toLowerCase()
  const color = s === 'ok' || s === 'running' || s === 'active' || s === 'healthy'
    ? 'bg-green-100 text-green-700'
    : s === 'error' || s === 'failed' || s === 'down'
    ? 'bg-red-100 text-red-700'
    : 'bg-gray-100 text-gray-600'
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {String(status ?? 'unknown')}
    </span>
  )
}

export default function LogsPage() {
  const [tab, setTab] = useState<TabKey>('system')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  // System
  const [health, setHealth] = useState<HealthData | null>(null)
  const [modules, setModules] = useState<HealthModule[]>([])

  // HLR
  const [hlr, setHlr] = useState<HlrCredits | null>(null)

  // Scheduler
  const [jobs, setJobs] = useState<ScraperJob[]>([])

  // API
  const [scraperStatus, setScraperStatus] = useState<ScraperStatus | null>(null)

  // Log Analysis
  const [logAnalysisLoading, setLogAnalysisLoading] = useState(false)
  const [logAnalysisResult, setLogAnalysisResult] = useState<string | null>(null)
  const [logAnalysisError, setLogAnalysisError] = useState<string | null>(null)

  // Containers
  const [containers, setContainers] = useState<{ name: string; image: string; status: string; state: string; health: string | null }[]>([])

  // Ollama
  const [ollamaInfo, setOllamaInfo] = useState<{ reachable: boolean; models: string[]; active_model: string | null } | null>(null)

  // Log Stream
  const [logStream, setLogStream] = useState<{ available: boolean; lines: string[]; reason?: string } | null>(null)
  const [logStreamLoading, setLogStreamLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const settled = await Promise.allSettled([
        fetch(`${API}/health`).then(r => r.json()),
        fetch(`${API}/api/v1/health/modules`).then(r => r.json()),
        fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/jobs`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/status`).then(r => r.json()),
      ])

      if (settled[0].status === 'fulfilled') setHealth(settled[0].value as HealthData)
      if (settled[1].status === 'fulfilled') {
        const raw = settled[1].value
        if (Array.isArray(raw)) {
          setModules(raw as HealthModule[])
        } else if (raw && typeof raw === 'object') {
          // Could be {modules: [...]} or {name: status, ...}
          const obj = raw as Record<string, unknown>
          if (Array.isArray(obj.modules)) {
            setModules(obj.modules as HealthModule[])
          } else {
            // Convert object entries to HealthModule[]
            const arr: HealthModule[] = []
            for (const [key, val] of Object.entries(obj)) {
              if (typeof val === 'object' && val !== null && 'name' in val) {
                arr.push(val as HealthModule)
              } else {
                arr.push({ name: key, status: String(val) })
              }
            }
            setModules(arr)
          }
        }
      }
      if (settled[2].status === 'fulfilled') setHlr(settled[2].value as HlrCredits)
      if (settled[3].status === 'fulfilled') {
        const raw = settled[3].value
        const jobArr = Array.isArray(raw) ? raw : (raw as Record<string, unknown>)?.jobs
        setJobs(Array.isArray(jobArr) ? jobArr as ScraperJob[] : [])
      }
      if (settled[4].status === 'fulfilled') setScraperStatus(settled[4].value as ScraperStatus)

      // Admin-authenticated endpoints (via proxy)
      const adminSettled = await Promise.allSettled([
        fetch('/api/proxy/admin/logs/containers').then(r => r.ok ? r.json() : null),
        fetch('/api/proxy/admin/logs/ollama').then(r => r.ok ? r.json() : null),
      ])
      if (adminSettled[0].status === 'fulfilled' && adminSettled[0].value) {
        setContainers((adminSettled[0].value as Record<string, unknown>).containers as typeof containers)
      }
      if (adminSettled[1].status === 'fulfilled' && adminSettled[1].value) {
        setOllamaInfo(adminSettled[1].value as typeof ollamaInfo)
      }

      setLastChecked(new Date())
    } catch {
      // partial failure is ok
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(refresh, 30_000)
    return () => clearInterval(interval)
  }, [autoRefresh, refresh])

  async function handleLogStream() {
    setLogStreamLoading(true)
    try {
      const res = await fetch('/api/proxy/admin/logs/stream')
      const data = await res.json() as Record<string, unknown>
      if (res.ok) {
        setLogStream(data as typeof logStream)
      } else {
        setLogStream({ available: false, lines: [], reason: String(data?.detail ?? `HTTP ${res.status}`) })
      }
    } catch (e) {
      setLogStream({ available: false, lines: [], reason: String(e) })
    } finally {
      setLogStreamLoading(false)
    }
  }

  async function handleLogAnalysis() {
    setLogAnalysisLoading(true)
    setLogAnalysisResult(null)
    setLogAnalysisError(null)
    try {
      const res = await fetch('/api/proxy/admin/logs/explain', { method: 'POST' })
      const data = await res.json() as Record<string, unknown>
      if (res.ok) {
        setLogAnalysisResult(String(data?.analysis ?? 'No analysis returned'))
      } else {
        setLogAnalysisError(String(data?.detail ?? `HTTP ${res.status}`))
      }
    } catch (e) {
      setLogAnalysisError(String(e))
    } finally {
      setLogAnalysisLoading(false)
    }
  }

  const TABS: { key: TabKey; label: string }[] = [
    { key: 'system', label: 'Σύστημα' },
    { key: 'hlr', label: 'HLR' },
    { key: 'scheduler', label: 'Scheduler' },
    { key: 'api', label: 'API' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Αρχεία Συστήματος</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            Auto-refresh (30s)
          </label>
          {autoRefresh && <span className="text-xs text-blue-500 animate-pulse">● Live</span>}
          <button
            onClick={refresh}
            disabled={loading}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Ανανέωση...' : 'Ανανέωση'}
          </button>
        </div>
      </div>

      {lastChecked && (
        <div className="text-xs text-gray-400 mb-4">
          Τελευταίος έλεγχος: {lastChecked.toLocaleTimeString('el-GR')}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
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

      {/* System Tab */}
      {tab === 'system' && (
        <div className="space-y-6">
          {/* Health Check */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-4">API Health Check</h2>
            <div className="flex items-center gap-4 mb-4">
              <StatusBadge status={health?.status} />
              {health?.version && (
                <span className="text-xs text-gray-500">v{String(health.version)}</span>
              )}
              {health?.uptime != null && (
                <span className="text-xs text-gray-500">Uptime: {String(Math.floor(health.uptime / 3600))}h</span>
              )}
            </div>
          </div>

          {/* Modules */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-4">Module Status</h2>
            {modules.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {modules.map((m) => (
                  <div key={m.name} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <span className="text-sm text-gray-700 truncate mr-2">{m.name}</span>
                    <StatusBadge status={m.status} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Κανένα module δεν βρέθηκε</div>
            )}
          </div>

          {/* Docker Containers */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Docker Containers ({String(containers.length)})</h2>
            </div>
            {containers.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Image</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">State</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {containers.map((c) => (
                      <tr key={c.name} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs font-mono truncate max-w-xs">{c.image}</td>
                        <td className="px-4 py-3 text-xs text-gray-600">{c.status}</td>
                        <td className="px-4 py-3"><StatusBadge status={c.state} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-6 text-sm text-gray-400">Container-Daten nicht verfügbar (Admin-Auth erforderlich)</div>
            )}
          </div>
        </div>
      )}

      {/* HLR Tab */}
      {tab === 'hlr' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-4">HLR Credits</h2>
            {hlr ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-1">Primary Credits</div>
                    <div className="text-2xl font-bold text-blue-600">{hlr.primary_credits != null ? String(hlr.primary_credits) : '—'}</div>
                    <div className="mt-1"><StatusBadge status={hlr.primary_status} /></div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-1">Fallback Credits</div>
                    <div className="text-2xl font-bold text-blue-600">{hlr.fallback_credits != null ? String(hlr.fallback_credits) : '—'}</div>
                    <div className="mt-1"><StatusBadge status={hlr.fallback_status} /></div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">Failover:</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    hlr.failover_active ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {hlr.failover_active ? 'Ενεργό' : 'Ανενεργό'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">Δεν υπάρχουν δεδομένα HLR</div>
            )}
          </div>
        </div>
      )}

      {/* Scheduler Tab */}
      {tab === 'scheduler' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Scheduler Jobs ({String(jobs.length)})</h2>
            </div>
            {jobs.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Letzter Run</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Fehler</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">Error Count</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {jobs.map((job, idx) => (
                      <tr key={job.name || idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{String(job.name)}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {job.last_run ? new Date(job.last_run).toLocaleString('el-GR') : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={job.status} />
                        </td>
                        <td className="px-4 py-3 text-xs text-red-600 max-w-xs truncate">
                          {job.error ? String(job.error) : '—'}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-gray-600">
                          {job.error_count != null ? String(job.error_count) : '0'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-sm text-gray-400">Keine Jobs gefunden</div>
            )}
          </div>
        </div>
      )}

      {/* API Tab */}
      {tab === 'api' && (
        <div className="space-y-6">
          {/* Ollama Status */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-4">Ollama Status</h2>
            {ollamaInfo ? (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">Status:</span>
                  <StatusBadge status={ollamaInfo.reachable ? 'ok' : 'error'} />
                </div>
                {ollamaInfo.active_model && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600">Active Model:</span>
                    <span className="text-sm font-mono text-gray-800">{ollamaInfo.active_model}</span>
                  </div>
                )}
                {ollamaInfo.models.length > 1 && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600">Alle Modelle:</span>
                    <span className="text-sm text-gray-500">{ollamaInfo.models.join(', ')}</span>
                  </div>
                )}
              </div>
            ) : scraperStatus ? (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">Status:</span>
                  <StatusBadge status={scraperStatus.ollama_status ?? scraperStatus.status ?? scraperStatus.ollama} />
                </div>
                {scraperStatus.ollama_model && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600">Model:</span>
                    <span className="text-sm font-mono text-gray-800">{String(scraperStatus.ollama_model)}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Ollama-Daten nicht verfügbar (Admin-Auth erforderlich)</div>
            )}
          </div>

          {/* Log Analysis — Ollama */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-2">Log-Analyse (Ollama)</h2>
            <div className="text-xs text-gray-400 mb-3">
              Analysiert die letzten API-Logs mit Ollama. Secrets werden vor der Analyse automatisch redaktiert.
            </div>
            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleLogAnalysis}
                disabled={logAnalysisLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {logAnalysisLoading ? 'Analyse...' : 'Log-Analyse starten'}
              </button>
            </div>
            {logAnalysisResult && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono">
                {logAnalysisResult}
              </div>
            )}
            {logAnalysisError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                {logAnalysisError}
              </div>
            )}
          </div>

          {/* Log Stream */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-2">API Container Logs</h2>
            <div className="text-xs text-gray-400 mb-3">
              Letzte 100 Zeilen aus ekklesia-api Container. Secrets werden automatisch redaktiert.
            </div>
            <button
              onClick={handleLogStream}
              disabled={logStreamLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 mb-4"
            >
              {logStreamLoading ? 'Laden...' : 'Logs laden'}
            </button>
            {logStream && !logStream.available && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-700">
                {logStream.reason || 'Docker proxy LOGS capability nicht aktiviert'}
              </div>
            )}
            {logStream && logStream.available && logStream.lines.length > 0 && (
              <div className="bg-gray-900 text-green-400 rounded-lg p-4 text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto">
                {logStream.lines.map((line, i) => (
                  <div key={i} className="whitespace-pre">{line}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

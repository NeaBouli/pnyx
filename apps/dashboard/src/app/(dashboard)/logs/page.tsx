'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface HealthData {
  status: string
  modules?: Record<string, unknown>
  timestamp?: string
}

export default function LogsPage() {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [loading, setLoading] = useState(false)

  const checkHealth = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/health`)
      const data = await r.json()
      setHealth(data)
      setLastChecked(new Date())
    } catch {
      setHealth({ status: 'error' })
      setLastChecked(new Date())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    checkHealth()
  }, [checkHealth])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [autoRefresh, checkHealth])

  const statusColor = health?.status === 'ok' ? 'text-green-600' : 'text-red-600'
  const statusBg = health?.status === 'ok' ? 'bg-green-100' : 'bg-red-100'
  const statusLabel = health?.status === 'ok' ? 'Online' : health?.status === 'error' ? 'Σφάλμα' : health?.status ?? '—'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Αρχεία Συστήματος</h1>

      {/* Phase 2 placeholder */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 mb-6">
        <div className="flex items-start gap-3">
          <span className="text-yellow-500 text-lg mt-0.5">⚠️</span>
          <div>
            <div className="font-semibold text-yellow-800">Φάση 2</div>
            <div className="text-sm text-yellow-700 mt-0.5">
              Τα αναλυτικά logs υλοποιούνται στη Φάση 2 (structured logging, φιλτράρισμα, εξαγωγή).
            </div>
          </div>
        </div>
      </div>

      {/* Health check panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">API Health Check</h2>
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
            <button
              onClick={checkHealth}
              disabled={loading}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading ? 'Έλεγχος...' : 'Ανανέωση'}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-4">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusBg} ${statusColor}`}>
            {statusLabel}
          </span>
          {lastChecked && (
            <span className="text-xs text-gray-400">
              Τελευταίος έλεγχος: {lastChecked.toLocaleTimeString('el-GR')}
            </span>
          )}
          {autoRefresh && (
            <span className="text-xs text-blue-500 animate-pulse">● Live</span>
          )}
        </div>

        {health?.modules && Object.keys(health.modules).length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2">Ενεργά Modules</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(health.modules).map(([name, status]) => (
                <span
                  key={name}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    status === 'ok' || status === true
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Placeholder log viewer */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Server Logs</h2>
          <span className="text-xs text-gray-400">Φάση 2</span>
        </div>
        <div className="bg-gray-950 p-6 font-mono text-xs text-gray-400 min-h-[200px] flex items-center justify-center">
          <div className="text-center">
            <div className="text-gray-600 mb-2">// Αναλυτικό log viewer — Φάση 2</div>
            <div className="text-gray-600">// Structured logs: FastAPI · Alembic · Scheduler</div>
          </div>
        </div>
      </div>
    </div>
  )
}

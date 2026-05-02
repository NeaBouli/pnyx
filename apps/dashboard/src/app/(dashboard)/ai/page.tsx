'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${API}${path}${sep}admin_key=${ADMIN_KEY}`
}

export default function AIPage() {
  const [claude, setClaude] = useState<Record<string, unknown> | null>(null)
  const [deepl, setDeepl] = useState<Record<string, unknown> | null>(null)
  const [scraper, setScraper] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      const [claudeRes, deeplRes, scraperRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
        fetch(`${API}/api/v1/admin/deepl/usage`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/status`).then(r => r.json()),
      ])
      const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
      setClaude(v(claudeRes) as Record<string, unknown> | null)
      setDeepl(v(deeplRes) as Record<string, unknown> | null)
      setScraper(v(scraperRes) as Record<string, unknown> | null)
      setLoading(false)
    }
    load()
  }, [])

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const [c, d, s] = await Promise.allSettled([
          fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
          fetch(`${API}/api/v1/admin/deepl/usage`).then(r => r.json()),
          fetch(`${API}/api/v1/scraper/status`).then(r => r.json()),
        ])
        const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
        setClaude(v(c) as Record<string, unknown> | null)
        setDeepl(v(d) as Record<string, unknown> | null)
        setScraper(v(s) as Record<string, unknown> | null)
      } catch { /* ignore */ }
    }, 60000)
    return () => clearInterval(interval)
  }, [])

  async function handleAction(name: string, fn: () => Promise<unknown>) {
    if (!confirm(`Aktion "${name}" ausführen?`)) return
    setActionLoading(name)
    setActionResult(null)
    try {
      const result = await fn()
      setActionResult(`${name}: OK`)
      if (name === 'ollama-check') {
        setScraper(result as Record<string, unknown> | null)
      }
    } catch {
      setActionResult(`${name}: Σφάλμα`)
    } finally {
      setActionLoading(null)
      setTimeout(() => setActionResult(null), 5000)
    }
  }

  const ollamaModel = (scraper?.ollama_model ?? claude?.ollama_model ?? scraper?.model) as string | null
  const ollamaStatus = (scraper?.ollama_status ?? scraper?.status ?? claude?.ollama_status) as string | null
  const ollamaOk = ollamaStatus === 'ok' || ollamaStatus === 'available' || ollamaStatus === 'healthy'

  const claudeTokensToday = claude?.tokens_today as number | null
  const claudeTokensMonth = claude?.tokens_month as number | null
  const claudeIsActive = claude?.is_active as boolean | null

  const deeplCount = deepl?.character_count as number | null
  const deeplLimit = (deepl?.character_limit as number) ?? 500000
  const deeplPct = deeplCount != null ? Math.round((deeplCount / deeplLimit) * 100) : null
  const deeplReset = deepl?.reset_date as string | null

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{String('AI & Εργαλεία')}</h1>

      {actionResult && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
          {String(actionResult)}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-gray-500">{String('Φόρτωση...')}</div>
      ) : (
        <div className="space-y-6">
          {/* Ollama */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">{String('Ollama (Self-hosted LLM)')}</h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                ollamaOk ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}>
                {ollamaOk ? String('Online') : String(ollamaStatus ?? 'Offline')}
              </span>
            </div>
            <div className="p-5 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{String('Μοντέλο')}</span>
                <span className="font-medium text-gray-800">{String(ollamaModel ?? 'llama3.2')}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{String('Κατάσταση')}</span>
                <span className={`font-medium ${ollamaOk ? 'text-green-600' : 'text-red-600'}`}>
                  {ollamaOk ? String('Λειτουργικό') : String('Μη Διαθέσιμο')}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{String('Χρήση')}</span>
                <span className="text-gray-500">{String('Summaries, Compass, RAG Agent')}</span>
              </div>
            </div>
          </div>

          {/* Claude Haiku */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">{String('Claude Haiku (Anthropic)')}</h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                claudeIsActive ? 'bg-green-100 text-green-700' : claudeIsActive === false ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {claudeIsActive ? String('Ενεργό') : claudeIsActive === false ? String('Ανενεργό') : String('Άγνωστο')}
              </span>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">{String('Tokens Σήμερα')}</div>
                  <div className="text-xl font-bold text-gray-800">
                    {claudeTokensToday != null ? String(claudeTokensToday.toLocaleString('el-GR')) : String('—')}
                  </div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">{String('Tokens Μήνα')}</div>
                  <div className="text-xl font-bold text-gray-800">
                    {claudeTokensMonth != null ? String(claudeTokensMonth.toLocaleString('el-GR')) : String('—')}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* DeepL */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">{String('DeepL Translation')}</h2>
              {deeplPct != null && (
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  deeplPct > 80 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                }`}>
                  {String(deeplPct)}{String('%')}
                </span>
              )}
            </div>
            <div className="p-5 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{String('Χαρακτήρες')}</span>
                <span className="font-medium text-gray-800">
                  {deeplCount != null
                    ? `${String(deeplCount.toLocaleString('el-GR'))} / ${String(deeplLimit.toLocaleString('el-GR'))}`
                    : String('—')}
                </span>
              </div>
              {deeplPct != null && (
                <div className="w-full bg-gray-100 rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full transition-all ${deeplPct > 80 ? 'bg-red-500' : 'bg-green-500'}`}
                    style={{ width: `${Math.min(100, deeplPct)}%` }}
                  />
                </div>
              )}
              {deeplReset && (
                <div className="text-xs text-gray-400">
                  {String('Reset:')} {String(new Date(deeplReset).toLocaleDateString('el-GR'))}
                </div>
              )}
              <div className="text-xs text-gray-400">{String('Χρήση: Compass-Fragen Ελληνικά → Αγγλικά')}</div>
            </div>
          </div>

          {/* RAG Agent */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">{String('RAG Agent')}</h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                {String('Hybrid')}
              </span>
            </div>
            <div className="p-5 space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">{String('Primary')}</span>
                <span className="text-gray-800">{String('Ollama')} ({String(ollamaModel ?? 'llama3.2')})</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">{String('Fallback')}</span>
                <span className="text-gray-800">{String('Claude Haiku')}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">{String('Rate Limit')}</span>
                <span className="text-gray-500">{String('5 αιτήματα/λεπτό')}</span>
              </div>
            </div>
          </div>

          {/* One-Click Repair Buttons */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">{String('Ενέργειες Επισκευής')}</h2>
            </div>
            <div className="p-5 flex flex-wrap gap-3">
              <button
                onClick={() => handleAction('ollama-check', () =>
                  fetch(`${API}/api/v1/scraper/status`).then(r => r.json())
                )}
                disabled={actionLoading === 'ollama-check'}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'ollama-check' ? String('Έλεγχος...') : String('Ollama πρωτεύον')}
              </button>
              <button
                onClick={() => handleAction('heal-scraper', () =>
                  fetch(adminURL('/api/v1/admin/scraper/heal-status'), { method: 'POST' }).then(r => r.json())
                )}
                disabled={actionLoading === 'heal-scraper'}
                className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-lg text-sm font-medium hover:bg-yellow-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'heal-scraper' ? String('Επιδιόρθωση...') : String('Scraper heilen')}
              </button>
              <button
                onClick={() => handleAction('compass-gen', () =>
                  fetch(adminURL('/api/v1/admin/compass/generate-questions'), { method: 'POST' }).then(r => r.json())
                )}
                disabled={actionLoading === 'compass-gen'}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'compass-gen' ? String('Δημιουργία...') : String('Compass-Fragen generieren')}
              </button>
            </div>
          </div>

          {/* Compass Generator */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">{String('Compass-Fragen Generator')}</h2>
            </div>
            <div className="p-5 text-sm text-gray-500">
              <div className="mb-2">{String('Ollama αναλύει τρέχοντα Bills → DeepL μεταφράζει → Νέες θέσεις για VAA')}</div>
              <div className="text-xs text-gray-400">{String('Ενεργοποίηση: Ρυθμίσεις → Compass Διαχείριση')}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

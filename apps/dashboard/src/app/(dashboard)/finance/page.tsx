'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

export default function FinancePage() {
  const [hlr, setHlr] = useState<Record<string, unknown> | null>(null)
  const [arweave, setArweave] = useState<Record<string, unknown> | null>(null)
  const [payments, setPayments] = useState<Record<string, unknown> | null>(null)
  const [claude, setClaude] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    const [hlrRes, arRes, payRes, claudeRes] = await Promise.allSettled([
      fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
      fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
      fetch(`${API}/api/v1/payments/status`).then(r => r.json()),
      fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
    ])
    const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
    setHlr(v(hlrRes) as Record<string, unknown> | null)
    setArweave(v(arRes) as Record<string, unknown> | null)
    setPayments(v(payRes) as Record<string, unknown> | null)
    setClaude(v(claudeRes) as Record<string, unknown> | null)
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    const interval = setInterval(loadData, 60000)
    return () => clearInterval(interval)
  }, [loadData])

  const hlrPrimary = hlr?.primary as Record<string, unknown> | null
  const hlrFallback = hlr?.fallback as Record<string, unknown> | null
  const primaryCredits = hlrPrimary?.remaining as number | null
  const primaryTotal = (hlrPrimary?.total as number) ?? 1000
  const primaryPct = primaryCredits != null ? Math.round((primaryCredits / primaryTotal) * 100) : null
  const primaryProvider = hlrPrimary?.provider as string | null
  const primaryCost = hlrPrimary?.cost_per_query as number | null

  const fallbackCredits = hlrFallback?.remaining as number | null
  const fallbackProvider = hlrFallback?.provider as string | null
  const failoverActive = hlr?.failover_active === true

  const claudeTokensToday = claude?.tokens_today as number | null
  const claudeTokensMonth = claude?.tokens_month as number | null
  const claudeIsActive = claude?.is_active as boolean | null

  // Estimated runtime removed — no avg_queries_per_day in API

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Οικονομικά</h1>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Ανανέωση...' : 'Ανανέωση'}
        </button>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
      ) : (
        <div className="space-y-6">
          {/* HLR Credits */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-800">HLR Credits</h2>
              {failoverActive && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                  Failover ενεργό
                </span>
              )}
            </div>
            <div className="space-y-4">
              {/* Primary */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">
                    {String('Κύρια')} ({String(primaryProvider ?? 'primary')})
                  </span>
                  <span className="font-medium text-gray-800">
                    {String(primaryCredits ?? '—')} / {String(primaryTotal)}
                  </span>
                </div>
                {primaryPct != null && (
                  <div className="w-full bg-gray-100 rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full transition-all ${primaryPct > 20 ? 'bg-blue-500' : 'bg-red-500'}`}
                      style={{ width: `${primaryPct}%` }}
                    />
                  </div>
                )}
                {primaryCost != null && (
                  <div className="text-xs text-gray-400 mt-1">
                    {String('Κόστος/Query:')} {String(primaryCost.toFixed(4))} EUR
                  </div>
                )}
              </div>
              {/* Fallback */}
              {hlrFallback && (
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">
                      {String('Εφεδρική')} ({String(fallbackProvider ?? 'fallback')})
                    </span>
                    <span className="font-medium text-gray-800">
                      {String(fallbackCredits ?? '—')}
                    </span>
                  </div>
                </div>
              )}
              {/* Estimated runtime — Phase 2 */}
            </div>
          </div>

          {/* Arweave */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Arweave Wallet Balance</h2>
            {arweave ? (
              <div>
                <div className="text-3xl font-bold text-blue-600">
                  {arweave.balance_ar != null ? `${String((arweave.balance_ar as number).toFixed(4))} AR` : String('—')}
                </div>
                {arweave.wallet_address != null && (
                  <div className="text-xs text-gray-400 mt-1">
                    Wallet: {String((arweave.wallet_address as string).slice(0, 16))}...
                  </div>
                )}
                {arweave.tx_count != null && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    Transactions: {String(arweave.tx_count)}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-400">{String('Μη διαθέσιμο')}</div>
            )}
          </div>

          {/* Payment Status */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Κατάσταση Πληρωμών</h2>
            {payments ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">{String('Διακομιστής')}</div>
                  <div className="text-xl font-bold text-gray-800">
                    {(payments.server as Record<string, unknown>)?.balance != null
                      ? `${String(((payments.server as Record<string, unknown>).balance as number).toFixed(2))} EUR`
                      : String('—')}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {String('Μηνιαίο:')} {(payments.server as Record<string, unknown>)?.cost_monthly != null
                      ? `${String(((payments.server as Record<string, unknown>).cost_monthly as number).toFixed(2))} EUR`
                      : String('—')}
                  </div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-1">{String('Domain')}</div>
                  <div className="text-xl font-bold text-gray-800">
                    {(payments.domain as Record<string, unknown>)?.balance != null
                      ? `${String(((payments.domain as Record<string, unknown>).balance as number).toFixed(2))} EUR`
                      : String('—')}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {String('Λήξη:')} {(payments.domain as Record<string, unknown>)?.expires
                      ? String(new Date((payments.domain as Record<string, unknown>).expires as string).toLocaleDateString('el-GR'))
                      : String('—')}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">{String('Δεν υπάρχουν δεδομένα πληρωμών')}</div>
            )}
          </div>

          {/* Claude AI Budget */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Claude AI Budget</h2>
            {claude ? (
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
            ) : (
              <div className="text-sm text-gray-400">{String('Μη διαθέσιμο')}</div>
            )}
          </div>

          {/* Donations */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Δωρεές & Υποστήριξη</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">PayPal</span>
                <a
                  href="https://www.paypal.com/donate/?hosted_button_id=ekklesia"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  {String('Donate via PayPal')}
                </a>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Bitcoin (BTC)</span>
                <span className="text-xs font-mono text-gray-500 select-all">
                  {String('bc1qekklesia...placeholder')}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-600">Litecoin (LTC)</span>
                <span className="text-xs font-mono text-gray-500 select-all">
                  {String('ltc1qekklesia...placeholder')}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

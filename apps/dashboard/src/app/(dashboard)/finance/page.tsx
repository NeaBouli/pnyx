'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

export default function FinancePage() {
  const [hlr, setHlr] = useState<Record<string, unknown> | null>(null)
  const [arweave, setArweave] = useState<Record<string, unknown> | null>(null)
  const [payments, setPayments] = useState<Record<string, unknown> | null>(null)
  const [claude, setClaude] = useState<Record<string, unknown> | null>(null)
  const [paymentLogs, setPaymentLogs] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''
    const [hlrRes, arRes, payRes, claudeRes, logsRes] = await Promise.allSettled([
      fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
      fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
      fetch(`${API}/api/v1/payments/status`).then(r => r.json()),
      fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
      ADMIN_KEY ? fetch(`${API}/api/v1/payments/admin/logs?admin_key=${ADMIN_KEY}`).then(r => r.json()) : Promise.resolve(null),
    ])
    const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
    setHlr(v(hlrRes) as Record<string, unknown> | null)
    setArweave(v(arRes) as Record<string, unknown> | null)
    setPayments(v(payRes) as Record<string, unknown> | null)
    setClaude(v(claudeRes) as Record<string, unknown> | null)
    setPaymentLogs(v(logsRes) as Record<string, unknown> | null)
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
          {/* HLR Credits + Failover Control */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-800">HLR Επαλήθευση Κινητού</h2>
              <div className="flex items-center gap-2">
                {failoverActive ? (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                    Failover ενεργό — {String(hlr?.failover_reason ?? '')}
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                    Κανονική λειτουργία
                  </span>
                )}
              </div>
            </div>

            {/* Auto-Failover Status Panel */}
            <div className={`rounded-lg p-4 mb-4 border ${
              failoverActive ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'
            }`}>
              <div className="text-sm font-medium mb-2">
                {failoverActive ? '⚠️ Auto-Failover Ενεργοποιημένο' : '✅ Αυτόματη Ανίχνευση Σφαλμάτων'}
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${!failoverActive ? 'bg-green-500' : 'bg-yellow-500'}`} />
                  <span className="text-gray-600">Trigger A: Timeout/Error</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${(primaryCredits ?? 999) > 50 ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-gray-600">Trigger B: Credits {'<'} 50</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${!failoverActive ? 'bg-green-500' : 'bg-yellow-500'}`} />
                  <span className="text-gray-600">Trigger C: Auth Error</span>
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-2">
                Εφεδρική πηγή: {hlrFallback?.enabled === true ? '✅ Ενεργοποιημένη' : '❌ Απενεργοποιημένη'}
                {' | '}
                Διαμορφωμένη: {hlrFallback?.configured === true ? '✅' : '❌'}
              </div>
            </div>

            {/* Provider Switch */}
            <div className="flex items-center justify-between mb-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div>
                <div className="text-sm font-medium text-gray-700">Ενεργός Provider</div>
                <div className="text-xs text-gray-400 mt-0.5">Εναλλαγή μεταξύ κύριας και εφεδρικής πηγής</div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium ${!failoverActive ? 'text-blue-600' : 'text-gray-400'}`}>
                  {String(primaryProvider ?? 'hlrlookup.com')}
                </span>
                <div className={`relative w-12 h-6 rounded-full cursor-not-allowed ${
                  failoverActive ? 'bg-yellow-400' : 'bg-blue-600'
                }`} title="Αλλαγή μέσω .env στον server (HLRLOOKUPS_PROVIDER)">
                  <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${
                    failoverActive ? 'left-6' : 'left-0.5'
                  }`} />
                </div>
                <span className={`text-xs font-medium ${failoverActive ? 'text-yellow-600' : 'text-gray-400'}`}>
                  {String(fallbackProvider ?? 'hlr-lookups.com')}
                </span>
              </div>
            </div>
            <div className="text-xs text-gray-400 mb-4 text-center">
              Χειροκίνητη εναλλαγή: αλλάξτε <code className="bg-gray-100 px-1 rounded">HLRLOOKUPS_PROVIDER</code> στο .env του server
            </div>

            {/* Credits Detail */}
            <div className="space-y-4">
              {/* Primary */}
              <div className={`p-3 rounded-lg border ${!failoverActive ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'}`}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700 font-medium">
                    {String('Κύρια πηγή')} — {String(primaryProvider ?? '')}
                    {!failoverActive && <span className="ml-2 text-xs text-blue-600">(ενεργή)</span>}
                  </span>
                  <span className="font-semibold text-gray-800">
                    {String(primaryCredits ?? '—')} / {String(hlrPrimary?.initial ?? primaryTotal)}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all ${(primaryPct ?? 0) > 20 ? 'bg-blue-500' : (primaryPct ?? 0) > 5 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(primaryPct ?? 0, 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>Κόστος: {primaryCost != null ? `${String(primaryCost.toFixed(4))} EUR/query` : '—'}</span>
                  <span>{String(primaryPct ?? 0)}% διαθέσιμο</span>
                </div>
              </div>

              {/* Fallback */}
              {hlrFallback && (
                <div className={`p-3 rounded-lg border ${failoverActive ? 'border-yellow-200 bg-yellow-50' : 'border-gray-200 bg-gray-50'}`}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 font-medium">
                      {String('Εφεδρική πηγή')} — {String(fallbackProvider ?? '')}
                      {failoverActive && <span className="ml-2 text-xs text-yellow-600">(ενεργή λόγω failover)</span>}
                    </span>
                    <span className="font-semibold text-gray-800">
                      {String(fallbackCredits ?? '—')} / {String(hlrFallback?.initial ?? '1000')}
                    </span>
                  </div>
                  {(() => {
                    const fbTotal = (hlrFallback?.initial as number) ?? 1000
                    const fbPct = fallbackCredits != null ? Math.round((fallbackCredits / fbTotal) * 100) : 0
                    return (
                      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                        <div
                          className={`h-2.5 rounded-full transition-all ${fbPct > 20 ? 'bg-green-500' : fbPct > 5 ? 'bg-yellow-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(fbPct, 100)}%` }}
                        />
                      </div>
                    )
                  })()}
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>Κόστος: {hlrFallback?.cost_per_query_eur != null ? `${String((hlrFallback.cost_per_query_eur as number).toFixed(4))} EUR/query` : '—'}</span>
                    <span>Πληρωμή: BTC / LTC</span>
                  </div>
                </div>
              )}
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

          {/* Claude AI Προϋπολογισμός */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Claude AI Προϋπολογισμός</h2>
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
                  href="https://www.paypal.com/paypalme/VendettaLabs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  {String('Δωρεά μέσω PayPal →')}
                </a>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Bitcoin (BTC)</span>
                <span className="text-xs font-mono text-gray-500 select-all">
                  bc1q83370mce8qfkyyepspg6xf42f577s47rtl3mhx
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Litecoin (LTC)</span>
                <span className="text-xs font-mono text-gray-500 select-all">
                  ltc1qmr467kl8w0e8axplq5uyrpws3mc4sclpu4ds8w
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-2 p-2 bg-gray-50 rounded">
                PayPal δωρεές καταμετρούνται χειροκίνητα. Αυτόματη καταμέτρηση μέσω PayPal IPN — Φάση 2.
              </div>
            </div>
          </div>

          {/* PayPal IPN Placeholder */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-3">Αυτόματη Καταμέτρηση Δωρεών</h2>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="text-sm font-medium text-yellow-800">PayPal IPN Webhook — Φάση 2</div>
              <div className="text-xs text-yellow-600 mt-1">
                Όταν ρυθμιστεί: αυτόματη καταμέτρηση δωρεών μέσω PayPal
              </div>
              <div className="text-xs text-gray-500 mt-2">
                Webhook URL: https://api.ekklesia.gr/api/v1/payments/webhook/paypal
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Webhook ενεργό — αυτόματη καταμέτρηση PayPal IPN
              </div>
            </div>
          </div>

          {/* Payment Logs */}
          {paymentLogs && (paymentLogs.payments as Record<string, unknown>[])?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-800">Ιστορικό Πληρωμών</h2>
                <span className="text-xs text-gray-400">
                  {String(paymentLogs.total_count ?? '0')} συνολικά
                </span>
              </div>
              {(paymentLogs.paypal as Record<string, unknown>)?.count != null && Number((paymentLogs.paypal as Record<string, unknown>).count) > 0 && (
                <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                  PayPal: {String((paymentLogs.paypal as Record<string, unknown>).total_eur ?? '0')} EUR ({String((paymentLogs.paypal as Record<string, unknown>).count)} δωρεές)
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Ημερομηνία</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-500">Ποσό</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Μέθοδος</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Κατανομή</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {(paymentLogs.payments as Record<string, unknown>[]).slice(0, 10).map((p, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-600">{String(p.date ?? '—')}</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-800">{String(p.amount ?? '0')} {String(p.currency ?? 'EUR')}</td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            p.method === 'paypal' ? 'bg-blue-100 text-blue-700' :
                            p.method === 'stripe' ? 'bg-purple-100 text-purple-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>{String(p.method ?? '—')}</span>
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {p.allocation ? `Server: ${String((p.allocation as Record<string, unknown>).server ?? '0')}€` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

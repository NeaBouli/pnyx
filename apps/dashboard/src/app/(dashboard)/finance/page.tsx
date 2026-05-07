'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type Tab = 'overview' | 'wallets' | 'income' | 'expenses' | 'report'

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => undefined)
}

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}

function fmtInt(n: number | null | undefined): string {
  if (n == null) return '—'
  return String(Math.round(n))
}

export default function FinancePage() {
  const [tab, setTab] = useState<Tab>('overview')
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null)
  const [hlr, setHlr] = useState<Record<string, unknown> | null>(null)
  const [arweave, setArweave] = useState<Record<string, unknown> | null>(null)
  const [payments, setPayments] = useState<Record<string, unknown> | null>(null)
  const [claude, setClaude] = useState<Record<string, unknown> | null>(null)
  const [paymentLogs, setPaymentLogs] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    const [hlrRes, arRes, payRes, claudeRes, logsRes, ovRes] = await Promise.allSettled([
      fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
      fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
      fetch(`${API}/api/v1/payments/status`).then(r => r.json()),
      fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
      fetch('/api/proxy/payments/admin/logs').then(r => r.json()),
      fetch('/api/proxy/payments/admin/finance/overview').then(r => r.json()),
    ])
    const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
    setHlr(v(hlrRes) as Record<string, unknown> | null)
    setArweave(v(arRes) as Record<string, unknown> | null)
    setPayments(v(payRes) as Record<string, unknown> | null)
    setClaude(v(claudeRes) as Record<string, unknown> | null)
    setPaymentLogs(v(logsRes) as Record<string, unknown> | null)
    setOverview(v(ovRes) as Record<string, unknown> | null)
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => {
    const interval = setInterval(loadData, 60000)
    return () => clearInterval(interval)
  }, [loadData])

  // ── Derived values ──────────────────────────────────────────────────────────
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

  const ovIncome = overview?.einnahmen as Record<string, unknown> | null
  const ovExpenses = overview?.ausgaben as Record<string, unknown> | null
  const ovWallets = overview?.wallets as Record<string, unknown> | null
  const ovBtc = ovWallets?.btc as Record<string, unknown> | null
  const ovLtc = ovWallets?.ltc as Record<string, unknown> | null
  const ovAr = ovWallets?.arweave as Record<string, unknown> | null
  const ovHlrPrimary = ovWallets?.hlr_primary as Record<string, unknown> | null
  const ovHlrFallback = ovWallets?.hlr_fallback as Record<string, unknown> | null

  const TABS: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Επισκόπηση' },
    { key: 'wallets', label: 'Πορτοφόλια' },
    { key: 'income', label: 'Εισπράξεις' },
    { key: 'expenses', label: 'Έξοδα' },
    { key: 'report', label: 'Αναφορά' },
  ]

  // ── Report text ─────────────────────────────────────────────────────────────
  function buildReport(): string {
    const now = new Date().toLocaleDateString('el-GR')
    const saldo = overview?.saldo != null ? fmt(overview.saldo as number) : '—'
    const runway = overview?.runway_monate != null ? String(overview.runway_monate) : '—'
    const totalIn = ovIncome?.gesamt != null ? fmt(ovIncome.gesamt as number) : '—'
    const totalOut = ovExpenses?.server_gesamt != null ? fmt(ovExpenses.server_gesamt as number) : '—'
    const serverMo = ovExpenses?.server_monatlich != null ? fmt(ovExpenses.server_monatlich as number) : '—'
    return `ΜΗΝΙΑΙΑ ΑΝΑΦΟΡΑ ΔΙΑΦΑΝΕΙΑΣ — ekklesia.gr
Ημερομηνία: ${now}

== ΕΙΣΠΡΑΞΕΙΣ ==
Σύνολο εισπράξεων: ${totalIn} EUR
  - PayPal: ${ovIncome?.paypal_gesamt != null ? fmt(ovIncome.paypal_gesamt as number) : '—'} EUR (${ovIncome?.paypal_count ?? 0} δωρεές)
  - Server fund: ${ovIncome?.server_received != null ? fmt(ovIncome.server_received as number) : '—'} EUR
  - Domain fund: ${ovIncome?.domain_received != null ? fmt(ovIncome.domain_received as number) : '—'} EUR
  - BTC αξία: ${ovIncome?.btc_eur != null ? fmt(ovIncome.btc_eur as number) : '—'} EUR
  - LTC αξία: ${ovIncome?.ltc_eur != null ? fmt(ovIncome.ltc_eur as number) : '—'} EUR

== ΕΞΟΔΑ ==
Κόστος server (συνολικό): ${totalOut} EUR
Μηνιαίο κόστος: ${serverMo} EUR

== ΥΠΟΛΟΙΠΟ & RUNWAY ==
Σαλδο: ${saldo} EUR
Runway: ${runway} μήνες

== WALLETS ==
BTC: ${ovBtc?.balance_btc != null ? fmt(ovBtc.balance_btc as number, 8) : '—'} BTC (${ovBtc?.balance_eur != null ? fmt(ovBtc.balance_eur as number) : '—'} EUR)
LTC: ${ovLtc?.balance_ltc != null ? fmt(ovLtc.balance_ltc as number, 8) : '—'} LTC (${ovLtc?.balance_eur != null ? fmt(ovLtc.balance_eur as number) : '—'} EUR)
Arweave: ${ovAr?.balance_ar != null ? fmt(ovAr.balance_ar as number, 4) : '—'} AR
HLR credits (κύρια): ${ovHlrPrimary?.remaining != null ? String(ovHlrPrimary.remaining) : '—'}
HLR credits (εφεδρική): ${ovHlrFallback?.remaining != null ? String(ovHlrFallback.remaining) : '—'}

Αναφορά δημιουργήθηκε αυτόματα από το dashboard.ekklesia.gr
`
  }

  function exportCSV() {
    if (!paymentLogs) return
    const logs = (paymentLogs.payments as Record<string, unknown>[]) ?? []
    const rows = [
      ['Ημερομηνία', 'Ποσό', 'Νόμισμα', 'Μέθοδος', 'Server', 'Domain', 'Reserve'],
      ...logs.map(p => {
        const alloc = p.allocation as Record<string, unknown> | null
        return [
          String(p.date ?? ''),
          String(p.amount ?? ''),
          String(p.currency ?? 'EUR'),
          String(p.method ?? ''),
          String(alloc?.server ?? '0'),
          String(alloc?.domain ?? '0'),
          String(alloc?.reserve ?? '0'),
        ]
      }),
    ]
    const csv = rows.map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ekklesia-finance-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Header */}
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

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === t.key
                ? 'bg-white border border-b-white border-gray-200 text-blue-600 -mb-px'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
      ) : (
        <div className="space-y-6">

          {/* ══ TAB 1: ΕΠΙΣΚΟΠΗΣΗ ══ */}
          {tab === 'overview' && (
            <>
              {/* Saldo + Runway */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
                  <div className="text-xs text-blue-600 font-medium mb-1">Σαλδο</div>
                  <div className="text-3xl font-bold text-blue-700">
                    {overview ? `${fmt(overview.saldo as number)} €` : '—'}
                  </div>
                </div>
                <div className="bg-green-50 border border-green-200 rounded-xl p-5">
                  <div className="text-xs text-green-600 font-medium mb-1">Runway</div>
                  <div className="text-3xl font-bold text-green-700">
                    {overview ? `${String(overview.runway_monate ?? 0)} μήνες` : '—'}
                  </div>
                  <div className="text-xs text-green-500 mt-1">{String(overview?.server_gedeckt_bis ?? '')}</div>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-5">
                  <div className="text-xs text-purple-600 font-medium mb-1">Τελευταία ενημέρωση</div>
                  <div className="text-sm font-semibold text-purple-700 break-all">
                    {overview?.letztes_update
                      ? String(new Date(overview.letztes_update as string).toLocaleString('el-GR'))
                      : '—'}
                  </div>
                </div>
              </div>

              {/* Income vs Expenses columns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {/* Εισπράξεις */}
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <h2 className="text-base font-semibold text-gray-800 mb-4">Εισπράξεις</h2>
                  {ovIncome ? (
                    <div className="space-y-2">
                      {[
                        ['PayPal', `${fmt(ovIncome.paypal_gesamt as number)} €`],
                        ['Server fund', `${fmt(ovIncome.server_received as number)} €`],
                        ['Domain fund', `${fmt(ovIncome.domain_received as number)} €`],
                        ['BTC (EUR)', `${fmt(ovIncome.btc_eur as number)} €`],
                        ['LTC (EUR)', `${fmt(ovIncome.ltc_eur as number)} €`],
                        ['Reserve', `${fmt(ovIncome.reserve as number)} €`],
                      ].map(([label, value]) => (
                        <div key={label} className="flex justify-between text-sm">
                          <span className="text-gray-500">{label}</span>
                          <span className="font-mono text-gray-800">{value}</span>
                        </div>
                      ))}
                      <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between text-sm font-bold">
                        <span className="text-gray-700">Σύνολο</span>
                        <span className="text-green-600">{fmt(ovIncome.gesamt as number)} €</span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-400">Χρειάζεται admin key</div>
                  )}
                </div>

                {/* Έξοδα */}
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <h2 className="text-base font-semibold text-gray-800 mb-4">Έξοδα</h2>
                  {ovExpenses ? (
                    <div className="space-y-2">
                      {[
                        ['Server (μηνιαίο)', `${fmt(ovExpenses.server_monatlich as number)} €`],
                        ['Server (συνολικό)', `${fmt(ovExpenses.server_gesamt as number)} €`],
                        ['HLR credits χρησιμοποιήθηκαν', fmtInt(ovExpenses.hlr_verbraucht_credits as number)],
                        ['Σύνολο/μήνα', `${fmt(ovExpenses.gesamt_monatlich as number)} €`],
                      ].map(([label, value]) => (
                        <div key={label} className="flex justify-between text-sm">
                          <span className="text-gray-500">{label}</span>
                          <span className="font-mono text-gray-800">{value}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-gray-400">Χρειάζεται admin key</div>
                  )}
                </div>
              </div>

              {/* Payment Status (public) */}
              {payments && (
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <h2 className="text-base font-semibold text-gray-800 mb-4">Κατάσταση Πληρωμών (δημόσια)</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="text-xs text-gray-500 mb-1">Διακομιστής</div>
                      <div className="text-xl font-bold text-gray-800">
                        {(payments.server as Record<string, unknown>)?.balance != null
                          ? `${fmt((payments.server as Record<string, unknown>).balance as number)} EUR`
                          : '—'}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        Μηνιαίο: {(payments.server as Record<string, unknown>)?.cost_monthly != null
                          ? `${fmt((payments.server as Record<string, unknown>).cost_monthly as number)} EUR`
                          : '—'}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="text-xs text-gray-500 mb-1">Domain</div>
                      <div className="text-xl font-bold text-gray-800">
                        {(payments.domain as Record<string, unknown>)?.balance != null
                          ? `${fmt((payments.domain as Record<string, unknown>).balance as number)} EUR`
                          : '—'}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        Λήξη: {(payments.domain as Record<string, unknown>)?.expires
                          ? String(new Date((payments.domain as Record<string, unknown>).expires as string).toLocaleDateString('el-GR'))
                          : '—'}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ══ TAB 2: ΠΟΡΤΟΦΟΛΙΑ ══ */}
          {tab === 'wallets' && (
            <>
              {/* BTC */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-lg font-bold text-orange-500">₿</span>
                  <h2 className="text-base font-semibold text-gray-800">Bitcoin (BTC)</h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-3">
                  <div className="bg-orange-50 rounded-lg p-3">
                    <div className="text-xs text-orange-600 mb-1">Balance</div>
                    <div className="font-bold text-gray-800">
                      {ovBtc?.balance_btc != null ? `${fmt(ovBtc.balance_btc as number, 8)} BTC` : '—'}
                    </div>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3">
                    <div className="text-xs text-orange-600 mb-1">EUR Αξία</div>
                    <div className="font-bold text-gray-800">
                      {ovBtc?.balance_eur != null ? `${fmt(ovBtc.balance_eur as number)} €` : '—'}
                    </div>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3">
                    <div className="text-xs text-orange-600 mb-1">Transactions</div>
                    <div className="font-bold text-gray-800">
                      {ovBtc?.tx_count != null ? String(ovBtc.tx_count) : '—'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500 break-all flex-1">
                    {String(ovBtc?.address ?? 'bc1q83370mce8qfkyyepspg6xf42f577s47rtl3mhx')}
                  </span>
                  <button
                    onClick={() => copyToClipboard(String(ovBtc?.address ?? 'bc1q83370mce8qfkyyepspg6xf42f577s47rtl3mhx'))}
                    className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                    title="Αντιγραφή"
                  >
                    Αντιγραφή
                  </button>
                </div>
                {ovBtc?.btc_eur != null && (
                  <div className="text-xs text-gray-400 mt-1">
                    Τιμή BTC: {fmt(ovBtc.btc_eur as number, 0)} €
                  </div>
                )}
                {ovBtc?.error != null && (
                  <div className="text-xs text-red-500 mt-1">{'Σφάλμα: ' + String(ovBtc.error)}</div>
                )}
              </div>

              {/* LTC */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-lg font-bold text-gray-500">Ł</span>
                  <h2 className="text-base font-semibold text-gray-800">Litecoin (LTC)</h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-3">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-600 mb-1">Balance</div>
                    <div className="font-bold text-gray-800">
                      {ovLtc?.balance_ltc != null ? `${fmt(ovLtc.balance_ltc as number, 8)} LTC` : '—'}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-600 mb-1">EUR Αξία</div>
                    <div className="font-bold text-gray-800">
                      {ovLtc?.balance_eur != null ? `${fmt(ovLtc.balance_eur as number)} €` : '—'}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-600 mb-1">Transactions</div>
                    <div className="font-bold text-gray-800">
                      {ovLtc?.tx_count != null ? String(ovLtc.tx_count) : '—'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500 break-all flex-1">
                    {String(ovLtc?.address ?? 'ltc1qmr467kl8w0e8axplq5uyrpws3mc4sclpu4ds8w')}
                  </span>
                  <button
                    onClick={() => copyToClipboard(String(ovLtc?.address ?? 'ltc1qmr467kl8w0e8axplq5uyrpws3mc4sclpu4ds8w'))}
                    className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                    title="Αντιγραφή"
                  >
                    Αντιγραφή
                  </button>
                </div>
                {ovLtc?.error != null && (
                  <div className="text-xs text-red-500 mt-1">{'Σφάλμα: ' + String(ovLtc.error)}</div>
                )}
              </div>

              {/* Arweave */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-4">Arweave Wallet</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="text-xs text-blue-600 mb-1">Balance</div>
                    <div className="font-bold text-gray-800">
                      {(() => {
                        const bal = ovAr?.balance_ar ?? arweave?.balance_ar
                        return bal != null ? `${fmt(bal as number, 4)} AR` : '—'
                      })()}
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="text-xs text-blue-600 mb-1">Transactions</div>
                    <div className="font-bold text-gray-800">
                      {arweave?.tx_count != null ? String(arweave.tx_count) : '—'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500 break-all flex-1">
                    {String(ovAr?.address ?? arweave?.wallet_address ?? '2hkK3Bcr6garERqyBCLCiJ-d8zZzM5ZWe3_AzGdhBTs')}
                  </span>
                  <button
                    onClick={() => copyToClipboard(String(ovAr?.address ?? arweave?.wallet_address ?? '2hkK3Bcr6garERqyBCLCiJ-d8zZzM5ZWe3_AzGdhBTs'))}
                    className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                    title="Αντιγραφή"
                  >
                    Αντιγραφή
                  </button>
                </div>
              </div>

              {/* HLR Credits — full failover section */}
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

                <div className={`rounded-lg p-4 mb-4 border ${
                  failoverActive ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'
                }`}>
                  <div className="text-sm font-medium mb-2">
                    {failoverActive ? 'Auto-Failover Ενεργοποιημένο' : 'Αυτόματη Ανίχνευση Σφαλμάτων'}
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${!failoverActive ? 'bg-green-500' : 'bg-yellow-500'}`} />
                      <span className="text-gray-600">Trigger A: Timeout/Error</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${(primaryCredits ?? 999) > 50 ? 'bg-green-500' : 'bg-red-500'}`} />
                      <span className="text-gray-600">Trigger B: Credits &lt; 50</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${!failoverActive ? 'bg-green-500' : 'bg-yellow-500'}`} />
                      <span className="text-gray-600">Trigger C: Auth Error</span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Εφεδρική πηγή: {hlrFallback?.enabled === true ? 'Ενεργοποιημένη' : 'Απενεργοποιημένη'}
                    {' | '}
                    Διαμορφωμένη: {hlrFallback?.configured === true ? 'Ναι' : 'Όχι'}
                  </div>
                </div>

                <div className="flex items-center justify-between mb-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div>
                    <div className="text-sm font-medium text-gray-700">Ενεργός Provider</div>
                    <div className="text-xs text-gray-400 mt-0.5">Εναλλαγή μέσω .env (HLRLOOKUPS_PROVIDER)</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium ${!failoverActive ? 'text-blue-600' : 'text-gray-400'}`}>
                      {String(primaryProvider ?? 'hlrlookup.com')}
                    </span>
                    <div className={`relative w-12 h-6 rounded-full cursor-not-allowed ${
                      failoverActive ? 'bg-yellow-400' : 'bg-blue-600'
                    }`}>
                      <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${
                        failoverActive ? 'left-6' : 'left-0.5'
                      }`} />
                    </div>
                    <span className={`text-xs font-medium ${failoverActive ? 'text-yellow-600' : 'text-gray-400'}`}>
                      {String(fallbackProvider ?? 'hlr-lookups.com')}
                    </span>
                  </div>
                </div>

                <div className="space-y-4">
                  {/* Primary */}
                  <div className={`p-3 rounded-lg border ${!failoverActive ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'}`}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700 font-medium">
                        Κύρια πηγή — {String(primaryProvider ?? '')}
                        {!failoverActive && <span className="ml-2 text-xs text-blue-600">(ενεργή)</span>}
                      </span>
                      <span className="font-semibold text-gray-800">
                        {primaryCredits != null ? String(primaryCredits) : String(ovHlrPrimary?.remaining ?? '—')} / {String(hlrPrimary?.initial ?? primaryTotal)}
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
                          Εφεδρική πηγή — {String(fallbackProvider ?? '')}
                          {failoverActive && <span className="ml-2 text-xs text-yellow-600">(ενεργή λόγω failover)</span>}
                        </span>
                        <span className="font-semibold text-gray-800">
                          {fallbackCredits != null ? String(fallbackCredits) : String(ovHlrFallback?.remaining ?? '—')} / {String(hlrFallback?.initial ?? '1000')}
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

              {/* Claude AI */}
              {claude && (
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <h2 className="text-base font-semibold text-gray-800 mb-3">Claude AI Προϋπολογισμός</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="text-xs text-gray-500 mb-1">Tokens Σήμερα</div>
                      <div className="text-xl font-bold text-gray-800">
                        {claudeTokensToday != null ? String(claudeTokensToday.toLocaleString('el-GR')) : '—'}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="text-xs text-gray-500 mb-1">Tokens Μήνα</div>
                      <div className="text-xl font-bold text-gray-800">
                        {claudeTokensMonth != null ? String(claudeTokensMonth.toLocaleString('el-GR')) : '—'}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ══ TAB 3: ΕΙΣΠΡΑΞΕΙΣ ══ */}
          {tab === 'income' && (
            <>
              {/* PayPal summary */}
              {paymentLogs && (paymentLogs.paypal as Record<string, unknown>)?.count != null
                && Number((paymentLogs.paypal as Record<string, unknown>).count) > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                  <div className="text-sm font-medium text-blue-800">
                    PayPal: {String((paymentLogs.paypal as Record<string, unknown>).total_eur ?? '0')} EUR
                    ({String((paymentLogs.paypal as Record<string, unknown>).count)} δωρεές)
                  </div>
                </div>
              )}

              {/* Donations addresses */}
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
                      Δωρεά μέσω PayPal
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
                </div>
              </div>

              {/* PayPal Webhook status */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-3">PayPal IPN Webhook</h2>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="text-sm font-medium text-green-800">Webhook ενεργό</div>
                  <div className="text-xs text-green-600 mt-1">Αυτόματη καταμέτρηση PayPal IPN</div>
                  <div className="text-xs text-gray-500 mt-2 font-mono">
                    https://api.ekklesia.gr/api/v1/payments/webhook/paypal
                  </div>
                </div>
              </div>

              {/* Payment Logs table */}
              {paymentLogs && (paymentLogs.payments as Record<string, unknown>[])?.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-semibold text-gray-800">Ιστορικό Πληρωμών</h2>
                    <span className="text-xs text-gray-400">
                      {String(paymentLogs.total_count ?? '0')} συνολικά
                    </span>
                  </div>
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
                        {(paymentLogs.payments as Record<string, unknown>[]).slice(0, 20).map((p, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-3 py-2 text-gray-600">{String(p.date ?? '—')}</td>
                            <td className="px-3 py-2 text-right font-mono text-gray-800">
                              {String(p.amount ?? '0')} {String(p.currency ?? 'EUR')}
                            </td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                p.method === 'paypal' ? 'bg-blue-100 text-blue-700' :
                                p.method === 'stripe' ? 'bg-purple-100 text-purple-700' :
                                'bg-gray-100 text-gray-600'
                              }`}>{String(p.method ?? '—')}</span>
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-500">
                              {p.allocation
                                ? `Server: ${String((p.allocation as Record<string, unknown>).server ?? '0')}€`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Manual entry placeholder */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-3">Χειροκίνητη Καταχώριση</h2>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-500">
                  Η χειροκίνητη καταχώριση εισπράξεων είναι διαθέσιμη μέσω API (POST /api/v1/payments/admin/logs).
                </div>
              </div>
            </>
          )}

          {/* ══ TAB 4: ΕΞΟΔΑ ══ */}
          {tab === 'expenses' && (
            <>
              {/* Hetzner */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-4">Server (Hetzner)</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="text-xs text-red-600 mb-1">Μηνιαίο κόστος</div>
                    <div className="text-xl font-bold text-gray-800">
                      {ovExpenses?.server_monatlich != null ? `${fmt(ovExpenses.server_monatlich as number)} €` : '15.00 €'}
                    </div>
                  </div>
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="text-xs text-red-600 mb-1">Συνολικό κόστος</div>
                    <div className="text-xl font-bold text-gray-800">
                      {ovExpenses?.server_gesamt != null ? `${fmt(ovExpenses.server_gesamt as number)} €` : '—'}
                    </div>
                  </div>
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="text-xs text-red-600 mb-1">Παρόχος</div>
                    <div className="font-bold text-gray-800">Hetzner CX33</div>
                    <div className="text-xs text-gray-400">Helsinki, Ubuntu 24.04</div>
                  </div>
                </div>
              </div>

              {/* HLR */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-4">HLR Credits</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-1">Κύριος πάροχος (hlrlookup.com)</div>
                    <div className="font-bold text-gray-800">
                      {ovHlrPrimary?.remaining != null
                        ? `${String(ovHlrPrimary.remaining)} / 2499 credits`
                        : primaryCredits != null ? `${String(primaryCredits)} credits` : '—'}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      Αξία: {ovHlrPrimary?.eur != null ? `${fmt(ovHlrPrimary.eur as number)} €` : '—'} (0.006 €/query)
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-1">HLR credits χρησιμοποιήθηκαν</div>
                    <div className="font-bold text-gray-800">
                      {ovExpenses?.hlr_verbraucht_credits != null
                        ? String(ovExpenses.hlr_verbraucht_credits)
                        : '—'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Arweave */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-4">Arweave Transactions</h2>
                <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500">
                  Αρχεία αποτελεσμάτων ψηφοφορίας αποθηκεύονται σε Arweave (append-only).
                  Κάθε αρχείο κοστίζει ελάχιστο AR.
                  Τρέχον υπόλοιπο: {(() => {
                    const bal = ovAr?.balance_ar ?? arweave?.balance_ar
                    return bal != null ? `${fmt(bal as number, 4)} AR` : '—'
                  })()}
                </div>
              </div>

              {/* Manual entry placeholder */}
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-800 mb-3">Χειροκίνητη Καταχώριση Εξόδου</h2>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-500">
                  Χειροκίνητη καταχώριση εξόδων — προσεχής ανάπτυξη.
                </div>
              </div>
            </>
          )}

          {/* ══ TAB 5: ΑΝΑΦΟΡΑ ══ */}
          {tab === 'report' && (
            <>
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-gray-800">Αυτόματη Αναφορά Διαφάνειας</h2>
                  <button
                    onClick={exportCSV}
                    disabled={!paymentLogs}
                    className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-40"
                  >
                    Export CSV
                  </button>
                </div>
                <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-700 whitespace-pre-wrap font-mono overflow-x-auto">
                  {buildReport()}
                </pre>
              </div>
            </>
          )}

        </div>
      )}
    </div>
  )
}

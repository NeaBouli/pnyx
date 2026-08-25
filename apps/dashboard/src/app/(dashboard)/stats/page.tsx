'use client'

import { useState, useEffect } from 'react'
import { asRecord, numberFrom } from '@/lib/response'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

export default function StatsPage() {
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null)
  const [adminStats, setAdminStats] = useState<Record<string, unknown> | null>(null)
  const [sentry, setSentry] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [analyticsResult, adminResult, sentryResult] = await Promise.allSettled([
          fetch(`${API}/api/v1/analytics/overview`).then(r => r.ok ? r.json() : null),
          fetch('/api/proxy/admin/stats').then(r => r.ok ? r.json() : null),
          fetch('/api/proxy/admin/sentry/status').then(r => r.ok ? r.json() : null),
        ])
        if (analyticsResult.status === 'fulfilled') setAnalytics(asRecord(analyticsResult.value))
        if (adminResult.status === 'fulfilled') setAdminStats(asRecord(adminResult.value))
        if (sentryResult.status === 'fulfilled') setSentry(asRecord(sentryResult.value))
      } catch { /* non-critical */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  const totalIdentities = numberFrom(adminStats?.total_identities)
  const activeIdentities = numberFrom(adminStats?.active_identities)
  const votes = asRecord(analytics?.votes)
  const bills = asRecord(analytics?.bills)
  const divergence = asRecord(analytics?.divergence)
  const totalVotes = numberFrom(votes?.total ?? analytics?.total_votes)
  const totalBills = numberFrom(bills?.total ?? analytics?.total_bills)
  const activeBills = numberFrom(bills?.active ?? analytics?.active_bills)
  const avgDivergence = numberFrom(divergence?.average_score ?? analytics?.avg_divergence)
  const sentryEnabled = sentry?.enabled === true && sentry?.dsn_configured === true

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Στατιστικά</h1>

      {loading ? (
        <div className="p-8 text-center text-gray-500">{String('Φόρτωση...')}</div>
      ) : (
        <div className="space-y-6">
          {/* Available data from analytics/overview */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Εγγεγραμμένες Ταυτότητες')}</div>
              <div className="text-3xl font-bold text-blue-600">
                {totalIdentities != null ? String(totalIdentities.toLocaleString('el-GR')) : String('—')}
              </div>
              <div className="text-xs text-gray-400 mt-1">{String('Ed25519 ανώνυμες ταυτότητες')}</div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Ενεργές Ταυτότητες')}</div>
              <div className="text-3xl font-bold text-blue-600">
                {activeIdentities != null ? String(activeIdentities.toLocaleString('el-GR')) : String('—')}
              </div>
              <div className="text-xs text-gray-400 mt-1">{String('Χωρίς PII — μόνο κρυπτογραφικές εγγραφές')}</div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Ψήφοι Συνολικά')}</div>
              <div className="text-3xl font-bold text-blue-600">
                {totalVotes != null ? String(totalVotes.toLocaleString('el-GR')) : String('—')}
              </div>
              <div className="text-xs text-gray-400 mt-1">{String('Απο analytics/overview')}</div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Νομοσχέδια Συνολικά')}</div>
              <div className="text-3xl font-bold text-blue-600">
                {totalBills != null ? String(totalBills.toLocaleString('el-GR')) : String('—')}
              </div>
              {activeBills != null && (
                <div className="text-xs text-gray-400 mt-1">{String(activeBills)} {String('ενεργά')}</div>
              )}
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Divergence Μέσος Όρος')}</div>
              <div className="text-3xl font-bold text-red-600">
                {avgDivergence != null ? `${String((avgDivergence * 100).toFixed(1))}%` : String('—')}
              </div>
              <div className="text-xs text-gray-400 mt-1">{String('Βουλή vs Πολίτες')}</div>
            </div>
          </div>

          {/* Integration Cards */}
          <h2 className="text-lg font-semibold text-gray-800 mt-8 mb-4">{String('Ενσωματώσεις')}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Plausible */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{String('Plausible Analytics')}</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{String('Σχεδιασμός Φάσης 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Στατιστικά επισκεπτών με προστασία απορρήτου')}</div>
              <div className="text-xs text-gray-500 mb-1">{String('Self-hosted, συμβατό με GDPR, χωρίς cookies')}</div>
              <div className="text-xs text-gray-400 mb-3">{String('Εκτιμώμενο κόστος: Δωρεάν (self-hosted Docker)')}</div>
              <span className="inline-block px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg text-xs font-medium cursor-not-allowed">
                {String('Δεν είναι ακόμη διαθέσιμο')}
              </span>
            </div>

            {/* Sentry */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">Sentry — Παρακολούθηση Σφαλμάτων</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sentryEnabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                  {sentryEnabled ? 'Ενεργό' : 'Ανενεργό'}
                </span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-2">Sentry Cloud (Free Tier)</div>
              <div className="space-y-1 text-xs text-gray-500">
                <div>API: {sentryEnabled ? 'Sentry SDK + FastAPI ενεργό' : 'Το DSN δεν είναι ενεργό'}</div>
                <div>Περιβάλλον: {String(sentry?.environment ?? '—')}</div>
                <div>Όριο: 5.000 events/μήνα (Free Tier)</div>
                <div>GDPR: Χωρίς PII, χωρίς cookies</div>
              </div>
              <a
                href="https://sentry.io"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-3 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700 transition-colors"
              >
                Sentry Dashboard →
              </a>
            </div>

            {/* Play Console */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{String('Google Play Console API')}</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{String('Phase 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Στατιστικά λήψεων, αξιολογήσεις και ποσοστό ANR')}</div>
              <div className="text-xs text-gray-500 mb-3">{String('Απαιτεί Service Account και πρόσβαση API στο Play Console')}</div>
              <span className="inline-block px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg text-xs font-medium cursor-not-allowed">
                {String('Δεν είναι συνδεδεμένο')}
              </span>
            </div>

            {/* F-Droid */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{String('F-Droid')}</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{String('Open Source')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Δεν διατίθενται στατιστικά λήψεων')}</div>
              <div className="text-xs text-gray-500">{String('Το F-Droid δεν αποστέλλει αριθμούς εγκαταστάσεων στους προγραμματιστές.')}</div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}

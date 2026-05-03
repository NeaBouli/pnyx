'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

export default function StatsPage() {
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const r = await fetch(`${API}/api/v1/analytics/overview`)
        if (r.ok) {
          setAnalytics(await r.json())
        }
      } catch { /* non-critical */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  const totalIdentities = analytics?.total_identities as number | null
  const totalVerifications = analytics?.total_verifications as number | null
  const totalVotes = analytics?.total_votes as number | null
  const totalBills = analytics?.total_bills as number | null
  const activeBills = analytics?.active_bills as number | null
  const avgDivergence = analytics?.avg_divergence as number | null

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
              <div className="text-xs text-gray-500 mb-1">{String('Επαληθεύσεις Συνολικά')}</div>
              <div className="text-3xl font-bold text-blue-600">
                {totalVerifications != null ? String(totalVerifications.toLocaleString('el-GR')) : String('—')}
              </div>
              <div className="text-xs text-gray-400 mt-1">{String('HLR + SMS verifications')}</div>
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
          <h2 className="text-lg font-semibold text-gray-800 mt-8 mb-4">{String('Integrations (Phase 2)')}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Plausible */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{String('Plausible Analytics')}</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">{String('Empfohlen')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Datenschutzkonforme Besucherstatistik')}</div>
              <div className="text-xs text-gray-500 mb-1">{String('Selbst-gehostet, GDPR-konform, kein Cookie-Banner noetig')}</div>
              <div className="text-xs text-gray-400 mb-3">{String('Εκτιμώμενο κόστος: Δωρεάν (self-hosted Docker)')}</div>
              <a
                href="/settings"
                className="inline-block px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 transition-colors"
              >
                {String('Aktivieren -> Einstellungen')}
              </a>
            </div>

            {/* Sentry */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">Sentry — Παρακολούθηση Σφαλμάτων</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">Ενεργό</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-2">Sentry Cloud (Free Tier)</div>
              <div className="space-y-1 text-xs text-gray-500">
                <div>API: Sentry SDK + FastAPI Integration</div>
                <div>Dashboard: @sentry/nextjs</div>
                <div>Mobile: @sentry/react-native (εκκρεμεί)</div>
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
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Download-Statistiken, Bewertungen, ANR-Rate')}</div>
              <div className="text-xs text-gray-500 mb-3">{String('Erfordert Service Account + API Freigabe in Play Console')}</div>
              <span className="inline-block px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg text-xs font-medium cursor-not-allowed">
                {String('Nicht verbunden')}
              </span>
            </div>

            {/* F-Droid */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{String('F-Droid')}</h3>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{String('Open Source')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mb-1">{String('Keine Download-Statistiken verfuegbar')}</div>
              <div className="text-xs text-gray-500">{String('Open Source Prinzip: F-Droid meldet keine Installationszahlen an Entwickler zurueck.')}</div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}

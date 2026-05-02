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

          {/* Phase 2 Placeholders */}
          <h2 className="text-lg font-semibold text-gray-800 mt-8 mb-4">{String('Αναμένονται (Phase 2)')}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600">{String('Phase 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mt-3">{String('App Downloads')}</div>
              <div className="text-xs text-gray-400 mt-1">
                {String('Play Console API — ακόμη δεν έχει συνδεθεί. Απαιτείται Google Play Developer API integration.')}
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600">{String('Phase 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mt-3">{String('Website Επισκέπτες')}</div>
              <div className="text-xs text-gray-400 mt-1">
                {String('Κανένα analytics tool εγκατεστημένο. Σύσταση: Plausible (self-hosted, GDPR-konform).')}
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600">{String('Phase 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mt-3">{String('App Crashes')}</div>
              <div className="text-xs text-gray-400 mt-1">
                {String('Κανένα crash-reporting. Σύσταση: Sentry Free Tier.')}
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600">{String('Phase 2')}</span>
              </div>
              <div className="text-sm font-medium text-gray-700 mt-3">{String('F-Droid Installs')}</div>
              <div className="text-xs text-gray-400 mt-1">
                {String('Δεν είναι trackable — Open Source αρχή. Τα F-Droid downloads δεν αναφέρονται στους developers.')}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

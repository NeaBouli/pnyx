'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'



interface AdminStats {
  total_identities?: number
  active_identities?: number
  revoked_identities?: number
}

interface AnalyticsOverview {
  votes?: { total?: number }
  bills?: { total?: number }
}

export default function UsersPage() {
  const { data: session } = useSession()
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)

  const [nullifierInput, setNullifierInput] = useState('')
  const [revokeLoading, setRevokeLoading] = useState(false)
  const [revokeConfirm, setRevokeConfirm] = useState(false)
  const [revokeResult, setRevokeResult] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [statsRes, analyticsRes] = await Promise.allSettled([
        fetch('/api/proxy/admin/stats').then(r => r.json()),
        fetch(`${API}/api/v1/analytics/overview`).then(r => r.json()),
      ])
      const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
      setAdminStats(v(statsRes) as AdminStats | null)
      setAnalytics(v(analyticsRes) as AnalyticsOverview | null)
      setLoading(false)
    }
    load()
  }, [])

  const role = session?.user?.role

  async function handleRevoke() {
    if (!nullifierInput.trim()) return
    setRevokeLoading(true)
    setRevokeResult(null)
    try {
      const res = await fetch(`${API}/api/v1/identity/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nullifier_hash: nullifierInput.trim(), phone_number: 'required_but_unknown' }),
      })
      const data = await res.json() as Record<string, unknown>
      if (res.ok) {
        setRevokeResult(String(data?.message ?? data?.detail ?? 'Ανάκληση επιτυχής'))
        setNullifierInput('')
      } else {
        setRevokeResult(String('Σφάλμα: ' + String(data?.detail ?? data?.error ?? res.status)))
      }
    } catch (e) {
      setRevokeResult(String('Σφάλμα: ' + String(e)))
    } finally {
      setRevokeLoading(false)
      setRevokeConfirm(false)
    }
  }

  const totalIdentities = adminStats?.total_identities
  const totalVotes = (analytics?.votes as Record<string, unknown> | undefined)?.total as number | undefined

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{String('Χρήστες & Ταυτότητες')}</h1>
        <button
          disabled
          title="Kein PII-Export moeglich — Datenschutz"
          className="px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
        >
          {String('CSV (kein PII-Export)')}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">{String('Σύνολο Ταυτοτήτων')}</div>
          <div className="text-3xl font-bold text-blue-600">
            {loading ? (
              <span className="text-gray-300 text-lg">{String('...')}</span>
            ) : totalIdentities != null ? (
              String(totalIdentities.toLocaleString('el-GR'))
            ) : (
              <span className="text-gray-400 text-lg">{String('—')}</span>
            )}
          </div>
          <div className="text-xs text-gray-400 mt-1">{String('Ανώνυμες Ed25519')}</div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">{String('Ενεργές')}</div>
          <div className="text-3xl font-bold text-green-600">
            {adminStats?.active_identities != null
              ? String(adminStats.active_identities.toLocaleString('el-GR'))
              : <span className="text-gray-300 text-lg">{String('—')}</span>}
          </div>
          <div className="text-xs text-gray-400 mt-1">{String('Placeholder Phase 2')}</div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">{String('Ανακληθείσες')}</div>
          <div className="text-3xl font-bold text-red-600">
            {adminStats?.revoked_identities != null
              ? String(adminStats.revoked_identities.toLocaleString('el-GR'))
              : <span className="text-gray-300 text-lg">{String('—')}</span>}
          </div>
          <div className="text-xs text-gray-400 mt-1">{String('Placeholder Phase 2')}</div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-xs text-gray-500 mb-1">{String('Ψήφοι Συνολικά')}</div>
          <div className="text-3xl font-bold text-purple-600">
            {loading ? (
              <span className="text-gray-300 text-lg">{String('...')}</span>
            ) : totalVotes != null ? (
              String(totalVotes.toLocaleString('el-GR'))
            ) : (
              <span className="text-gray-400 text-lg">{String('—')}</span>
            )}
          </div>
          <div className="text-xs text-gray-400 mt-1">{String('analytics/overview')}</div>
        </div>
      </div>

      {/* Registered Identities Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-800">{String('Καταχωρημένες Ταυτότητες')}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{String('Κανένα User-List-Endpoint — Phase 2')}</p>
          </div>
          <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">{String('Phase 2')}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">#</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{String('Status')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{String('Εγγραφή')}</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">{String('Ψήφοι')}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={4} className="py-12 text-center text-gray-400">
                  <div className="text-sm font-medium text-gray-500">{String('Κανένας User-List-Endpoint διαθέσιμος')}</div>
                  <div className="text-xs mt-1">{String('Η λίστα χρηστών υλοποιείται στη Phase 2')}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Revoke Section */}
      {(role === 'SUPER_ADMIN' || role === 'SYSTEM_ADMIN') && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900 mb-1">{String('Ανάκληση Ταυτότητας')}</h2>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4 text-xs text-yellow-800">
            {String('Η ανάκληση απαιτεί τον Nullifier Hash ΚΑΙ τον αριθμό τηλεφώνου του χρήστη. Ο αριθμός τηλεφώνου είναι άγνωστος στο σύστημα μετά την εγγραφή.')}
          </div>
          <div className="flex gap-3 mb-3">
            <input
              type="text"
              value={nullifierInput}
              onChange={(e) => setNullifierInput(e.target.value)}
              placeholder="Nullifier Hash (hex)"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
            />
          </div>
          {!revokeConfirm ? (
            <button
              onClick={() => setRevokeConfirm(true)}
              disabled={!nullifierInput.trim()}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {String('Ανάκληση')}
            </button>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="text-sm font-medium text-red-800 mb-1">{String('Επιβεβαίωση Ανάκλησης')}</div>
              <div className="text-sm text-red-700 mb-3 font-mono break-all">{nullifierInput}</div>
              <div className="flex gap-2">
                <button
                  onClick={handleRevoke}
                  disabled={revokeLoading}
                  className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  {revokeLoading ? String('Ανάκληση...') : String('Ναι, Ανάκληση')}
                </button>
                <button
                  onClick={() => setRevokeConfirm(false)}
                  disabled={revokeLoading}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 disabled:opacity-50"
                >
                  {String('Ακύρωση')}
                </button>
              </div>
            </div>
          )}
          {revokeResult && (
            <div className={`mt-3 p-3 rounded-lg text-sm font-medium ${revokeResult.startsWith('Σφάλμα') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
              {revokeResult}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

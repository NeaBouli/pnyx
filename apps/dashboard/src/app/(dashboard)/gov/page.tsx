'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${API}${path}${sep}admin_key=${ADMIN_KEY}`
}

type ApplicationStatus = 'pending' | 'approved' | 'rejected'

interface GovApplication {
  applicant: string
  district: string
  ada: string
  status: ApplicationStatus
  date: string
}

interface DiavgeiaDecision {
  ada?: string
  subject?: string
  decisionType?: string
  organizationLabel?: string
  issueDate?: string
  [key: string]: unknown
}

interface GovGrGates {
  '500_aktive_nutzer': boolean
  '3_ngo_partnerschaften': boolean
  roadmap_publiziert: boolean
  govgr_genehmigung: boolean
}

interface GovGrStatus {
  module: string
  status: string
  progress: string
  gates: GovGrGates
  env_configured: boolean
}

const APP_STATUS_LABELS: Record<ApplicationStatus, string> = {
  pending: 'Εκκρεμής',
  approved: 'Εγκρίθηκε',
  rejected: 'Απορρίφθηκε',
}

const APP_STATUS_COLORS: Record<ApplicationStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

const EXAMPLE_APPLICATIONS: GovApplication[] = [
  {
    applicant: 'Δήμος Αθηναίων',
    district: 'Αττική',
    ada: 'ΑΔΑ: ΧΧΧΧ-ΧΧΧ',
    status: 'pending',
    date: '2026-04-15',
  },
]

const GATE_LABELS: { key: keyof GovGrGates; label: string; description: string }[] = [
  { key: '500_aktive_nutzer', label: '500 Ενεργοί Χρήστες', description: 'Τουλάχιστον 500 επαληθευμένοι, ενεργοί χρήστες στην πλατφόρμα' },
  { key: '3_ngo_partnerschaften', label: '3 Συνεργασίες ΜΚΟ', description: 'Συνεργασίες με τουλάχιστον 3 αναγνωρισμένες ΜΚΟ' },
  { key: 'roadmap_publiziert', label: 'Δημοσιευμένο Roadmap', description: 'Δημόσιο roadmap με δέσμευση διαφάνειας' },
  { key: 'govgr_genehmigung', label: 'Έγκριση gov.gr', description: 'Επίσημη έγκριση από το gov.gr για ενσωμάτωση OAuth 2.0' },
]

export default function GovPage() {
  const [govGr, setGovGr] = useState<GovGrStatus | null>(null)
  const [loading, setLoading] = useState(true)

  // Diavgeia state
  const [adaInput, setAdaInput] = useState('')
  const [diavgeiaResults, setDiavgeiaResults] = useState<DiavgeiaDecision[]>([])
  const [diavgeiaLoading, setDiavgeiaLoading] = useState(false)
  const [diavgeiaError, setDiavgeiaError] = useState<string | null>(null)
  const [diavgeiaAction, setDiavgeiaAction] = useState<string | null>(null)
  const [diavgeiaActionResult, setDiavgeiaActionResult] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/api/v1/auth/govgr/status`)
        if (res.ok) {
          setGovGr(await res.json())
        }
      } catch { /* non-critical */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  async function handleDiavgeiaSearch() {
    if (!adaInput.trim()) return
    setDiavgeiaLoading(true)
    setDiavgeiaError(null)
    setDiavgeiaResults([])
    try {
      const res = await fetch(`${API}/api/v1/admin/diavgeia/scrape?admin_key=${ADMIN_KEY}&ada=${encodeURIComponent(adaInput.trim())}`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json() as Record<string, unknown>
        const decisions = Array.isArray(data) ? data : (Array.isArray(data?.decisions) ? data.decisions as DiavgeiaDecision[] : [data as DiavgeiaDecision])
        setDiavgeiaResults(decisions)
      } else {
        setDiavgeiaError(`HTTP ${String(res.status)}`)
      }
    } catch (e) {
      setDiavgeiaError(String(e))
    } finally {
      setDiavgeiaLoading(false)
    }
  }

  async function handleDiavgeiaAdminAction(action: 'scrape' | 'refresh-orgs-cache') {
    setDiavgeiaAction(action)
    setDiavgeiaActionResult(null)
    try {
      const url = action === 'scrape'
        ? adminURL('/api/v1/admin/diavgeia/scrape')
        : adminURL('/api/v1/admin/diavgeia/refresh-orgs-cache')
      const res = await fetch(url, { method: 'POST' })
      const data = await res.json() as Record<string, unknown>
      setDiavgeiaActionResult(res.ok ? String(data?.message ?? data?.status ?? 'OK') : `Σφάλμα: ${String(data?.detail ?? res.status)}`)
    } catch (e) {
      setDiavgeiaActionResult(`Σφάλμα: ${String(e)}`)
    } finally {
      setDiavgeiaAction(null)
    }
  }

  const fulfilledCount = govGr?.gates
    ? Object.values(govGr.gates).filter(Boolean).length
    : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">gov.gr Integration</h1>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          govGr?.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-800'
        }`}>
          {govGr?.status === 'active' ? 'Ενεργό' : govGr?.status === 'stub' ? 'Αναμονή' : 'Αναμονή'}
        </span>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
      ) : (
        <div className="space-y-6">
          {/* Gates Progress */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">Προϋποθέσεις Ενεργοποίησης</h2>
              <span className="text-sm font-medium text-gray-500">
                {govGr?.progress ?? `${fulfilledCount}/4`} Προϋποθέσεις
              </span>
            </div>
            <div className="p-5">
              {/* Progress bar */}
              <div className="w-full bg-gray-100 rounded-full h-3 mb-6">
                <div
                  className="bg-blue-500 h-3 rounded-full transition-all"
                  style={{ width: `${(fulfilledCount / 4) * 100}%` }}
                />
              </div>

              {/* Gate cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {GATE_LABELS.map(({ key, label, description }) => {
                  const fulfilled = govGr?.gates?.[key] ?? false
                  return (
                    <div key={key} className={`rounded-xl p-4 border ${fulfilled ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-gray-800">{label}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          fulfilled ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'
                        }`}>
                          {fulfilled ? 'Πληρώθηκε' : 'Εκκρεμεί'}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">{description}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Info boxes */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
            <div className="font-semibold text-blue-800 mb-1">gov.gr OAuth 2.0</div>
            <div className="text-sm text-blue-700">
              Το gov.gr OAuth θα ενεργοποιηθεί μόλις πληρωθούν και οι 4 προϋποθέσεις.
              Μέχρι τότε χρησιμοποιείται το MOD-01 HLR για επαλήθευση ταυτότητας.
            </div>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-xl p-5">
            <div className="font-semibold text-orange-800 mb-1">Τρέχουσα Κατάσταση: {govGr?.module ?? 'MOD-09'}</div>
            <div className="text-sm text-orange-700">
              Αυτή τη στιγμή χρησιμοποιείται το MOD-01 HLR για επαλήθευση ταυτότητας. Η ενσωμάτωση
              gov.gr OAuth 2.0 είναι σε αναμονή και θα ενεργοποιηθεί μετά την πλήρωση όλων των προϋποθέσεων.
            </div>
            {govGr?.env_configured === false && (
              <div className="text-xs text-orange-600 mt-2">
                Ρύθμιση ENV: Δεν έχει ολοκληρωθεί ακόμα
              </div>
            )}
          </div>

          {/* Applications table (existing) */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Εισερχόμενες Αιτήσεις</h2>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Αιτών</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Περιφέρεια</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Diavgeia ΑΔΑ</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ημερομηνία</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ενέργειες</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {EXAMPLE_APPLICATIONS.map((app, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{app.applicant}</td>
                    <td className="px-4 py-3 text-gray-600">{app.district}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{app.ada}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${APP_STATUS_COLORS[app.status]}`}>
                        {APP_STATUS_LABELS[app.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(app.date).toLocaleDateString('el-GR')}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        disabled
                        className="text-xs text-gray-400 cursor-not-allowed"
                      >
                        Έγκριση (n/a)
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
              Ενεργοποιείται μετά τη σύνδεση gov.gr OAuth 2.0 και Diavgeia API.
            </div>
          </div>

          {/* Diavgeia Section */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">Diavgeia</h2>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDiavgeiaAdminAction('scrape')}
                  disabled={diavgeiaAction === 'scrape'}
                  className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-200 transition-colors disabled:opacity-50"
                >
                  {diavgeiaAction === 'scrape' ? String('Scrape...') : String('Scrape τώρα')}
                </button>
                <button
                  onClick={() => handleDiavgeiaAdminAction('refresh-orgs-cache')}
                  disabled={diavgeiaAction === 'refresh-orgs-cache'}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  {diavgeiaAction === 'refresh-orgs-cache' ? String('Ανανέωση...') : String('Org-Cache ανανέωση')}
                </button>
              </div>
            </div>

            {diavgeiaActionResult && (
              <div className="mx-5 mt-3 p-2 bg-gray-50 rounded text-xs text-gray-600 border border-gray-200">
                {String(diavgeiaActionResult)}
              </div>
            )}

            <div className="p-5">
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={adaInput}
                  onChange={(e) => setAdaInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleDiavgeiaSearch()}
                  placeholder="ΑΔΑ π.χ. ΨΧΧΧ-ΑΒΓ"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleDiavgeiaSearch}
                  disabled={diavgeiaLoading || !adaInput.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {diavgeiaLoading ? String('Αναζήτηση...') : String('Αναζήτηση')}
                </button>
              </div>

              {diavgeiaError && (
                <div className="text-sm text-red-600 mb-3">{String('Σφάλμα:')} {String(diavgeiaError)}</div>
              )}

              {diavgeiaResults.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">ΑΔΑ</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Τύπος</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Οργανισμός</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Ημερομηνία</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {diavgeiaResults.map((d, i) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-mono text-xs text-gray-700">{String(d.ada ?? '—')}</td>
                          <td className="px-3 py-2 text-xs text-gray-600">{String(d.decisionType ?? d.subject ?? '—')}</td>
                          <td className="px-3 py-2 text-xs text-gray-600">{String(d.organizationLabel ?? '—')}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">{d.issueDate ? String(new Date(String(d.issueDate)).toLocaleDateString('el-GR')) : String('—')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {!diavgeiaLoading && diavgeiaResults.length === 0 && !diavgeiaError && (
                <div className="text-sm text-gray-400 text-center py-4">{String('Εισάγετε ΑΔΑ και πατήστε Αναζήτηση')}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_EKKLESIA_API || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

type BillStatus = 'ANNOUNCED' | 'ACTIVE' | 'WINDOW_24H' | 'PARLIAMENT_VOTED' | 'OPEN_END'
type GovernanceLevel = 'NATIONAL' | 'REGIONAL' | 'MUNICIPAL' | 'COMMUNITY'

interface Bill {
  id: number
  title_el: string
  title_en?: string
  status: BillStatus
  governance_level: GovernanceLevel
  created_at: string
  source_url?: string
}

const STATUS_LABELS: Record<BillStatus, string> = {
  ANNOUNCED: 'Ανακοινώθηκε',
  ACTIVE: 'Ενεργό',
  WINDOW_24H: 'Παράθυρο 24ω',
  PARLIAMENT_VOTED: 'Ψηφίστηκε',
  OPEN_END: 'Ανοιχτό',
}

const STATUS_COLORS: Record<BillStatus, string> = {
  ANNOUNCED: 'bg-gray-100 text-gray-700',
  ACTIVE: 'bg-green-100 text-green-700',
  WINDOW_24H: 'bg-yellow-100 text-yellow-800',
  PARLIAMENT_VOTED: 'bg-blue-100 text-blue-700',
  OPEN_END: 'bg-purple-100 text-purple-700',
}

const GOVERNANCE_LABELS: Record<GovernanceLevel, string> = {
  NATIONAL: 'Εθνικό',
  REGIONAL: 'Περιφερειακό',
  MUNICIPAL: 'Δημοτικό',
  COMMUNITY: 'Κοινοτικό',
}

const ALL_STATUSES: BillStatus[] = ['ANNOUNCED', 'ACTIVE', 'WINDOW_24H', 'PARLIAMENT_VOTED', 'OPEN_END']

interface NewBillForm {
  title_el: string
  title_en: string
  summary_short_el: string
  governance_level: GovernanceLevel
  source_url: string
}

export default function BillsPage() {
  const [bills, setBills] = useState<Bill[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<BillStatus | 'ALL'>('ALL')
  const [showModal, setShowModal] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<NewBillForm>({
    title_el: '',
    title_en: '',
    summary_short_el: '',
    governance_level: 'NATIONAL',
    source_url: '',
  })

  useEffect(() => {
    async function load() {
      try {
        const r = await fetch(`${API}/api/v1/bills?limit=100`)
        const data = await r.json()
        setBills(Array.isArray(data) ? data : data.bills ?? [])
      } catch {
        setError('Αδύνατη η φόρτωση νομοσχεδίων')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = filter === 'ALL' ? bills : bills.filter((b) => b.status === filter)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/bills?admin_key=${ADMIN_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const newBill = await r.json()
      setBills((prev) => [newBill, ...prev])
      setShowModal(false)
      setForm({ title_el: '', title_en: '', summary_short_el: '', governance_level: 'NATIONAL', source_url: '' })
    } catch (err) {
      setError('Αδύνατη η δημιουργία νομοσχεδίου')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStatusChange(id: number, status: BillStatus) {
    try {
      await fetch(`${API}/api/v1/admin/bills/${id}/transition?admin_key=${ADMIN_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      setBills((prev) => prev.map((b) => (b.id === id ? { ...b, status } : b)))
    } catch {
      setError('Αδύνατη η αλλαγή κατάστασης')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Νομοσχέδια</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          + Νέο Νομοσχέδιο
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
        </div>
      )}

      {/* Filter */}
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={() => setFilter('ALL')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            filter === 'ALL' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Όλα ({bills.length})
        </button>
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {STATUS_LABELS[s]} ({bills.filter((b) => b.status === s).length})
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Δεν βρέθηκαν νομοσχέδια</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Τίτλος</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Επίπεδο</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Ημερομηνία</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Ενέργειες</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((bill) => (
                <tr key={bill.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-500 font-mono">#{bill.id}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 truncate max-w-xs">{bill.title_el}</div>
                    {bill.title_en && <div className="text-xs text-gray-400 truncate max-w-xs">{bill.title_en}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[bill.status]}`}>
                      {STATUS_LABELS[bill.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{GOVERNANCE_LABELS[bill.governance_level]}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(bill.created_at).toLocaleDateString('el-GR')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <a
                        href={`/bills/${bill.id}`}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        Λεπτομέρειες
                      </a>
                      <select
                        value={bill.status}
                        onChange={(e) => handleStatusChange(bill.id, e.target.value as BillStatus)}
                        className="text-xs border border-gray-200 rounded px-1.5 py-0.5 text-gray-700"
                      >
                        {ALL_STATUSES.map((s) => (
                          <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                        ))}
                      </select>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* New Bill Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Νέο Νομοσχέδιο</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Ελληνικά) *</label>
                <input
                  required
                  value={form.title_el}
                  onChange={(e) => setForm({ ...form, title_el: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="π.χ. Νόμος για την Υγεία"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Αγγλικά)</label>
                <input
                  value={form.title_en}
                  onChange={(e) => setForm({ ...form, title_en: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Healthcare Act"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Σύντομη Περίληψη *</label>
                <textarea
                  required
                  value={form.summary_short_el}
                  onChange={(e) => setForm({ ...form, summary_short_el: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                  placeholder="Σύντομη περιγραφή του νομοσχεδίου..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Επίπεδο Διακυβέρνησης *</label>
                <select
                  value={form.governance_level}
                  onChange={(e) => setForm({ ...form, governance_level: e.target.value as GovernanceLevel })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="NATIONAL">Εθνικό</option>
                  <option value="REGIONAL">Περιφερειακό</option>
                  <option value="MUNICIPAL">Δημοτικό</option>
                  <option value="COMMUNITY">Κοινοτικό</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Πηγή URL</label>
                <input
                  type="url"
                  value={form.source_url}
                  onChange={(e) => setForm({ ...form, source_url: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Ακύρωση
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {submitting ? 'Αποθήκευση...' : 'Δημιουργία'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

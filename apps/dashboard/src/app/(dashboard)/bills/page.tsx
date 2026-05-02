'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

type BillStatus = 'ANNOUNCED' | 'ACTIVE' | 'WINDOW_24H' | 'PARLIAMENT_VOTED' | 'OPEN_END'
type GovernanceLevel = 'NATIONAL' | 'REGIONAL' | 'MUNICIPAL' | 'COMMUNITY'

interface Bill {
  id: number
  title_el: string
  title_en?: string
  summary_short_el?: string
  status: BillStatus
  governance_level: GovernanceLevel
  created_at: string
  source_url?: string
  ai_reviewed?: boolean
  ai_summary?: string
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

const PARTIES = ['ΝΔ', 'ΣΥΡΙΖΑ', 'ΠΑΣΟΚ', 'ΚΚΕ', 'ΕΛ', 'ΝΙΚΗ', 'ΠΛ', 'ΣΠΑΡΤ'] as const
const PARTY_VOTE_OPTIONS = ['—', 'ΝΑΙ', 'ΟΧΙ', 'ΑΠΟΧΗ'] as const

interface NewBillForm {
  title_el: string
  title_en: string
  summary_short_el: string
  governance_level: GovernanceLevel
  source_url: string
}

interface EditBillForm {
  title_el: string
  title_en: string
  summary_short_el: string
  governance_level: GovernanceLevel
  source_url: string
}

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${API}${path}${sep}admin_key=${ADMIN_KEY}`
}

export default function BillsPage() {
  const [bills, setBills] = useState<Bill[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<BillStatus | 'ALL'>('ALL')
  const [showModal, setShowModal] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<Record<number, string>>({})
  const [form, setForm] = useState<NewBillForm>({
    title_el: '', title_en: '', summary_short_el: '', governance_level: 'NATIONAL', source_url: '',
  })

  // Edit modal
  const [editBill, setEditBill] = useState<Bill | null>(null)
  const [editForm, setEditForm] = useState<EditBillForm>({
    title_el: '', title_en: '', summary_short_el: '', governance_level: 'NATIONAL', source_url: '',
  })
  const [editSubmitting, setEditSubmitting] = useState(false)

  // Text modal
  const [textBill, setTextBill] = useState<Bill | null>(null)
  const [textContent, setTextContent] = useState('')
  const [textSubmitting, setTextSubmitting] = useState(false)

  // Party votes modal
  const [partyBill, setPartyBill] = useState<Bill | null>(null)
  const [partyVotes, setPartyVotes] = useState<Record<string, string>>({})
  const [partySubmitting, setPartySubmitting] = useState(false)

  const loadBills = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v1/bills?limit=100`)
      const data = await r.json()
      setBills(Array.isArray(data) ? data : data.bills ?? [])
    } catch {
      setError('Αδύνατη η φόρτωση νομοσχεδίων')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadBills() }, [loadBills])

  const filtered = filter === 'ALL' ? bills : bills.filter((b) => b.status === filter)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      const r = await fetch(adminURL('/api/v1/admin/bills'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setShowModal(false)
      setForm({ title_el: '', title_en: '', summary_short_el: '', governance_level: 'NATIONAL', source_url: '' })
      setSuccess('Νομοσχέδιο δημιουργήθηκε')
      await loadBills()
    } catch {
      setError('Αδύνατη η δημιουργία νομοσχεδίου')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStatusChange(id: number, newStatus: BillStatus) {
    try {
      await fetch(adminURL(`/api/v1/bills/${id}/transition`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_status: newStatus }),
      })
      setBills((prev) => prev.map((b) => (b.id === id ? { ...b, status: newStatus } : b)))
    } catch {
      setError('Αδύνατη η αλλαγή κατάστασης')
    }
  }

  async function handleAction(id: number, action: 'review' | 'fetch-text') {
    setActionLoading(prev => ({ ...prev, [id]: action }))
    try {
      const path = action === 'review'
        ? `/api/v1/admin/bills/${id}/review`
        : `/api/v1/admin/bills/${id}/fetch-text`
      const r = await fetch(adminURL(path), { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      if (action === 'review') {
        setBills(prev => prev.map(b => b.id === id ? { ...b, ai_reviewed: true } : b))
      }
    } catch {
      setError(`Αδύνατη η ενέργεια ${action} για #${String(id)}`)
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[id]; return n })
    }
  }

  // Edit modal handlers
  function openEditModal(bill: Bill) {
    setEditBill(bill)
    setEditForm({
      title_el: bill.title_el || '',
      title_en: bill.title_en || '',
      summary_short_el: bill.summary_short_el || '',
      governance_level: bill.governance_level,
      source_url: bill.source_url || '',
    })
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!editBill) return
    setEditSubmitting(true)
    try {
      const r = await fetch(adminURL(`/api/v1/admin/bills/${editBill.id}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setEditBill(null)
      setSuccess('Νομοσχέδιο ενημερώθηκε')
      await loadBills()
    } catch {
      setError('Αδύνατη η ενημέρωση νομοσχεδίου')
    } finally {
      setEditSubmitting(false)
    }
  }

  // Text modal handlers
  function openTextModal(bill: Bill) {
    setTextBill(bill)
    setTextContent('')
  }

  async function handleSetText(e: React.FormEvent) {
    e.preventDefault()
    if (!textBill) return
    setTextSubmitting(true)
    try {
      const r = await fetch(adminURL(`/api/v1/admin/bills/${textBill.id}/set-text`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text_el: textContent }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setTextBill(null)
      setSuccess('Κείμενο αποθηκεύτηκε')
    } catch {
      setError('Αδύνατη η αποθήκευση κειμένου')
    } finally {
      setTextSubmitting(false)
    }
  }

  async function handleAutoScrape() {
    if (!textBill) return
    setTextSubmitting(true)
    try {
      const r = await fetch(adminURL(`/api/v1/admin/bills/${textBill.id}/fetch-text`), { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setTextBill(null)
      setSuccess('Αυτόματο scrape ξεκίνησε')
    } catch {
      setError('Αδύνατο το αυτόματο scrape')
    } finally {
      setTextSubmitting(false)
    }
  }

  // Party votes handlers
  function openPartyModal(bill: Bill) {
    setPartyBill(bill)
    const init: Record<string, string> = {}
    for (const p of PARTIES) { init[p] = '—' }
    setPartyVotes(init)
  }

  async function handlePartySubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!partyBill) return
    setPartySubmitting(true)
    try {
      const r = await fetch(adminURL(`/api/v1/admin/bills/${partyBill.id}/party-votes`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ votes: partyVotes }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setPartyBill(null)
      setSuccess('Ψήφοι κομμάτων αποθηκεύτηκαν')
    } catch {
      setError('Αδύνατη η αποθήκευση ψήφων κομμάτων')
    } finally {
      setPartySubmitting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Νομοσχέδια</h1>
        <div className="flex items-center gap-3">
          <a
            href={`${API}/api/v1/export/bills.csv`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
          >
            CSV
          </a>
          <a
            href={`${API}/api/v1/export/results.json`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
          >
            JSON
          </a>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            + Νέο Νομοσχέδιο
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {success}
          <button className="ml-2 underline" onClick={() => setSuccess(null)}>Κλείσιμο</button>
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
          Όλα ({String(bills.length)})
        </button>
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {STATUS_LABELS[s]} ({String(bills.filter((b) => b.status === s).length)})
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Τίτλος</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Επίπεδο</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">AI</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ημερομηνία</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ενέργειες</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((bill) => (
                  <tr key={bill.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-gray-500 font-mono">#{String(bill.id)}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 truncate max-w-xs">{bill.title_el}</div>
                      {bill.title_en ? <div className="text-xs text-gray-400 truncate max-w-xs">{String(bill.title_en)}</div> : null}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={bill.status}
                        onChange={(e) => handleStatusChange(bill.id, e.target.value as BillStatus)}
                        className={`px-2 py-1 rounded-full text-xs font-medium border-0 cursor-pointer ${STATUS_COLORS[bill.status]}`}
                      >
                        {ALL_STATUSES.map((s) => (
                          <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{GOVERNANCE_LABELS[bill.governance_level]}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        bill.ai_reviewed ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {bill.ai_reviewed ? 'Ελέγχθηκε' : 'Εκκρεμεί'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {new Date(bill.created_at).toLocaleDateString('el-GR')}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <button
                          onClick={() => openEditModal(bill)}
                          className="px-2 py-0.5 text-xs bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 transition-colors"
                          title="Επεξεργασία"
                        >
                          Επεξεργασία
                        </button>
                        <button
                          onClick={() => openTextModal(bill)}
                          className="px-2 py-0.5 text-xs bg-emerald-50 text-emerald-600 rounded hover:bg-emerald-100 transition-colors"
                          title="Κείμενο"
                        >
                          Κείμενο
                        </button>
                        <button
                          onClick={() => openPartyModal(bill)}
                          className="px-2 py-0.5 text-xs bg-amber-50 text-amber-600 rounded hover:bg-amber-100 transition-colors"
                          title="Κόμματα"
                        >
                          Κόμματα
                        </button>
                        <button
                          onClick={() => handleAction(bill.id, 'review')}
                          disabled={!!actionLoading[bill.id]}
                          className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors disabled:opacity-50"
                          title="AI Review"
                        >
                          {actionLoading[bill.id] === 'review' ? '...' : 'Review'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New Bill Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Νέο Νομοσχέδιο</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Ελληνικά) *</label>
                <input
                  required
                  value={form.title_el}
                  onChange={(e) => setForm({ ...form, title_el: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Αγγλικά)</label>
                <input
                  value={form.title_en}
                  onChange={(e) => setForm({ ...form, title_en: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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

      {/* Edit Modal */}
      {editBill && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Επεξεργασία #{String(editBill.id)}</h2>
              <button onClick={() => setEditBill(null)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>
            <form onSubmit={handleEditSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Ελληνικά)</label>
                <textarea
                  value={editForm.title_el}
                  onChange={(e) => setEditForm({ ...editForm, title_el: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος (Αγγλικά)</label>
                <textarea
                  value={editForm.title_en}
                  onChange={(e) => setEditForm({ ...editForm, title_en: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Σύντομη Περίληψη</label>
                <textarea
                  value={editForm.summary_short_el}
                  onChange={(e) => setEditForm({ ...editForm, summary_short_el: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Επίπεδο Διακυβέρνησης</label>
                <select
                  value={editForm.governance_level}
                  onChange={(e) => setEditForm({ ...editForm, governance_level: e.target.value as GovernanceLevel })}
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
                  value={editForm.source_url}
                  onChange={(e) => setEditForm({ ...editForm, source_url: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditBill(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Ακύρωση
                </button>
                <button
                  type="submit"
                  disabled={editSubmitting}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
                >
                  {editSubmitting ? 'Αποθήκευση...' : 'Αποθήκευση'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Text Modal */}
      {textBill && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Κείμενο #{String(textBill.id)}</h2>
              <button onClick={() => setTextBill(null)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>
            <form onSubmit={handleSetText} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Κείμενο Νομοσχεδίου (Ελληνικά)</label>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                  rows={10}
                  placeholder="Εισάγετε το κείμενο του νομοσχεδίου..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setTextBill(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Ακύρωση
                </button>
                <button
                  type="button"
                  onClick={handleAutoScrape}
                  disabled={textSubmitting}
                  className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors disabled:opacity-50"
                >
                  {textSubmitting ? '...' : 'Αυτόματο Scrape'}
                </button>
                <button
                  type="submit"
                  disabled={textSubmitting || !textContent.trim()}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {textSubmitting ? 'Αποθήκευση...' : 'Αποθήκευση'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Party Votes Modal */}
      {partyBill && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Ψήφοι Κομμάτων #{String(partyBill.id)}</h2>
              <button onClick={() => setPartyBill(null)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>
            <form onSubmit={handlePartySubmit} className="p-6 space-y-3">
              {PARTIES.map((party) => (
                <div key={party} className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 w-20">{party}</span>
                  <select
                    value={partyVotes[party] || '—'}
                    onChange={(e) => setPartyVotes({ ...partyVotes, [party]: e.target.value })}
                    className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {PARTY_VOTE_OPTIONS.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              ))}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setPartyBill(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Ακύρωση
                </button>
                <button
                  type="submit"
                  disabled={partySubmitting}
                  className="flex-1 px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors disabled:opacity-50"
                >
                  {partySubmitting ? 'Αποθήκευση...' : 'Αποθήκευση'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

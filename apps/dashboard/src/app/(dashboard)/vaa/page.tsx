'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

const CATEGORIES = [
  'Οικονομία', 'Κοινωνία', 'Περιβάλλον', 'Υγεία',
  'Παιδεία', 'Εξωτερική Πολιτική', 'Δικαιοσύνη',
]

const PARTIES = ['ΝΔ', 'ΣΥΡΙΖΑ', 'ΠΑΣΟΚ', 'ΚΚΕ', 'ΕΛ', 'ΝΙΚΗ', 'ΠΛ', 'ΣΠΑΡΤ']

const POSITION_OPTIONS = [
  { value: -2, label: 'Πολύ Αρνητικό (-2)' },
  { value: -1, label: 'Αρνητικό (-1)' },
  { value: 0, label: 'Ουδέτερο (0)' },
  { value: 1, label: 'Θετικό (+1)' },
  { value: 2, label: 'Πολύ Θετικό (+2)' },
]

interface VAAStatement {
  id?: number
  text_el?: string
  text_en?: string
  category?: string
  is_active?: boolean
  [key: string]: unknown
}

interface VAAParty {
  id?: number
  name?: string
  abbreviation?: string
  [key: string]: unknown
}

export default function VAAPage() {
  const [statements, setStatements] = useState<VAAStatement[]>([])
  const [parties, setParties] = useState<VAAParty[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal state
  const [showModal, setShowModal] = useState(false)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalResult, setModalResult] = useState<string | null>(null)

  // New statement form
  const [formTextEl, setFormTextEl] = useState('')
  const [formTextEn, setFormTextEn] = useState('')
  const [formCategory, setFormCategory] = useState(CATEGORIES[0])
  const [partyPositions, setPartyPositions] = useState<Record<string, number>>(
    Object.fromEntries(PARTIES.map(p => [p, 0]))
  )

  // Active toggles (local optimistic)
  const [activeOverrides, setActiveOverrides] = useState<Record<string | number, boolean>>({})

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [stmtsRes, partiesRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/vaa/statements`).then(r => r.json()),
          fetch(`${API}/api/v1/vaa/parties`).then(r => r.json()),
        ])
        if (stmtsRes.status === 'fulfilled') {
          const data = stmtsRes.value as unknown
          setStatements(Array.isArray(data) ? data : ((data as Record<string, unknown>)?.statements as VAAStatement[] ?? []))
        }
        if (partiesRes.status === 'fulfilled') {
          const data = partiesRes.value as unknown
          setParties(Array.isArray(data) ? data : ((data as Record<string, unknown>)?.parties as VAAParty[] ?? []))
        }
      } catch (e) {
        setError(String(e))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  function toggleActive(id: string | number, current: boolean) {
    setActiveOverrides(prev => ({ ...prev, [id]: !current }))
  }

  function resetModal() {
    setFormTextEl('')
    setFormTextEn('')
    setFormCategory(CATEGORIES[0])
    setPartyPositions(Object.fromEntries(PARTIES.map(p => [p, 0])))
    setModalResult(null)
  }

  async function handleCreateStatement() {
    setModalLoading(true)
    setModalResult(null)
    try {
      const res = await fetch(`/api/proxy/admin/vaa/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text_el: formTextEl,
          text_en: formTextEn,
          category: formCategory,
          party_positions: partyPositions,
        }),
      })
      if (res.ok) {
        const data = await res.json() as VAAStatement
        setStatements(prev => [...prev, data])
        setModalResult('Η θέση δημιουργήθηκε επιτυχώς')
        setTimeout(() => { setShowModal(false); resetModal() }, 1500)
      } else if (res.status === 404) {
        setModalResult('Backend endpoint σε ανάπτυξη — η θέση δεν αποθηκεύτηκε')
      } else {
        const data = await res.json() as Record<string, unknown>
        setModalResult(`Σφάλμα: ${String(data?.detail ?? res.status)}`)
      }
    } catch {
      setModalResult('Backend endpoint σε ανάπτυξη — η θέση δεν αποθηκεύτηκε')
    } finally {
      setModalLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{String('VAA Θέσεις')}</h1>
        <button
          onClick={() => { resetModal(); setShowModal(true) }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          {String('+ Νέα Θέση')}
        </button>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">{String('Φόρτωση...')}</div>
      ) : error ? (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{String(error)}</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          {statements.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">{String('Δεν βρέθηκαν θέσεις')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Κείμενο (EL)</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Κατηγορία</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Ενεργό</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Ενέργειες</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {statements.map((stmt, i) => {
                    const id = stmt.id ?? i
                    const isActive = id in activeOverrides ? activeOverrides[id] : (stmt.is_active ?? true)
                    return (
                      <tr key={String(id)} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 text-gray-500 font-mono text-xs">{String(id)}</td>
                        <td className="px-4 py-3 text-gray-800 max-w-xs">
                          <div className="truncate">{String(stmt.text_el ?? stmt.text_en ?? '—')}</div>
                        </td>
                        <td className="px-4 py-3">
                          {stmt.category ? (
                            <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                              {String(stmt.category)}
                            </span>
                          ) : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => toggleActive(id, isActive)}
                            role="switch"
                            aria-checked={isActive}
                            className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 cursor-pointer ${isActive ? 'bg-green-500' : 'bg-gray-300'}`}
                          >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${isActive ? 'translate-x-4' : 'translate-x-0'}`} />
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button
                              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                              onClick={() => {/* edit placeholder */}}
                            >
                              {String('Επεξεργασία')}
                            </button>
                            <button
                              className="text-xs text-red-500 hover:text-red-700 font-medium"
                              onClick={() => setStatements(prev => prev.filter((_, j) => j !== i))}
                            >
                              {String('Διαγραφή')}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {parties.length > 0 && (
        <div className="mt-4 text-xs text-gray-400">
          {String('Κόμματα:')} {parties.map(p => String(p.abbreviation ?? p.name ?? '')).join(', ')}
        </div>
      )}

      {/* New Statement Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">{String('Νέα Θέση VAA')}</h2>
              <button
                onClick={() => { setShowModal(false); resetModal() }}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-700">
                {String('Σημείωση: Ο backend endpoint /api/v1/admin/vaa/create είναι σε ανάπτυξη. Η φόρμα είναι έτοιμη.')}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{String('Κείμενο (EL)')}</label>
                <textarea
                  rows={3}
                  value={formTextEl}
                  onChange={(e) => setFormTextEl(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{String('Κείμενο (EN)')}</label>
                <textarea
                  rows={3}
                  value={formTextEn}
                  onChange={(e) => setFormTextEn(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{String('Κατηγορία')}</label>
                <select
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {CATEGORIES.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">{String('Θέσεις Κομμάτων')}</div>
                <div className="space-y-2">
                  {PARTIES.map(party => (
                    <div key={party} className="flex items-center gap-3">
                      <span className="text-sm font-medium text-gray-700 w-16">{String(party)}</span>
                      <select
                        value={partyPositions[party] ?? 0}
                        onChange={(e) => setPartyPositions(prev => ({ ...prev, [party]: Number(e.target.value) }))}
                        className="flex-1 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {POSITION_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              {modalResult && (
                <div className={`p-3 rounded-lg text-sm font-medium ${modalResult.startsWith('Σφάλμα') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                  {String(modalResult)}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex gap-2 justify-end">
              <button
                onClick={() => { setShowModal(false); resetModal() }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                {String('Ακύρωση')}
              </button>
              <button
                onClick={handleCreateStatement}
                disabled={modalLoading || !formTextEl.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {modalLoading ? String('Αποθήκευση...') : String('Αποθήκευση')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

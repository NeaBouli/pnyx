'use client'

import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface Bill {
  id: number
  title_el: string
  status: string
}

interface VoteResults {
  bill_id: number
  total_votes: number
  citizen_votes: number
  yes: number
  no: number
  abstain: number
  dont_know: number
  divergence_score?: number
  representation_score?: number
  parliament_vote?: string
}

interface MPParty {
  party: string
  abbreviation: string
  alignment_score: number
  aligned_count: number
  total_count: number
}

const VOTE_COLORS: Record<string, string> = {
  'ΝΑΙ': '#16a34a',
  'ΟΧΙ': '#dc2626',
  'ΑΠΟΧΗ': '#9ca3af',
  'ΔΕΝ ΞΕΡΩ': '#ca8a04',
}

const PIE_COLORS = ['#16a34a', '#dc2626', '#9ca3af', '#ca8a04']

export default function VotesPage() {
  const [bills, setBills] = useState<Bill[]>([])
  const [selectedBillId, setSelectedBillId] = useState<number | null>(null)
  const [results, setResults] = useState<VoteResults | null>(null)
  const [loadingBills, setLoadingBills] = useState(true)
  const [loadingResults, setLoadingResults] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mpRanking, setMpRanking] = useState<MPParty[]>([])
  const [representation, setRepresentation] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    async function loadBills() {
      try {
        const r = await fetch(`${API}/api/v1/bills?limit=100`)
        const data = await r.json()
        setBills(Array.isArray(data) ? data : data.bills ?? [])
      } catch {
        setError('Αδύνατη η φόρτωση νομοσχεδίων')
      } finally {
        setLoadingBills(false)
      }
    }
    loadBills()
  }, [])

  // Load MP ranking and representation
  useEffect(() => {
    async function loadExtra() {
      try {
        const [mpRes, repRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/mp/ranking`).then(r => r.json()),
          fetch(`${API}/api/v1/analytics/representation`).then(r => r.json()),
        ])
        if (mpRes.status === 'fulfilled' && mpRes.value) {
          const parties = Array.isArray(mpRes.value) ? mpRes.value : mpRes.value.parties ?? []
          setMpRanking(parties)
        }
        if (repRes.status === 'fulfilled') setRepresentation(repRes.value)
      } catch { /* non-critical */ }
    }
    loadExtra()
  }, [])

  useEffect(() => {
    if (!selectedBillId) { setResults(null); return }
    async function loadResults() {
      setLoadingResults(true)
      setError(null)
      try {
        const r = await fetch(`${API}/api/v1/bills/${selectedBillId}/results`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setResults(await r.json())
      } catch {
        setError('Αδύνατη η φόρτωση αποτελεσμάτων')
        setResults(null)
      } finally {
        setLoadingResults(false)
      }
    }
    loadResults()
  }, [selectedBillId])

  const chartData = results
    ? [
        { name: 'ΝΑΙ', value: results.yes ?? 0 },
        { name: 'ΟΧΙ', value: results.no ?? 0 },
        { name: 'ΑΠΟΧΗ', value: results.abstain ?? 0 },
        { name: 'ΔΕΝ ΞΕΡΩ', value: results.dont_know ?? 0 },
      ]
    : []

  const repScore = representation?.score as number | null

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Αποτελέσματα Ψηφοφοριών</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
        </div>
      )}

      {/* Representation Score */}
      {repScore != null && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-gray-800">Representation Score</h2>
            <span className="text-2xl font-bold text-purple-600">{(repScore * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3">
            <div className="bg-purple-500 h-3 rounded-full transition-all" style={{ width: `${Math.min(100, repScore * 100)}%` }} />
          </div>
          <div className="text-xs text-gray-400 mt-1">Πόσο αντιπροσωπεύει η Βουλή τους πολίτες</div>
        </div>
      )}

      {/* Bill selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Επιλογή Νομοσχεδίου</label>
        {loadingBills ? (
          <div className="text-sm text-gray-500">Φόρτωση νομοσχεδίων...</div>
        ) : (
          <select
            value={selectedBillId ?? ''}
            onChange={(e) => setSelectedBillId(e.target.value ? Number(e.target.value) : null)}
            className="w-full max-w-md border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">-- Επιλέξτε νομοσχέδιο --</option>
            {bills.map((b) => (
              <option key={b.id} value={b.id}>#{b.id} — {b.title_el}</option>
            ))}
          </select>
        )}
      </div>

      {loadingResults && <div className="p-8 text-center text-gray-500">Φόρτωση αποτελεσμάτων...</div>}

      {results && !loadingResults && (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Συνολικές Ψήφοι</div>
              <div className="text-2xl font-bold text-blue-600">{results.total_votes?.toLocaleString('el-GR') ?? '—'}</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Ψήφοι Πολιτών</div>
              <div className="text-2xl font-bold text-blue-600">{results.citizen_votes?.toLocaleString('el-GR') ?? '—'}</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Divergence Score</div>
              <div className={`text-2xl font-bold ${results.divergence_score != null && results.divergence_score > 0.3 ? 'text-red-600' : 'text-green-600'}`}>
                {results.divergence_score != null ? `${(results.divergence_score * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Βουλή</div>
              <div className="text-2xl font-bold text-gray-800">
                {results.parliament_vote ?? '—'}
              </div>
            </div>
          </div>

          {/* Side by side: Pie + Bar */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Pie chart - citizen distribution */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-base font-semibold text-gray-800 mb-4">Κατανομή Πολιτών</h2>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {chartData.map((entry, i) => (
                      <Cell key={entry.name} fill={PIE_COLORS[i] ?? '#6b7280'} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Bar chart - comparison */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-base font-semibold text-gray-800 mb-4">Κατανομή Ψήφων</h2>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value: number) => [value.toLocaleString('el-GR'), 'Ψήφοι']} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={VOTE_COLORS[entry.name] ?? '#6b7280'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Detail table */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Επιλογή</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Ψήφοι</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Ποσοστό</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {chartData.map((row) => {
                  const pct = results.total_votes > 0 ? ((row.value / results.total_votes) * 100).toFixed(1) : '0.0'
                  return (
                    <tr key={row.name} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium" style={{ color: VOTE_COLORS[row.name] ?? '#374151' }}>{row.name}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{row.value.toLocaleString('el-GR')}</td>
                      <td className="px-4 py-3 text-right text-gray-500">{pct}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!selectedBillId && !loadingBills && (
        <div className="p-12 text-center text-gray-400 bg-white border border-gray-200 rounded-xl">
          Επιλέξτε νομοσχέδιο για να δείτε τα αποτελέσματα
        </div>
      )}

      {/* MP Ranking */}
      <div className="mt-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Κατάταξη Κομμάτων (MP Ranking)</h2>
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          {mpRanking.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">#</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κόμμα</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Ευθυγράμμιση</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Συμφωνία</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mpRanking.map((party, i) => (
                  <tr key={party.abbreviation ?? i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-400">{i + 1}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {party.party ?? party.abbreviation}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{ width: `${Math.min(100, (party.alignment_score ?? 0) * 100)}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-700">
                          {((party.alignment_score ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-500">
                      {party.aligned_count ?? '—'}/{party.total_count ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-sm text-gray-400">
              Δεν υπάρχουν δεδομένα κατάταξης κομμάτων
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

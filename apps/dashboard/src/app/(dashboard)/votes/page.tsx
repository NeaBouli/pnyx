'use client'

import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const API = process.env.NEXT_PUBLIC_EKKLESIA_API || 'https://api.ekklesia.gr'

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
}

const VOTE_COLORS: Record<string, string> = {
  ΝΑΙ: '#16a34a',
  ΟΧΙ: '#dc2626',
  ΑΠΟΧΗ: '#9ca3af',
  'ΔΕΝ ΞΕΡΩ': '#ca8a04',
}

export default function VotesPage() {
  const [bills, setBills] = useState<Bill[]>([])
  const [selectedBillId, setSelectedBillId] = useState<number | null>(null)
  const [results, setResults] = useState<VoteResults | null>(null)
  const [loadingBills, setLoadingBills] = useState(true)
  const [loadingResults, setLoadingResults] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  useEffect(() => {
    if (!selectedBillId) {
      setResults(null)
      return
    }
    async function loadResults() {
      setLoadingResults(true)
      setError(null)
      try {
        const r = await fetch(`${API}/api/v1/bills/${selectedBillId}/results`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const data = await r.json()
        setResults(data)
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

  const divergencePct =
    results?.divergence_score != null
      ? `${(results.divergence_score * 100).toFixed(1)}%`
      : '—'

  const representationPct =
    results?.representation_score != null
      ? `${(results.representation_score * 100).toFixed(1)}%`
      : '—'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Αποτελέσματα Ψηφοφοριών</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
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
              <option key={b.id} value={b.id}>
                #{b.id} — {b.title_el}
              </option>
            ))}
          </select>
        )}
      </div>

      {loadingResults && (
        <div className="p-8 text-center text-gray-500">Φόρτωση αποτελεσμάτων...</div>
      )}

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
                {divergencePct}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">Πολίτες vs Βουλή</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Representation Score</div>
              <div className="text-2xl font-bold text-purple-600">{representationPct}</div>
            </div>
          </div>

          {/* Bar chart */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Κατανομή Ψήφων</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number) => [value.toLocaleString('el-GR'), 'Ψήφοι']}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={VOTE_COLORS[entry.name] ?? '#6b7280'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
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
                  const pct = results.total_votes > 0
                    ? ((row.value / results.total_votes) * 100).toFixed(1)
                    : '0.0'
                  return (
                    <tr key={row.name} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium" style={{ color: VOTE_COLORS[row.name] ?? '#374151' }}>
                        {row.name}
                      </td>
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
    </div>
  )
}

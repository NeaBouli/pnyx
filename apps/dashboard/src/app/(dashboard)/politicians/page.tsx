'use client'

import { useCallback, useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface Politician {
  ada_number: string
  role: string
  region: string
  org_label: string
  governance_level: string
  avg_score: number | null
  evaluator_count: number
}

export default function PoliticiansPage() {
  const [politicians, setPoliticians] = useState<Politician[]>([])
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v1/politicians/`)
      if (r.ok) setPoliticians(await r.json())
    } catch { /* */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const totalEvaluations = politicians.reduce((sum, p) => sum + p.evaluator_count, 0)
  const scored = politicians.filter(p => p.avg_score !== null)
  const avgAll = scored.length > 0
    ? (scored.reduce((s, p) => s + (p.avg_score || 0), 0) / scored.length).toFixed(1)
    : '—'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Πολιτικοί — Αξιολόγηση</h1>
          <p className="text-sm text-gray-500 mt-1">MOD-25: Liquide Evaluierung von Volksvertretern</p>
        </div>
        <button
          onClick={() => { setLoading(true); loadData() }}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Aktualisieren
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500">Εκπρόσωποι</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{politicians.length}</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500">Ø Βαθμολογία</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{avgAll}</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500">Αξιολογήσεις</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{totalEvaluations}</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-3">
            {[1,2,3].map(i => <div key={i} className="animate-pulse bg-gray-200 rounded h-10" />)}
          </div>
        ) : politicians.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            Δεν υπάρχουν αξιολογούμενοι εκπρόσωποι.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Οργανισμός / Εκπρόσωπος</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ρόλος</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Περιοχή</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Αξιολογήσεις</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Ø Score</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">ADA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {politicians.map(p => {
                  const scoreColor = p.avg_score === null ? 'text-gray-400'
                    : p.avg_score >= 2 ? 'text-green-600'
                    : p.avg_score >= 0 ? 'text-yellow-600'
                    : 'text-red-600'
                  return (
                    <tr key={p.ada_number} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-900 font-medium">{p.org_label || p.ada_number}</td>
                      <td className="px-4 py-3 text-gray-700">{p.role}</td>
                      <td className="px-4 py-3 text-gray-700">{p.region || '—'}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{p.evaluator_count}</td>
                      <td className={`px-4 py-3 text-right font-bold ${scoreColor}`}>
                        {p.avg_score !== null ? (p.avg_score > 0 ? '+' : '') + p.avg_score.toFixed(1) : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs font-mono">{p.ada_number}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

'use client'

import { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type TimeRange = 30 | 90 | 365

export default function AnalyticsPage() {
  const [range, setRange] = useState<TimeRange>(90)
  const [divergence, setDivergence] = useState<Record<string, unknown>[] | null>(null)
  const [votes, setVotes] = useState<Record<string, unknown>[] | null>(null)
  const [topDiv, setTopDiv] = useState<Record<string, unknown>[] | null>(null)
  const [representation, setRepresentation] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [divRes, voteRes, topRes, repRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/analytics/divergence-trends?days=${range}`).then(r => r.json()),
        fetch(`${API}/api/v1/analytics/votes-timeline?days=30`).then(r => r.json()),
        fetch(`${API}/api/v1/analytics/top-divergence?limit=10`).then(r => r.json()),
        fetch(`${API}/api/v1/analytics/representation`).then(r => r.json()),
      ])
      const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
      setDivergence(v(divRes) as Record<string, unknown>[] | null)
      setVotes(v(voteRes) as Record<string, unknown>[] | null)
      const td = v(topRes)
      setTopDiv(Array.isArray(td) ? td : (td as Record<string, unknown>)?.bills as Record<string, unknown>[] ?? null)
      setRepresentation(v(repRes) as Record<string, unknown> | null)
      setLoading(false)
    }
    load()
  }, [range])

  const repScore = representation?.score as number | null

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Αναλυτικά</h1>

      {loading && <div className="p-8 text-center text-gray-500">Φόρτωση...</div>}

      {!loading && (
        <div className="space-y-6">
          {/* Representation Score */}
          {repScore != null && (
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-base font-semibold text-gray-800 mb-3">Representation Score</h2>
              <div className="flex items-end gap-4">
                <div className="text-5xl font-bold text-purple-600">{(repScore * 100).toFixed(1)}%</div>
                <div className="text-sm text-gray-400 pb-2">Συνολική αντιπροσώπευση πολιτών από τη Βουλή</div>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-4 mt-4">
                <div className="bg-purple-500 h-4 rounded-full transition-all" style={{ width: `${Math.min(100, repScore * 100)}%` }} />
              </div>
            </div>
          )}

          {/* Divergence trends with range toggle */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-800">Divergence Trends</h2>
              <div className="flex gap-1">
                {([30, 90, 365] as TimeRange[]).map(d => (
                  <button
                    key={d}
                    onClick={() => setRange(d)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                      range === d ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {d}ημ
                  </button>
                ))}
              </div>
            </div>
            {Array.isArray(divergence) && divergence.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={divergence} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v?.slice(5) ?? ''} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="divergence" stroke="#dc2626" dot={false} strokeWidth={2} name="Divergence" />
                  {divergence[0]?.avg_divergence !== undefined && (
                    <Line type="monotone" dataKey="avg_divergence" stroke="#9333ea" dot={false} strokeWidth={1.5} name="Μέσος όρος" strokeDasharray="5 5" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Votes timeline */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Ψήφοι ανά Ημέρα (30 ημέρες)</h2>
            {Array.isArray(votes) && votes.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={votes} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v?.slice(5) ?? ''} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="votes" fill="#2563eb" radius={[4, 4, 0, 0]} name="Ψήφοι" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-40 flex items-center justify-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Top 10 Divergence */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Top 10 Bills κατά Divergence</h2>
            </div>
            {Array.isArray(topDiv) && topDiv.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">#</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Bill</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-500">Ψήφοι</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-500">Divergence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {topDiv.slice(0, 10).map((item, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 text-gray-400">{i + 1}</td>
                      <td className="px-4 py-2.5 text-gray-800 truncate max-w-xs">
                        #{item.bill_id as number} — {item.title_el as string ?? item.title as string ?? ''}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-500">
                        {(item.total_votes as number)?.toLocaleString('el-GR') ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span className="font-mono text-red-600">
                          {((item.divergence_score as number ?? item.divergence as number ?? 0) * 100).toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα</div>
            )}
          </div>

          {/* Placeholders */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
              <div className="text-2xl mb-2">📊</div>
              <div className="text-sm font-medium text-gray-500">Στατιστικά Επισκεπτών</div>
              <div className="text-xs text-gray-400 mt-1">Κανένα analytics tool -- Σύσταση: Plausible</div>
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
              <div className="text-2xl mb-2">🐛</div>
              <div className="text-sm font-medium text-gray-500">App Crashes</div>
              <div className="text-xs text-gray-400 mt-1">Κανένα crash-reporting -- Σύσταση: Sentry Free</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

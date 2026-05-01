'use client'

import { useState, useEffect } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts'

const API = process.env.NEXT_PUBLIC_EKKLESIA_API || 'https://api.ekklesia.gr'

interface CPLMData {
  x: number
  y: number
  total_votes?: number
  updated_at?: string
}

interface CPLMHistoryEntry {
  date: string
  x: number
  y: number
}

export default function CPLMPage() {
  const [current, setCurrent] = useState<CPLMData | null>(null)
  const [history, setHistory] = useState<CPLMHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [currentRes, historyRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/public/cplm`),
          fetch(`${API}/api/v1/public/cplm/history`),
        ])

        if (currentRes.status === 'fulfilled' && currentRes.value.ok) {
          const data = await currentRes.value.json()
          setCurrent(data)
        }

        if (historyRes.status === 'fulfilled' && historyRes.value.ok) {
          const data = await historyRes.value.json()
          setHistory(Array.isArray(data) ? data.slice(-30) : [])
        }
      } catch {
        setError('Αδύνατη η φόρτωση CPLM δεδομένων')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const scatterPoint = current ? [{ x: current.x, y: current.y }] : []

  const quadrantLabel = (x: number, y: number): string => {
    if (x >= 0 && y >= 0) return 'Φιλελεύθερο / Αριστερό'
    if (x < 0 && y >= 0) return 'Αυταρχικό / Αριστερό'
    if (x >= 0 && y < 0) return 'Φιλελεύθερο / Δεξιό'
    return 'Αυταρχικό / Δεξιό'
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">CPLM — Συλλογικός Πολιτικός Χάρτης</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Οικονομία (X-Άξονας)</div>
              <div className="text-2xl font-bold text-blue-600">
                {current ? current.x.toFixed(2) : '—'}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">-10 (Κρατικό) → +10 (Αγορά)</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Κοινωνία (Y-Άξονας)</div>
              <div className="text-2xl font-bold text-purple-600">
                {current ? current.y.toFixed(2) : '—'}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">-10 (Αυταρχικό) → +10 (Φιλελεύθερο)</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Τεταρτημόριο</div>
              <div className="text-sm font-semibold text-gray-800 mt-1">
                {current ? quadrantLabel(current.x, current.y) : '—'}
              </div>
              {current?.total_votes != null && (
                <div className="text-xs text-gray-400 mt-1">{current.total_votes.toLocaleString('el-GR')} ψήφοι</div>
              )}
            </div>
          </div>

          {/* Scatter chart */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-1">Τρέχουσα Θέση</h2>
            <p className="text-xs text-gray-500 mb-4">X = Οικονομία, Y = Κοινωνία. Κέντρο = (0, 0)</p>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  type="number"
                  dataKey="x"
                  domain={[-10, 10]}
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Οικονομία', position: 'insideBottom', offset: -4, fontSize: 11 }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  domain={[-10, 10]}
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Κοινωνία', angle: -90, position: 'insideLeft', offset: 8, fontSize: 11 }}
                />
                <Tooltip
                  formatter={(value: number, name: string) => [value.toFixed(2), name === 'x' ? 'Οικονομία' : 'Κοινωνία']}
                />
                <ReferenceLine x={0} stroke="#d1d5db" strokeWidth={1} />
                <ReferenceLine y={0} stroke="#d1d5db" strokeWidth={1} />
                <Scatter
                  data={scatterPoint}
                  fill="#2563eb"
                  r={8}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* History line chart */}
          {history.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-base font-semibold text-gray-800 mb-4">Εξέλιξη (τελευταίες 30 μέρες)</h2>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={history} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v?.slice(5) ?? ''}
                  />
                  <YAxis domain={[-10, 10]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="x" stroke="#2563eb" dot={false} name="Οικονομία" strokeWidth={2} />
                  <Line type="monotone" dataKey="y" stroke="#9333ea" dot={false} name="Κοινωνία" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                <span><span className="inline-block w-3 h-0.5 bg-blue-600 mr-1 align-middle"></span>Οικονομία</span>
                <span><span className="inline-block w-3 h-0.5 bg-purple-600 mr-1 align-middle"></span>Κοινωνία</span>
              </div>
            </div>
          )}

          {current?.updated_at && (
            <p className="text-xs text-gray-400">
              Τελευταία ενημέρωση: {new Date(current.updated_at).toLocaleString('el-GR')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

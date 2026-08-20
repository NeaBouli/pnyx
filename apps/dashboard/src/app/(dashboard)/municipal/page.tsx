'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

interface Periferia {
  id: number
  name_el: string
  code: string
}

interface Dimos {
  id: number
  name_el: string
  population?: number | null
}

interface Decision {
  ada: string
  subject: string
  organization_label?: string | null
  publish_timestamp?: string | null
  document_url?: string | null
}

interface DecisionResponse {
  total: number
  data: Decision[]
}

interface ScraperJob {
  name: string
  status?: string
  last_run?: string | null
  last_success?: string | null
  last_error?: string | null
  error_count?: number
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: 'no-store', signal })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'AbortError'
}

function safeDocumentUrl(value?: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : null
  } catch {
    return null
  }
}

export default function MunicipalPage() {
  const [periferies, setPeriferies] = useState<Periferia[]>([])
  const [dimos, setDimos] = useState<Dimos[]>([])
  const [selectedPeriferia, setSelectedPeriferia] = useState('')
  const [selectedDimos, setSelectedDimos] = useState('')
  const [decisions, setDecisions] = useState<DecisionResponse | null>(null)
  const [scraper, setScraper] = useState<ScraperJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [decisionLoading, setDecisionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [regionResult, jobResult] = await Promise.allSettled([
        getJson<Periferia[]>('/api/v1/periferia'),
        getJson<{ scrapers?: ScraperJob[] }>('/api/v1/scraper/jobs'),
      ])
      if (regionResult.status === 'rejected') throw regionResult.reason
      setPeriferies(regionResult.value)
      setScraper(
        jobResult.status === 'fulfilled'
          ? jobResult.value.scrapers?.find((job) => job.name === 'diavgeia_municipal') ?? null
          : null,
      )
    } catch (reason) {
      setError(`Αδυναμία φόρτωσης δεδομένων δήμων: ${String(reason)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timeout = window.setTimeout(() => { void loadOverview() }, 0)
    return () => window.clearTimeout(timeout)
  }, [loadOverview])

  useEffect(() => {
    if (!selectedPeriferia) return

    const controller = new AbortController()
    let active = true

    getJson<Dimos[]>(`/api/v1/periferia/${selectedPeriferia}/dimos`, controller.signal)
      .then((rows) => {
        if (!active) return
        setDimos(rows)
        setSelectedDimos('')
        setDecisions(null)
      })
      .catch((reason) => {
        if (active && !isAbortError(reason)) setError(`Αδυναμία φόρτωσης δήμων: ${String(reason)}`)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [selectedPeriferia])

  useEffect(() => {
    if (!selectedDimos) return

    const controller = new AbortController()
    let active = true

    getJson<DecisionResponse>(`/api/v1/municipal/${selectedDimos}/decisions?limit=20`, controller.signal)
      .then((rows) => {
        if (active) setDecisions(rows)
      })
      .catch((reason) => {
        if (active && !isAbortError(reason)) setError(`Αδυναμία φόρτωσης αποφάσεων: ${String(reason)}`)
      })
      .finally(() => {
        if (active) setDecisionLoading(false)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [selectedDimos])

  const selectedMunicipality = useMemo(
    () => dimos.find((entry) => String(entry.id) === selectedDimos),
    [dimos, selectedDimos],
  )
  const scraperOk = scraper?.status === 'ok' || scraper?.status === 'success'

  function handlePeriferiaChange(value: string) {
    setError(null)
    setSelectedPeriferia(value)
    setDimos([])
    setSelectedDimos('')
    setDecisions(null)
  }

  function handleDimosChange(value: string) {
    setError(null)
    setDecisionLoading(Boolean(value))
    setSelectedDimos(value)
    setDecisions(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Δήμοι & Περιφέρειες</h1>
          <p className="mt-1 text-sm text-gray-500">Ζωντανή επισκόπηση των καταλόγων και αποφάσεων της Διαύγειας.</p>
        </div>
        <button
          onClick={loadOverview}
          disabled={loading}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Ανανέωση...' : 'Ανανέωση'}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-medium uppercase text-gray-500">Ενεργές Περιφέρειες</div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{loading ? '—' : periferies.length}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-medium uppercase text-gray-500">Δήμοι στην επιλογή</div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{selectedPeriferia ? dimos.length : '—'}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium uppercase text-gray-500">Συγχρονισμός Δήμων</div>
            <span className={`h-2.5 w-2.5 rounded-full ${scraperOk ? 'bg-green-500' : 'bg-red-500'}`} />
          </div>
          <div className="mt-2 text-sm font-semibold text-gray-900">{scraperOk ? 'Λειτουργεί' : scraper ? 'Πρόβλημα' : 'Χωρίς δεδομένα'}</div>
          <div className="mt-1 text-xs text-gray-500">
            {scraper?.last_success ? `Τελευταία επιτυχία: ${new Date(scraper.last_success).toLocaleString('el-GR')}` : 'Δεν έχει καταγραφεί επιτυχία'}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 font-semibold text-gray-800">Έλεγχος δημοτικών δεδομένων</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="text-sm font-medium text-gray-700">
            Περιφέρεια
            <select
              value={selectedPeriferia}
              onChange={(event) => handlePeriferiaChange(event.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-normal"
            >
              <option value="">— Επιλέξτε Περιφέρεια —</option>
              {periferies.map((region) => <option key={region.id} value={region.id}>{region.name_el}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">
            Δήμος
            <select
              value={selectedDimos}
              onChange={(event) => handleDimosChange(event.target.value)}
              disabled={!selectedPeriferia || dimos.length === 0}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-normal disabled:bg-gray-100 disabled:text-gray-400"
            >
              <option value="">— Επιλέξτε Δήμο —</option>
              {dimos.map((entry) => <option key={entry.id} value={entry.id}>{entry.name_el}</option>)}
            </select>
          </label>
        </div>
        {selectedMunicipality && (
          <div className="mt-4 text-xs text-gray-500">
            Δήμος: {selectedMunicipality.name_el}
            {selectedMunicipality.population ? ` · Πληθυσμός: ${selectedMunicipality.population.toLocaleString('el-GR')}` : ''}
          </div>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 className="font-semibold text-gray-800">Αποφάσεις Διαύγειας</h2>
          <span className="text-xs text-gray-500">{decisions ? `${decisions.total} συνολικά` : 'Επιλέξτε Δήμο'}</span>
        </div>
        {decisionLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Φόρτωση...</div>
        ) : decisions?.data.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">ΑΔΑ</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Θέμα</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Ημερομηνία</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {decisions.data.map((decision) => {
                  const documentUrl = safeDocumentUrl(decision.document_url)
                  return <tr key={decision.ada} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                      {documentUrl ? <a className="text-blue-600 hover:underline" href={documentUrl} target="_blank" rel="noreferrer">{decision.ada}</a> : decision.ada}
                    </td>
                    <td className="max-w-2xl px-4 py-3 text-gray-700">{decision.subject}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-500">
                      {decision.publish_timestamp ? new Date(decision.publish_timestamp).toLocaleDateString('el-GR') : '—'}
                    </td>
                  </tr>
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-gray-500">
            {selectedDimos ? 'Δεν βρέθηκαν δημόσιες αποφάσεις για τον επιλεγμένο Δήμο.' : 'Επιλέξτε Περιφέρεια και Δήμο.'}
          </div>
        )}
      </div>
    </div>
  )
}

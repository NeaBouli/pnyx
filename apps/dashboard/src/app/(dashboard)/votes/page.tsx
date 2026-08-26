'use client'

import { useState, useEffect, useDeferredValue } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts'
import { arrayFrom, asRecord, numberFrom } from '@/lib/response'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

const PARTIES = ['ΝΔ', 'ΣΥΡΙΖΑ', 'ΠΑΣΟΚ', 'ΚΚΕ', 'ΕΛ', 'ΝΙΚΗ', 'ΠΛ', 'ΣΠΑΡΤ'] as const

type BillStatus = 'ANNOUNCED' | 'ACTIVE' | 'WINDOW_24H' | 'PARLIAMENT_VOTED' | 'OPEN_END'
type GovernanceLevel = 'NATIONAL' | 'REGIONAL' | 'MUNICIPAL' | 'COMMUNITY' | 'INSTITUTIONAL'
type ResultsVisibility = 'HIDDEN' | 'WINDOW' | 'ALWAYS'
type BillSort = 'DATE_DESC' | 'DATE_ASC' | 'TITLE_ASC' | 'ID_ASC'

interface Bill {
  id: string
  title_el: string
  title_en?: string | null
  categories?: unknown[] | null
  status: BillStatus
  governance_level?: GovernanceLevel | null
  vote_date?: string | null
  display_date?: string | null
  created_at?: string | null
  results_visibility?: ResultsVisibility | null
  source?: string | null
}

interface VoteResults {
  bill_id: string
  total_votes: number
  tier1_vote_count: number
  zk_vote_count: number
  yes_count: number
  no_count: number
  abstain_count: number
  unknown_count: number
  divergence?: {
    score: number
    parliament_result?: string | null
  } | null
  results_hidden?: boolean
  disclaimer_el?: string
}

interface MPParty {
  party: string
  abbreviation: string
  alignment_score: number
  aligned_count: number
  total_count: number
}

interface PartyCompare {
  party: string
  alignment_score: number
  bills_compared: number
}

const VOTE_COLORS: Record<string, string> = {
  'ΝΑΙ': '#16a34a',
  'ΟΧΙ': '#dc2626',
  'ΑΠΟΧΗ': '#9ca3af',
  'ΔΕΝ ΞΕΡΩ': '#ca8a04',
}

const PIE_COLORS = ['#16a34a', '#dc2626', '#9ca3af', '#ca8a04']

const PARTY_BAR_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#06b6d4', '#ec4899', '#f97316',
]

const STATUS_LABELS: Record<BillStatus, string> = {
  ANNOUNCED: 'Ανακοινώθηκε',
  ACTIVE: 'Ενεργό',
  WINDOW_24H: 'Παράθυρο 24ω',
  PARLIAMENT_VOTED: 'Ψηφίστηκε',
  OPEN_END: 'Ανοιχτό',
}

const GOVERNANCE_LABELS: Record<GovernanceLevel, string> = {
  NATIONAL: 'Εθνικό',
  REGIONAL: 'Περιφερειακό',
  MUNICIPAL: 'Δημοτικό',
  COMMUNITY: 'Κοινοτικό',
  INSTITUTIONAL: 'Θεσμικό',
}

const VISIBILITY_LABELS: Record<ResultsVisibility, string> = {
  HIDDEN: 'Κρυφά',
  WINDOW: 'Παράθυρο 24ω',
  ALWAYS: 'Πάντα ορατά',
}

const SOURCE_LABELS: Record<string, string> = {
  PARLIAMENT: 'Βουλή',
  DIAVGEIA: 'Διαύγεια',
}

const STATUS_OPTIONS = Object.keys(STATUS_LABELS) as BillStatus[]
const GOVERNANCE_OPTIONS = Object.keys(GOVERNANCE_LABELS) as GovernanceLevel[]
const VISIBILITY_OPTIONS = Object.keys(VISIBILITY_LABELS) as ResultsVisibility[]
const BILL_PAGE_SIZE = 100

function billDate(bill: Bill): string {
  return (bill.display_date || bill.vote_date || bill.created_at || '').slice(0, 10)
}

type VotesMainTab = 'results' | 'party-compare'

export default function VotesPage() {
  const [mainTab, setMainTab] = useState<VotesMainTab>('results')
  const [bills, setBills] = useState<Bill[]>([])
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null)
  const [results, setResults] = useState<VoteResults | null>(null)
  const [loadingBills, setLoadingBills] = useState(true)
  const [loadingResults, setLoadingResults] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mpRanking, setMpRanking] = useState<MPParty[]>([])
  const [representation, setRepresentation] = useState<Record<string, unknown> | null>(null)
  const [partyCompare, setPartyCompare] = useState<PartyCompare[]>([])
  const [loadingCompare, setLoadingCompare] = useState(false)
  const [partyCompareSortDir, setPartyCompareSortDir] = useState<'desc' | 'asc'>('desc')
  const [billSearch, setBillSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<BillStatus | 'ALL'>('ALL')
  const [governanceFilter, setGovernanceFilter] = useState<GovernanceLevel | 'ALL'>('ALL')
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [visibilityFilter, setVisibilityFilter] = useState<ResultsVisibility | 'ALL'>('ALL')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [billSort, setBillSort] = useState<BillSort>('DATE_DESC')
  const [totalBills, setTotalBills] = useState(0)
  const [availableCategories, setAvailableCategories] = useState<string[]>([])
  const [billOffset, setBillOffset] = useState(0)
  const deferredBillSearch = useDeferredValue(billSearch)

  useEffect(() => {
    const controller = new AbortController()

    async function loadBills() {
      setLoadingBills(true)
      try {
        const params = new URLSearchParams({
          limit: String(BILL_PAGE_SIZE),
          offset: String(billOffset),
          sort: billSort,
        })
        if (deferredBillSearch.trim()) params.set('q', deferredBillSearch.trim())
        if (statusFilter !== 'ALL') params.set('status', statusFilter)
        if (governanceFilter !== 'ALL') params.set('governance', governanceFilter)
        if (sourceFilter !== 'ALL') params.set('source', sourceFilter)
        if (categoryFilter !== 'ALL') params.set('category', categoryFilter)
        if (visibilityFilter !== 'ALL') params.set('results_visibility', visibilityFilter)
        if (dateFrom) params.set('date_from', dateFrom)
        if (dateTo) params.set('date_to', dateTo)

        const r = await fetch(`${API}/api/v1/public/bills?${params}`, { signal: controller.signal })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const payload = await r.json()
        const loadedBills: Bill[] = Array.isArray(payload?.data) ? payload.data : []
        setBills(loadedBills)
        setTotalBills(Number(payload?.meta?.total) || loadedBills.length)
        setAvailableCategories((current) => [...new Set([
          ...current,
          ...loadedBills.flatMap((bill) => (bill.categories ?? []).map((category) => String(category).trim())),
        ].filter(Boolean))].sort((a, b) => a.localeCompare(b, 'el')))
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') return
        setError('Αδύνατη η φόρτωση νομοσχεδίων')
      } finally {
        if (!controller.signal.aborted) setLoadingBills(false)
      }
    }
    loadBills()
    return () => controller.abort()
  }, [deferredBillSearch, statusFilter, governanceFilter, sourceFilter, categoryFilter, visibilityFilter, dateFrom, dateTo, billSort, billOffset])

  function clearBillSelection() {
    setSelectedBillId(null)
    setResults(null)
    setPartyCompare([])
  }

  function resetBillPage() {
    setBillOffset(0)
    clearBillSelection()
  }

  function resetBillFilters() {
    setBillSearch('')
    setStatusFilter('ALL')
    setGovernanceFilter('ALL')
    setSourceFilter('ALL')
    setCategoryFilter('ALL')
    setVisibilityFilter('ALL')
    setDateFrom('')
    setDateTo('')
    setBillSort('DATE_DESC')
    setBillOffset(0)
    clearBillSelection()
  }

  useEffect(() => {
    async function loadExtra() {
      try {
        const [mpRes, repRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/mp/ranking`).then(r => r.json()),
          fetch(`${API}/api/v1/analytics/representation`).then(r => r.json()),
        ])
        if (mpRes.status === 'fulfilled' && mpRes.value) {
          const parties = arrayFrom<Record<string, unknown>>(mpRes.value, 'ranking', 'parties')
          setMpRanking(parties.map(party => {
            const agreementPct = numberFrom(party.agreement_pct)
            return {
              party: String(party.party_name_el ?? party.party ?? party.party_abbr ?? ''),
              abbreviation: String(party.party_abbr ?? party.abbreviation ?? ''),
              alignment_score: agreementPct != null
                ? agreementPct / 100
                : numberFrom(party.alignment_score, 0) ?? 0,
              aligned_count: numberFrom(party.bills_agree ?? party.aligned_count, 0) ?? 0,
              total_count: numberFrom(party.bills_analyzed ?? party.total_count, 0) ?? 0,
            }
          }))
        }
        if (repRes.status === 'fulfilled') setRepresentation(repRes.value)
      } catch { /* non-critical */ }
    }
    loadExtra()
  }, [])

  // Load results when bill selected
  useEffect(() => {
    if (!selectedBillId) return
    const billId = selectedBillId
    async function loadResults() {
      setLoadingResults(true)
      setError(null)
      try {
        const r = await fetch(`${API}/api/v1/vote/${encodeURIComponent(billId)}/results`)
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

  // Load party compare when bill selected
  useEffect(() => {
    if (!selectedBillId) return
    async function loadCompare() {
      setLoadingCompare(true)
      const compareResults: PartyCompare[] = []
      const settled = await Promise.allSettled(
        PARTIES.map(async (abbr) => {
          try {
            const r = await fetch(`${API}/api/v1/mp/compare/${encodeURIComponent(abbr)}`)
            if (!r.ok) return null
            const data = await r.json()
            const summary = asRecord(data?.summary)
            const party = asRecord(data?.party)
            const agreementPct = numberFrom(summary?.agreement_pct)
            return {
              party: String(party?.abbreviation ?? abbr),
              alignment_score: agreementPct != null
                ? agreementPct / 100
                : numberFrom(data?.alignment_score, 0) ?? 0,
              bills_compared: numberFrom(summary?.bills_analyzed ?? data?.bills_compared, 0) ?? 0,
            } as PartyCompare
          } catch { return null }
        })
      )
      for (const s of settled) {
        if (s.status === 'fulfilled' && s.value) compareResults.push(s.value)
      }
      setPartyCompare(compareResults)
      setLoadingCompare(false)
    }
    loadCompare()
  }, [selectedBillId])

  const chartData = results
    ? [
        { name: 'ΝΑΙ', value: results.yes_count ?? 0 },
        { name: 'ΟΧΙ', value: results.no_count ?? 0 },
        { name: 'ΑΠΟΧΗ', value: results.abstain_count ?? 0 },
        { name: 'ΔΕΝ ΞΕΡΩ', value: results.unknown_count ?? 0 },
      ]
    : []

  const legacyRepScore = numberFrom(representation?.score)
  const repPercent = numberFrom(representation?.cumulative_representation)
    ?? (legacyRepScore != null ? legacyRepScore * 100 : null)
  const divergenceScore = results?.divergence?.score

  const partyChartData = partyCompare.map((p) => ({
    name: p.party,
    score: Math.round((p.alignment_score ?? 0) * 100),
  }))

  // Global party compare from /mp/ranking
  const globalPartySorted = [...mpRanking].sort((a, b) =>
    partyCompareSortDir === 'desc'
      ? (b.alignment_score ?? 0) - (a.alignment_score ?? 0)
      : (a.alignment_score ?? 0) - (b.alignment_score ?? 0)
  )

  const globalPartyChartData = [...mpRanking]
    .sort((a, b) => (b.alignment_score ?? 0) - (a.alignment_score ?? 0))
    .map((p) => ({
      name: p.abbreviation ?? p.party,
      score: Math.round((p.alignment_score ?? 0) * 100),
    }))

  const firstVisibleBill = totalBills > 0 ? billOffset + 1 : 0
  const lastVisibleBill = Math.min(billOffset + bills.length, totalBills)
  const currentBillPage = Math.floor(billOffset / BILL_PAGE_SIZE) + 1
  const totalBillPages = Math.max(1, Math.ceil(totalBills / BILL_PAGE_SIZE))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Αποτελέσματα Ψηφοφοριών</h1>
        <div className="flex items-center gap-2">
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
          <a
            href={`${API}/api/v1/export/divergence.csv`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium hover:bg-purple-200 transition-colors"
          >
            Divergence CSV
          </a>
        </div>
      </div>

      {/* Main Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {([
          { key: 'results', label: 'Αποτελέσματα' },
          { key: 'party-compare', label: 'Σύγκριση Κομμάτων' },
        ] as { key: VotesMainTab; label: string }[]).map(t => (
          <button
            key={t.key}
            onClick={() => setMainTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              mainTab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {String(t.label)}
          </button>
        ))}
      </div>

      {mainTab === 'results' && (<>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
        </div>
      )}

      {/* Representation Score */}
      {repPercent != null && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-gray-800">Representation Score</h2>
            <span className="text-2xl font-bold text-purple-600">{repPercent.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3">
            <div className="bg-purple-500 h-3 rounded-full transition-all" style={{ width: `${Math.min(100, repPercent)}%` }} />
          </div>
          <div className="text-xs text-gray-400 mt-1">Πόσο αντιπροσωπεύει η Βουλή τους πολίτες</div>
        </div>
      )}

      {/* Bill filters and selector */}
      <div className="mb-6 bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Επιλογή Νομοσχεδίου</h2>
            {!loadingBills && (
              <p className="text-xs text-gray-500 mt-0.5" aria-live="polite">
                Εμφανίζονται {firstVisibleBill.toLocaleString('el-GR')}–{lastVisibleBill.toLocaleString('el-GR')} από {totalBills.toLocaleString('el-GR')} νομοσχέδια
              </p>
            )}
            {loadingBills && bills.length > 0 && (
              <p className="text-xs text-blue-600 mt-0.5" aria-live="polite">Ενημέρωση λίστας...</p>
            )}
          </div>
          <button
            type="button"
            onClick={resetBillFilters}
            className="min-h-10 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Καθαρισμός φίλτρων
          </button>
        </div>

        {loadingBills && bills.length === 0 ? (
          <div className="text-sm text-gray-500">Φόρτωση νομοσχεδίων...</div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <label className="sm:col-span-2 lg:col-span-2 text-xs font-medium text-gray-600">
                Αναζήτηση
                <input
                  type="search"
                  value={billSearch}
                  onChange={(e) => { setBillSearch(e.target.value); resetBillPage() }}
                  placeholder="Τίτλος ή κωδικός νομοσχεδίου"
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </label>

              <label className="text-xs font-medium text-gray-600">
                Κατάσταση
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value as BillStatus | 'ALL'); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">Όλες</option>
                  {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
                </select>
              </label>

              <label className="text-xs font-medium text-gray-600">
                Επίπεδο διακυβέρνησης
                <select
                  value={governanceFilter}
                  onChange={(e) => { setGovernanceFilter(e.target.value as GovernanceLevel | 'ALL'); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">Όλα</option>
                  {GOVERNANCE_OPTIONS.map((level) => <option key={level} value={level}>{GOVERNANCE_LABELS[level]}</option>)}
                </select>
              </label>

              <label className="text-xs font-medium text-gray-600">
                Πηγή
                <select
                  value={sourceFilter}
                  onChange={(e) => { setSourceFilter(e.target.value); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">Όλες</option>
                  {Object.keys(SOURCE_LABELS).map((source) => <option key={source} value={source}>{SOURCE_LABELS[source]}</option>)}
                </select>
              </label>

              <label className="text-xs font-medium text-gray-600">
                Κατηγορία
                <select
                  value={categoryFilter}
                  onChange={(e) => { setCategoryFilter(e.target.value); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">Όλες</option>
                  {availableCategories.map((category) => <option key={category} value={category}>{category}</option>)}
                </select>
              </label>

              <label className="text-xs font-medium text-gray-600">
                Ορατότητα αποτελεσμάτων
                <select
                  value={visibilityFilter}
                  onChange={(e) => { setVisibilityFilter(e.target.value as ResultsVisibility | 'ALL'); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">Όλες</option>
                  {VISIBILITY_OPTIONS.map((visibility) => <option key={visibility} value={visibility}>{VISIBILITY_LABELS[visibility]}</option>)}
                </select>
              </label>

              <label className="text-xs font-medium text-gray-600">
                Από ημερομηνία
                <input
                  type="date"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => { setDateFrom(e.target.value); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </label>

              <label className="text-xs font-medium text-gray-600">
                Έως ημερομηνία
                <input
                  type="date"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => { setDateTo(e.target.value); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </label>

              <label className="text-xs font-medium text-gray-600">
                Ταξινόμηση
                <select
                  value={billSort}
                  onChange={(e) => { setBillSort(e.target.value as BillSort); resetBillPage() }}
                  className="mt-1 w-full min-h-10 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="DATE_DESC">Νεότερα πρώτα</option>
                  <option value="DATE_ASC">Παλαιότερα πρώτα</option>
                  <option value="TITLE_ASC">Τίτλος Α–Ω</option>
                  <option value="ID_ASC">Κωδικός</option>
                </select>
              </label>
            </div>

            <label className="block text-xs font-medium text-gray-600">
              Νομοσχέδιο
              <select
                value={selectedBillId ?? ''}
                disabled={bills.length === 0}
                onChange={(e) => {
                  setResults(null)
                  setPartyCompare([])
                  setSelectedBillId(e.target.value || null)
                }}
                className="mt-1 w-full min-h-11 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 disabled:bg-gray-100 disabled:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">{bills.length === 0 ? 'Δεν βρέθηκαν νομοσχέδια' : '-- Επιλέξτε νομοσχέδιο --'}</option>
                {bills.map((bill) => {
                  const date = billDate(bill)
                  return (
                    <option key={bill.id} value={bill.id}>
                      {date ? `${date} — ` : ''}#{String(bill.id)} — {bill.title_el}
                    </option>
                  )
                })}
              </select>
            </label>

            {totalBills > BILL_PAGE_SIZE && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-3">
                <span className="text-xs text-gray-500">
                  Σελίδα {currentBillPage.toLocaleString('el-GR')} από {totalBillPages.toLocaleString('el-GR')}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={billOffset === 0 || loadingBills}
                    onClick={() => { setBillOffset((offset) => Math.max(0, offset - BILL_PAGE_SIZE)); clearBillSelection() }}
                    className="min-h-10 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    Προηγούμενα
                  </button>
                  <button
                    type="button"
                    disabled={billOffset + bills.length >= totalBills || loadingBills}
                    onClick={() => { setBillOffset((offset) => offset + BILL_PAGE_SIZE); clearBillSelection() }}
                    className="min-h-10 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                  >
                    Επόμενα
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {loadingResults && <div className="p-8 text-center text-gray-500">Φόρτωση αποτελεσμάτων...</div>}

      {results?.results_hidden && !loadingResults && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-sm text-yellow-800">
          {results.disclaimer_el ?? 'Τα αποτελέσματα δεν είναι ακόμη δημόσια.'}
        </div>
      )}

      {results && !results.results_hidden && !loadingResults && (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Συνολικές Ψήφοι</div>
              <div className="text-2xl font-bold text-blue-600">{results.total_votes?.toLocaleString('el-GR') ?? '—'}</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Tier 1 / ZK</div>
              <div className="text-2xl font-bold text-blue-600">
                {results.tier1_vote_count?.toLocaleString('el-GR') ?? '0'} / {results.zk_vote_count?.toLocaleString('el-GR') ?? '0'}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Divergence Score</div>
              <div className={`text-2xl font-bold ${divergenceScore != null && divergenceScore > 0.3 ? 'text-red-600' : 'text-green-600'}`}>
                {divergenceScore != null ? `${(divergenceScore * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">Βουλή</div>
              <div className="text-2xl font-bold text-gray-800">
                {results.divergence?.parliament_result ?? '—'}
              </div>
            </div>
          </div>

          {/* Side by side: Pie + Bar */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

          {/* Party Divergence Chart */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Ευθυγράμμιση Κομμάτων με Πολίτες</h2>
            {loadingCompare ? (
              <div className="p-8 text-center text-gray-500">Φόρτωση σύγκρισης κομμάτων...</div>
            ) : partyChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={partyChartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} unit="%" />
                  <Tooltip formatter={(value: number) => [`${String(value)}%`, 'Alignment']} />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {partyChartData.map((entry, i) => (
                      <Cell key={entry.name} fill={PARTY_BAR_COLORS[i] ?? '#6b7280'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="p-8 text-center text-sm text-gray-400">Δεν υπάρχουν δεδομένα σύγκρισης</div>
            )}
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
                    <td className="px-4 py-3 text-gray-400">{String(i + 1)}</td>
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

      </>)}

      {/* Party Compare Tab */}
      {mainTab === 'party-compare' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">{String('Σύγκριση Κομμάτων — Alignment με Πολίτες')}</h2>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPartyCompareSortDir(d => d === 'desc' ? 'asc' : 'desc')}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                {partyCompareSortDir === 'desc' ? String('Φθίνουσα ↓') : String('Αύξουσα ↑')}
              </button>
              <a
                href={`${API}/api/v1/export/divergence.csv`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200 transition-colors"
              >
                {String('CSV')}
              </a>
            </div>
          </div>

          {/* Bar Chart */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">{String('Alignment Score ανά Κόμμα (%)')}</h3>
            {globalPartyChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={globalPartyChartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} unit="%" />
                  <Tooltip formatter={(value: number) => [`${String(value)}%`, 'Alignment']} />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {globalPartyChartData.map((entry, i) => {
                      const score = entry.score
                      const color = score >= 60 ? '#16a34a' : score >= 40 ? '#ca8a04' : '#dc2626'
                      return <Cell key={String(i)} fill={color} />
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="p-8 text-center text-sm text-gray-400">{String('Δεν υπάρχουν δεδομένα MP Ranking')}</div>
            )}
          </div>

          {/* Table */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">#</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{String('Κόμμα')}</th>
                  <th
                    className="text-right px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-blue-600 select-none"
                    onClick={() => setPartyCompareSortDir(d => d === 'desc' ? 'asc' : 'desc')}
                  >
                    {String('Alignment Score')} {partyCompareSortDir === 'desc' ? '↓' : '↑'}
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">{String('Συμφωνούν')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {globalPartySorted.length > 0 ? globalPartySorted.map((party, i) => {
                  const pct = (party.alignment_score ?? 0) * 100
                  const color = pct >= 60 ? 'text-green-600' : pct >= 40 ? 'text-yellow-600' : 'text-red-600'
                  return (
                    <tr key={party.abbreviation ?? String(i)} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-400">{String(i + 1)}</td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        <div>{String(party.party ?? party.abbreviation ?? '')}</div>
                        {party.party && party.abbreviation && party.party !== party.abbreviation && (
                          <div className="text-xs text-gray-400">{String(party.abbreviation)}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-24 bg-gray-100 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${pct >= 60 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                              style={{ width: `${Math.min(100, pct)}%` }}
                            />
                          </div>
                          <span className={`text-sm font-bold ${color}`}>{pct.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500">
                        {party.aligned_count != null && party.total_count != null
                          ? `${String(party.aligned_count)}/${String(party.total_count)}`
                          : String('—')}
                      </td>
                    </tr>
                  )
                }) : (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-sm text-gray-400">
                      {String('Δεν υπάρχουν δεδομένα. Βεβαιωθείτε ότι το /api/v1/mp/ranking επιστρέφει δεδομένα.')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

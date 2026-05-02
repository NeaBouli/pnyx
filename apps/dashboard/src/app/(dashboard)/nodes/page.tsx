'use client'

import { useState, useEffect, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type NodeStatus = 'active' | 'pending' | 'concept' | 'offline' | 'suspended'

interface NodeRow {
  name: string
  domain: string
  district: string
  population: string
  status: NodeStatus
  lastActivity: string
  ed25519Key: string
}

interface ScraperJob {
  name?: string
  status?: string
  last_run?: string
  last_success?: string
  last_error?: string | null
  error_count?: number
}

const STATUS_LABELS: Record<NodeStatus, string> = {
  active: 'Ενεργό',
  pending: 'Εκκρεμής',
  concept: 'Κόνσεπτ',
  offline: 'Εκτός',
  suspended: 'Ανεσταλμένο',
}

const STATUS_COLORS: Record<NodeStatus, string> = {
  active: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-800',
  concept: 'bg-gray-100 text-gray-600',
  offline: 'bg-red-100 text-red-700',
  suspended: 'bg-red-100 text-red-700',
}

const REGISTERED_NODES: NodeRow[] = [
  {
    name: 'test.ekklesia.gr',
    domain: 'test.ekklesia.gr',
    district: 'Test Node',
    population: '—',
    status: 'active',
    lastActivity: '—',
    ed25519Key: '',
  },
  {
    name: 'vr.ekklesia.gr',
    domain: 'vr.ekklesia.gr',
    district: 'MiroFisch',
    population: '—',
    status: 'concept',
    lastActivity: '—',
    ed25519Key: '',
  },
]

const GREEK_DISTRICTS = [
  'Αττική', 'Θεσσαλονίκη', 'Κεντρική Μακεδονία', 'Δυτική Μακεδονία',
  'Ανατολική Μακεδονία & Θράκη', 'Ήπειρος', 'Θεσσαλία', 'Στερεά Ελλάδα',
  'Δυτική Ελλάδα', 'Πελοπόννησος', 'Κρήτη', 'Βόρειο Αιγαίο',
  'Νότιο Αιγαίο', 'Ιόνια Νησιά',
]

export default function NodesPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [scrapers, setScrapers] = useState<ScraperJob[]>([])
  const [loading, setLoading] = useState(true)
  const [showRegisterModal, setShowRegisterModal] = useState(false)
  const [registerForm, setRegisterForm] = useState({ name: '', domain: '', district: '', contact: '', ed25519Key: '' })

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [hRes, sRes] = await Promise.allSettled([
        fetch(`${API}/health`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/jobs`).then(r => r.json()),
      ])
      const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
      setHealth(v(hRes) as Record<string, unknown> | null)
      const scraperData = v(sRes) as Record<string, unknown> | unknown[] | null
      const arr = Array.isArray(scraperData) ? scraperData : (scraperData as Record<string, unknown>)?.scrapers
      setScrapers(Array.isArray(arr) ? arr as ScraperJob[] : [])
    } catch { /* non-critical */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => {
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  const healthStatus = health?.status as string | null
  const isOk = healthStatus === 'ok'
  const modules = health?.modules as Record<string, string> | undefined
  const moduleCount = modules ? Object.keys(modules).length : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Node-Panel</h1>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Ανανέωση...' : 'Ανανέωση'}
        </button>
      </div>

      {/* ── Eigener Server Status ── */}
      <div className="space-y-6">
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="font-semibold text-gray-800">Eigener Server Status</h2>
            {health ? (
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${isOk ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                {isOk ? 'Λειτουργικό' : 'Σφάλμα'}
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">Φόρτωση...</span>
            )}
          </div>
          <div className="p-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-1">Module</div>
                <div className="text-lg font-bold text-gray-800">
                  {moduleCount > 0 ? `${moduleCount} Module` : '—'}
                </div>
                {modules && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(modules).slice(0, 6).map(([name, status]) => (
                      <div key={name} className="flex items-center justify-between text-xs">
                        <span className="text-gray-600 truncate">{name}</span>
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          status === 'ok' || status === 'true' ? 'bg-green-500' : status === 'disabled' ? 'bg-gray-400' : 'bg-red-500'
                        }`} />
                      </div>
                    ))}
                    {moduleCount > 6 && (
                      <div className="text-xs text-gray-400">+{moduleCount - 6} weitere</div>
                    )}
                  </div>
                )}
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-1">��ρήση Δίσκου</div>
                <div className="text-lg font-bold text-gray-400">—</div>
                <div className="text-xs text-gray-400 mt-1">Server-Monitoring — Phase 2</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-1">Letzte Sync-Zeit</div>
                <div className="text-lg font-bold text-gray-800">
                  {scrapers.length > 0 && scrapers[0]?.last_run
                    ? new Date(String(scrapers[0].last_run)).toLocaleString('el-GR')
                    : '—'}
                </div>
              </div>
            </div>

            {/* Scheduler Jobs */}
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Scheduler Jobs</h3>
            {scrapers.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {scrapers.map((job, i) => {
                  const ok = job.status === 'ok' || job.status === 'success'
                  return (
                    <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-800 truncate">{String(job.name ?? `Job ${i + 1}`)}</span>
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                      </div>
                      {job.last_run && <div className="text-xs text-gray-400">Τελ.: {new Date(String(job.last_run)).toLocaleString('el-GR')}</div>}
                      {job.error_count != null && job.error_count > 0 && (
                        <div className="text-xs text-red-500">Σφάλματα: {job.error_count}</div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400">Δεν βρέθηκαν δεδομένα scheduler jobs</div>
            )}
          </div>
        </div>

        {/* ── Registrierte Nodes ── */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="font-semibold text-gray-800">Registrierte Nodes</h2>
            <span className="text-xs text-gray-400">{REGISTERED_NODES.length} Nodes</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Domain</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Περιφέρεια</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Πληθυσμός</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ed25519 Key</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Letzte Aktivität</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {REGISTERED_NODES.map((node) => (
                  <tr key={node.domain} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{node.name}</td>
                    <td className="px-4 py-3 text-gray-600 font-mono text-xs">{node.domain}</td>
                    <td className="px-4 py-3 text-gray-600">{node.district}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{node.population}</td>
                    <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                      {node.ed25519Key ? String(node.ed25519Key).slice(0, 16) + '…' : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[node.status]}`}>
                        {STATUS_LABELS[node.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{node.lastActivity}</td>
                    <td className="px-4 py-3">
                      <button disabled className="text-xs text-gray-400 cursor-not-allowed">Details (Phase 2)</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Node-Verwaltung ── */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="px-5 py-4 border-b border-gray-200">
            <h2 className="font-semibold text-gray-800">Node-Verwaltung</h2>
          </div>
          <div className="p-5 flex flex-wrap gap-3">
            <button
              onClick={() => setShowRegisterModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              + Node registrieren
            </button>
            <div className="relative group">
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
                title="POST /federation/nodes/sync — Phase 2"
              >
                Sync auslösen
              </button>
              <div className="absolute left-0 top-full mt-1 px-3 py-1.5 bg-gray-800 text-white text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                POST /federation/nodes/sync — Phase 2
              </div>
            </div>
            <div className="relative group">
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                Node-Schlüssel rotieren
              </button>
              <div className="absolute left-0 top-full mt-1 px-3 py-1.5 bg-gray-800 text-white text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                Phase 2
              </div>
            </div>
          </div>
        </div>

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <div className="font-semibold text-blue-800 mb-1">Ομοσπονδιακό Δίκτυο Κόμβων</div>
          <div className="text-sm text-blue-700 mb-2">
            Κάθε Δήμος/Κοινότητα μπορεί να λειτουργήσει τον δικό της κόμβο ekklesia.gr
            και να συγχρονιστεί με τον κεντρικό κόμβο.
          </div>
          <div className="text-xs text-blue-600 bg-blue-100 rounded-lg p-2">
            Αρχιτεκτονική τεκμηριωμένη — Υλοποίηση μετά το Alpha Gate
          </div>
        </div>
      </div>

      {/* ── Register Modal ── */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowRegisterModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Node registrieren</h3>
              <button onClick={() => setShowRegisterModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={registerForm.name}
                  onChange={e => setRegisterForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="z.B. Athens Node"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Domain</label>
                <input
                  type="text"
                  value={registerForm.domain}
                  onChange={e => setRegisterForm(prev => ({ ...prev, domain: e.target.value }))}
                  placeholder="z.B. athens.ekklesia.gr"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Περιφέρεια</label>
                <select
                  value={registerForm.district}
                  onChange={e => setRegisterForm(prev => ({ ...prev, district: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">— Περιφέρεια auswählen —</option>
                  {GREEK_DISTRICTS.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Kontakt-Email</label>
                <input
                  type="email"
                  value={registerForm.contact}
                  onChange={e => setRegisterForm(prev => ({ ...prev, contact: e.target.value }))}
                  placeholder="admin@node.ekklesia.gr"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ed25519 Public Key</label>
                <input
                  type="text"
                  value={registerForm.ed25519Key}
                  onChange={e => setRegisterForm(prev => ({ ...prev, ed25519Key: e.target.value }))}
                  placeholder="base64-kodierter Public Key"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowRegisterModal(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                Abbrechen
              </button>
              <button
                disabled
                title="POST /federation/nodes — Phase 2"
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                Registrieren (POST /federation/nodes — Phase 2)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${API}${path}${sep}admin_key=${ADMIN_KEY}`
}

type SettingsTab = 'modules' | 'scraper' | 'apps' | 'compass' | 'kb'

// ─── Toggle ───

interface ToggleProps {
  id: string
  label: string
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  disabledReason?: string
  warning?: string
  sub?: string
}

function Toggle({ id, label, value, onChange, disabled, disabledReason, warning, sub }: ToggleProps) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-gray-800 cursor-pointer">{label}</label>
        {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
        {disabledReason && <div className="text-xs text-yellow-600 mt-0.5">{disabledReason}</div>}
        {warning && <div className="text-xs text-red-600 mt-0.5">{warning}</div>}
      </div>
      <button
        id={id}
        role="switch"
        aria-checked={value}
        disabled={disabled}
        onClick={() => !disabled && onChange(!value)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
          disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
        } ${value ? 'bg-green-600' : 'bg-gray-300'}`}
      >
        <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${value ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

// ─── Types ───

interface ModuleState {
  hlr: boolean
  ai_ollama: boolean
  ai_claude: boolean
  discourse: boolean
  greek_topics: boolean
  newsletter: boolean
  push_notifications: boolean
  arweave: boolean
  deepl: boolean
}

interface ScraperJob {
  name?: string
  job_id?: string
  interval?: string
  last_run?: string
  next_run?: string
  status?: string
  error_count?: number
  circuit_breaker?: string
  healthy?: boolean
}

interface CompassQuestion {
  id: number
  text_el?: string
  text_en?: string
  category?: string
  status?: string
}

export default function SettingsPage() {
  const { data: session } = useSession()
  const role = session?.user?.role

  const [tab, setTab] = useState<SettingsTab>('modules')
  const [modules, setModules] = useState<ModuleState>({
    hlr: true, ai_ollama: true, ai_claude: true, discourse: true,
    greek_topics: false, newsletter: true, push_notifications: true,
    arweave: true, deepl: true,
  })
  const [hlrData, setHlrData] = useState<Record<string, unknown> | null>(null)
  const [claudeData, setClaudeData] = useState<Record<string, unknown> | null>(null)
  const [deeplData, setDeeplData] = useState<Record<string, unknown> | null>(null)
  const [notifData, setNotifData] = useState<Record<string, unknown> | null>(null)
  const [arweaveData, setArweaveData] = useState<Record<string, unknown> | null>(null)
  const [scraperJobs, setScraperJobs] = useState<ScraperJob[]>([])
  const [appVersion, setAppVersion] = useState<Record<string, unknown> | null>(null)
  const [compassPending, setCompassPending] = useState<CompassQuestion[]>([])

  const [forceUpdate, setForceUpdate] = useState(false)
  const [forceUpdateVersion, setForceUpdateVersion] = useState('')
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      const [hlr, claude, deepl, notif, arweave, jobs, version, compass] = await Promise.allSettled([
        fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
        fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
        fetch(`${API}/api/v1/admin/deepl/usage`).then(r => r.json()),
        fetch(`${API}/api/v1/notifications/status`).then(r => r.json()),
        fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/jobs`).then(r => r.json()),
        fetch(`${API}/api/v1/app/version`).then(r => r.json()),
        fetch(adminURL('/api/v1/admin/compass/pending-review')).then(r => r.json()),
      ])
      const v = (r: PromiseSettledResult<unknown>) => r.status === 'fulfilled' ? r.value : null
      setHlrData(v(hlr) as Record<string, unknown> | null)
      setClaudeData(v(claude) as Record<string, unknown> | null)
      setDeeplData(v(deepl) as Record<string, unknown> | null)
      setNotifData(v(notif) as Record<string, unknown> | null)
      setArweaveData(v(arweave) as Record<string, unknown> | null)
      const jobsVal = v(jobs) as Record<string, unknown> | unknown[] | null
      const jobsArray = Array.isArray(jobsVal) ? jobsVal : (jobsVal as Record<string, unknown>)?.scrapers
      setScraperJobs(Array.isArray(jobsArray) ? jobsArray : [])
      setAppVersion(v(version) as Record<string, unknown> | null)
      const cp = v(compass)
      setCompassPending(Array.isArray(cp) ? cp : (cp as Record<string, unknown> | null)?.questions as CompassQuestion[] ?? [])
    }
    load()
  }, [])

  if (role !== 'SUPER_ADMIN') {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{String('Ρυθμίσεις')}</h1>
        <div className="p-8 text-center bg-red-50 border border-red-200 rounded-xl text-red-700">
          {String('Πρόσβαση μόνο για Super Admin.')}
        </div>
      </div>
    )
  }

  function setModule(key: keyof ModuleState, val: boolean) {
    setModules((prev) => ({ ...prev, [key]: val }))
  }

  async function handleAction(name: string, fn: () => Promise<unknown>) {
    setActionLoading(name)
    try { await fn() } catch { /* non-critical */ }
    finally { setActionLoading(null) }
  }

  async function handleCompassAction(id: number, action: 'approve' | 'reject') {
    setActionLoading(`compass-${id}`)
    try {
      await fetch(adminURL(`/api/v1/admin/compass/${action}/${id}`), { method: 'POST' })
      setCompassPending(prev => prev.filter(q => q.id !== id))
    } catch { /* non-critical */ }
    finally { setActionLoading(null) }
  }

  const hlrPrimary = hlrData?.primary as Record<string, unknown> | null

  const tabs: { key: SettingsTab; label: string }[] = [
    { key: 'modules', label: 'Module' },
    { key: 'scraper', label: 'Αυτοματισμοί' },
    { key: 'apps', label: 'Apps' },
    { key: 'compass', label: 'Compass' },
    { key: 'kb', label: 'Βάση Γνώσεων' },
  ]

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{String('Ρυθμίσεις')}</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {String(t.label)}
          </button>
        ))}
      </div>

      {/* Tab 1: Modules */}
      {tab === 'modules' && (
        <div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 text-sm text-blue-800">
            {String('Αλλαγή Toggle = μόνο UI. Πραγματική αλλαγή απαιτεί .env τροποποίηση στον Server.')}
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="divide-y divide-gray-100">
              <Toggle
                id="hlr" label="HLR Επαλήθευση" value={modules.hlr}
                onChange={(v) => setModule('hlr', v)}
                sub={hlrPrimary ? `Credits: ${String(hlrPrimary?.remaining ?? '—')} (${String(hlrPrimary?.provider ?? 'primary')})` : undefined}
              />
              <Toggle
                id="ai_ollama" label="AI Chatbot (Ollama)" value={modules.ai_ollama}
                onChange={(v) => setModule('ai_ollama', v)}
                sub={claudeData?.ollama_model ? `Μοντέλο: ${String(claudeData.ollama_model)}` : undefined}
              />
              <Toggle
                id="ai_claude" label="AI Chatbot (Claude)" value={modules.ai_claude}
                onChange={(v) => setModule('ai_claude', v)}
                sub={claudeData?.tokens_today != null ? `Σήμερα: ${String((claudeData.tokens_today as number).toLocaleString('el-GR'))} tokens` : claudeData?.is_active ? 'Ενεργό' : undefined}
              />
              <Toggle id="discourse" label="Discourse Forum Sync" value={modules.discourse} onChange={(v) => setModule('discourse', v)} sub="FORUM_SYNC_ENABLED" />
              <Toggle
                id="greek_topics" label="Scraper Ελληνικών Θεμάτων" value={modules.greek_topics}
                onChange={(v) => setModule('greek_topics', v)}
                disabled disabledReason="Απενεργοποιημένο"
                warning="Νομική διευκρίνιση σε εξέλιξη"
              />
              <Toggle
                id="newsletter" label="Newsletter" value={modules.newsletter}
                onChange={(v) => setModule('newsletter', v)}
                sub={notifData?.subscriber_count != null ? `Συνδρομητές: ${String(notifData.subscriber_count)}` : undefined}
              />
              <Toggle
                id="push" label="Push Notifications" value={modules.push_notifications}
                onChange={(v) => setModule('push_notifications', v)}
                sub={notifData?.device_count != null ? `Συσκευές: ${String(notifData.device_count)}` : undefined}
              />
              <Toggle
                id="arweave" label="Arweave Αρχειοθέτηση" value={modules.arweave}
                onChange={(v) => setModule('arweave', v)}
                sub={arweaveData?.balance_ar != null ? `Balance: ${String((arweaveData.balance_ar as number).toFixed(4))} AR` : undefined}
              />
              <Toggle
                id="deepl" label="DeepL Translation" value={modules.deepl}
                onChange={(v) => setModule('deepl', v)}
                sub={deeplData?.character_count != null ? `Χρήση: ${String(((deeplData.character_count as number) / 1000).toFixed(0))}k / 500k` : undefined}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Scraper */}
      {tab === 'scraper' && (
        <div>
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-4">
            <h2 className="font-semibold text-gray-900 mb-3">{String('Scheduler Jobs (8)')}</h2>
            {scraperJobs.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                {scraperJobs.map((job, i) => {
                  const ok = job.status === 'ok' || job.status === 'success' || job.healthy === true
                  return (
                    <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-800">{String(job.name ?? job.job_id ?? `Job ${i + 1}`)}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                          {ok ? String('OK') : String(job.status ?? 'Error')}
                        </span>
                      </div>
                      {job.interval && <div className="text-xs text-gray-400">{String('Κάθε')} {String(job.interval)}</div>}
                      {job.last_run && <div className="text-xs text-gray-400">{String('Τελ.:')} {String(new Date(String(job.last_run)).toLocaleString('el-GR'))}</div>}
                      {job.next_run && <div className="text-xs text-gray-400">{String('Επόμ.:')} {String(new Date(String(job.next_run)).toLocaleString('el-GR'))}</div>}
                      {job.circuit_breaker && (
                        <div className={`text-xs mt-0.5 ${String(job.circuit_breaker) === 'open' ? 'text-red-500' : 'text-green-500'}`}>
                          {String('CB:')} {String(job.circuit_breaker)}
                        </div>
                      )}
                      {job.error_count != null && job.error_count > 0 && (
                        <div className="text-xs text-red-500">{String('Σφάλματα:')} {String(job.error_count)}</div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400 mb-4">{String('Δεν βρέθηκαν δεδομένα jobs')}</div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => handleAction('test', () => fetch(`${API}/api/v1/scraper/test`).then(r => r.json()))}
                disabled={actionLoading === 'test'}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'test' ? String('Δοκιμή...') : String('Δοκιμή Scraper')}
              </button>
              <button
                onClick={() => handleAction('heal', () => fetch(adminURL('/api/v1/admin/scraper/heal-status'), { method: 'POST' }))}
                disabled={actionLoading === 'heal'}
                className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-sm font-medium hover:bg-yellow-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'heal' ? String('Επιδιόρθωση...') : String('Επιδιόρθωση Scraper')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Apps */}
      {tab === 'apps' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900 mb-3">{String('App Distribution')}</h2>
          <div className="space-y-3 mb-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{String('Τρέχουσα Έκδοση')}</span>
              <span className="text-sm font-medium text-gray-800">
                {String(appVersion?.latest_version ?? appVersion?.version ?? '—')}
                {appVersion?.latest_version_code ? ` (${String(appVersion.latest_version_code)})` : ''}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{String('Play Store')}</span>
              <a href="https://play.google.com/store/apps/details?id=ekklesia.gr" target="_blank" rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline">{String('Άνοιγμα')}</a>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{String('F-Droid')}</span>
              <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs">{String('MR Εκκρεμεί')}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{String('Direct APK')}</span>
              <span className="text-xs text-gray-400">{String('Σύντομα')}</span>
            </div>
          </div>

          <div className="divide-y divide-gray-100 border-t border-gray-100 pt-2">
            <Toggle id="force_update" label="Force Update" value={forceUpdate} onChange={setForceUpdate} />
            {forceUpdate && (
              <div className="py-2 pl-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">{String('Ελάχιστη Έκδοση')}</label>
                <input
                  type="text"
                  value={forceUpdateVersion}
                  onChange={(e) => setForceUpdateVersion(e.target.value)}
                  placeholder="π.χ. 1.2.0"
                  className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
            <Toggle id="maintenance" label="Maintenance Mode" value={maintenanceMode} onChange={setMaintenanceMode} warning={maintenanceMode ? 'App zeigt Maintenance-Bildschirm' : undefined} />
          </div>

          <div className="mt-4 space-y-2">
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
              {String('Download-Statistiken (Play Console API — Phase 2)')}
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
              {String('Crash Reports (Sentry — Phase 2)')}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Compass */}
      {tab === 'compass' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900 mb-3">{String('Compass Διαχείριση')}</h2>
          <div className="mb-4">
            <button
              onClick={() => handleAction('compass-gen', () =>
                fetch(adminURL('/api/v1/admin/compass/generate-questions'), { method: 'POST' }).then(r => r.json())
              )}
              disabled={actionLoading === 'compass-gen'}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {actionLoading === 'compass-gen' ? String('Δημιουργία...') : String('Νέες Ερωτήσεις (Ollama + DeepL)')}
            </button>
          </div>

          {compassPending.length > 0 ? (
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-700 mb-2">
                {String('Εκκρεμείς')} ({String(compassPending.length)})
              </div>
              {compassPending.map((q) => (
                <div key={q.id} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <div className="text-sm text-gray-800 mb-2">{String(q.text_el ?? q.text_en ?? `#${q.id}`)}</div>
                  {q.category ? <div className="text-xs text-gray-400 mb-2">{String('Κατηγορία:')} {String(q.category)}</div> : null}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleCompassAction(q.id, 'approve')}
                      disabled={actionLoading === `compass-${q.id}`}
                      className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium hover:bg-green-200 disabled:opacity-50"
                    >
                      {String('Έγκριση')}
                    </button>
                    <button
                      onClick={() => handleCompassAction(q.id, 'reject')}
                      disabled={actionLoading === `compass-${q.id}`}
                      className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium hover:bg-red-200 disabled:opacity-50"
                    >
                      {String('Απόρριψη')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-400">{String('Δεν υπάρχουν εκκρεμείς ερωτήσεις')}</div>
          )}
        </div>
      )}

      {/* Tab 5: Knowledge Base */}
      {tab === 'kb' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900 mb-3">{String('Knowledge Base (RAG)')}</h2>
          <div className="bg-gray-50 rounded-lg p-6 text-center">
            <div className="text-sm font-medium text-gray-500">{String('Knowledge Base CRUD — Phase 2')}</div>
            <div className="text-xs text-gray-400 mt-1">{String('FAQ, Αποστολή, Concepts για τον RAG Agent')}</div>
          </div>
        </div>
      )}
    </div>
  )
}

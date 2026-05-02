'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || ''

function adminURL(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${API}${path}${sep}admin_key=${ADMIN_KEY}`
}

// ─── Toggle ───

interface ToggleProps {
  id: string
  label: string
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  disabledReason?: string
  color?: 'green' | 'blue'
  warning?: string
  sub?: string
}

function Toggle({ id, label, value, onChange, disabled, disabledReason, color = 'green', warning, sub }: ToggleProps) {
  const activeColor = color === 'blue' ? 'bg-blue-600' : 'bg-green-600'
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
        } ${value ? activeColor : 'bg-gray-300'}`}
      >
        <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${value ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

// ─── Section ───

function Section({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-5">
      <h2 className="font-semibold text-gray-900 mb-1">{title}</h2>
      {sub && <p className="text-xs text-gray-500 mb-4">{sub}</p>}
      {!sub && <div className="mb-3" />}
      {children}
    </section>
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
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  // Load all data
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
      const jobsVal = v(jobs)
      setScraperJobs(Array.isArray(jobsVal) ? jobsVal : [])
      setAppVersion(v(version) as Record<string, unknown> | null)
      const cp = v(compass)
      setCompassPending(Array.isArray(cp) ? cp : (cp as Record<string, unknown>)?.questions as CompassQuestion[] ?? [])
    }
    load()
  }, [])

  if (role !== 'SUPER_ADMIN') {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Ρυθμίσεις</h1>
        <div className="p-8 text-center bg-red-50 border border-red-200 rounded-xl text-red-700">
          Πρόσβαση μόνο για Super Admin.
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

  function handleSave() {
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const hlrPrimary = hlrData?.primary as Record<string, unknown> | null
  const hlrFallback = hlrData?.fallback as Record<string, unknown> | null

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Ρυθμίσεις</h1>
        <button
          onClick={handleSave}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            saved ? 'bg-green-100 text-green-700' : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {saved ? 'Αποθηκεύτηκε' : 'Αποθήκευση'}
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 text-sm text-blue-800">
        Ορισμένες αλλαγές απαιτούν επανεκκίνηση του server για να τεθούν σε ισχύ.
      </div>

      {/* SECTION 1: Modules */}
      <Section title="Module — Ενεργοποίηση / Απενεργοποίηση" sub="Απαιτείται επανεκκίνηση για να εφαρμοστούν αλλαγές">
        <div className="divide-y divide-gray-100">
          <Toggle
            id="hlr" label="HLR Επαλήθευση" value={modules.hlr}
            onChange={(v) => setModule('hlr', v)}
            sub={hlrPrimary ? `Credits: ${hlrPrimary.remaining ?? '—'} (${hlrPrimary.provider ?? 'primary'})` : undefined}
          />
          <Toggle
            id="ai_ollama" label="AI Chatbot (Ollama)" value={modules.ai_ollama}
            onChange={(v) => setModule('ai_ollama', v)}
            sub={claudeData?.ollama_model ? `Μοντέλο: ${claudeData.ollama_model as string}` : undefined}
          />
          <Toggle
            id="ai_claude" label="AI Chatbot (Claude)" value={modules.ai_claude}
            onChange={(v) => setModule('ai_claude', v)}
            sub={claudeData?.used_eur != null ? `Budget: ${(claudeData.used_eur as number).toFixed(2)}/${claudeData.budget_eur ?? '?'} EUR` : undefined}
          />
          <Toggle id="discourse" label="Discourse Forum Sync" value={modules.discourse} onChange={(v) => setModule('discourse', v)} sub="FORUM_SYNC_ENABLED" />
          <Toggle
            id="greek_topics" label="Greek Topics Scraper" value={modules.greek_topics}
            onChange={(v) => setModule('greek_topics', v)}
            disabled disabledReason="Απενεργοποιημένο"
            warning="Νομική διευκρίνιση σε εξέλιξη"
          />
          <Toggle
            id="newsletter" label="Newsletter" value={modules.newsletter}
            onChange={(v) => setModule('newsletter', v)}
            sub={notifData?.subscriber_count != null ? `Συνδρομητές: ${notifData.subscriber_count}` : undefined}
          />
          <Toggle
            id="push" label="Push Notifications" value={modules.push_notifications}
            onChange={(v) => setModule('push_notifications', v)}
            sub={notifData?.device_count != null ? `Συσκευές: ${notifData.device_count}` : undefined}
          />
          <Toggle
            id="arweave" label="Arweave Αρχειοθέτηση" value={modules.arweave}
            onChange={(v) => setModule('arweave', v)}
            sub={arweaveData?.balance != null ? `Balance: ${(arweaveData.balance as number).toFixed(4)} AR` : undefined}
          />
          <Toggle
            id="deepl" label="DeepL Translation" value={modules.deepl}
            onChange={(v) => setModule('deepl', v)}
            sub={deeplData?.character_count != null ? `Χρήση: ${((deeplData.character_count as number) / 1000).toFixed(0)}k / 500k` : undefined}
          />
        </div>
      </Section>

      {/* SECTION 2: Scraper & Jobs */}
      <Section title="Scraper & Jobs" sub="8 Scheduler Jobs — Κατάσταση και έλεγχος">
        {scraperJobs.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {scraperJobs.map((job, i) => {
              const ok = job.status === 'ok' || job.status === 'success' || job.healthy === true
              return (
                <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-800">{job.name ?? job.job_id ?? `Job ${i + 1}`}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {ok ? 'OK' : job.status ?? 'Error'}
                    </span>
                  </div>
                  {job.interval && <div className="text-xs text-gray-400">Κάθε {job.interval}</div>}
                  {job.last_run && <div className="text-xs text-gray-400">Τελ.: {new Date(job.last_run).toLocaleString('el-GR')}</div>}
                  {job.next_run && <div className="text-xs text-gray-400">Επόμ.: {new Date(job.next_run).toLocaleString('el-GR')}</div>}
                  {job.circuit_breaker && (
                    <div className={`text-xs mt-0.5 ${job.circuit_breaker === 'open' ? 'text-red-500' : 'text-green-500'}`}>
                      CB: {job.circuit_breaker}
                    </div>
                  )}
                  {job.error_count != null && job.error_count > 0 && (
                    <div className="text-xs text-red-500">Σφάλματα: {job.error_count}</div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-sm text-gray-400 mb-4">Δεν βρέθηκαν δεδομένα jobs</div>
        )}
        <div className="flex gap-3">
          <button
            onClick={() => handleAction('test', () => fetch(`${API}/api/v1/scraper/test`).then(r => r.json()))}
            disabled={actionLoading === 'test'}
            className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'test' ? 'Δοκιμή...' : 'Δοκιμή Scraper'}
          </button>
          <button
            onClick={() => handleAction('heal', () => fetch(adminURL('/api/v1/admin/scraper/heal-status'), { method: 'POST' }))}
            disabled={actionLoading === 'heal'}
            className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-sm font-medium hover:bg-yellow-200 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'heal' ? 'Επιδιόρθωση...' : 'Heal Scraper'}
          </button>
        </div>
      </Section>

      {/* SECTION 3: App Distribution */}
      <Section title="App Distribution" sub="Τρέχουσα έκδοση και κανάλια διανομής">
        <div className="space-y-3 mb-4">
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">Τρέχουσα Έκδοση</span>
            <span className="text-sm font-medium text-gray-800">
              {appVersion?.version ?? appVersion?.versionName ?? '—'}
              {appVersion?.versionCode ? ` (${appVersion.versionCode})` : ''}
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">Play Store</span>
            <a href="https://play.google.com/store/apps/details?id=ekklesia.gr" target="_blank" rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline">Άνοιγμα</a>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">F-Droid</span>
            <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs">MR Εκκρεμεί</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">Direct APK</span>
            <span className="text-xs text-gray-400">Σύντομα</span>
          </div>
        </div>

        <Toggle id="force_update" label="Force Update" value={forceUpdate} onChange={setForceUpdate} color="blue" />
        {forceUpdate && (
          <div className="py-2 pl-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Ελάχιστη Έκδοση</label>
            <input
              type="text"
              value={forceUpdateVersion}
              onChange={(e) => setForceUpdateVersion(e.target.value)}
              placeholder="π.χ. 1.2.0"
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        <div className="mt-4 space-y-2">
          <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
            Download-Στατιστικά (Play Console API -- Φάση 2)
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
            Crash Reports (Sentry -- Φάση 2)
          </div>
        </div>
      </Section>

      {/* SECTION 4: Compass */}
      <Section title="Compass Διαχείριση" sub="Εκκρεμείς ερωτήσεις και δημιουργία νέων">
        <div className="mb-4">
          <button
            onClick={() => handleAction('compass-gen', () =>
              fetch(adminURL('/api/v1/admin/compass/generate-questions'), { method: 'POST' }).then(r => r.json())
            )}
            disabled={actionLoading === 'compass-gen'}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'compass-gen' ? 'Δημιουργία...' : 'Νέες Ερωτήσεις (Ollama + DeepL)'}
          </button>
        </div>

        {compassPending.length > 0 ? (
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-700 mb-2">Εκκρεμείς ({compassPending.length})</div>
            {compassPending.map((q) => (
              <div key={q.id} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                <div className="text-sm text-gray-800 mb-2">{q.text_el ?? q.text_en ?? `#${q.id}`}</div>
                {q.category && <div className="text-xs text-gray-400 mb-2">Κατηγορία: {q.category}</div>}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleCompassAction(q.id, 'approve')}
                    disabled={actionLoading === `compass-${q.id}`}
                    className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium hover:bg-green-200 disabled:opacity-50"
                  >
                    Έγκριση
                  </button>
                  <button
                    onClick={() => handleCompassAction(q.id, 'reject')}
                    disabled={actionLoading === `compass-${q.id}`}
                    className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium hover:bg-red-200 disabled:opacity-50"
                  >
                    Απόρριψη
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-400">Δεν υπάρχουν εκκρεμείς ερωτήσεις</div>
        )}
      </Section>

      {/* SECTION 5: Knowledge Base */}
      <Section title="Knowledge Base (RAG)" sub="CRUD για τη βάση γνώσεων του AI Agent">
        <div className="bg-gray-50 rounded-lg p-6 text-center">
          <div className="text-3xl mb-2">📚</div>
          <div className="text-sm font-medium text-gray-500">Knowledge Base CRUD -- Φάση 2</div>
          <div className="text-xs text-gray-400 mt-1">FAQ, Αποστολή, Concepts για τον RAG Agent</div>
        </div>
      </Section>
    </div>
  )
}

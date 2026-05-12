'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

function adminProxyPath(path: string): string {
  return `/api/proxy/${path.replace(/^\/api\/v1\//, '')}`
}

type SettingsTab = 'modules' | 'scraper' | 'newsletter' | 'apps' | 'compass' | 'kb' | 'notifications'

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
  last_error?: string
  recent_errors?: string[]
  circuit_breaker?: string
  healthy?: boolean
}

interface NewsletterStats {
  subscriber_count?: number
  sent?: number
  opened?: number
  bounced?: number
  lists?: NewsletterList[]
}

interface NewsletterList {
  id?: number
  name?: string
  subscriber_count?: number
  enabled?: boolean
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

  const [newsletterStats, setNewsletterStats] = useState<NewsletterStats | null>(null)
  const [newsletterLists, setNewsletterLists] = useState<NewsletterList[]>([])
  const [scraperTestResult, setScraperTestResult] = useState<string | null>(null)

  const [forceUpdate, setForceUpdate] = useState(false)
  const [forceUpdateVersion, setForceUpdateVersion] = useState('')
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Notifications tab state
  const [notifTitle, setNotifTitle] = useState('')
  const [notifBody, setNotifBody] = useState('')
  const [notifConfirm, setNotifConfirm] = useState(false)
  const [notifResult, setNotifResult] = useState<string | null>(null)
  const [notifSending, setNotifSending] = useState(false)

  useEffect(() => {
    async function load() {
      const [hlr, claude, deepl, notif, arweave, jobs, version, compass, nlStats, nlLists] = await Promise.allSettled([
        fetch(`${API}/api/v1/identity/hlr/credits`).then(r => r.json()),
        fetch(`${API}/api/v1/claude/budget`).then(r => r.json()),
        fetch(`${API}/api/v1/admin/deepl/usage`).then(r => r.json()),
        fetch(`${API}/api/v1/notifications/status`).then(r => r.json()),
        fetch(`${API}/api/v1/arweave/status`).then(r => r.json()),
        fetch(`${API}/api/v1/scraper/jobs`).then(r => r.json()),
        fetch(`${API}/api/v1/app/version`).then(r => r.json()),
        fetch(adminProxyPath('/api/v1/admin/compass/pending-review')).then(r => r.json()),
        fetch(`${API}/api/v1/newsletter/stats`).then(r => r.json()),
        fetch(`${API}/api/v1/newsletter/lists`).then(r => r.json()),
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
      const nlStatsVal = v(nlStats) as NewsletterStats | null
      setNewsletterStats(nlStatsVal)
      const nlListsVal = v(nlLists)
      setNewsletterLists(Array.isArray(nlListsVal) ? nlListsVal as NewsletterList[] : [])
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
      await fetch(adminProxyPath(`/api/v1/admin/compass/${action}/${id}`), { method: 'POST' })
      setCompassPending(prev => prev.filter(q => q.id !== id))
    } catch { /* non-critical */ }
    finally { setActionLoading(null) }
  }

  const hlrPrimary = hlrData?.primary as Record<string, unknown> | null

  async function handleSendPush() {
    setNotifSending(true)
    setNotifResult(null)
    try {
      const res = await fetch(adminProxyPath('/api/v1/notify/send'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title_el: notifTitle, body_el: notifBody, title_en: notifTitle, body_en: notifBody }),
      })
      const data = await res.json() as Record<string, unknown>
      if (res.ok) {
        const sent = data?.sent ?? data?.devices ?? data?.count
        setNotifResult(sent != null ? `Εστάλη σε ${String(sent)} συσκευές` : 'Εστάλη επιτυχώς')
        setNotifTitle('')
        setNotifBody('')
      } else {
        setNotifResult(`Σφάλμα: ${String(data?.detail ?? data?.error ?? res.status)}`)
      }
    } catch (e) {
      setNotifResult(`Σφάλμα αποστολής: ${String(e)}`)
    } finally {
      setNotifSending(false)
      setNotifConfirm(false)
    }
  }

  const tabs: { key: SettingsTab; label: string }[] = [
    { key: 'modules', label: 'Module' },
    { key: 'scraper', label: 'Αυτοματισμοί' },
    { key: 'newsletter', label: 'Newsletter' },
    { key: 'apps', label: 'Apps' },
    { key: 'compass', label: 'Compass' },
    { key: 'kb', label: 'Βάση Γνώσεων' },
    { key: 'notifications', label: 'Ειδοποιήσεις' },
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
                  const isParliament = (job.name ?? job.job_id ?? '').toLowerCase().includes('parliament') || (job.name ?? job.job_id ?? '').toLowerCase().includes('βουλ')
                  const isDiavgeia = (job.name ?? job.job_id ?? '').toLowerCase().includes('diavgeia')
                  const errors: string[] = Array.isArray(job.recent_errors) ? job.recent_errors.slice(0, 3) : job.last_error ? [String(job.last_error)] : []
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
                        <div className="text-xs text-red-500 mt-0.5">{String('Σφάλματα:')} {String(job.error_count)}</div>
                      )}
                      {errors.length > 0 && (
                        <div className="mt-1">
                          <div className="text-xs font-medium text-red-600 mb-0.5">{String('Τελευταία σφάλματα:')}</div>
                          {errors.map((e, ei) => (
                            <div key={ei} className="text-xs text-red-500 bg-red-50 rounded px-1.5 py-0.5 mb-0.5 truncate">{String(e)}</div>
                          ))}
                        </div>
                      )}
                      {(isParliament || isDiavgeia) && (
                        <div className="mt-2">
                          <button
                            onClick={() => handleAction(`run-${i}`, () => {
                              const url = isDiavgeia
                                ? adminProxyPath('/api/v1/admin/diavgeia/scrape')
                                : adminProxyPath('/api/v1/scraper/fetch')
                              return fetch(url, { method: 'POST' }).then(r => r.json())
                            })}
                            disabled={actionLoading === `run-${i}`}
                            className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium hover:bg-blue-200 transition-colors disabled:opacity-50"
                          >
                            {actionLoading === `run-${i}` ? String('Εκτέλεση...') : String('Εκτέλεση τώρα')}
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400 mb-4">{String('Δεν βρέθηκαν δεδομένα jobs')}</div>
            )}
            <div className="flex flex-wrap gap-3">
              <button
                onClick={async () => {
                  setActionLoading('test')
                  setScraperTestResult(null)
                  try {
                    const res = await fetch(`${API}/api/v1/scraper/test`).then(r => r.json())
                    setScraperTestResult(JSON.stringify(res, null, 2))
                  } catch (e) {
                    setScraperTestResult(String(e))
                  } finally {
                    setActionLoading(null)
                  }
                }}
                disabled={actionLoading === 'test'}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'test' ? String('Δοκιμή...') : String('Δοκιμή Scraper')}
              </button>
              <button
                onClick={() => handleAction('heal', () => fetch(adminProxyPath('/api/v1/admin/scraper/heal-status'), { method: 'POST' }))}
                disabled={actionLoading === 'heal'}
                className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-sm font-medium hover:bg-yellow-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'heal' ? String('Επιδιόρθωση...') : String('Επιδιόρθωση Scraper')}
              </button>
              <button
                onClick={() => handleAction('diavgeia-refresh', () => fetch(adminProxyPath('/api/v1/admin/diavgeia/refresh-orgs-cache'), { method: 'POST' }).then(r => r.json()))}
                disabled={actionLoading === 'diavgeia-refresh'}
                className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium hover:bg-purple-200 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'diavgeia-refresh' ? String('Ανανέωση...') : String('Diavgeia Org-Cache')}
              </button>
            </div>
            {scraperTestResult && (
              <div className="mt-3 bg-gray-900 text-green-400 rounded-lg p-3 text-xs font-mono whitespace-pre-wrap overflow-auto max-h-40">
                {scraperTestResult}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Newsletter */}
      {tab === 'newsletter' && (
        <div className="space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Συνδρομητές')}</div>
              <div className="text-2xl font-bold text-blue-600">
                {newsletterStats?.subscriber_count != null ? String(newsletterStats.subscriber_count) : String('—')}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Απεστάλησαν')}</div>
              <div className="text-2xl font-bold text-gray-800">
                {newsletterStats?.sent != null ? String(newsletterStats.sent) : String('—')}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Ανοίχτηκαν')}</div>
              <div className="text-2xl font-bold text-green-600">
                {newsletterStats?.opened != null ? String(newsletterStats.opened) : String('—')}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Αναπήδησαν')}</div>
              <div className="text-2xl font-bold text-red-600">
                {newsletterStats?.bounced != null ? String(newsletterStats.bounced) : String('—')}
              </div>
            </div>
          </div>

          {/* Lists */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h2 className="font-semibold text-gray-900 mb-3">{String('Λίστες')}</h2>
            {newsletterLists.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {newsletterLists.map((list, i) => (
                  <div key={list.id ?? i} className="flex items-center justify-between py-2.5">
                    <div>
                      <span className="text-sm font-medium text-gray-800">{String(list.name ?? `List ${i + 1}`)}</span>
                      {list.subscriber_count != null && (
                        <span className="ml-2 text-xs text-gray-400">{String(list.subscriber_count)} {String('συνδρομητές')}</span>
                      )}
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${list.enabled !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {list.enabled !== false ? String('Ενεργή') : String('Ανενεργή')}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-400">{String('Δεν βρέθηκαν λίστες')}</div>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h2 className="font-semibold text-gray-900 mb-3">{String('Ενέργειες')}</h2>
            <div className="flex flex-wrap gap-3 mb-3">
              <a
                href="https://listmonk.ekklesia.gr"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                {String('Listmonk Admin')}
              </a>
              <button
                disabled
                title="Χρησιμοποίησε Listmonk Admin για εκστρατείες"
                className="px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                {String('Εκκίνηση Καμπάνιας')}
              </button>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
              {String('Χρησιμοποίησε Listmonk Admin για τη διαχείριση καμπανιών newsletter.')}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Apps */}
      {tab === 'apps' && (
        <div className="space-y-4">
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
          </div>

          {/* Force Update + Minimum Version */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h2 className="font-semibold text-gray-900 mb-3">{String('Αναγκαστική Ενημέρωση')}</h2>
            <div className="divide-y divide-gray-100">
              <Toggle
                id="force_update"
                label="Force Update"
                value={appVersion?.force_update === true || forceUpdate}
                onChange={setForceUpdate}
                sub={String('Αλλαγή μέσω .env: APP_FORCE_UPDATE=true')}
              />
              <div className="py-3">
                <label className="block text-sm font-medium text-gray-700 mb-1">{String('Ελάχιστη Έκδοση (Version Code)')}</label>
                <input
                  type="text"
                  value={forceUpdateVersion || String(appVersion?.min_required_version_code ?? '')}
                  onChange={(e) => setForceUpdateVersion(e.target.value)}
                  placeholder="π.χ. 5"
                  className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div className="text-xs text-gray-400 mt-1">{String('Αλλαγή μέσω .env: APP_MIN_VERSION_CODE=X')}</div>
              </div>
            </div>
          </div>

          {/* Maintenance Mode */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h2 className="font-semibold text-gray-900 mb-3">{String('Λειτουργία Συντήρησης')}</h2>
            <Toggle
              id="maintenance"
              label="Maintenance Mode"
              value={maintenanceMode}
              onChange={setMaintenanceMode}
              warning={maintenanceMode ? String('Η σελίδα θα κλείσει για τους χρήστες') : undefined}
            />
            {maintenanceMode && (
              <div className="mt-2 bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">
                {String('Προσοχή: Ενεργοποίηση Maintenance Mode κλείνει την εφαρμογή για όλους τους χρήστες.')}
              </div>
            )}
          </div>

          {/* Info box */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
            <div className="font-medium mb-1">{String('Backend-Endpoints fehlen')}</div>
            <div className="text-xs text-blue-700">
              {String('Backend-Endpoints fuer Live-Aenderungen fehlen — .env auf Server aendern und Container neu starten.')}
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
                fetch(adminProxyPath('/api/v1/admin/compass/generate-questions'), { method: 'POST' }).then(r => r.json())
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
          <h2 className="font-semibold text-gray-900 mb-3">{String('Βάση Γνώσεων (RAG)')}</h2>
          <div className="bg-gray-50 rounded-lg p-6 text-center">
            <div className="text-sm font-medium text-gray-500">{String('Βάση Γνώσεων CRUD — Phase 2')}</div>
            <div className="text-xs text-gray-400 mt-1">{String('FAQ, Αποστολή, Concepts για τον RAG Agent')}</div>
          </div>
        </div>
      )}

      {/* Tab 6: Notifications */}
      {tab === 'notifications' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900 mb-1">{String('Push Notifications')}</h2>
          {notifData?.device_count != null && (
            <div className="text-xs text-gray-400 mb-4">
              {String('Εγγεγραμμένες συσκευές:')} <span className="font-medium text-gray-700">{String(notifData.device_count)}</span>
            </div>
          )}

          <div className="space-y-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{String('Τίτλος')}</label>
              <input
                type="text"
                maxLength={50}
                value={notifTitle}
                onChange={(e) => setNotifTitle(e.target.value)}
                placeholder="max 50 χαρακτήρες"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="text-right text-xs text-gray-400 mt-0.5">{String(notifTitle.length)}/50</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{String('Μήνυμα')}</label>
              <textarea
                maxLength={200}
                rows={4}
                value={notifBody}
                onChange={(e) => setNotifBody(e.target.value)}
                placeholder="max 200 χαρακτήρες"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <div className="text-right text-xs text-gray-400 mt-0.5">{String(notifBody.length)}/200</div>
            </div>
          </div>

          {!notifConfirm ? (
            <button
              onClick={() => setNotifConfirm(true)}
              disabled={!notifTitle.trim() || !notifBody.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {String('Αποστολή Push')}
            </button>
          ) : (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="text-sm font-medium text-yellow-800 mb-1">{String('Επιβεβαίωση Αποστολής')}</div>
              <div className="text-sm text-yellow-700 mb-3">{String('Η ειδοποίηση θα σταλεί σε όλες τις εγγεγραμμένες συσκευές. Συνέχεια;')}</div>
              <div className="flex gap-2">
                <button
                  onClick={handleSendPush}
                  disabled={notifSending}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {notifSending ? String('Αποστολή...') : String('Ναι, Αποστολή')}
                </button>
                <button
                  onClick={() => setNotifConfirm(false)}
                  disabled={notifSending}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 disabled:opacity-50"
                >
                  {String('Ακύρωση')}
                </button>
              </div>
            </div>
          )}

          {notifResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm font-medium ${notifResult.startsWith('Σφάλμα') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
              {String(notifResult)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

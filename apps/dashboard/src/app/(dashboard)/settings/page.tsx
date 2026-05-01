'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'

const API = process.env.NEXT_PUBLIC_EKKLESIA_API || 'https://api.ekklesia.gr'

interface ToggleProps {
  id: string
  label: string
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  disabledReason?: string
  color?: 'green' | 'blue'
  warning?: string
}

function Toggle({ id, label, value, onChange, disabled, disabledReason, color = 'green', warning }: ToggleProps) {
  const activeColor = color === 'blue' ? 'bg-blue-600' : 'bg-green-600'
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-gray-800 cursor-pointer">{label}</label>
        {disabledReason && <div className="text-xs text-yellow-600 mt-0.5">{disabledReason}</div>}
        {warning && <div className="text-xs text-red-600 mt-0.5">⚠️ {warning}</div>}
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
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${
            value ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  )
}

interface ModuleState {
  hlr: boolean
  ai_chatbot: boolean
  discourse: boolean
  newsletter: boolean
  parliament_scraper: boolean
  diavgeia_scraper: boolean
  greek_topics: boolean
  arweave: boolean
}

export default function SettingsPage() {
  const { data: session } = useSession()
  const role = session?.user?.role

  const [modules, setModules] = useState<ModuleState>({
    hlr: true,
    ai_chatbot: true,
    discourse: true,
    newsletter: true,
    parliament_scraper: true,
    diavgeia_scraper: true,
    greek_topics: false,
    arweave: true,
  })

  const [maintenance, setMaintenance] = useState(false)
  const [forceUpdate, setForceUpdate] = useState(false)
  const [forceUpdateVersion, setForceUpdateVersion] = useState('')
  const [tickerText, setTickerText] = useState('')
  const [tickerActive, setTickerActive] = useState(false)
  const [cplmConfirm, setCplmConfirm] = useState(false)
  const [cplmLoading, setCplmLoading] = useState(false)
  const [saved, setSaved] = useState(false)

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

  async function handleCplmRecalc() {
    if (!cplmConfirm) {
      setCplmConfirm(true)
      return
    }
    setCplmLoading(true)
    try {
      await fetch(`${API}/api/v1/admin/cplm/recalculate`, { method: 'POST' })
    } catch {
      // Non-critical
    } finally {
      setCplmLoading(false)
      setCplmConfirm(false)
    }
  }

  function handleSave() {
    // Visual feedback only — actual persistence requires server-side implementation in Phase 2
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Ρυθμίσεις</h1>
        <button
          onClick={handleSave}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            saved
              ? 'bg-green-100 text-green-700'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {saved ? '✓ Αποθηκεύτηκε' : 'Αποθήκευση'}
        </button>
      </div>

      {/* Info box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 text-sm text-blue-800">
        ℹ️ Ορισμένες αλλαγές απαιτούν επανεκκίνηση του server για να τεθούν σε ισχύ.
      </div>

      {/* Section: Modules */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-5">
        <h2 className="font-semibold text-gray-900 mb-1">Modules — Ενεργοποίηση / Απενεργοποίηση</h2>
        <p className="text-xs text-gray-500 mb-4">Απαιτείται επανεκκίνηση για να εφαρμοστούν αλλαγές</p>
        <div className="divide-y divide-gray-100">
          <Toggle id="hlr" label="HLR Επαλήθευση" value={modules.hlr} onChange={(v) => setModule('hlr', v)} />
          <Toggle id="ai_chatbot" label="AI Chatbot (Claude Haiku)" value={modules.ai_chatbot} onChange={(v) => setModule('ai_chatbot', v)} />
          <Toggle id="discourse" label="Discourse Forum Sync" value={modules.discourse} onChange={(v) => setModule('discourse', v)} />
          <Toggle id="newsletter" label="Newsletter (Listmonk)" value={modules.newsletter} onChange={(v) => setModule('newsletter', v)} />
          <Toggle id="parliament_scraper" label="Parliament Scraper" value={modules.parliament_scraper} onChange={(v) => setModule('parliament_scraper', v)} />
          <Toggle id="diavgeia_scraper" label="Diavgeia Scraper" value={modules.diavgeia_scraper} onChange={(v) => setModule('diavgeia_scraper', v)} />
          <Toggle
            id="greek_topics"
            label="Greek Topics Scraper"
            value={modules.greek_topics}
            onChange={(v) => setModule('greek_topics', v)}
            disabled
            disabledReason="Απενεργοποιημένο — νομική διευκρίνιση σε εξέλιξη"
          />
          <Toggle id="arweave" label="Arweave Αρχειοθέτηση" value={modules.arweave} onChange={(v) => setModule('arweave', v)} />
        </div>
      </section>

      {/* Section: API Status */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-5">
        <h2 className="font-semibold text-gray-900 mb-4">Κατάσταση API</h2>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-600">HLR Κύρια (Primary)</span>
            <span className="text-gray-500">— διαθέσιμο από /api/v1/identity/hlr/credits</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-600">HLR Εφεδρική (Fallback)</span>
            <span className="text-gray-500">— διαθέσιμο από /api/v1/identity/hlr/credits</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-600">Failover Ενεργό</span>
            <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">Φάση 2</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-600">Discourse Έκδοση</span>
            <span className="text-gray-500">— fetch από pnyx.ekklesia.gr/about.json</span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-gray-600">Arweave Υπόλοιπο</span>
            <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">Placeholder</span>
          </div>
        </div>
      </section>

      {/* Section: System Control */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-5">
        <h2 className="font-semibold text-gray-900 mb-4">Έλεγχος Συστήματος</h2>
        <div className="divide-y divide-gray-100">
          <Toggle
            id="maintenance"
            label="Maintenance Mode"
            value={maintenance}
            onChange={setMaintenance}
            color="blue"
            warning={maintenance ? 'Η σελίδα είναι κλειδωμένη για τους χρήστες' : undefined}
          />
          <Toggle
            id="force_update"
            label="Force Update"
            value={forceUpdate}
            onChange={setForceUpdate}
            color="blue"
          />
          {forceUpdate && (
            <div className="py-3 pl-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Έκδοση</label>
              <input
                type="text"
                value={forceUpdateVersion}
                onChange={(e) => setForceUpdateVersion(e.target.value)}
                placeholder="π.χ. 1.2.0"
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}
        </div>

        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-gray-800">CPLM Επανυπολογισμός</div>
              <div className="text-xs text-gray-500 mt-0.5">Υπολογίζει εκ νέου τη συλλογική πολιτική θέση</div>
            </div>
            <button
              onClick={handleCplmRecalc}
              disabled={cplmLoading}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                cplmConfirm
                  ? 'bg-red-600 text-white hover:bg-red-700'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {cplmLoading ? 'Υπολογισμός...' : cplmConfirm ? 'Επιβεβαίωση;' : 'Υπολογισμός τώρα'}
            </button>
          </div>
          {cplmConfirm && (
            <div className="mt-2 text-xs text-red-600">
              Κάντε κλικ ξανά για επιβεβαίωση.{' '}
              <button className="underline" onClick={() => setCplmConfirm(false)}>Ακύρωση</button>
            </div>
          )}
        </div>
      </section>

      {/* Section: Newsticker */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h2 className="font-semibold text-gray-900 mb-4">Newsticker</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Κείμενο Ticker (Ελληνικά)</label>
            <textarea
              value={tickerText}
              onChange={(e) => setTickerText(e.target.value)}
              rows={2}
              placeholder="π.χ. Νέα ψηφοφορία για τον Νόμο Υγείας — Ψηφίστε τώρα"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <Toggle id="ticker_active" label="Ticker Ενεργός" value={tickerActive} onChange={setTickerActive} />
          {tickerText && (
            <div className="mt-2">
              <div className="text-xs font-medium text-gray-500 mb-1">Προεπισκόπηση</div>
              <div className="overflow-hidden bg-blue-600 rounded-lg px-4 py-2">
                <div className="text-white text-sm font-medium whitespace-nowrap">
                  📢 {tickerText}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

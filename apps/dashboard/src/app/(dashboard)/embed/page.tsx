'use client'

import { useState, useMemo } from 'react'

type EmbedType = 'vote' | 'results' | 'cplm' | 'lifecycle' | 'divergence'
type BillFilter = 'all' | 'district' | 'single'
type EmbedSize = 'compact' | 'normal' | 'large'
type EmbedLang = 'el' | 'en' | 'both'
type EmbedTheme = 'light' | 'dark'

const EMBED_TYPES: { value: EmbedType; label: string }[] = [
  { value: 'vote', label: 'Ψηφοφορία' },
  { value: 'results', label: 'Αποτελέσματα' },
  { value: 'cplm', label: 'CPLM Χάρτης' },
  { value: 'lifecycle', label: 'Κύκλος Ζωής' },
  { value: 'divergence', label: 'Δείκτης Απόκλισης' },
]

const SIZES: { value: EmbedSize; label: string; height: number }[] = [
  { value: 'compact', label: 'Συμπαγές', height: 300 },
  { value: 'normal', label: 'Κανονικό', height: 450 },
  { value: 'large', label: 'Μεγάλο', height: 600 },
]

export default function EmbedPage() {
  const [embedType, setEmbedType] = useState<EmbedType>('vote')
  const [billFilter, setBillFilter] = useState<BillFilter>('all')
  const [billId, setBillId] = useState('')
  const [size, setSize] = useState<EmbedSize>('normal')
  const [lang, setLang] = useState<EmbedLang>('el')
  const [theme, setTheme] = useState<EmbedTheme>('light')
  const [copied, setCopied] = useState(false)

  const height = SIZES.find(s => s.value === size)?.height ?? 450

  const embedUrl = useMemo(() => {
    const params = new URLSearchParams()
    params.set('type', embedType)
    params.set('lang', lang)
    params.set('theme', theme)
    params.set('size', size)
    if (billFilter === 'single' && billId) params.set('bill', billId)
    if (billFilter === 'district') params.set('district', 'auto')
    return `https://ekklesia.gr/embed?${params.toString()}`
  }, [embedType, billFilter, billId, size, lang, theme])

  const embedCode = useMemo(() => {
    const titleMap: Record<EmbedType, string> = {
      vote: 'Ψηφοφορία πολιτών',
      results: 'Αποτελέσματα ψηφοφορίας',
      cplm: 'Πολιτικός Καθρέφτης',
      lifecycle: 'Κύκλος Δημοκρατίας',
      divergence: 'Δείκτης Απόκλισης',
    }
    return `<iframe
  src="${embedUrl}"
  width="100%" height="${height}"
  frameborder="0" loading="lazy"
  style="border:1px solid #2563eb;border-radius:8px"
  title="ekklesia.gr — ${titleMap[embedType]}">
</iframe>
<p style="font-size:12px;color:#6b7280;margin-top:4px">
  Πηγή: <a href="https://ekklesia.gr">ekklesia.gr</a> |
  <a href="https://ekklesia.gr/el/bills">Ψηφίστε στο ekklesia.gr</a> |
  Περισσότερα στο <a href="https://ekklesia.gr">ekklesia.gr</a>
</p>`
  }, [embedUrl, height, embedType])

  const handleCopy = () => {
    navigator.clipboard.writeText(embedCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Embed Κώδικας</h1>
          <p className="text-sm text-gray-500 mt-1">Δημιουργήστε κώδικα ενσωμάτωσης για εξωτερικές ιστοσελίδες</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Filters */}
        <div className="space-y-5">
          {/* Embed Type */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Τι να ενσωματωθεί;</h3>
            <div className="space-y-2">
              {EMBED_TYPES.map(t => (
                <label key={t.value} className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="embedType" value={t.value} checked={embedType === t.value}
                    onChange={() => setEmbedType(t.value)} className="text-blue-600" />
                  <span className="text-sm text-gray-700">{t.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Bill Filter */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Φίλτρο νομοσχεδίων</h3>
            <div className="space-y-2">
              {[
                { value: 'all' as BillFilter, label: 'Όλα τα νομοσχέδια' },
                { value: 'district' as BillFilter, label: 'Κατά περιφέρεια (αυτόματα)' },
                { value: 'single' as BillFilter, label: 'Συγκεκριμένο νομοσχέδιο' },
              ].map(f => (
                <label key={f.value} className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="billFilter" value={f.value} checked={billFilter === f.value}
                    onChange={() => setBillFilter(f.value)} className="text-blue-600" />
                  <span className="text-sm text-gray-700">{f.label}</span>
                </label>
              ))}
            </div>
            {billFilter === 'single' && (
              <input type="text" value={billId} onChange={e => setBillId(e.target.value)}
                placeholder="π.χ. GR-5293" className="mt-3 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            )}
          </div>

          {/* Size + Lang + Theme */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Εμφάνιση</h3>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500">Μέγεθος</label>
                <select value={size} onChange={e => setSize(e.target.value as EmbedSize)}
                  className="w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm">
                  {SIZES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500">Γλώσσα</label>
                <select value={lang} onChange={e => setLang(e.target.value as EmbedLang)}
                  className="w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm">
                  <option value="el">Ελληνικά</option>
                  <option value="en">English</option>
                  <option value="both">Δίγλωσσο</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500">Θέμα</label>
                <select value={theme} onChange={e => setTheme(e.target.value as EmbedTheme)}
                  className="w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm">
                  <option value="light">Φωτεινό</option>
                  <option value="dark">Σκοτεινό</option>
                </select>
              </div>
            </div>
          </div>

          {/* Attribution — always on */}
          <div className="bg-green-50 border border-green-200 rounded-xl p-4">
            <div className="flex items-center gap-2">
              <span className="text-green-600">✅</span>
              <span className="text-sm font-medium text-green-800">Αναφορά πηγής — πάντα εμφανής</span>
            </div>
            <p className="text-xs text-green-600 mt-1">
              Κάθε embed περιλαμβάνει: &quot;Πηγή: ekklesia.gr&quot; + σύνδεσμο ψηφοφορίας + &quot;Περισσότερα στο ekklesia.gr&quot;
            </p>
          </div>
        </div>

        {/* Right: Preview + Code */}
        <div className="space-y-5">
          {/* Preview */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Προεπισκόπηση</h3>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4" style={{ minHeight: Math.min(height, 300) }}>
              <div className="flex items-center justify-center h-full text-center">
                <div>
                  <div className="text-3xl mb-2">🔗</div>
                  <div className="text-sm text-gray-500">Embed Προεπισκόπηση</div>
                  <div className="text-xs text-gray-400 mt-1">
                    Τύπος: {EMBED_TYPES.find(t => t.value === embedType)?.label} | {String(height)}px
                  </div>
                  <div className="text-xs text-blue-500 mt-2 break-all">{embedUrl}</div>
                </div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-2 text-center">
              Embed endpoints (/embed/*) υλοποιούνται σε Φάση 2
            </div>
          </div>

          {/* Generated Code */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">Κώδικας HTML</h3>
              <div className="flex gap-2">
                <button onClick={handleCopy}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 transition-colors">
                  {copied ? '✓ Αντιγράφηκε!' : 'Αντιγραφή'}
                </button>
                <button onClick={() => window.open(embedUrl, '_blank')}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors">
                  Δοκιμή →
                </button>
              </div>
            </div>
            <pre className="bg-gray-900 text-green-400 rounded-lg p-4 text-xs overflow-x-auto whitespace-pre-wrap font-mono">
              {embedCode}
            </pre>
          </div>

          {/* Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="text-sm font-medium text-blue-800 mb-1">Πληροφορίες Ενσωμάτωσης</div>
            <ul className="text-xs text-blue-600 space-y-1">
              <li>• Ο κώδικας λειτουργεί σε οποιαδήποτε ιστοσελίδα (HTML/WordPress/CMS)</li>
              <li>• Αυτόματη προσαρμογή στο πλάτος του container</li>
              <li>• Χωρίς cookies, χωρίς tracking, χωρίς εξωτερικές εξαρτήσεις</li>
              <li>• Δωρεάν χρήση υπό CC BY 4.0</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

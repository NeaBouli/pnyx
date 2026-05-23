'use client'

import { useCallback, useEffect, useState } from 'react'

interface Campaign {
  id: number
  name: string
  subject: string
  status: string
  sent_date: string | null
  stats: Record<string, number>
}

export default function NewsletterAdminPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)

  // Compose
  const [subject, setSubject] = useState('')
  const [htmlContent, setHtmlContent] = useState('')
  const [preview, setPreview] = useState<string | null>(null)
  const [draftId, setDraftId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    try {
      const r = await fetch('/api/proxy/admin/newsletter/stats')
      if (r.ok) {
        const data = await r.json()
        setCampaigns(data.recent_campaigns || [])
      }
    } catch { /* */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  async function handlePreview() {
    if (!subject || !htmlContent) return
    setError(null)
    setSuccess(null)
    try {
      const r = await fetch('/api/proxy/admin/newsletter/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, html_content: htmlContent }),
      })
      if (r.ok) {
        const data = await r.json()
        if (data.html_preview) {
          setPreview(data.html_preview)
        } else {
          setError('API returned no preview HTML')
        }
      } else {
        const errData = await r.json().catch(() => ({}))
        setError(errData.detail || errData.error || `Preview fehlgeschlagen (${r.status})`)
      }
    } catch { setError('Netzwerkfehler') }
  }

  async function handleDraft() {
    if (!subject || !htmlContent) return
    setSubmitting(true)
    setError(null)
    try {
      const r = await fetch('/api/proxy/admin/newsletter/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, html_content: htmlContent }),
      })
      if (r.ok) {
        const data = await r.json()
        setDraftId(data.campaign_id)
        setSuccess(`Draft erstellt: #${data.campaign_id}`)
        loadStats()
      } else {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Draft fehlgeschlagen')
      }
    } catch { setError('Netzwerkfehler') }
    finally { setSubmitting(false) }
  }

  async function handleSend() {
    if (!draftId) return
    if (!confirm('Newsletter jetzt an alle Abonnenten senden?')) return
    setSending(true)
    setError(null)
    try {
      const r = await fetch('/api/proxy/admin/newsletter/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaign_id: draftId, confirm: true }),
      })
      if (r.ok) {
        setSuccess('Newsletter gesendet!')
        setDraftId(null)
        setSubject('')
        setHtmlContent('')
        setPreview(null)
        loadStats()
      } else {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Senden fehlgeschlagen')
      }
    } catch { setError('Netzwerkfehler') }
    finally { setSending(false) }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Newsletter — Compose & Send</h1>

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-4">{error}</div>}
      {success && <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 mb-4">{success}</div>}

      {/* Compose */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Compose</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Betreff</label>
            <input
              value={subject} onChange={e => setSubject(e.target.value)}
              placeholder="ekklesia.gr — Μηνιαία Αναφορά"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">HTML Inhalt</label>
            <textarea
              value={htmlContent} onChange={e => setHtmlContent(e.target.value)}
              rows={10} placeholder="<h2>Neuigkeiten...</h2><p>...</p>"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">Header + Footer werden automatisch hinzugefügt. Keine Attachments in v1.</p>
          </div>
          <div className="flex gap-3">
            <button onClick={handlePreview} className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
              Vorschau
            </button>
            <button onClick={handleDraft} disabled={submitting || !subject || !htmlContent}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
              {submitting ? 'Wird erstellt...' : 'Draft erstellen'}
            </button>
            {draftId && (
              <button onClick={handleSend} disabled={sending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50">
                {sending ? 'Wird gesendet...' : `Draft #${draftId} senden`}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Vorschau</h2>
          <div className="border border-gray-100 rounded-lg p-4 bg-gray-50" dangerouslySetInnerHTML={{ __html: preview }} />
        </div>
      )}

      {/* Recent Campaigns */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-800">Letzte Campaigns</h2>
        </div>
        {loading ? (
          <div className="p-6"><div className="animate-pulse bg-gray-200 rounded h-10" /></div>
        ) : campaigns.length === 0 ? (
          <div className="p-6 text-center text-gray-500">Keine Campaigns gefunden.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Gesendet</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {campaigns.map(c => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-700">#{c.id}</td>
                    <td className="px-4 py-3 text-gray-900 font-medium">{c.name || c.subject}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        c.status === 'sent' ? 'bg-green-100 text-green-700' :
                        c.status === 'draft' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-gray-100 text-gray-500'
                      }`}>{c.status}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{c.sent_date || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

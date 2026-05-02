'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

export default function ForumPage() {
  const [discourse, setDiscourse] = useState<Record<string, unknown> | null>(null)
  const [forumSyncEnabled, setForumSyncEnabled] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [aboutRes, healthRes] = await Promise.allSettled([
          fetch('/api/discourse').then(r => r.json()),
          fetch(`${API}/health`).then(r => r.json()),
        ])
        if (aboutRes.status === 'fulfilled') setDiscourse(aboutRes.value as Record<string, unknown>)
        if (healthRes.status === 'fulfilled') {
          const modules = (healthRes.value as Record<string, unknown>)?.modules as Record<string, unknown> | undefined
          if (modules?.forum_sync !== undefined) {
            setForumSyncEnabled(modules.forum_sync === 'ok' || modules.forum_sync === true)
          }
        }
      } catch { /* non-critical */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  const about = discourse?.about as Record<string, unknown> | undefined
  const version = about?.version as string | undefined
  const title = about?.title as string | undefined
  const description = about?.description as string | undefined
  const isOnline = version != null

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{String('Forum (Discourse)')}</h1>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          isOnline ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {isOnline ? String('Ενεργό') : String('Εκτός Σύνδεσης')}
        </span>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">{String('Φόρτωση...')}</div>
      ) : (
        <div className="space-y-6">
          {/* Stats cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Discourse Έκδοση')}</div>
              <div className="text-2xl font-bold text-blue-600">{String(version ?? '—')}</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="text-xs text-gray-500 mb-1">{String('Τίτλος Forum')}</div>
              <div className="text-lg font-bold text-blue-600">{String(title ?? '—')}</div>
            </div>
          </div>

          {/* Forum details */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">{String('Λεπτομέρειες Forum')}</h2>
            </div>
            <div className="p-5 space-y-3 text-sm">
              {title && (
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-600">{String('Τίτλος')}</span>
                  <span className="text-gray-800">{String(title)}</span>
                </div>
              )}
              {description && (
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-600">{String('Περιγραφή')}</span>
                  <span className="text-gray-500 text-xs max-w-xs truncate">{String(description)}</span>
                </div>
              )}
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-gray-600">{String('URL')}</span>
                <a href="https://pnyx.ekklesia.gr" target="_blank" rel="noopener noreferrer"
                  className="text-blue-600 hover:underline">{String('pnyx.ekklesia.gr')}</a>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-gray-600">{String('Admin Panel')}</span>
                <a href="https://pnyx.ekklesia.gr/admin" target="_blank" rel="noopener noreferrer"
                  className="text-blue-600 hover:underline">{String('Admin →')}</a>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-gray-600">{String('Bill-Sync Κατάσταση')}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  forumSyncEnabled === true ? 'bg-green-100 text-green-700' :
                  forumSyncEnabled === false ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-500'
                }`}>
                  {forumSyncEnabled === true ? String('Ενεργοποιημένο') :
                   forumSyncEnabled === false ? String('Απενεργοποιημένο') :
                   String('Άγνωστο')}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-gray-600">{String('SSO Provider')}</span>
                <span className="text-gray-500">{String('Discourse Connect (HMAC)')}</span>
              </div>
            </div>
          </div>

          {/* Synced bills placeholder */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">{String('Τελευταία Συγχρονισμένα Bills')}</h2>
            </div>
            <div className="p-8 text-center text-gray-400">
              <div className="text-sm">{String('Η λίστα των συγχρονισμένων bills εμφανίζεται μόνο αν το FORUM_SYNC_ENABLED είναι ενεργό.')}</div>
              <div className="text-xs text-gray-300 mt-1">{String('Κάθε 10 λεπτά, max 20 bills/sync')}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

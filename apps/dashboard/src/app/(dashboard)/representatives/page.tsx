'use client'

import { useState, useEffect, useCallback } from 'react'

type Role = 'Βουλευτής' | 'Περιφερειάρχης' | 'Δήμαρχος' | 'Δημοτικός Σύμβουλος'

interface Invite {
  id: number
  invite_code: string
  ada_number: string | null
  role: string
  region: string | null
  municipality: string | null
  used: boolean
  expired: boolean
  expires_at: string | null
  created_at: string | null
}

const ROLES: Role[] = ['Βουλευτής', 'Περιφερειάρχης', 'Δήμαρχος', 'Δημοτικός Σύμβουλος']

export default function RepresentativesPage() {
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [lastCode, setLastCode] = useState<string | null>(null)
  const [lastExpires, setLastExpires] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const [role, setRole] = useState<Role>('Βουλευτής')
  const [region, setRegion] = useState('')
  const [municipality, setMunicipality] = useState('')

  const loadInvites = useCallback(async () => {
    try {
      const r = await fetch('/api/proxy/rep/admin/invites')
      const data = await r.json()
      setInvites(Array.isArray(data) ? data : [])
    } catch {
      setError('Αδύνατη η φόρτωση προσκλήσεων')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadInvites() }, [loadInvites])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const r = await fetch('/api/proxy/rep/admin/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role,
          region: region || null,
          municipality: municipality || null,
        }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      setLastCode(data.invite_code)
      setLastExpires(data.expires_at)
      setSuccess(`Πρόσκληση δημιουργήθηκε: ${data.invite_code}`)
      setRegion('')
      setMunicipality('')
      setCopied(false)
      await loadInvites()
    } catch {
      setError('Αδύνατη η δημιουργία πρόσκλησης')
    } finally {
      setSubmitting(false)
    }
  }

  function handleCopy() {
    if (lastCode) {
      navigator.clipboard.writeText(lastCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Εκπρόσωποι — Προσκλήσεις</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>Κλείσιμο</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {success}
          <button className="ml-2 underline" onClick={() => setSuccess(null)}>Κλείσιμο</button>
        </div>
      )}

      {/* Create Invite Form */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Δημιουργία Πρόσκλησης</h2>
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ρόλος *</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Περιφέρεια</label>
              <input
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="π.χ. Αττικής"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Δήμος</label>
              <input
                value={municipality}
                onChange={(e) => setMunicipality(e.target.value)}
                placeholder="π.χ. Αθηναίων"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {submitting ? 'Δημιουργία...' : 'Δημιουργία Πρόσκλησης'}
          </button>
        </form>
      </div>

      {/* Last Generated Code */}
      {lastCode && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-blue-800">Κωδικός Πρόσκλησης</h3>
            {lastExpires && (
              <span className="text-xs text-blue-600">
                Ισχύει έως: {new Date(lastExpires).toLocaleString('el-GR')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-3xl font-mono font-bold text-blue-900 tracking-widest">{lastCode}</span>
            <button
              onClick={handleCopy}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
            >
              {copied ? 'Αντιγράφηκε!' : 'Αντιγραφή'}
            </button>
          </div>
          <div className="mt-4 flex items-center gap-4">
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(lastCode)}`}
              alt="QR Code"
              width={120}
              height={120}
              className="rounded-lg border border-blue-200"
            />
            <div className="text-xs text-blue-700 leading-relaxed">
              Ο εκπρόσωπος χρησιμοποιεί τον κωδικό μαζί με τον αριθμό ADA Διαύγειας
              για να ενεργοποιήσει τον λογαριασμό του στην εφαρμογή εκπρόσωπος.
            </div>
          </div>
        </div>
      )}

      {/* Invites List */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-700">Ιστορικό Προσκλήσεων</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
        ) : invites.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Δεν υπάρχουν προσκλήσεις</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κωδικός</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ρόλος</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Περιοχή</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">ADA</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ημερομηνία</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {invites.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono font-medium text-gray-900">{inv.invite_code}</td>
                    <td className="px-4 py-3 text-gray-700">{inv.role}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {[inv.region, inv.municipality].filter(Boolean).join(', ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{inv.ada_number || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        inv.used
                          ? 'bg-green-100 text-green-700'
                          : inv.expired
                            ? 'bg-red-100 text-red-700'
                            : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {inv.used ? 'Χρησιμοποιήθηκε' : inv.expired ? 'Έληξε' : 'Ανοιχτή'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {inv.created_at ? new Date(inv.created_at).toLocaleString('el-GR') : '—'}
                    </td>
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

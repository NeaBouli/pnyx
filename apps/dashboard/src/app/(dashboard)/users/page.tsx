'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { ROLE_MODULES, type DashboardRole } from '@/lib/auth'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

const ROLE_LABELS: Record<DashboardRole, string> = {
  SUPER_ADMIN: 'Super Admin',
  SYSTEM_ADMIN: 'Διαχειριστής',
  CONTENT: 'Περιεχόμενο',
  ANALYST: 'Αναλυτής',
  SUPPORT: 'Υποστήριξη',
  NODE_ADMIN: 'Node Admin',
}

export default function UsersPage() {
  const { data: session } = useSession()
  const [stats, setStats] = useState<{ total_identities?: number } | null>(null)

  useEffect(() => {
    async function loadStats() {
      try {
        const r = await fetch(`${API}/api/v1/admin/stats`)
        if (r.ok) {
          const data = await r.json()
          setStats(data)
        }
      } catch {
        // Stats not available — non-critical
      }
    }
    loadStats()
  }, [])

  const role = session?.user?.role as DashboardRole | undefined
  const username = session?.user?.githubUsername ?? session?.user?.name ?? '—'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Χρήστες</h1>

      {/* Phase 2 placeholder */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 mb-6">
        <div className="flex items-start gap-3">
          <span className="text-yellow-500 text-lg mt-0.5">⚠️</span>
          <div>
            <div className="font-semibold text-yellow-800">Φάση 2</div>
            <div className="text-sm text-yellow-700 mt-0.5">
              Η διαχείριση χρηστών υλοποιείται στη Φάση 2. Προς το παρόν εμφανίζονται βασικά στατιστικά.
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {/* Identity count */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">Καταχωρημένες Ταυτότητες</div>
          <div className="text-3xl font-bold text-blue-600">
            {stats?.total_identities != null
              ? stats.total_identities.toLocaleString('el-GR')
              : <span className="text-gray-400 text-lg">Μη διαθέσιμο</span>}
          </div>
          <div className="text-xs text-gray-400 mt-1">Ανώνυμες Ed25519 ταυτότητες</div>
        </div>

        {/* Current user */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">Τρέχων Χρήστης</div>
          <div className="text-xl font-semibold text-gray-900">{username}</div>
          {role && (
            <div className="mt-1">
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                {ROLE_LABELS[role]}
              </span>
            </div>
          )}
        </div>

        {/* Role permissions */}
        {role && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="text-sm text-gray-500 mb-2">Δικαιώματα Ρόλου</div>
            <div className="flex flex-wrap gap-1">
              {ROLE_MODULES[role].map((mod) => (
                <span key={mod} className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                  {mod}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Coming soon table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-800">Κατάλογος Χρηστών</h2>
          <p className="text-sm text-gray-500 mt-0.5">Διαθέσιμο στη Φάση 2</p>
        </div>
        <div className="p-12 text-center text-gray-400">
          <div className="text-4xl mb-3">👥</div>
          <div className="font-medium text-gray-500">Διαχείριση χρηστών — Φάση 2</div>
          <div className="text-sm mt-1">Αναλυτική λίστα, αναστολή λογαριασμών, εξαγωγή δεδομένων</div>
        </div>
      </div>
    </div>
  )
}

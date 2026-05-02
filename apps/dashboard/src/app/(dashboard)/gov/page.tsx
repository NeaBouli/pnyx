'use client'

import { useState, useEffect } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr'

type ApplicationStatus = 'pending' | 'approved' | 'rejected'

interface GovApplication {
  applicant: string
  district: string
  ada: string
  status: ApplicationStatus
  date: string
}

interface GovGrGates {
  '500_aktive_nutzer': boolean
  '3_ngo_partnerschaften': boolean
  roadmap_publiziert: boolean
  govgr_genehmigung: boolean
}

interface GovGrStatus {
  module: string
  status: string
  progress: string
  gates: GovGrGates
  env_configured: boolean
}

const APP_STATUS_LABELS: Record<ApplicationStatus, string> = {
  pending: 'Εκκρεμής',
  approved: 'Εγκρίθηκε',
  rejected: 'Απορρίφθηκε',
}

const APP_STATUS_COLORS: Record<ApplicationStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

const EXAMPLE_APPLICATIONS: GovApplication[] = [
  {
    applicant: 'Δήμος Αθηναίων',
    district: 'Αττική',
    ada: 'ΑΔΑ: ΧΧΧΧ-ΧΧΧ',
    status: 'pending',
    date: '2026-04-15',
  },
]

const GATE_LABELS: { key: keyof GovGrGates; label: string; description: string }[] = [
  { key: '500_aktive_nutzer', label: '500 Aktive Nutzer', description: 'Mindestens 500 verifizierte, aktive Nutzer auf der Plattform' },
  { key: '3_ngo_partnerschaften', label: '3 NGO Partnerschaften', description: 'Partnerschaften mit mindestens 3 anerkannten NGOs' },
  { key: 'roadmap_publiziert', label: 'Roadmap Publiziert', description: 'Öffentliche Roadmap mit Transparenz-Verpflichtung' },
  { key: 'govgr_genehmigung', label: 'gov.gr Genehmigung', description: 'Offizielle Genehmigung durch gov.gr für OAuth 2.0 Integration' },
]

export default function GovPage() {
  const [govGr, setGovGr] = useState<GovGrStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/api/v1/auth/govgr/status`)
        if (res.ok) {
          setGovGr(await res.json())
        }
      } catch { /* non-critical */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  const fulfilledCount = govGr?.gates
    ? Object.values(govGr.gates).filter(Boolean).length
    : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">gov.gr Integration</h1>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          govGr?.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-800'
        }`}>
          {govGr?.status === 'active' ? 'Ενεργό' : govGr?.status === 'stub' ? 'Stub' : 'Αναμονή'}
        </span>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Φόρτωση...</div>
      ) : (
        <div className="space-y-6">
          {/* Gates Progress */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">Aktivierungsbedingungen</h2>
              <span className="text-sm font-medium text-gray-500">
                {govGr?.progress ?? `${fulfilledCount}/4`} Aktivierungsbedingungen
              </span>
            </div>
            <div className="p-5">
              {/* Progress bar */}
              <div className="w-full bg-gray-100 rounded-full h-3 mb-6">
                <div
                  className="bg-blue-500 h-3 rounded-full transition-all"
                  style={{ width: `${(fulfilledCount / 4) * 100}%` }}
                />
              </div>

              {/* Gate cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {GATE_LABELS.map(({ key, label, description }) => {
                  const fulfilled = govGr?.gates?.[key] ?? false
                  return (
                    <div key={key} className={`rounded-xl p-4 border ${fulfilled ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-gray-800">{label}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          fulfilled ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'
                        }`}>
                          {fulfilled ? 'Erfüllt' : 'Offen'}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">{description}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Info boxes */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
            <div className="font-semibold text-blue-800 mb-1">gov.gr OAuth 2.0</div>
            <div className="text-sm text-blue-700">
              gov.gr OAuth wird aktiviert sobald alle 4 Bedingungen erfüllt sind.
              Bis dahin wird MOD-01 HLR für Identitätsverifikation genutzt.
            </div>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-xl p-5">
            <div className="font-semibold text-orange-800 mb-1">Aktueller Status: {govGr?.module ?? 'MOD-09'}</div>
            <div className="text-sm text-orange-700">
              Aktuell wird MOD-01 HLR für Identitätsverifikation genutzt. Die gov.gr OAuth 2.0
              Integration ist als Stub vorbereitet und wird nach Erfüllung aller Bedingungen aktiviert.
            </div>
            {govGr?.env_configured === false && (
              <div className="text-xs text-orange-600 mt-2">
                ENV-Konfiguration: Noch nicht eingerichtet
              </div>
            )}
          </div>

          {/* Applications table (existing) */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">Εισερχόμενες Αιτήσεις</h2>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Αιτών</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Περιφέρεια</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Diavgeia ΑΔΑ</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ημερομηνία</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ενέργειες</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {EXAMPLE_APPLICATIONS.map((app, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{app.applicant}</td>
                    <td className="px-4 py-3 text-gray-600">{app.district}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{app.ada}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${APP_STATUS_COLORS[app.status]}`}>
                        {APP_STATUS_LABELS[app.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(app.date).toLocaleDateString('el-GR')}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        disabled
                        className="text-xs text-gray-400 cursor-not-allowed"
                      >
                        Έγκριση (n/a)
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
              Ενεργοποιείται μετά τη σύνδεση gov.gr OAuth 2.0 και Diavgeia API.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

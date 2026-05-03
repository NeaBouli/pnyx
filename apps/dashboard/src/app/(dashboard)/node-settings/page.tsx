'use client'

import { useState } from 'react'

const PERIFERIES = [
  'Αττική', 'Κεντρική Μακεδονία', 'Θεσσαλία', 'Δυτική Ελλάδα',
  'Στερεά Ελλάδα', 'Πελοπόννησος', 'Κρήτη', 'Ανατολική Μακεδονία & Θράκη',
  'Δυτική Μακεδονία', 'Ήπειρος', 'Βόρειο Αιγαίο', 'Νότιο Αιγαίο',
  'Ιόνια Νησιά', 'Θεσσαλονίκη',
]

type Tab = 'general' | 'pages' | 'district' | 'staff'

const TABS: { key: Tab; label: string }[] = [
  { key: 'general', label: 'Γενικά' },
  { key: 'pages', label: 'Σελίδες' },
  { key: 'district', label: 'Περιφέρεια' },
  { key: 'staff', label: 'Συνεργάτες' },
]

export default function NodeSettingsPage() {
  const [tab, setTab] = useState<Tab>('general')
  const [showInviteModal, setShowInviteModal] = useState(false)

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Ρυθμίσεις Κόμβου</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Γενικά */}
      {tab === 'general' && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 space-y-5">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
            Φάση 2 — Ρύθμιση μέσω .env
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Όνομα Κόμβου</label>
            <input
              disabled
              type="text"
              placeholder="π.χ. Athens Node"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Subdomain</label>
            <input
              disabled
              type="text"
              placeholder="π.χ. athens.ekklesia.gr"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email Διαχειριστή</label>
            <input
              disabled
              type="email"
              placeholder="admin@node.ekklesia.gr"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Συχνότητα Συγχρονισμού</label>
            <select
              disabled
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            >
              <option value="10min">Κάθε 10 λεπτά</option>
              <option value="30min">Κάθε 30 λεπτά</option>
              <option value="1h">Κάθε 1 ώρα</option>
              <option value="6h">Κάθε 6 ώρες</option>
            </select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Τελευταίος Συγχρονισμός</label>
              <div className="text-sm text-gray-400 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                Δεν υπάρχουν δεδομένα συγχρονισμού
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Έκδοση Κόμβου</label>
              <div className="text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                1.0.0
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Σελίδες */}
      {tab === 'pages' && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
            Φάση 2 — Ρύθμιση μέσω .env
          </div>
          {[
            { label: 'Ψηφοφορίες', defaultOn: true },
            { label: 'Αποτελέσματα', defaultOn: true },
            { label: 'CPLM', defaultOn: true },
            { label: 'Forum Link', defaultOn: false },
            { label: 'Δημόσιο API', defaultOn: true },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
              <span className="text-sm font-medium text-gray-700">{item.label}</span>
              <div className="relative">
                <div
                  className={`w-10 h-5 rounded-full cursor-not-allowed ${
                    item.defaultOn ? 'bg-blue-400' : 'bg-gray-300'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                      item.defaultOn ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Περιφέρεια */}
      {tab === 'district' && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 space-y-5">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
            Φάση 2 — Ρύθμιση μέσω .env
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Περιφέρεια</label>
            <select
              disabled
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            >
              <option value="">— Επιλέξτε Περιφέρεια —</option>
              {PERIFERIES.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Δήμος</label>
            <select
              disabled
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            >
              <option value="">— Επιλέξτε πρώτα Περιφέρεια —</option>
            </select>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-sm font-medium text-gray-700">Μόνο τοπικά νομοσχέδια</span>
            <div className="relative">
              <div className="w-10 h-5 rounded-full bg-gray-300 cursor-not-allowed">
                <div className="absolute top-0.5 translate-x-0.5 w-4 h-4 bg-white rounded-full shadow" />
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Γλώσσα</label>
            <select
              disabled
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
            >
              <option value="el">Ελληνικά</option>
              <option value="en">English</option>
              <option value="both">Δίγλωσσο</option>
            </select>
          </div>
        </div>
      )}

      {/* Tab 4: Συνεργάτες */}
      {tab === 'staff' && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">Συνεργάτες Κόμβου</h3>
            <button
              onClick={() => setShowInviteModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              + Πρόσκληση
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Ρόλος</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="px-4 py-8 text-center text-gray-400" colSpan={3}>
                    Δεν υπάρχουν συνεργάτες — Φάση 2
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowInviteModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Πρόσκληση Συνεργάτη</h3>
              <button onClick={() => setShowInviteModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  disabled
                  type="email"
                  placeholder="user@example.com"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ρόλος</label>
                <select
                  disabled
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
                >
                  <option value="NODE_STAFF">NODE_STAFF</option>
                </select>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
                Φάση 2 — Η λειτουργία πρόσκλησης δεν είναι ακόμα διαθέσιμη
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowInviteModal(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                Κλείσιμο
              </button>
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                Αποστολή (Φάση 2)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

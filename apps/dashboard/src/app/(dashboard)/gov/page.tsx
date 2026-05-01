'use client'

type ApplicationStatus = 'pending' | 'approved' | 'rejected'

interface GovApplication {
  applicant: string
  district: string
  ada: string
  status: ApplicationStatus
  date: string
}

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  pending: 'Εκκρεμής',
  approved: 'Εγκρίθηκε',
  rejected: 'Απορρίφθηκε',
}

const STATUS_COLORS: Record<ApplicationStatus, string> = {
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

export default function GovPage() {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Αιτήσεις Gov.gr</h1>
        <button
          disabled
          className="px-4 py-2 bg-gray-200 text-gray-500 rounded-lg text-sm font-medium cursor-not-allowed"
        >
          Έγκριση Αίτησης (Απενεργοποιημένο)
        </button>
      </div>

      {/* Info box */}
      <div className="bg-orange-50 border border-orange-200 rounded-xl p-5 mb-6">
        <div className="flex items-start gap-3">
          <span className="text-orange-500 text-xl mt-0.5">🏗️</span>
          <div>
            <div className="font-semibold text-orange-800">Αναμονή Αδειοδότησης gov.gr OAuth 2.0</div>
            <div className="text-sm text-orange-700 mt-0.5">
              Οι αιτήσεις αρχών ενεργοποιούνται μετά την ολοκλήρωση της ενσωμάτωσης με το gov.gr
              OAuth 2.0 (πρόσβαση σε πιστοποιημένες οντότητες, εκπρόσωποι δήμων / περιφερειών).
            </div>
          </div>
        </div>
      </div>

      {/* Applications table */}
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
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[app.status]}`}>
                    {STATUS_LABELS[app.status]}
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
  )
}

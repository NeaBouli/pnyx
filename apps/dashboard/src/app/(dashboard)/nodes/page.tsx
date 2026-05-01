'use client'

type NodeStatus = 'active' | 'pending' | 'offline'

interface NodeRow {
  name: string
  domain: string
  district: string
  status: NodeStatus
  last_sync: string
}

const STATUS_LABELS: Record<NodeStatus, string> = {
  active: 'Ενεργό',
  pending: 'Εκκρεμής',
  offline: 'Εκτός',
}

const STATUS_COLORS: Record<NodeStatus, string> = {
  active: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-800',
  offline: 'bg-red-100 text-red-700',
}

const EXAMPLE_NODES: NodeRow[] = [
  {
    name: 'test.ekklesia.gr',
    domain: 'test.ekklesia.gr',
    district: 'Testumgebung',
    status: 'pending',
    last_sync: '—',
  },
]

export default function NodesPage() {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Κόμβοι (Nodes)</h1>
        <div className="relative group">
          <button
            disabled
            className="px-4 py-2 bg-gray-200 text-gray-500 rounded-lg text-sm font-medium cursor-not-allowed"
          >
            + Προσθήκη Κόμβου
          </button>
          <div className="absolute right-0 top-full mt-1 px-3 py-1.5 bg-gray-800 text-white text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
            Διαθέσιμο μετά τη Φάση 2
          </div>
        </div>
      </div>

      {/* Info box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 mb-6">
        <div className="flex items-start gap-3">
          <span className="text-blue-500 text-xl mt-0.5">🔗</span>
          <div>
            <div className="font-semibold text-blue-800">Ομοσπονδιακό Δίκτυο Κόμβων — Φάση 2</div>
            <div className="text-sm text-blue-700 mt-0.5">
              Η αρχιτεκτονική federation επιτρέπει σε δήμους και περιφέρειες να τρέχουν αυτόνομες
              εκδηλώσεις του ekklesia.gr και να συγχρονίζονται με τον κεντρικό κόμβο.
            </div>
          </div>
        </div>
      </div>

      {/* Nodes table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-800">Κατάλογος Κόμβων</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Όνομα</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Domain</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Περιφέρεια</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Κατάσταση</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Τελ. Sync</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {EXAMPLE_NODES.map((node) => (
              <tr key={node.domain} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-medium text-gray-900">{node.name}</td>
                <td className="px-4 py-3 text-gray-600 font-mono text-xs">{node.domain}</td>
                <td className="px-4 py-3 text-gray-600">{node.district}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[node.status]}`}>
                    {STATUS_LABELS[node.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400">{node.last_sync}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
          Ο κεντρικός κόμβος ekklesia.gr αναλαμβάνει χαρακτηριστικά δικτύου στη Φάση 2.
        </div>
      </div>
    </div>
  )
}

import { fetchHealth, fetchHlrCredits, fetchDiscourseVersion, fetchBills, fetchCPLM } from '@/lib/api'

type BillStatus = 'ANNOUNCED' | 'ACTIVE' | 'WINDOW_24H' | 'PARLIAMENT_VOTED' | 'OPEN_END'

interface StatCardProps {
  title: string
  titleEn?: string
  value: string | number
  sub?: string
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray' | 'purple'
  badge?: { label: string; color: 'green' | 'red' | 'yellow' | 'gray' }
  progress?: number
}

function StatCard({ title, titleEn, value, sub, color = 'blue', badge, progress }: StatCardProps) {
  const valueColors = {
    blue: 'text-blue-600',
    green: 'text-green-600',
    red: 'text-red-600',
    yellow: 'text-yellow-600',
    gray: 'text-gray-600',
    purple: 'text-purple-600',
  }
  const badgeColors = {
    green: 'bg-green-100 text-green-700',
    red: 'bg-red-100 text-red-700',
    yellow: 'bg-yellow-100 text-yellow-800',
    gray: 'bg-gray-100 text-gray-600',
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between mb-1">
        <div className="text-sm font-medium text-gray-500" data-en={titleEn}>{title}</div>
        {badge && (
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeColors[badge.color]}`}>
            {badge.label}
          </span>
        )}
      </div>
      <div className={`text-3xl font-bold mt-1 ${valueColors[color]}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
      {progress != null && (
        <div className="mt-2">
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

const STATUS_LABELS: Record<BillStatus, string> = {
  ANNOUNCED: 'Ανακοινώθηκε',
  ACTIVE: 'Ενεργό',
  WINDOW_24H: 'Παράθυρο 24ω',
  PARLIAMENT_VOTED: 'Ψηφίστηκε',
  OPEN_END: 'Ανοιχτό',
}

const STATUS_COLORS: Record<BillStatus, string> = {
  ANNOUNCED: 'bg-gray-100 text-gray-700',
  ACTIVE: 'bg-green-100 text-green-700',
  WINDOW_24H: 'bg-yellow-100 text-yellow-800',
  PARLIAMENT_VOTED: 'bg-blue-100 text-blue-700',
  OPEN_END: 'bg-purple-100 text-purple-700',
}

export default async function OverviewPage() {
  const [health, hlr, discourseVersion, billsRes, cplmRes] = await Promise.allSettled([
    fetchHealth(),
    fetchHlrCredits(),
    fetchDiscourseVersion(),
    fetchBills(5),
    fetchCPLM(),
  ])

  const healthData = health.status === 'fulfilled' ? health.value : null
  const hlrData = hlr.status === 'fulfilled' ? hlr.value : null
  const discourse = discourseVersion.status === 'fulfilled' ? discourseVersion.value : 'offline'
  const billsData = billsRes.status === 'fulfilled' ? billsRes.value : null
  const cplmData = cplmRes.status === 'fulfilled' ? cplmRes.value : null

  const apiStatus = healthData?.status === 'ok' ? 'Ενεργό' : 'Σφάλμα'
  const apiColor = healthData?.status === 'ok' ? 'green' : 'red'
  const apiOk = healthData?.status === 'ok'

  const primaryCredits = hlrData?.primary?.remaining ?? null
  const primaryTotal = hlrData?.primary?.total ?? 1000
  const primaryPct = primaryCredits != null ? Math.round((primaryCredits / primaryTotal) * 100) : null
  const hlrSub = hlrData
    ? `Εφεδρικό: ${hlrData?.fallback?.remaining ?? '—'}`
    : 'Μη διαθέσιμο'

  const bills = Array.isArray(billsData) ? billsData : billsData?.bills ?? []
  const activeBills = bills.filter((b: { status: string }) => b.status === 'ACTIVE').length
  const totalBills = bills.length

  const cplmX = cplmData?.x != null ? cplmData.x.toFixed(1) : null
  const cplmY = cplmData?.y != null ? cplmData.y.toFixed(1) : null
  const cplmLabel = cplmX && cplmY ? `(${cplmX}, ${cplmY})` : '—'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6" data-en="Dashboard Overview">
        Επισκόπηση Dashboard
      </h1>

      {/* 6-tile grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <StatCard
          title="Κατάσταση API"
          titleEn="API Health"
          value={apiStatus}
          sub={healthData?.modules ? `${Object.keys(healthData.modules).length} ενεργά modules` : undefined}
          color={apiColor as 'green' | 'red'}
          badge={{ label: apiOk ? 'OK' : 'ERROR', color: apiOk ? 'green' : 'red' }}
        />
        <StatCard
          title="HLR Credits (Κύρια)"
          titleEn="HLR Credits Primary"
          value={primaryCredits != null ? primaryCredits : '—'}
          sub={hlrSub}
          color={primaryCredits != null ? 'blue' : 'gray'}
          progress={primaryPct ?? undefined}
        />
        <StatCard
          title="Ενεργά Νομοσχέδια"
          titleEn="Active Bills"
          value={activeBills}
          sub={totalBills > 0 ? `${totalBills} συνολικά στο σύστημα` : 'Φορτώθηκαν 5 πρόσφατα'}
          color="blue"
        />
        <StatCard
          title="CPLM Θέση"
          titleEn="CPLM Position"
          value={cplmLabel}
          sub="X = Οικονομία, Y = Κοινωνία"
          color={cplmData ? 'purple' : 'gray'}
        />
        <StatCard
          title="Discourse"
          titleEn="Discourse"
          value={discourse}
          sub="pnyx.ekklesia.gr"
          color={discourse === 'offline' ? 'red' : 'blue'}
          badge={{ label: discourse === 'offline' ? 'Offline' : 'Live', color: discourse === 'offline' ? 'red' : 'green' }}
        />
        <StatCard
          title="Διακομιστής"
          titleEn="Server"
          value="Online"
          sub="ekklesia.gr — Hetzner CX33"
          color="green"
          badge={{ label: 'Online', color: 'green' }}
        />
      </div>

      {/* Recent bills table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Τελευταία Νομοσχέδια</h2>
          <a href="/bills" className="text-sm text-blue-600 hover:underline">Όλα →</a>
        </div>
        {bills.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">Δεν βρέθηκαν νομοσχέδια</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-gray-500">ID</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-500">Τίτλος</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-500">Κατάσταση</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-500">Ημερομηνία</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {bills.slice(0, 5).map((bill: { id: number; title_el: string; status: BillStatus; created_at: string }) => (
                <tr key={bill.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">#{bill.id}</td>
                  <td className="px-4 py-2.5 font-medium text-gray-900 truncate max-w-xs">{bill.title_el}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[bill.status] ?? 'bg-gray-100 text-gray-600'}`}>
                      {STATUS_LABELS[bill.status] ?? bill.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs">
                    {new Date(bill.created_at).toLocaleDateString('el-GR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

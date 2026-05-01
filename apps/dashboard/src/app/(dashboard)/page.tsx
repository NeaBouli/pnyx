import { fetchHealth, fetchHlrCredits, fetchDiscourseVersion } from '@/lib/api'

interface StatCardProps {
  title: string
  titleEn?: string
  value: string | number
  sub?: string
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray'
}

function StatCard({ title, titleEn, value, sub, color = 'blue' }: StatCardProps) {
  const valueColors = {
    blue: 'text-blue-600',
    green: 'text-green-600',
    red: 'text-red-600',
    yellow: 'text-yellow-600',
    gray: 'text-gray-600',
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div className="text-sm font-medium text-gray-500 mb-1" data-en={titleEn}>
        {title}
      </div>
      <div className={`text-3xl font-bold mt-2 ${valueColors[color]}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  )
}

export default async function OverviewPage() {
  const [health, hlr, discourseVersion] = await Promise.allSettled([
    fetchHealth(),
    fetchHlrCredits(),
    fetchDiscourseVersion(),
  ])

  const healthData = health.status === 'fulfilled' ? health.value : null
  const hlrData = hlr.status === 'fulfilled' ? hlr.value : null
  const discourse = discourseVersion.status === 'fulfilled' ? discourseVersion.value : 'offline'

  const apiStatus = healthData?.status === 'ok' ? 'Ενεργό' : 'Σφάλμα'
  const apiColor = healthData?.status === 'ok' ? 'green' : 'red'
  const moduleCount = healthData?.modules ? Object.keys(healthData.modules).length : 0

  const primaryCredits =
    hlrData?.primary?.remaining != null ? hlrData.primary.remaining : '—'
  const fallbackCredits =
    hlrData?.fallback?.remaining != null ? hlrData.fallback.remaining : '—'
  const hlrSub =
    hlrData
      ? `Κύριο: ${primaryCredits} · Εφεδρικό: ${fallbackCredits}`
      : 'Δεν είναι διαθέσιμα στοιχεία'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6" data-en="Dashboard Overview">
        Επισκόπηση Dashboard
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard
          title="Κατάσταση API"
          titleEn="API Health"
          value={apiStatus}
          sub={moduleCount > 0 ? `${moduleCount} ενεργά modules` : undefined}
          color={apiColor}
        />
        <StatCard
          title="HLR Credits"
          titleEn="HLR Credits"
          value={hlrData ? `${primaryCredits}` : '—'}
          sub={hlrSub}
          color={hlrData ? 'blue' : 'gray'}
        />
        <StatCard
          title="Διακομιστής"
          titleEn="Server"
          value="Online"
          sub={moduleCount > 0 ? `${moduleCount} modules` : 'ekklesia.gr'}
          color="green"
        />
        <StatCard
          title="Discourse"
          titleEn="Discourse"
          value={discourse}
          sub="pnyx.ekklesia.gr"
          color={discourse === 'offline' ? 'red' : 'blue'}
        />
      </div>
    </div>
  )
}

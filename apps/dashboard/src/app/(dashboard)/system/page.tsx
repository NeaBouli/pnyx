import { fetchHealth, fetchHlrCredits } from '@/lib/api'

interface ModuleBadgeProps {
  name: string
  status: string
}

function ModuleBadge({ name, status }: ModuleBadgeProps) {
  const isOk = status === 'ok' || status === 'up' || status === 'healthy'
  return (
    <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
      <span className="text-sm font-medium text-gray-700">{name}</span>
      <span className={isOk ? 'status-badge-green' : 'status-badge-red'}>
        {isOk ? '✓ Ενεργό' : `✗ ${status}`}
      </span>
    </div>
  )
}

interface HlrRowProps {
  label: string
  provider: Record<string, unknown> | null | undefined
}

function HlrRow({ label, provider }: HlrRowProps) {
  if (!provider) {
    return (
      <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
        <span className="text-sm text-gray-600">{label}</span>
        <span className="status-badge-yellow">Μη διαθέσιμο</span>
      </div>
    )
  }
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <div className="text-right">
        <div className="text-sm font-semibold text-gray-800">
          {provider.remaining != null ? `${String(provider.remaining)} credits` : '—'}
        </div>
        {provider.provider ? (
          <div className="text-xs text-gray-400">{String(provider.provider)}</div>
        ) : null}
      </div>
    </div>
  )
}

export default async function SystemPage() {
  const [health, hlr] = await Promise.allSettled([fetchHealth(), fetchHlrCredits()])

  const healthData = health.status === 'fulfilled' ? health.value : null
  const hlrData = hlr.status === 'fulfilled' ? hlr.value : null

  const modules: Record<string, string> = healthData?.modules ?? {}

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900" data-en="System Status">
        Κατάσταση Συστήματος
      </h1>

      {/* Health Overview */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800" data-en="API Health">
            Κατάσταση API
          </h2>
          {healthData ? (
            <span
              className={
                healthData.status === 'ok' ? 'status-badge-green' : 'status-badge-red'
              }
            >
              {healthData.status === 'ok' ? '✓ Λειτουργικό' : '✗ Σφάλμα'}
            </span>
          ) : (
            <span className="status-badge-red">✗ Μη διαθέσιμο</span>
          )}
        </div>
        <div className="p-4">
          {Object.keys(modules).length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(modules).map(([name, status]) => (
                <ModuleBadge key={name} name={name} status={status} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-4" data-en="No module data available">
              Δεν υπάρχουν διαθέσιμα δεδομένα modules
            </p>
          )}
        </div>
      </div>

      {/* HLR Credits */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">HLR Credits</h2>
          <p className="text-xs text-gray-400 mt-0.5" data-en="Phone number validation credits">
            Credits επαλήθευσης αριθμών τηλεφώνου
          </p>
        </div>
        <div className="px-6 py-4 space-y-1">
          <HlrRow
            label="Κύρια πηγή (Primary)"
            provider={hlrData?.primary as Record<string, unknown> | null | undefined}
          />
          <HlrRow
            label="Εφεδρική πηγή (Fallback)"
            provider={hlrData?.fallback as Record<string, unknown> | null | undefined}
          />
          <HlrRow
            label="Έκτακτη πηγή (Failover)"
            provider={hlrData?.failover as Record<string, unknown> | null | undefined}
          />
        </div>
      </div>
    </div>
  )
}

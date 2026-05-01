'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut } from 'next-auth/react'
import { canAccess, type DashboardRole } from '@/lib/auth'

const NAV_ITEMS = [
  { href: '/', module: 'overview', label: 'Επισκόπηση', labelEn: 'Overview', icon: '🏠' },
  { href: '/system', module: 'system', label: 'Σύστημα', labelEn: 'System', icon: '⚙️' },
  { href: '/bills', module: 'bills', label: 'Νομοσχέδια', labelEn: 'Bills', icon: '📋' },
  { href: '/votes', module: 'votes', label: 'Ψηφοφορίες', labelEn: 'Votes', icon: '🗳️' },
  { href: '/cplm', module: 'cplm', label: 'CPLM', labelEn: 'CPLM', icon: '📊' },
  { href: '/users', module: 'users', label: 'Χρήστες', labelEn: 'Users', icon: '👥' },
  { href: '/logs', module: 'logs', label: 'Αρχεία', labelEn: 'Logs', icon: '📝' },
]

const ROLE_LABELS: Record<DashboardRole, string> = {
  SUPER_ADMIN: 'Super Admin',
  SYSTEM_ADMIN: 'Διαχειριστής',
  CONTENT: 'Περιεχόμενο',
  ANALYST: 'Αναλυτής',
  SUPPORT: 'Υποστήριξη',
  NODE_ADMIN: 'Node Admin',
}

interface SidebarProps {
  username: string
  role: DashboardRole
  avatarUrl?: string | null
}

export default function Sidebar({ username, role, avatarUrl }: SidebarProps) {
  const pathname = usePathname()

  const visibleLinks = NAV_ITEMS.filter((item) => canAccess(role, item.module))

  return (
    <aside className="fixed left-0 top-0 h-full w-60 bg-gray-900 text-white flex flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="text-xl font-bold text-white tracking-tight">ekklesia.gr</div>
        <div className="text-xs text-gray-400 mt-0.5" data-en="Dashboard">
          Πίνακας Ελέγχου
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {visibleLinks.map((item) => {
          const isActive =
            item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)

          return (
            <Link
              key={item.href}
              href={item.href}
              data-en={item.labelEn}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>

      {/* User Info */}
      <div className="px-4 py-4 border-t border-gray-800 space-y-3">
        <div className="flex items-center gap-3">
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarUrl}
              alt={username}
              className="w-8 h-8 rounded-full bg-gray-700"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm font-bold">
              {username.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white truncate">{username}</div>
            <div className="mt-0.5">
              <span className="status-badge-blue text-xs">{ROLE_LABELS[role]}</span>
            </div>
          </div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: '/login' })}
          data-en="Sign out"
          className="w-full text-left px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          🚪 Αποσύνδεση
        </button>
      </div>
    </aside>
  )
}

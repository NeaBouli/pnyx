'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { signOut } from 'next-auth/react'
import { canAccess, type DashboardRole } from '@/lib/auth'

interface NavGroup {
  title: string
  items: NavItem[]
}

interface NavItem {
  href: string
  module: string
  label: string
  icon: string
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: 'ΚΥΡΙΟ ΜΕΝΟΥ',
    items: [
      { href: '/', module: 'overview', label: 'Επισκόπηση', icon: '📊' },
      { href: '/analytics', module: 'analytics', label: 'Αναλυτικά', icon: '📈' },
      { href: '/bills', module: 'bills', label: 'Νομοσχέδια', icon: '🏛️' },
      { href: '/votes', module: 'votes', label: 'Ψηφοφορίες', icon: '🗳️' },
      { href: '/cplm', module: 'cplm', label: 'CPLM', icon: '🧭' },
    ],
  },
  {
    title: 'ΣΥΣΤΗΜΑ',
    items: [
      { href: '/system', module: 'system', label: 'Σύστημα', icon: '💻' },
      { href: '/ai', module: 'ai', label: 'AI & Εργαλεία', icon: '🤖' },
      { href: '/forum', module: 'forum', label: 'Forum', icon: '💬' },
      { href: '/logs', module: 'logs', label: 'Αρχεία', icon: '📋' },
    ],
  },
  {
    title: 'ΔΙΑΧΕΙΡΙΣΗ',
    items: [
      { href: '/settings', module: 'settings', label: 'Ρυθμίσεις', icon: '⚙️' },
      { href: '/users', module: 'users', label: 'Χρήστες', icon: '👥' },
      { href: '/nodes', module: 'node', label: 'Κόμβοι', icon: '🔗' },
      { href: '/gov', module: 'gov', label: 'Gov Αιτήσεις', icon: '🏗️' },
    ],
  },
]

// NODE_ADMIN sees only these modules
const NODE_ADMIN_MODULES = ['overview', 'bills', 'votes', 'cplm', 'node', 'gov']

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
  const [nodeView, setNodeView] = useState(false)

  const isSuperAdmin = role === 'SUPER_ADMIN'
  const effectiveNodeView = role === 'NODE_ADMIN' || (isSuperAdmin && nodeView)

  function isVisible(module: string): boolean {
    if (effectiveNodeView) {
      return NODE_ADMIN_MODULES.includes(module)
    }
    return canAccess(role, module)
  }

  return (
    <aside className="fixed left-0 top-0 h-full w-60 bg-gray-900 text-white flex flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="text-xl font-bold text-white tracking-tight">ekklesia.gr</div>
        <div className="text-xs text-gray-400 mt-0.5">Πίνακας Ελέγχου</div>
      </div>

      {/* Super Admin toggle */}
      {isSuperAdmin && (
        <div className="px-4 py-3 border-b border-gray-800">
          <button
            onClick={() => setNodeView(!nodeView)}
            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              nodeView
                ? 'bg-yellow-600/20 text-yellow-400'
                : 'bg-blue-600/20 text-blue-400'
            }`}
          >
            <span>{nodeView ? 'Node View' : 'Super Admin'}</span>
            <span className="text-[10px] opacity-60">Εναλλαγή</span>
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        {NAV_GROUPS.map((group) => {
          const visibleItems = group.items.filter((item) => isVisible(item.module))
          if (visibleItems.length === 0) return null

          return (
            <div key={group.title} className="mb-4">
              <div className="px-3 mb-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                {group.title}
              </div>
              <div className="space-y-0.5">
                {visibleItems.map((item) => {
                  const isActive =
                    item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
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
              </div>
            </div>
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
              <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 rounded-full text-xs font-medium">
                {ROLE_LABELS[role]}
              </span>
            </div>
          </div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: '/login' })}
          className="w-full text-left px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          Αποσύνδεση
        </button>
      </div>
    </aside>
  )
}

'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Sidebar from './Sidebar'
import type { DashboardRole } from '@/lib/auth'

interface DashboardShellProps {
  children: React.ReactNode
}

export default function DashboardShell({ children }: DashboardShellProps) {
  const { data: session, status } = useSession()
  const router = useRouter()
  // Below md (768px) the sidebar is a drawer; choosing a link closes it.
  const [navOpen, setNavOpen] = useState(false)

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace('/login')
    }
  }, [status, router])

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-gray-500 text-sm" data-en="Loading...">
          Φόρτωση...
        </div>
      </div>
    )
  }

  if (!session?.user) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="md:hidden sticky top-0 z-30 flex items-center gap-3 px-4 py-3 bg-gray-900 text-white">
        <button
          type="button"
          onClick={() => setNavOpen(true)}
          aria-controls="dashboard-sidebar"
          aria-expanded={navOpen}
          className="px-3 py-1.5 rounded-lg bg-gray-800 text-sm font-medium"
        >
          ☰ Μενού
        </button>
        <span className="text-sm font-bold truncate">ekklesia.gr</span>
      </header>
      <Sidebar
        username={session.user.githubUsername}
        role={session.user.role as DashboardRole}
        avatarUrl={session.user.image}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />
      <main className="md:ml-60 min-h-screen min-w-0">
        <div className="p-4 md:p-6">{children}</div>
      </main>
    </div>
  )
}

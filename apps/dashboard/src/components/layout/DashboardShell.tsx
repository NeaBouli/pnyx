'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import Sidebar from './Sidebar'
import type { DashboardRole } from '@/lib/auth'

interface DashboardShellProps {
  children: React.ReactNode
}

export default function DashboardShell({ children }: DashboardShellProps) {
  const { data: session, status } = useSession()
  const router = useRouter()

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
      <Sidebar
        username={session.user.githubUsername}
        role={session.user.role as DashboardRole}
        avatarUrl={session.user.image}
      />
      <main className="ml-60 min-h-screen">
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}

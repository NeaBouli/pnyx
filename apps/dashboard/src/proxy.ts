import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { auth, canAccess, type DashboardRole } from '@/lib/auth'

const PAGE_MODULES: Record<string, string> = {
  '/': 'overview',
  '/ai': 'ai',
  '/analytics': 'analytics',
  '/bills': 'bills',
  '/cplm': 'cplm',
  '/embed': 'embed',
  '/finance': 'finance',
  '/forum': 'forum',
  '/gov': 'gov',
  '/logs': 'logs',
  '/monitor': 'monitor',
  '/newsletter-admin': 'newsletter-admin',
  '/node-settings': 'node-settings',
  '/nodes': 'node',
  '/politicians': 'politicians',
  '/representatives': 'representatives',
  '/settings': 'settings',
  '/stats': 'stats',
  '/system': 'system',
  '/users': 'users',
  '/vaa': 'vaa',
  '/votes': 'votes',
}

function moduleForPath(pathname: string): string | null {
  if (pathname === '/') return PAGE_MODULES['/']

  const match = Object.keys(PAGE_MODULES)
    .filter((path) => path !== '/' && (pathname === path || pathname.startsWith(`${path}/`)))
    .sort((a, b) => b.length - a.length)[0]

  return match ? PAGE_MODULES[match] : null
}

function loginRedirect(request: NextRequest): NextResponse {
  const url = request.nextUrl.clone()
  url.pathname = '/login'
  url.searchParams.set('callbackUrl', request.nextUrl.pathname)
  return NextResponse.redirect(url)
}

export const proxy = auth((request) => {
  const { pathname } = request.nextUrl

  if (
    pathname === '/login' ||
    pathname.startsWith('/api/auth') ||
    pathname.startsWith('/_next') ||
    pathname === '/favicon.ico'
  ) {
    return NextResponse.next()
  }

  if (!request.auth?.user) {
    if (pathname.startsWith('/api/')) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    return loginRedirect(request)
  }

  const requiredModule = moduleForPath(pathname)
  if (requiredModule && !canAccess(request.auth.user.role as DashboardRole, requiredModule)) {
    if (pathname.startsWith('/api/')) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  return NextResponse.next()
})

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}

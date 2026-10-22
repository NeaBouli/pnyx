import { NextRequest, NextResponse } from 'next/server'
import type { NextFetchEvent, NextMiddleware } from 'next/server'
import type { NextAuthRequest } from 'next-auth'
import { auth, canAccess, type DashboardRole } from '@/lib/auth'
import { createNonce, noncePolicy } from '@/lib/csp'

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
  '/municipal': 'municipal',
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

// Select NextAuth's middleware overload rather than its route-handler overload.
const withAuth: (handler: (request: NextAuthRequest, event: NextFetchEvent) => ReturnType<NextMiddleware>) => NextMiddleware = auth
const authorizedProxy = withAuth((request) => {
  const { pathname } = request.nextUrl

  if (
    pathname === '/login' ||
    pathname.startsWith('/api/auth') ||
    pathname.startsWith('/_next') ||
    pathname === '/favicon.ico'
  ) {
    return NextResponse.next({ request: { headers: request.headers } })
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

  return NextResponse.next({ request: { headers: request.headers } })
})

export async function proxy(request: NextRequest, event: NextFetchEvent) {
  const nonce = createNonce()
  const policy = noncePolicy(nonce)
  const headers = new Headers(request.headers)
  // Next reads the enforced request CSP to nonce bootstrap and Flight scripts,
  // including when the response policy is Report-Only. Ignore client values.
  headers.set('x-nonce', nonce)
  headers.set('Content-Security-Policy', policy)
  headers.delete('Content-Security-Policy-Report-Only')

  const pathname = request.nextUrl.pathname
  // These paths previously bypassed the proxy matcher. Keep them outside auth
  // while covering their responses with the same per-request security policy.
  const asset = pathname.startsWith('/_next/static') ||
    pathname.startsWith('/_next/image') || pathname.startsWith('/favicon.ico')
  let response: Response
  if (pathname !== '/' && pathname.endsWith('/')) {
    const url = new URL(request.url)
    url.pathname = pathname.slice(0, -1)
    response = NextResponse.redirect(url, 308)
  } else if (asset) {
    response = NextResponse.next({ request: { headers } })
  } else {
    response = await authorizedProxy(new NextRequest(request, { headers }), event) ??
      NextResponse.next({ request: { headers } })
  }

  response.headers.delete('Content-Security-Policy')
  response.headers.delete('Content-Security-Policy-Report-Only')
  response.headers.set(
    process.env.CSP_ENFORCE === 'false'
      ? 'Content-Security-Policy-Report-Only'
      : 'Content-Security-Policy',
    policy,
  )
  // Never replay nonce-bearing HTML or Flight with another request's policy.
  if (!asset) response.headers.set('Cache-Control', 'private, no-store, max-age=0')
  return response
}

export const config = {
  matcher: ['/:path*'],
}

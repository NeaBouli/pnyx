import { NextRequest, NextResponse } from 'next/server'
import { auth, type DashboardRole } from '@/lib/auth'

const API_BASE = process.env.EKKLESIA_API || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.ADMIN_KEY || process.env.EKKLESIA_ADMIN_KEY || ''

export const dynamic = 'force-dynamic'

const PROXY_ADMIN_ROLES = new Set<DashboardRole>(['SUPER_ADMIN'])

type ProxyAccess =
  | { ok: true }
  | { ok: false; response: NextResponse }

async function requireProxyAccess(): Promise<ProxyAccess> {
  const session = await auth()

  if (!session?.user) {
    return {
      ok: false,
      response: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }),
    }
  }

  if (!PROXY_ADMIN_ROLES.has(session.user.role)) {
    return {
      ok: false,
      response: NextResponse.json({ error: 'Forbidden' }, { status: 403 }),
    }
  }

  if (!ADMIN_KEY) {
    return {
      ok: false,
      response: NextResponse.json({ error: 'Dashboard proxy admin key not configured' }, { status: 503 }),
    }
  }

  return { ok: true }
}

function buildTargetUrl(request: NextRequest, segments: string[]): string {
  const path = segments.join('/')
  const search = request.nextUrl.searchParams.toString()
  return `${API_BASE}/api/v1/${path}${search ? '?' + search : ''}`
}

async function parseJsonResponse(resp: Response) {
  const text = await resp.text()
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

async function forwardProxyRequest(
  request: NextRequest,
  params: Promise<{ path: string[] }>,
  method: 'GET' | 'POST' | 'PATCH',
) {
  const access = await requireProxyAccess()
  if (!access.ok) return access.response

  const { path: segments } = await params
  const url = buildTargetUrl(request, segments)

  let body: string | undefined
  if (method !== 'GET') {
    try {
      body = await request.text()
    } catch {
      body = undefined
    }
  }

  try {
    const resp = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${ADMIN_KEY}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
      body,
    })
    const data = await parseJsonResponse(resp)
    return NextResponse.json(data, { status: resp.status })
  } catch (e) {
    return NextResponse.json({ error: 'Proxy error' }, { status: 502 })
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return forwardProxyRequest(request, params, 'GET')
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return forwardProxyRequest(request, params, 'POST')
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return forwardProxyRequest(request, params, 'PATCH')
}

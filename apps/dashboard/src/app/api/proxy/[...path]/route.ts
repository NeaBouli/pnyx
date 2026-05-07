import { NextRequest, NextResponse } from 'next/server'

const API_BASE = process.env.EKKLESIA_API || 'https://api.ekklesia.gr'
const ADMIN_KEY = process.env.ADMIN_KEY || process.env.EKKLESIA_ADMIN_KEY || ''

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/')
  const search = request.nextUrl.searchParams.toString()
  const url = `${API_BASE}/api/v1/${path}${search ? '?' + search : ''}`

  try {
    const resp = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${ADMIN_KEY}`,
        'Content-Type': 'application/json',
      },
      next: { revalidate: 0 },
    })
    const data = await resp.json()
    return NextResponse.json(data, { status: resp.status })
  } catch (e) {
    return NextResponse.json({ error: 'Proxy error' }, { status: 502 })
  }
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/')
  const search = request.nextUrl.searchParams.toString()
  const url = `${API_BASE}/api/v1/${path}${search ? '?' + search : ''}`

  let body: string | null = null
  try { body = await request.text() } catch { /* ignore */ }

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ADMIN_KEY}`,
        'Content-Type': 'application/json',
      },
      body,
    })
    const data = await resp.json()
    return NextResponse.json(data, { status: resp.status })
  } catch (e) {
    return NextResponse.json({ error: 'Proxy error' }, { status: 502 })
  }
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/')
  const url = `${API_BASE}/api/v1/${path}`
  let body: string | null = null
  try { body = await request.text() } catch { /* ignore */ }

  try {
    const resp = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${ADMIN_KEY}`,
        'Content-Type': 'application/json',
      },
      body,
    })
    const data = await resp.json()
    return NextResponse.json(data, { status: resp.status })
  } catch (e) {
    return NextResponse.json({ error: 'Proxy error' }, { status: 502 })
  }
}

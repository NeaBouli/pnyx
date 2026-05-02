import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const r = await fetch('https://pnyx.ekklesia.gr/about.json', {
      next: { revalidate: 60 },
    })
    if (!r.ok) throw new Error('Discourse unreachable')
    const data = await r.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ error: 'offline' }, { status: 503 })
  }
}

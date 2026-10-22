import type { Metadata } from 'next'
import { headers } from 'next/headers'
import './globals.css'
import SessionProvider from '@/components/layout/SessionProvider'

// Every page, including login and not-found, needs the current request's nonce.
export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Dashboard — ekklesia.gr',
  description: 'Πίνακας ελέγχου διαχείρισης ekklesia.gr',
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  await headers()
  return (
    <html lang="el">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  )
}

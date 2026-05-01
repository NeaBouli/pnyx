import type { Metadata } from 'next'
import './globals.css'
import SessionProvider from '@/components/layout/SessionProvider'

export const metadata: Metadata = {
  title: 'Dashboard — ekklesia.gr',
  description: 'Πίνακας ελέγχου διαχείρισης ekklesia.gr',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="el">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  )
}

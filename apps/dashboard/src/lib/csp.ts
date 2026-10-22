// Match the browser's NEXT_PUBLIC_API_URL, permitting only its origin.
const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr').origin

export function createNonce(): string {
  return btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))))
}

export function noncePolicy(nonce: string): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'`,
    // Recharts and the dashboard's progress bars use inline styles.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://avatars.githubusercontent.com",
    `connect-src 'self' ${API_ORIGIN}`,
    "font-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    // NextAuth posts to /api/auth/signin/github, then navigates to GitHub.
    "form-action 'self'",
  ].join('; ')
}

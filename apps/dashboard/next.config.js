/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  // Keep browser requests and the server's policy on the same build-time API.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api.ekklesia.gr',
  },
  // Preserve canonical redirects in the proxy so they also receive nonce CSP.
  skipTrailingSlashRedirect: true,
  async headers() {
    return [{
      source: '/:path*',
      // The proxy owns CSP for pages, APIs, redirects and assets in both modes.
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      ],
    }]
  },
}
module.exports = nextConfig

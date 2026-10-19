import withPWAInit from "@ducanh2912/next-pwa";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const withPWA = withPWAInit({
  dest: "public",
  register: true,
  disable: process.env.NODE_ENV === "development",
  cacheStartUrl: false,
  dynamicStartUrl: false,
  cacheOnFrontEndNav: false,
  publicExcludes: ["!noprecache/**/*", "!**/*.html"],
  workboxOptions: {
    skipWaiting: true,
    runtimeCaching: [
      {
        urlPattern: /^https:\/\/api\.ekklesia\.gr\/.*/i,
        handler: "NetworkFirst",
        options: {
          cacheName: "api-cache",
          expiration: { maxEntries: 50, maxAgeSeconds: 300 },
        },
      },
      {
        // Only canonical static file paths; exclude every HTML/Flight route.
        urlPattern: /^https:\/\/ekklesia\.gr\/(?:_next\/static|assets)\/[^?]*\.(?:js|css|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf)(?:\?[^#]*)?$/i,
        handler: "StaleWhileRevalidate",
        options: {
          cacheName: "static-cache",
          expiration: { maxEntries: 100, maxAgeSeconds: 86400 },
        },
      },
    ],
  },
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // CI's default tsconfig still checks tests and their repo-only helpers.
  typescript: { tsconfigPath: "tsconfig.build.json" },
  poweredByHeader: false,
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr",
  },
  async redirects() {
    return [
      {
        // Legacy APK URL that bypasses middleware (dotted path).
        source: "/download/ekklesia-latest.apk",
        destination:
          "https://github.com/NeaBouli/pnyx/releases/download/v1.0.33/ekklesia-v1.0.33-vC62-DIRECT.apk",
        permanent: false,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
        ],
      },
    ];
  },
};

export default withPWA(withNextIntl(nextConfig));

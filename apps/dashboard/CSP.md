# Dashboard Content Security Policy

The Next proxy owns the response CSP, including authentication redirects, API
errors and static assets. The dashboard Traefik router has no CSP middleware.
`next.config.js` supplies `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin` without adding another CSP.

The default enforced policy is:

```text
default-src 'self'; script-src 'self' 'nonce-<per-request base64 nonce>'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://avatars.githubusercontent.com; connect-src 'self' https://api.ekklesia.gr; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
```

The nonce contains 32 random bytes generated with Web Crypto. Next receives the
same nonce-bearing CSP on its forwarded request, replacing client-supplied CSP
and nonce headers, and uses it on bootstrap and streamed Flight scripts. All
pages inherit dynamic rendering from the root layout. HTML and Flight responses
are private and not stored; static asset caching remains enabled. Canonical
trailing-slash redirects retain their 308 status and query in the proxy so that
they also carry CSP. As with other Next headers, responses rejected by an
upstream proxy or the HTTP server before application routing are outside this
application policy.

The script policy mirrors `apps/web/src/lib/csp.ts`, which does not use
`strict-dynamic`. Inline styles are required by Recharts and existing progress
bars, including `src/app/(dashboard)/analytics/page.tsx`.

## Origins

| Origin | Use and source |
| --- | --- |
| `https://api.ekklesia.gr` | Direct browser API requests: `src/lib/api.ts:1` and `src/app/(dashboard)/analytics/page.tsx:12`. `connect-src` uses only the origin of the same `NEXT_PUBLIC_API_URL` value, including when configured with a path. |
| `https://avatars.githubusercontent.com` | GitHub's profile `avatar_url`, passed from `src/lib/auth.ts` through `src/components/layout/DashboardShell.tsx` to the image in `src/components/layout/Sidebar.tsx`. |
| `https://github.com/login/oauth/authorize` | GitHub OAuth provider in `src/lib/auth.ts`. The login button in `src/app/login/page.tsx` calls NextAuth's `signIn('github')`, which posts to same-origin `/api/auth/signin/github`, receives a URL, then navigates to GitHub. No cross-origin form action or browser connection permission is required. |
| `https://api.github.com` | GitHub provider profile/email requests run on the server through NextAuth; no browser CSP permission is required. |
| `https://pnyx.ekklesia.gr` | Forum JSON is fetched only by `src/app/api/discourse/route.ts`. The browser calls `/api/discourse`. Forum links open a separate page. |
| `https://ekklesia.gr` | Generated embed markup and navigation links in `src/app/(dashboard)/embed/page.tsx:45`. |
| `https://listmonk.ekklesia.gr`, `https://play.google.com`, `https://f-droid.org` | Navigation and download links in `src/app/(dashboard)/settings/page.tsx:481`. The GitHub download link uses the already listed GitHub origin. |
| `https://sentry.io` | Navigation link in `src/app/(dashboard)/stats/page.tsx:142`. |

Links to the public site, Listmonk, Sentry and app downloads do not load resources
into the dashboard. The embed page displays generated iframe markup as text;
the newsletter preview uses a sandboxed `srcDoc` iframe. These uses require no
additional external origins.

## Rollback

Set `CSP_ENFORCE=false` in the dashboard process environment and restart it. The
proxy then emits exactly one `Content-Security-Policy-Report-Only` header and no
enforced CSP. The renderer still receives the nonce-bearing request policy, so
rollback does not remove script nonces. No rebuild is needed. Unset the flag or
set `CSP_ENFORCE=true` and restart to restore enforcement. Observe Report-Only
violations in browser developer tools; no reporting endpoint is configured.

## Verification

Run from `apps/dashboard` with installed dependencies:

```sh
npx tsc --noEmit
npm run lint
npm test
npm run build
npm run test:csp-render
```

`npm run build` also runs the CSP unit and production render checks through
`postbuild`, so the existing dashboard CI build includes these checks. When
invoking `next build` directly, run `npm run test:csp-render` afterward.

The unit suite covers policy content, configured API origin, nonce entropy,
untrusted incoming headers, redirects, role denials, asset caching and rollback.
The offline production check uses Next's actual router, compiled proxy and HTML
renderer with signed local session fixtures. It verifies repeated login,
authenticated overview/analytics and not-found renders, checking every script
against the response nonce. It also checks canonical/auth redirects, API 401,
role 403, assets, RSC/prefetch headers and runtime rollback without rebuilding.

Manual browser checklist after deployment:

- Complete GitHub OAuth login and return to the dashboard; verify sign-out too.
- Visit `/`, `/analytics` and `/newsletter-admin`; exercise charts, API refresh
  and newsletter preview. Check that the GitHub avatar loads.
- In Network, confirm one enforced CSP on HTML, API, redirects and static assets,
  plus both companion headers. Reload HTML and confirm a different nonce. Use
  script elements' `.nonce` property to compare their values to the header.
- Confirm the browser console has no CSP violations during these flows. Check
  rollback in a test environment, then restore enforcement.

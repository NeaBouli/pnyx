# Dashboard + GitHub Releases Audit — 2026-06-15

## Scope

Diagnosis only. No code fix, no deploy, no DB mutation, no GitHub Release creation.

Checked:
- GitHub Releases for `NeaBouli/pnyx`
- local dashboard source under `apps/dashboard`
- live dashboard responses at `https://dashboard.ekklesia.gr`
- current vC38 release artifacts and hashes

## Executive Summary

Two separate issues were confirmed:

1. **GitHub Releases are stale.** GitHub still marks `v1.0.3 / vC30` as the latest release, while the current verified mobile release is `v1.0.9 / vC38`.
2. **Dashboard has a live high-risk auth gap.** Dashboard pages redirect unauthenticated users to `/login`, but the server-side `/api/proxy/[...path]` route forwards requests with the production admin bearer key without checking the NextAuth session. Live unauthenticated GET probes returned admin/system data.

Remediation status:

- GitHub Releases: **FIXED**. `v1.0.9 / vC38` is now the latest GitHub Release.
- Dashboard admin proxy auth: **FIXED** in `a84b200` and deployed.
- Dashboard route/module auth: **FIXED** in `cc08d1b` and deployed.
- Dashboard Dockerfile hygiene: **FIXED** in `cc08d1b` (`npm ci` only).

The dashboard is now protected at the page layer and admin-proxy layer. It is still an internal admin surface with some intentionally Phase-2 sections, but the critical unauthenticated admin proxy and navigation-only authorization gaps are closed.

## A — GitHub Releases

Status: **FIXED**. GitHub Release `v1.0.9` / `εκκλησία v1.0.9 (vC38)` is now the latest release.

### Current State

`gh release list --repo NeaBouli/pnyx --limit 20`:

| Release | GitHub state | Tag | Published |
|---|---:|---|---|
| `εκκλησία v1.0.3 (vC30)` | Latest | `v1.0.3` | 2026-06-02 23:22 UTC |
| `εκκλησία v1.0.0` | Pre-release | `v1.0.0` | 2026-04-24 09:16 UTC |

`v1.0.3` assets:

| Asset | Size | SHA256 digest |
|---|---:|---|
| `app-play-release.aab` | 29.7 MB | `7cc92ddeb9be36a238bc62a375867eadc92f55a102a986e87220e524b76cdadc` |
| `app-play-release.apk` | 60.9 MB | `6b216b7d00823c34b2ba3b9dabee8cbe9de60d3310314690fa062fc23eb8a388` |

### Actual Current Mobile Release

Current verified release is **v1.0.9 / vC38**:

| Artifact | Path | Size | SHA256 |
|---|---|---:|---|
| Play AAB | `/Users/gio/Desktop/ekklesia-v1.0.9-vC38-PLAY.aab` | 49 MB | `46dce5d1f528266c0dfdf98d364124e84653dfa360ab426462005226da087b28` |
| Direct APK | `docs/download/ekklesia-latest.apk` | 79 MB | `5f725627da5d088136cff6d4430e9c7266779fae26bf9567150837a40e49dc66` |

Landing already shows `v1.0.9 · vC38`.

At diagnosis time, no local Git tag existed for `v1.0.9` or `vC38`.

Updated state after fix:

- GitHub tag `v1.0.9` exists and points to `cd973f4`.
- `gh release list` now shows `εκκλησία v1.0.9 (vC38)` as `Latest`.
- Assets:
  - `ekklesia-v1.0.9-vC38.apk`
  - `ekklesia-v1.0.9-vC38-PLAY.aab`

### Release Plan

Recommended follow-up:

- Create a GitHub Release for `v1.0.9 / vC38`.
- Attach the verified vC38 Direct APK and optionally the Play AAB.
- Mark it as the latest release.
- In the release notes, state clearly:
  - hidden S10 ZK canary passed
  - vC38 is the current download build
  - production/global ZK remains gated/off
  - R8/minify remains off; Play mapping warning is informational for this build
- Leave older releases untouched or add wording that they are superseded.

Release was not created during the initial diagnosis, but was created in the follow-up remediation pass.

## B — Dashboard Audit

### Routes / Pages

Dashboard pages found:

| Route | Purpose |
|---|---|
| `/` | Overview |
| `/ai` | AI and tools |
| `/analytics` | Analytics |
| `/bills` | Bill management |
| `/cplm` | CPLM |
| `/embed` | Embed snippets |
| `/finance` | Finance/payment status |
| `/forum` | Forum/Discourse status |
| `/gov` | gov.gr / Diavgeia integration |
| `/logs` | System logs |
| `/monitor` | Monitor/self-healing |
| `/newsletter-admin` | Newsletter compose/send |
| `/node-settings` | Node settings |
| `/nodes` | Node panel |
| `/politicians` | Politician evaluation |
| `/representatives` | Representative invites |
| `/settings` | Settings and admin actions |
| `/stats` | Stats |
| `/system` | System health |
| `/users` | Users/identity tools |
| `/vaa` | VAA statements |
| `/votes` | Vote/result analytics |
| `/login` | GitHub login |

### Auth Model

Implemented auth:

- `apps/dashboard/src/lib/auth.ts`
  - Uses NextAuth with GitHub provider.
  - Allowlist is currently hardcoded to `NeaBouli` only.
  - Assigns `NeaBouli` role `SUPER_ADMIN`.
- `apps/dashboard/src/app/(dashboard)/layout.tsx`
  - Calls `auth()`.
  - Redirects unauthenticated page requests to `/login`.
- `apps/dashboard/src/components/layout/Sidebar.tsx`
  - Uses `canAccess()` to hide/show nav items by role.

Live page behavior:

- `GET https://dashboard.ekklesia.gr` returns `307` to `/login`.
- `/login` returns `200`.

### Finding B1 — Unauthenticated Admin Proxy

Severity: **HIGH**

Status: **FIXED** in `a84b200` and deployed to `dashboard.ekklesia.gr`.

The proxy route forwards any path under `/api/proxy/...` to the API using the dashboard's server-side admin key:

- `apps/dashboard/src/app/api/proxy/[...path]/route.ts:3-4` loads `EKKLESIA_API` and `ADMIN_KEY`.
- `apps/dashboard/src/app/api/proxy/[...path]/route.ts:6-25` implements `GET`.
- `apps/dashboard/src/app/api/proxy/[...path]/route.ts:27-50` implements `POST`.
- `apps/dashboard/src/app/api/proxy/[...path]/route.ts:52-73` implements `PATCH`.
- None of these handlers call `auth()` or check role/module permissions.

Live unauthenticated probes, with no cookies/session:

| URL | Result |
|---|---|
| `https://dashboard.ekklesia.gr/api/proxy/admin/stats` | `200 application/json`, returned production vote/admin stats |
| `https://dashboard.ekklesia.gr/api/proxy/admin/logs/containers` | `200 application/json`, returned container names/statuses |
| `https://dashboard.ekklesia.gr/api/proxy/health/modules` | `200 application/json`, returned health module data |

Only GET probes were used to avoid mutating production. However, the route also exposes POST/PATCH forwarding behind the same missing session check. Dashboard code uses these methods for bill edits, scraper healing, compass generation, newsletter send/draft, notifications, Diavgeia scrape, VAA create, representative invite, log explain, and other admin actions.

Impact:

- Anyone who knows or discovers `/api/proxy/...` can reach at least some admin/system data without logging in.
- If backend admin endpoints accept the forwarded dashboard admin key, unauthenticated POST/PATCH paths may permit production mutations through the dashboard proxy.

Recommended fix:

- Add server-side auth enforcement inside `apps/dashboard/src/app/api/proxy/[...path]/route.ts`.
- Require `auth()` and a valid allowlisted dashboard session before forwarding any request.
- Add method/path allowlist and role checks before using `ADMIN_KEY`.
- Return `401` for unauthenticated, `403` for unauthorized.
- Add regression tests or at least live probes verifying unauthenticated proxy requests return `401/403`.

Implemented fix:

- `apps/dashboard/src/app/api/proxy/[...path]/route.ts` now calls `auth()` before building/forwarding the upstream API request.
- Unauthenticated requests return `401`.
- Signed-in users without `SUPER_ADMIN` role return `403`.
- Missing dashboard admin key returns `503` before any upstream request.
- `GET`, `POST`, and `PATCH` share the same guard.

Post-deploy live probes without cookies/session:

| Probe | Before fix | After fix |
|---|---:|---:|
| `GET /api/proxy/admin/stats` | `200` | `401` |
| `GET /api/proxy/admin/logs/containers` | `200` | `401` |
| `GET /api/proxy/health/modules` | `200` | `401` |
| `POST /api/proxy/admin/scraper/heal-status` | not probed before, vulnerable by code path | `401` |
| `PATCH /api/proxy/admin/bills/1` | not probed before, vulnerable by code path | `401` |

### Finding B2 — Role Checks Are Mostly Navigation-Level

Severity: **MEDIUM**

Status: **FIXED** in `cc08d1b` and deployed to `dashboard.ekklesia.gr`.

Evidence:

- `apps/dashboard/src/components/layout/Sidebar.tsx` filters visible links by role.
- `apps/dashboard/src/app/(dashboard)/layout.tsx` checks only that a session exists, not route/module authorization.
- No per-route module guard was found in the page layout or page files.

Impact:

- A signed-in dashboard user with a lower role may be able to manually navigate to a route hidden from the sidebar unless each page or API route enforces its own authorization.
- Today the allowlist only contains `NeaBouli`, so practical exposure is limited. It becomes important before adding more operators.

Recommended fix:

- Add a route/module authorization layer for dashboard pages.
- Keep API proxy authorization independent from UI navigation filtering.

Implemented fix:

- Added `apps/dashboard/src/proxy.ts` using the Next.js 16 `proxy` convention.
- Unauthenticated dashboard page requests redirect to `/login`.
- Authenticated requests are checked against the dashboard role/module matrix before page access.
- `/login`, `/api/auth/*`, Next internals, and favicon remain reachable.
- API proxy authorization remains independent and still requires `SUPER_ADMIN`.

Post-deploy live probes without cookies/session:

| Probe | Result |
|---|---:|
| `GET /` | `307` to `/login?callbackUrl=%2F` |
| `GET /settings` | `307` to `/login?callbackUrl=%2Fsettings` |
| `GET /monitor` | `307` to `/login?callbackUrl=%2Fmonitor` |
| `GET /api/discourse` | `401` |
| `GET /api/proxy/admin/stats` | `401` |
| `POST /api/proxy/admin/scraper/heal-status` | `401` |

### Finding B3 — Incomplete / Placeholder Dashboard Areas

Severity: **MEDIUM**

Confirmed placeholders/incomplete areas:

- VAA create endpoint expected but noted as still in development:
  - `apps/dashboard/src/app/(dashboard)/vaa/page.tsx:117-124`
  - `apps/dashboard/src/app/(dashboard)/vaa/page.tsx:193`
  - `apps/dashboard/src/app/(dashboard)/vaa/page.tsx:237`
- Node federation remains Phase 2 / disabled:
  - `apps/dashboard/src/app/(dashboard)/nodes/page.tsx:233`
  - `apps/dashboard/src/app/(dashboard)/nodes/page.tsx:255-274`
  - `apps/dashboard/src/app/(dashboard)/nodes/page.tsx:363-369`
- Users list remains Phase 2 / no user-list endpoint:
  - `apps/dashboard/src/app/(dashboard)/users/page.tsx:100`
  - `apps/dashboard/src/app/(dashboard)/users/page.tsx:110`
  - `apps/dashboard/src/app/(dashboard)/users/page.tsx:133-151`
- Settings has Phase 2 / disabled knowledge-base and integration items:
  - `apps/dashboard/src/app/(dashboard)/settings/page.tsx:639`
- Finance has manual-entry placeholder comments:
  - `apps/dashboard/src/app/(dashboard)/finance/page.tsx:688`
  - `apps/dashboard/src/app/(dashboard)/finance/page.tsx:764`

Assessment:

- Dashboard is not a finished admin product. It is a mixed internal panel: some sections are live and wired, some are read-only, and some are intentionally Phase 2.

### Sensitive Operations Exposed By Dashboard

The dashboard references sensitive/admin operations through the proxy, including:

- bill create/edit/review/fetch-text/set-text/status-transition/party-votes
- scraper heal/fetch/Diavgeia scrape/org cache refresh
- compass question generation/approve/reject
- notification send
- newsletter preview/draft/send
- representative invites
- logs/containers/log streaming/log explanation
- payment/admin finance logs

No dashboard code reference to ZK flags, ZK canary, root publication, or ZK allowlists was found. ZK production/canary flags are not currently controlled from the dashboard UI.

### Deployment Hygiene Finding

Severity: **LOW**

Status: **FIXED** in `cc08d1b`.

`apps/dashboard/Dockerfile.prod:4` uses:

```dockerfile
RUN npm ci || npm install
```

This violates the project rule that CI/builds should use `npm ci`, not fallback to `npm install`. It can also hide lockfile drift.

Recommended fix:

- Use `RUN npm ci` only.
- Fail the build if lockfile state is invalid.

Implemented fix:

- `apps/dashboard/Dockerfile.prod` now uses `RUN npm ci`.
- Server dashboard image rebuilt successfully with this stricter install path.

### Live Header Note

`https://dashboard.ekklesia.gr` currently returns `X-Powered-By: Next.js`.

This is a hardening note, not the main issue. The unauthenticated proxy is the priority.

## Overall Dashboard Assessment

Status: **critical auth findings remediated; internal admin surface remains in controlled use**

The dashboard page shell has GitHub allowlist auth, route/module authorization, and the server-side admin proxy now requires a valid `SUPER_ADMIN` dashboard session before forwarding with the production admin bearer key.

Completed remediation:

1. GitHub Release `v1.0.9 / vC38` created and marked latest.
2. Unauthenticated `/api/proxy/[...path]` access fixed.
3. Route/module authorization added beyond Sidebar filtering.
4. Live unauthenticated probes re-tested.
5. Dockerfile fallback `npm ci || npm install` removed.

Remaining non-critical dashboard work:

- Clean up or explicitly label placeholder/Phase-2 surfaces as product scope evolves.
- Add deeper role-specific authenticated browser tests before adding more allowlisted dashboard users.

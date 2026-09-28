# Architecture Map — Next Runtime Dependency Boundary (T-485)

Scope: `apps/web` + `apps/dashboard` Next.js runtimes against
GHSA-vcvr-r3jv-pc5j (`next` >=16.2.0 <16.3.6, patched 16.3.6; RCE needs Node.js
`next/og` `ImageResponse` rendering attacker-controlled SVG content/attributes/styles).
Base: `origin/main` 49e449a3bc9af1000e9d111fba9b9da2e27d673c. Read-only run: no
package, lock, source or config change. Existing maps (`EKKLESIA_V2_MINIMA.md`,
`FEDERATION.md`) stay untouched.

## 1. Grundidee

- Ekklesia.gr is a digital direct-democracy platform for Greek citizens (`apps/web/src/app/[locale]/layout.tsx::metadata.openGraph.description`).
- Citizens use the public web runtime (`apps/web`, port 3000) for bills, VAA, results (`apps/web/src/app/[locale]/**/page.tsx`).
- Operators use the auth-gated admin dashboard (`apps/dashboard`, port 3001) (`apps/dashboard/src/proxy.ts::proxy`, `apps/dashboard/package.json::scripts.start`).
- Both are standalone Next builds served by `node server.js` in Docker (`apps/{web,dashboard}/next.config.*::output`, `apps/{web,dashboard}/Dockerfile.prod::CMD`).
- Boundary of this map: the `next` package version as it flows from manifest to running route handlers, plus the advisory's `next/og` sink.

## 2. Spur (opened hops)

1. `apps/web/package.json::dependencies.next` = `16.3.4` (exact) → `apps/web/package-lock.json::packages["node_modules/next"]` = 16.3.4, `engines.node >=20.9.0`.
2. `apps/dashboard/package.json::dependencies.next` = `16.3.4` (exact) → `apps/dashboard/package-lock.json::packages["node_modules/next"]` = 16.3.4.
3. Lock `node_modules/next` → 8 platform `node_modules/@next/swc-*` entries, each 16.3.4 (both locks); `sharp` 0.35.4 via `overrides`.
4. Lock → `.github/workflows/ci.yml::test-clients` (`npm ci` → `image-codec.check.mjs` → lint → typecheck → [web: vitest] → `npm run build`).
5. Lock → `apps/web/Dockerfile.prod` (`npm ci` with repo `.npmrc`, docs/ copied into `public/`, `npm run build`) → runner `node server.js` (context `../../`, `infra/docker/docker-compose.prod.yml::web`).
6. Lock → `apps/dashboard/Dockerfile.prod` (`npm ci --ignore-scripts`, `npm run build`) → runner `node server.js` (context `../../apps/dashboard`, `docker-compose.prod.yml::dashboard`).
7. `server.js` → the web proxy matcher excludes `/api`, `_next`, `_vercel`, and dotted paths; matched page requests enter `apps/web/src/proxy.ts::proxy` (redirects/rewrites + next-intl) → `apps/web/src/app/[locale]/*/page.tsx` (9 pages, no route handlers).
8. `server.js` → the dashboard matcher excludes `_next/static`, `_next/image`, and `favicon.ico`; matched protected pages and non-auth APIs enter `apps/dashboard/src/proxy.ts::proxy` (session gate, then role check) → `(dashboard)/*/page.tsx` (23), `api/discourse/route.ts::GET` (JSON), and `api/proxy/[...path]/route.ts` (JSON, SUPER_ADMIN). `/api/auth/*` is matched but returns before the user and `canAccess` checks to reach `api/auth/[...nextauth]/route.ts::{GET,POST}`.
9. Side-hop `request-controlled value → next/og ImageResponse SVG` — **offen / nicht verdrahtet** (evidence below).

### Sink evidence (all `git grep` on 49e449a, excluding lockfiles)

| Pattern | Scope | Hits |
| --- | --- | --- |
| `next/og`, `ImageResponse`, `new ImageResponse`, `@vercel/og` | whole repo | 0 |
| `satori`, `resvg`, `generateImageMetadata` | apps/web, apps/dashboard | 0 |
| `export const runtime` (Node vs Edge) | apps/web, apps/dashboard | 0 → all routes default Node.js runtime |
| `opengraph-image.*`, `twitter-image.*`, `icon.*`, `apple-icon.*` files | apps/web, apps/dashboard | 0 (only `public/manifest.json`) |
| `route.ts` handlers | both | 3, all dashboard, none returns images |
| `node_modules/@vercel/og`, `satori`, `@resvg/*` in locks | both locks | 0 (next's og bundle only inside `next/dist/compiled`) |

Image neighbours: `openGraph` in web layout is static text, no `images`; `next/image` in
`NavHeader.tsx`/`sso-verify/page.tsx` uses the image optimizer, not `next/og`; inline
`<svg>` literals in NavHeader/sso-verify/login are static JSX.

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| web manifest+lock | pin `next` for public web | `apps/web/package.json::dependencies.next` | gebaut (16.3.4, affected) |
| dashboard manifest+lock | pin `next` for admin dashboard | `apps/dashboard/package.json::dependencies.next` | gebaut (16.3.4, affected) |
| CI client gate | install + verify + build both runtimes | `.github/workflows/ci.yml::test-clients` | gebaut |
| image-codec check | assert optimizer + sharp ⊂ next's sharp range | `apps/{web,dashboard}/image-codec.check.mjs` | gebaut |
| web Docker runtime | build standalone, serve on 3000 | `apps/web/Dockerfile.prod::CMD` | gebaut |
| dashboard Docker runtime | build standalone, serve on 3001 | `apps/dashboard/Dockerfile.prod::CMD` | gebaut |
| web request edge | locale/static redirects | `apps/web/src/proxy.ts::proxy` | gebaut |
| dashboard request edge | auth + RBAC gate | `apps/dashboard/src/proxy.ts::proxy` | gebaut |
| dashboard route handlers | auth, discourse JSON, API proxy JSON | `apps/dashboard/src/app/api/**/route.ts` | gebaut |
| OG image generation | `next/og` `ImageResponse` | — | offen (no symbol) |

## 4. Verdrahtung

- `package.json::next` → lock `node_modules/next`: exact pin, lock matches 16.3.4 in both apps.
- lock `next` → `@next/swc-*`: 8 platform binaries pinned to the same 16.3.4; must move together.
- lock → CI `npm ci` / `npm run build`: CI builds both runtimes from their own lock.
- lock → `Dockerfile.prod` `npm ci`: prod image installs the same lock; web keeps install scripts per `.npmrc`, dashboard passes `--ignore-scripts`.
- `Dockerfile.prod` → `node server.js`: standalone server, Node 22.13.0-alpine.
- `server.js` → web `proxy.ts`: only matcher-selected requests enter it; `/api`, `_next`, `_vercel`, and dotted paths bypass the proxy.
- `server.js` → dashboard `proxy.ts`: matcher-selected requests enter it, but `/api/auth/*` returns before the protected user and `canAccess` checks; protected pages and the other API paths continue through those checks.
- proxy or matcher bypass → pages/route handlers: no handler or page imports `next/og`.

## 5. Widerspruch und Lücken

- (a) Versionally affected: both runtimes resolve `next` 16.3.4 ∈ [16.2.0, 16.3.6).
- (b) Exploit path not evidenced: 0 `next/og`/`ImageResponse` call sites, no metadata image files, no SVG-rendering handler. The vulnerable code ships in `next/dist/compiled` but is unreachable without an importer.
- (c) Hygiene upgrade still justified: all routes run Node.js runtime by default, so any future `ImageResponse` with request data would hit the vulnerable sink directly.
- Attacker preconditions (all missing today): a Node-runtime route/metadata file importing `next/og`; request-controlled input reaching SVG content, attributes or styles in the JSX tree; reachability without auth (web) or with an operator session (dashboard).
- Gap: install-script parity differs (web `npm ci` + `.npmrc`, dashboard `npm ci --ignore-scripts`); not changed here.
- Gap: `image-codec.check.mjs` asserts `sharp` 0.35.4 satisfies `next.optionalDependencies.sharp`; 16.3.6 range not verified in this run (no install).
- Not checked: npm registry metadata for 16.3.6, live/runtime state, builds.

## 6. Diagramme

- `docs/architecture/map.puml` (mindmap + component)
- `docs/architecture/main-path.puml` (sequence of the built path)

```mermaid
mindmap
  root((Next runtime boundary))
    web manifest+lock
      gebaut: package.json next 16.3.4
      gebaut: lock next + 8 swc 16.3.4
    dashboard manifest+lock
      gebaut: package.json next 16.3.4
      gebaut: lock next + 8 swc 16.3.4
    CI client gate
      gebaut: ci.yml test-clients
      gebaut: image-codec.check.mjs
    Docker runtimes
      gebaut: web Dockerfile.prod node server.js
      gebaut: dashboard Dockerfile.prod node server.js
    Request edge
      gebaut: web matched paths to proxy; api, _next, _vercel, dotted bypass
      gebaut: dashboard protected paths to auth + canAccess
      gebaut: dashboard api/auth returns before access checks
    Dashboard route handlers
      gebaut: api/auth nextauth
      gebaut: api/discourse GET
      gebaut: api/proxy path
    OG image generation
      offen: no next/og ImageResponse
```

## 7. Nächster Schritt (single follow-fix node, T-486)

Modul: web + dashboard manifest+lock. Hop: `package.json::dependencies.next`
16.3.4 → 16.3.6 → lock `node_modules/next` + all 8 `@next/swc-*` to 16.3.6, in both apps.
Files: `apps/{web,dashboard}/package.json`, `apps/{web,dashboard}/package-lock.json` only.
Untouched: Dockerfiles, `next.config.*`, `proxy.ts`, all `src/**`, `.github/**`,
`@next/eslint-plugin-next` (#394), React, `overrides`.
Must stay green: CI `test-clients` Web + Dashboard (`image-codec.check.mjs`, lint,
typecheck, web vitest, `npm run build`), both `Dockerfile.prod` builds, and the
routes in hops 7–8 (web locale pages + proxy redirects; dashboard pages, `/login`,
`/api/auth/*`, `/api/discourse`, `/api/proxy/*`).

---

# Preserved Map Node — EKA-18 Local Developer Stack / Compose Exposure Boundary

Integrated from `origin/main` at T-486 refresh. The full evidence and acceptance
record remains in `.fleet/reports/T-481.md` and `.fleet/reports/T-482.md`.

## Module and hop

- Node: local developer stack / Compose exposure boundary.
- Hop H1: README Quick Start starts `infra/docker/docker-compose.yml`.
- Hop H2: host-side alembic, seeds, and uvicorn use the loopback defaults in
  `apps/api/config.py::Settings`.
- Hop H3: the API container uses the internal `db` and `redis` service names.
- Hop H4: only PostgreSQL and Redis host publications are narrowed to
  `127.0.0.1`; the API's port 8000 publication remains unchanged.

## Security invariant

Development datastores with repository-public or absent credentials are not
reachable through a non-loopback host interface, while host development tools
retain `localhost:5432` and `localhost:6379` access and containers retain their
service-DNS access. Production Compose, API auth, salt policy, and datastore
authentication are outside this node.

## Built state

- `infra/docker/docker-compose.yml` binds db and redis to IPv4 loopback.
- `apps/api/tests/test_dev_compose_exposure.py` pins loopback publication,
  published ports, internal service-DNS targets, and dependencies.
- README warns that the development credentials are public and the stack is not
  for shared or production hosts.

# Architecture Map — EKA-53 Public DeepL Usage Route Boundary

Basis: proven `main` / rollback `4cc11930f4be82ba2d012def487fb34abca9da26` · Task: T-511 · Mapping only, no route change.
Node: Public API / DeepL usage route ownership.

The EKA-18 map above stays unchanged. EKA-53 is appended as a separate node.

## 1. Grundidee

- Ekklesia.gr exposes operational transparency data to citizens on the public community page (`README.md::What is Ekklesia?`, `docs/community.html::fetchDeeplUsage`).
- The community page displays the configured DeepL account's aggregate character count and limit; it does not expose the provider credential (`docs/community.html::fetchDeeplUsage`, `apps/api/routers/admin.py::deepl_usage`).
- The API handler is deliberately anonymous but is registered below the `/api/v1/admin` prefix, while sibling public status contracts live below `/api/v1/public` (`apps/api/routers/admin.py::router/deepl_usage`, `apps/api/routers/public_api.py::router`).
- The dashboard has six additional direct or proxied consumers of the same anonymous contract, and two maintained documents name the current URL.
- EKA-53 is a namespace/ownership defect, not evidence of credential disclosure: future reviewers cannot distinguish this public exception from a missing admin guard (`docs/community-audits/EKA_PNYX_Content_Coherence_Audit_2026-09-15.md::EKA-53`).
- Boundary: move the one read-only contract to the public router and migrate its First-Party consumers. Translation calls, provider configuration, admin authorization generally, dashboard session policy, production and deployment remain outside this node.

## 2. Spur (one built trace, hops opened)

| # | From → To | Datum over the edge |
| --- | --- | --- |
| D1 | `docs/community.html::fetchDeeplUsage` → `GET /api/v1/admin/deepl/usage` | anonymous browser request every page load / 60 seconds |
| D2 | `apps/api/main.py::app.include_router(admin.router)` → `apps/api/routers/admin.py::router` | mounts prefix `/api/v1/admin` |
| D3 | `admin.py::router` → `admin.py::deepl_usage` | route match `/deepl/usage`; uniquely has no `Depends(verify_admin)` |
| D4 | `admin.py::deepl_usage` → DeepL `GET /v2/usage` | server-side configured credential in `Authorization`; never returned |
| D5 | DeepL response → `deepl_usage` → community DOM | `available`, `character_count`, `character_limit`; provider errors collapse to zero/unavailable |

Opened direct neighbours that must migrate with D1: `apps/dashboard/src/lib/api.ts::fetchDeepLUsage`, dashboard overview, AI, system and settings pages (six call sites total), plus `docs/INTEGRATION-ANSWERS.md` and `docs/ekklesia_project_handover.md`. `docs/planning/r0/*` and the audit are historical inventories/evidence, not runtime consumers.

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| Community transparency client | renders aggregate DeepL usage publicly | `docs/community.html::fetchDeeplUsage` | gebaut; points at wrong namespace |
| Dashboard usage consumers | render the same aggregate on authenticated dashboard views | six call sites under `apps/dashboard/src` | gebaut; points at wrong namespace |
| Admin API router | owns privileged MOD-15 operations | `apps/api/routers/admin.py::router` | gebaut; public `deepl_usage` is quarantäne in this module |
| Public API router | owns anonymous public/status contracts | `apps/api/routers/public_api.py::router` | gebaut; DeepL usage contract is offen here |
| DeepL usage provider | returns account aggregate counts to the server | `GET https://api-free.deepl.com/v2/usage` | gebaut (external, read-only) |
| Route contract tests | pin public path, response shape and removal of anonymous admin path | — | offen |
| Maintained endpoint docs | describe First-Party API contracts | `docs/INTEGRATION-ANSWERS.md`, `docs/ekklesia_project_handover.md` | gebaut; stale path |

## 4. Verdrahtung

- Community page → admin-prefixed route: an anonymous browser fetch requests aggregate usage.
- `main.py` → admin router: FastAPI mounts the handler below `/api/v1/admin` solely because of its containing module.
- Admin router → `deepl_usage`: unlike neighbouring admin handlers, this endpoint intentionally omits `verify_admin`.
- `deepl_usage` → DeepL: the server supplies its configured credential and reads aggregate account usage; clients never receive the credential or provider body beyond the three-field projection.
- Handler → clients: success and fail-closed/unavailable responses share the established `{available, character_count, character_limit}` shape.
- Dashboard proxy → API: some authenticated dashboard clients forward the same path through a generic server-side proxy; changing only the final path segment from `admin/...` to `public/...` preserves dashboard session policy.

## 5. Widerspruch und Lücken

**Symptom:** `/api/v1/admin/deepl/usage` is anonymously callable even though every adjacent operation in the Admin router is privileged, so automated and human reviews repeatedly read it as a missing authorization check.

**Ursache:** D2/D3 bind a public transparency contract to the Admin router. The path is inherited from module placement rather than from its intended audience.

**Sicherheitsinvariante:** the public response contains only `available`, `character_count` and `character_limit`; the provider credential stays server-side, provider failures reveal no body or exception, and no write endpoint is introduced.

**Compatibility invariant:** every First-Party consumer switches atomically to `/api/v1/public/deepl/usage`; the anonymous `/api/v1/admin/deepl/usage` route must no longer exist. Keeping a public compatibility alias under `/admin` would preserve the exact ambiguity EKA-53 records and would not close the finding.

**Lücken / Grenzen:**

- No focused route test currently proves response projection, missing-key behavior, provider-error behavior, or absence of the old admin URL.
- The generic dashboard proxy attaches its admin Bearer header to all forwarded paths. It may continue to proxy the public path for authenticated dashboard pages; redesigning proxy authorization is a separate node.
- `services/ollama_service.py::deepl_available/deepl_translate` are separate runtime consumers of the provider and do not call this route; moving or refactoring them would add an unrelated hop.
- Historical R0 inventories and audit evidence must keep the observed old URL. They are not product documentation to rewrite.
- No live call is required for implementation tests: use a synthetic configured key and mocked `httpx` transport only.

## 6. Diagrammdateien

- `docs/architecture/map.puml` (EKA-53 mindmap + component diagram appended)
- `docs/architecture/main-path.puml` (EKA-53 built request trace appended)
- Rendered SVGs: `docs/architecture/map_002.svg`, `docs/architecture/map_003.svg`, `docs/architecture/main-path_001.svg` (the command also regenerated the preceding EKA-18 SVGs from the same multi-diagram sources).
- Rendered with `/Users/gio/.local/bin/plantuml -Playout=smetana -tsvg`.

```mermaid
mindmap
  root((Public DeepL usage transparency))
    Community client
      gebaut: community.html::fetchDeeplUsage
    Dashboard consumers
      gebaut: six direct or proxied call sites
    Admin API router
      quarantäne: public deepl_usage below admin prefix
    Public API router
      offen: GET public/deepl/usage
    DeepL provider
      gebaut: GET v2/usage with server-side credential
    Contract tests
      offen: new path and old-path absence
```

## 7. Nächster Schritt (engste Reparaturgrenze)

**Modul:** Public API / DeepL usage route ownership. **Hops:** D1–D5.

**Fix contract (separate worker run):**

1. Move the established handler from `apps/api/routers/admin.py` to `apps/api/routers/public_api.py` as `GET /api/v1/public/deepl/usage`; preserve response shape, timeout, read-only provider call and fail-closed error behavior. Do not create a wrapper or public alias under `/admin`.
2. Update exactly the First-Party runtime consumers found on the trace: `docs/community.html`, `apps/dashboard/src/lib/api.ts`, dashboard overview/AI/system/settings pages. Proxy-based callers may use `/api/proxy/public/deepl/usage`; direct callers use `/api/v1/public/deepl/usage`.
3. Update the two maintained endpoint references. Leave audit/R0/generated historical evidence unchanged.
4. Add focused API tests with a synthetic key and mocked provider covering: configured success projection, missing key, provider failure, new public route without admin auth, and old admin route returning 404. Add a static First-Party search assertion or equivalent focused regression so no runtime caller retains the old path.
5. Run the focused API test, affected API regression slice, dashboard typecheck/build, and a static docs/client search. No real provider request, credential, production, deploy or live check.

**Unberührt bleiben:** translation/service logic, other Admin/Public routes, dashboard proxy access policy, dependencies/lockfiles, env/config values, audit and R0 evidence, databases, secrets, provider state, production and deployment.

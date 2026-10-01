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

# Architecture Map — EKA-29 Metro 0.83.8 / image-size Exit

Basis: `origin/main 4cc11930f4be82ba2d012def487fb34abca9da26` · Task: T-506 · mapped before implementation, updated after proof.
Node: Mobile/Representative Build Toolchain / Expo-to-Metro asset-dimension hop.

## 1. Grundidee

- Ekklesia provides citizen and representative mobile clients built with Expo SDK 54 (`apps/mobile/package.json`, `apps/representative/package.json`).
- Expo's build toolchain reaches Metro through `@expo/metro`; the installed Expo 54 line pins `@expo/metro@54.2.0` and `metro@0.83.3` (`package-lock.json`).
- Metro reads image dimensions while bundling assets; 0.83.3 delegates that parsing to `image-size@^1.0.2` (`package-lock.json`).
- Both apps redirect that dependency to the audited local `image-size@1.2.2-pnyx.0` backport and run its focused regression test (`package.json`, `vendor/image-size/security-regression.test.mjs`).
- Four open Dependabot alerts remain because the package identity/version is still within the affected ranges (alerts 95–98).
- Metro 0.83.8 is an official 0.83.x security backport that vendors bounded image parsing and removes the `image-size` dependency (`react/metro` commit `809c36d897ef`).
- Boundary: dependency manifests/locks and existing build/security checks only; no application, native configuration, API, release, deployment or production change.

## 2. Spur

| # | From → To | Datum over the edge |
| --- | --- | --- |
| H1 | `apps/{mobile,representative}/package.json::dependencies.expo` → `package-lock.json::expo` | Expo range `~54.0.37` resolves 54.0.37 |
| H2 | `package-lock.json::@expo/metro@54.2.0` → `package-lock.json::metro` | exact Metro version `0.83.3` |
| H3 | `package-lock.json::metro@0.83.3` → root `image-size` override | `image-size@^1.0.2` is redirected to local `1.2.2-pnyx.0` |
| H4 | `package.json::test` → `vendor/image-size/security-regression.test.mjs` | focused malformed-image corpus runs against installed `image-size` |
| H5 | official `metro@0.83.8` → `metro/src/lib/imageSize` | Metro-owned parser replaces H3 and removes the external dependency |
| H6 | Expo bundle/build commands → installed Metro family | the app build consumes one coherent Metro patch line |

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| Mobile manifest/lock | pin the citizen app build graph | `apps/mobile/package.json` | gebaut; coherent Metro 0.83.8 family |
| Representative manifest/lock | pin the representative app build graph | `apps/representative/package.json` | gebaut; coherent Metro 0.83.8 family |
| Expo Metro adapter | select Metro for Expo SDK 54 | `node_modules/@expo/metro` lock entry | gebaut; exact 0.83.3 declaration overridden with tested 0.83.8 family |
| Metro asset parser | derive bundled image dimensions | `metro/src/Assets.js` | gebaut; internal bounded parser on 0.83.8 |
| Local image-size backport | former bounded parser | `vendor/image-size` | quarantäne; retained in repo but absent from both installed graphs |
| Security regression | reject malformed image loops | `vendor/image-size/metro-image-parser-regression.test.mjs` | gebaut; 26 parser/absence/validity checks |

## 4. Verdrahtung

- Expo 54 → `@expo/metro@54.2.0`: the application dependency graph installs Expo's Metro adapter.
- `@expo/metro` → Metro 0.83.3: the adapter uses an exact dependency, so a lock refresh alone cannot advance it.
- Metro 0.83.3 → local image-size backport: npm override preserves Metro's API while replacing the vulnerable registry artifact.
- Metro 0.83.8 → internal image parser: official patch removes `image-size`; all Metro family packages must stay on the same patch version.
- App scripts → security/build checks: existing test, typecheck, Expo dependency and native build paths prove the replacement graph.

## 5. Widerspruch und Lücken

- Official Metro 0.83.8 is semver-compatible within 0.83.x, but Expo 54 has not republished `@expo/metro` with the new exact pin; compatibility must be established by coherent overrides plus both app build/bundle suites.
- Overriding only `metro` is invalid because Metro packages exact-pin each other. The patch must move the full installed Metro family together or stop.
- Removing the local backport is safe only if `npm ls image-size` proves no remaining consumer in either workspace.
- The existing regression script targets the external package API. If that package disappears, equivalent coverage must exercise Metro's parser; silently deleting coverage is forbidden.
- TypeScript 7 remains blocked: latest `typescript-eslint@8.70.1` officially peers only with TypeScript `<6.1.0`.
- `PYSEC-2026-1325` remains blocked: all `ecdsa` versions are affected and upstream states no planned fix; `arweave-python-client@1.0.19` still requires `python-jose`, whose default dependency still requires `ecdsa`.

## 6. Diagrammdateien

- `docs/architecture/map.puml`
- `docs/architecture/main-path.puml`
- Rendered: `docs/architecture/map.svg`, `docs/architecture/map_001.svg`, `docs/architecture/main-path.svg`

```mermaid
mindmap
  root((Expo 54 asset build))
    Mobile manifest and lock
      built: Expo 54.0.37
      built: local image-size backport
    Representative manifest and lock
      built: Expo 54.0.37
      built: local image-size backport
    Expo Metro adapter
      built: at-expo/metro 54.2.0
      gap: exact Metro 0.83.3 pin
    Metro asset parser
      built: 0.83.3 delegates to image-size
      built upstream: 0.83.8 internal bounded parser
    Security regression
      built: malformed-image corpus
```

## 7. Nächster Schritt

**Modul:** Mobile/Representative Build Toolchain. **Hop:** H2–H6.

**Ergebnis:** Both manifests and locks now force one coherent Metro 0.83.8 family; `image-size` is absent from both installed graphs. The 26-case Metro parser regression, both workspace suites/typechecks, Expo dependency checks, Android production exports, npm audits/signatures and the independent Security Diff Scan all passed.

**Offen:** Expo 54 still declares exact Metro 0.83.3, three unused `@expo/metro` shims point at files removed in 0.83.8, and a signed Gradle/AAB, iOS bundle, HMR and device runtime were not exercised. These are explicit compatibility limits, not hidden gates.

**Nächster Knoten:** retire stale backport documentation only after merge closes alerts 95–98. Application source, native configuration, vendor implementation, API, CI, deploy and production remain untouched.

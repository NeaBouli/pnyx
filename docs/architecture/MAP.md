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

# Architecture Map — Sentry Capture Policy Boundary

Basis: `origin/main 4cc11930f4be82ba2d012def487fb34abca9da26` · Task: T-493 · Mapping only, no fix.
Node: API observability / Sentry event capture policy.

## 1. Grundidee

- Ekklesia.gr is a privacy-sensitive civic platform; the API handles request data and intermediate values that can include personal or security-relevant information.
- `apps/api/main.py::_sentry_init_options` is the single global policy boundary for Sentry error and transaction capture.
- FastAPI and Starlette integrations build Sentry events, `_before_send_filter` applies a second redaction layer, and the SDK transport sends the resulting envelope.
- This map opens only the event-construction policy hop. DSN, sampling, environment, provider configuration, deployment and stored Sentry events remain outside the boundary.

## 2. Spur (one trace, hops opened)

| # | From → To | Datum over the edge |
| --- | --- | --- |
| H1 | FastAPI/Starlette exception or transaction → Sentry integrations | exception, stack, request context and transaction metadata |
| H2 | `main.py::_sentry_init_options` → `sentry_sdk.init` | integrations, sampling, environment, PII and hook policy |
| H3 | Sentry SDK integration → event construction | stack frames; SDK default may attach frame-local variables |
| H4 | Sentry SDK integration → request extraction | request metadata; SDK default may attach a request body up to its configured size |
| H5 | constructed event → `main.py::_before_send_filter` | event/request/frame data; known sensitive keys and request fields are redacted recursively |
| H6 | `_before_send_filter` → Sentry transport | filtered event envelope sent to the configured DSN |

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| Sentry init policy | defines global capture controls | `apps/api/main.py::_sentry_init_options` | gebaut; frame-local and body policies are implicit SDK defaults |
| Web integrations | derive error/transaction/request events | `FastApiIntegration`, `StarletteIntegration` | gebaut (external SDK) |
| Event redaction | strips environment and redacts known sensitive values | `apps/api/main.py::_before_send_filter` | gebaut; defense layer, not a complete arbitrary-value denylist |
| SDK transport | serializes and sends envelopes | `sentry_sdk.init` / transport | gebaut (external SDK) |
| Policy regression tests | pin capture policy and transport result | `apps/api/tests/test_sentry_secret_scrubbing.py` | partial; filters and synthetic secrets covered, capture defaults not pinned |

## 4. Verdrahtung

- Application startup calls `_sentry_init_options(settings.sentry_dsn)` and passes the result to `sentry_sdk.init`.
- `FastApiIntegration` and `StarletteIntegration` collect exception, trace and request context before the application hook runs.
- `_before_send_filter` removes request environment, cookies and query strings; drops selected headers; and recursively redacts sensitive-key values in request data, extras and frame vars.
- Ordinary local-variable names and arbitrary body-field names are not guaranteed sensitive by that key-based filter.
- The filtered event proceeds to the SDK transport. Tests use an in-memory capture transport, so this boundary can be verified without network or Sentry access.

## 5. Widerspruch und Lücken

**Symptom:** global SDK defaults can collect arbitrary frame-local values and request bodies before `_before_send_filter` runs.

**Ursache:** `_sentry_init_options` deliberately sets `send_default_pii=False`, but does not explicitly set `include_local_variables` or `max_request_body_size`. The downstream redactor recognizes sensitive keys, not every value whose name appears harmless.

**Source → sink:** request/exception → FastAPI/Starlette integration → SDK event construction with implicit capture defaults → key-based `_before_send_filter` → transport.

**Sicherheitsinvariante:** Sentry events never contain frame-local variables or request bodies, independent of variable/key naming. Existing stack/exception metadata, URL and method metadata, sampling and redaction hooks remain available.

**Defense in depth:** `include_local_variables=False` prevents local values at event construction; `max_request_body_size="never"` prevents request-body collection. `_before_send_filter` remains in place for headers, query strings, cookies, extras and any event data supplied by other integrations.

**Lücken:**

- Current tests assert hook wiring and `send_default_pii=False`, but not the two capture-boundary settings.
- Existing transport tests use sensitive-looking names that the downstream redactor catches; they do not prove that arbitrary local/body values are excluded at source.
- No production/Sentry-event inspection is required or authorized for this change.

## 6. Diagrammdateien

- `docs/architecture/map.puml` (mindmap + component trace)
- `docs/architecture/main-path.puml` (event sequence)
- PlantUML rendering is optional for this mapping commit; source files are authoritative.

## 7. Nächster Schritt (engste Reparaturgrenze)

**Modul:** API observability / Sentry init policy. **Hop:** H2–H4.

1. Add `include_local_variables=False` and `max_request_body_size="never"` to `apps/api/main.py::_sentry_init_options`.
2. Extend `apps/api/tests/test_sentry_secret_scrubbing.py` with configuration invariants and SDK-transport checks showing arbitrary frame-local and request-body-only sentinel values are absent.
3. Preserve exception/stack and non-body request metadata where the SDK exposes it deterministically.
4. Leave `_before_send_filter`, DSN, integrations, sample rate, environment, deployment and provider settings unchanged.

Out of scope: production deployment, live Sentry inspection, data cleanup, legal/content wording and unrelated observability refactors.

# Architecture Map — EKA-63 MOD-22 Canonical Citizen Answers

Basis: `origin/main 4cc11930f4be82ba2d012def487fb34abca9da26` · Task: T-507 · Mapping only, no product fix.
Node: MOD-22 Hybrid Agent / deterministic canonical-answer boundary.

The accepted EKA-18 map above stays unchanged. EKA-63 is appended as separate diagrams in the same files.

## 1. Grundidee

- Ekklesia.gr lets Greek citizens inspect and vote on real parliamentary and municipal matters and includes an Ollama-powered citizen assistant (`README.md::What is Ekklesia?`, `README.md::Features`).
- `POST /api/v1/agent/ask` answers citizen questions through a safety filter, deterministic canonical answers, then lower-trust RAG/model generation (`apps/api/routers/agent.py::ask_agent`).
- Canonical answers exist for facts that must not drift: the helper returns a bilingual answer, a `knowledge_base` topic and the standard disclaimer without querying the database or either model (`agent.py::_canonical_response`).
- EKA-63 records four missing canonical topics: data deletion, ZK/Semaphore, representative verification and result visibility (`docs/community-audits/EKA_PNYX_AI_Readiness_Audit_2026-09-15.md::EKA-63`).
- System boundary of this node: request classification and deterministic response construction inside `routers/agent.py`, plus focused tests. It does not change the underlying identity, ZK, representative or result-visibility behavior.

## 2. Spur (one trace, hops opened)

| # | From → To | Datum over the edge |
| --- | --- | --- |
| A1 | `apps/api/main.py::app.include_router(agent.router)` → `apps/api/routers/agent.py::ask_agent` | `POST /api/v1/agent/ask` with validated `AskRequest(question, lang)` |
| A2 | `ask_agent` → `_safety_response` | raw citizen question plus canonical `el`/`en`; unsafe requests short-circuit |
| A3 | `ask_agent` → `_canonical_response` | safe question plus language |
| A4 | `_canonical_response` → topic match branches | lower-cased/normalized question; existing exact/substring matchers cover eight topics but none of the four EKA-63 topics |
| A5 | matched branch → nested `resp` → `_with_disclaimer` | bilingual fixed answer, stable topic id, `model=knowledge-base`, empty external-model dependency |
| A6 | no match → `_build_context` → `answer_citizen_question` / `_claude_answer` | the same four questions currently fall through to database-backed RAG and probabilistic model output |
| A7 | deterministic response → HTTP caller | JSON `{question, answer, model, sources, lang}` |

Opened fact neighbours that constrain A5 content but are not changed by this node:

| Topic | Repository truth opened for the answer contract |
| --- | --- |
| Data deletion/revocation | `apps/api/routers/identity.py::revoke_identity` marks the matching identity `REVOKED`; no mobile/web caller for `/identity/revoke` exists at this base. `docs/wiki/delete-account.html` describes uninstall/reverification and contains broader wording that is not a runtime guarantee. |
| ZK/Semaphore | `apps/api/routers/zk.py` gates Semaphore by explicit flags/scope allowlists and public Parliament scope/status; `README.md::Features` and `docs/wiki/zk-voting.html` describe the guarded rollout and group-size-five Arweave publication. |
| Representative verification | `apps/api/routers/representative.py::verify_representative` requires an unused, unexpired admin invite plus ADA verification via Diavgeia, then issues a 24-hour token; demo handling is a separate test path. |
| Results lifecycle | `apps/api/routers/voting.py::get_results` is the Web/Mobile results contract: default-hidden `ACTIVE` returns zeroed counts with `results_hidden=True`; `WINDOW_24H`, `PARLIAMENT_VOTED` and `OPEN_END` are visible before aggregation. `apps/api/services/bill_visibility.py::is_public_bill` separately excludes non-public bills. |

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| API composition | registers the agent route | `apps/api/main.py::app.include_router(agent.router)` | gebaut |
| MOD-22 Hybrid Agent | validates and routes citizen questions | `apps/api/routers/agent.py::ask_agent` | gebaut |
| Safety short-circuit | rejects manipulation requests | `agent.py::_safety_response` | gebaut |
| Canonical answer classifier | returns deterministic bilingual facts | `agent.py::_canonical_response` | teilweise: eight topics built; four EKA-63 topics open |
| RAG/model fallback | handles questions without a canonical branch | `agent.py::_build_context`, `answer_citizen_question`, `_claude_answer` | gebaut; wrong boundary for EKA-63 facts |
| Canonical regression tests | pin classification, facts, source topic and model bypass | `apps/api/tests/test_agent_guardrails.py` | teilweise: existing topics covered; EKA-63 matrix open |
| Identity/ZK/Representative/Visibility domains | authoritative behavior referenced by answer text | symbols listed above | gebaut; direct fact neighbours, unchanged |

## 4. Verdrahtung

- FastAPI composition → agent router: `main.py` exposes the router at `/api/v1/agent`.
- `/ask` → safety filter: harmful instructions stop before any knowledge or model path.
- `/ask` → canonical classifier: known safety/privacy/platform questions return a deterministic `knowledge-base` response.
- Canonical miss → RAG/models: a `None` return triggers DB context retrieval and Ollama/Claude, so missing EKA-63 matchers are the causal hop.
- Canonical hit → caller: the fixed bilingual answer and stable source topic return before DB/model calls.
- Domain source → answer contract: response wording must stay no stronger than the opened runtime symbol; documentation alone cannot upgrade a runtime fact.

## 5. Widerspruch und Lücken

**Symptom:** all four EKA-63 questions can be improvised by a model even though they concern security, identity or publication boundaries that must not drift.

**Ursache:** A4 has no matcher/response branches for those topics. A6 is therefore reached even when a deterministic repository fact exists.

**Source → sink:** citizen question → `ask_agent` → `_canonical_response` returns `None` → lower-trust KB/bill context and model generation → citizen-visible answer.

**Security invariant:** canonical security/platform facts bypass database retrieval and both model providers; answers cite a stable topic, keep the standard disclaimer and make no stronger claim than current source proves.

**Widersprüche / offene Grenzen:**

- Data deletion is not equivalent to identity revocation: `revoke_identity` changes key status but does not implement a general deletion transaction. No client caller exists. The canonical answer must state current mechanics and must not make GDPR/legal-compliance claims.
- ZK is guarded, not universally enabled: answer text must preserve explicit scope/status gates and must not expose operational allowlist/config values.
- Representative verification is ADA plus an admin-issued invite; ADA alone is insufficient. Demo identifiers must not be taught as a citizen path.
- Results visibility wording must follow `bill_visibility.py`; it must not invent result counts, live state or EKA-65/minimum-k behavior.
- Existing keyword matching uses broad substring tests. New matchers need positive EL/EN cases and nearby negative controls so generic words such as `results`, `delete` or `representative` do not swallow ordinary bill questions.

## 6. Diagrammdateien

- `docs/architecture/map.puml` — appended EKA-63 mindmap and component diagram
- `docs/architecture/main-path.puml` — appended EKA-63 sequence diagram

```mermaid
mindmap
  root((MOD-22 canonical citizen answers))
    API composition
      gebaut: main.py::include_router(agent.router)
    Hybrid agent
      gebaut: agent.py::ask_agent
      gebaut: _safety_response
    Canonical classifier
      gebaut: _canonical_response existing topics
      offen: data deletion/revocation
      offen: guarded ZK/Semaphore
      offen: representative ADA plus invite verification
      offen: results visibility lifecycle
    RAG and models
      gebaut: _build_context to Ollama/Claude
    Regression tests
      offen: EKA-63 bilingual matrix and model-bypass controls
```

## 7. Nächster Schritt (engste Reparaturgrenze)

**Modul:** MOD-22 Hybrid Agent. **Hop:** A4→A5 (`_canonical_response` topic classification and deterministic response).

**Späterer Implementierungsvertrag:** change only `apps/api/routers/agent.py` and one focused test file (prefer `apps/api/tests/test_agent_guardrails.py`, or one new `test_agent_eka63_canonicals.py` if isolation is clearer). Add four narrowly matched bilingual canonical topics, grounded in the opened source symbols. Tests must prove EL/EN response facts, stable topic/model/lang/disclaimer shape, nearby negative questions still fall through, and `ask_agent` returns each canonical without DB, Ollama or Claude calls. Run focused agent/security tests, then the affected API suite and `git diff --check`.

**Unberührt bleiben:** identity/revoke behavior, ZK flags/allowlists/verifier, representative invites/tokens/Diavgeia integration, result visibility/aggregation, public docs, KB seed data, prompt builder, model providers, dependencies, configuration, workflows, production and all other EKA findings (especially EKA-21/KDF and EKA-65).

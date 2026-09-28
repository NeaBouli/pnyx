# Architecture Map — EKA-18 Local Developer Stack / Compose Exposure Boundary

Basis: `origin/main 2bfda8e40dbd66c1486936f3594d7b232eb7606d` · Task: T-481 · Mapping only, no fix.
Node: Local Developer Stack / Compose Exposure Boundary.

## 1. Grundidee

- Ekklesia.gr is a digital direct-democracy platform where Greek citizens vote on real parliamentary bills and municipal decisions (`README.md` "What is Ekklesia?").
- A developer brings the platform up locally by starting the datastores via Compose, then running migrations/seeds and the API/web on the host (`README.md::Quick Start` steps 2–5).
- The Compose stack `infra/docker/docker-compose.yml` defines `db` (PostgreSQL), `redis` and `api` on one default Docker network.
- Host-side tools (alembic, seeds, host uvicorn) reach the datastores through the published host ports using `apps/api/config.py::Settings` defaults (`localhost` DB/Redis).
- System boundary of this node: the host network listeners created by Compose `ports:` plus the credentials interpolated into `environment:`. Production compose (`infra/docker/docker-compose.prod.yml`) is a separate neighbour and not on this trace.
- Audit record: `docs/community-audits/EKA_PNYX_Full_Scope_Audit_2026-09-15.md::EKA-18` (Info, "accepted risk if developers do not run it on shared networks; note in README").

## 2. Spur (one trace, hops opened)

| # | From → To | Datum over the edge |
| --- | --- | --- |
| H1 | `README.md::Quick Start` step 2 → `infra/docker/docker-compose.yml` | `cd infra/docker && docker compose up -d` (project dir = `infra/docker`, no `.env` present there) |
| H2 | `docker-compose.yml::services.db.environment` → Compose interpolation | `POSTGRES_PASSWORD: ${DB_PASSWORD:-<dev literal>}`; unset shell var ⇒ public dev literal |
| H3 | `docker-compose.yml::services.db.ports` → host listener | short syntax `"5432:5432"`, no `host_ip` ⇒ bind on all host interfaces |
| H4 | `docker-compose.yml::services.redis.ports` → host listener | `"6379:6379"`, no `host_ip`; no `command`/`requirepass` ⇒ unauthenticated Redis on all interfaces |
| H5 | `docker-compose.yml::services.api.environment` → API container | `DATABASE_URL=…${DB_PASSWORD:-<dev literal>}@db/ekklesia`, `REDIS_URL=redis://redis:6379`, `SERVER_SALT=${SERVER_SALT:-<dev literal>}`, `ENV=development` |
| H6 | API container → `db`/`redis` via service DNS | internal Docker network `default`; does **not** use host ports |
| H7 | `docker-compose.yml::services.api.ports` → host listener | `"8000:8000"`, all interfaces; uvicorn `--host 0.0.0.0 --reload` |
| H8 | `README.md::Quick Start` steps 3–4 → `apps/api/config.py::Settings` | host `alembic upgrade head`, seeds, `uvicorn main:app` read `database_url` (`…@localhost/ekklesia`, same dev literal) and `redis_url` (`redis://localhost:6379`) |
| H9 | `apps/api/alembic/env.py` (l.25–27) / `apps/api/database.py::engine` → host port 5432 | `settings.database_url` ⇒ requires DB published at least on host loopback |
| H10 | `apps/api/security_startup.py::validate_server_salt_config` | `ENV=development` ⇒ weak `SERVER_SALT` only warns (non-production), fail-closed only in production |

Static reproducer result (run 2026-09-28, `DB_PASSWORD`/`SERVER_SALT` unset, no containers started):
`docker compose -f infra/docker/docker-compose.yml config --format json` ⇒
`db  ports=[host_ip=<absent>, 5432→5432]`, `redis ports=[host_ip=<absent>, 6379→6379]`, `api ports=[host_ip=<absent>, 8000→8000]`, all on network `default`; `POSTGRES_PASSWORD`, `DATABASE_URL`, `SERVER_SALT` resolve to dev-fallback literals; `REDIS_URL` carries no credentials.

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| Quick Start doc | tells developers how to start the local stack | `README.md::Quick Start` | gebaut (no shared-network warning — EKA-18 audit asked for one) |
| Dev Compose: db | local PostgreSQL with dev credential | `infra/docker/docker-compose.yml::services.db` | gebaut; exposure = Befund |
| Dev Compose: redis | local Redis cache/limits | `infra/docker/docker-compose.yml::services.redis` | gebaut; exposure = Befund |
| Dev Compose: api | containerised API with reload | `infra/docker/docker-compose.yml::services.api` | gebaut |
| Compose interpolation | resolves `${VAR:-default}` from shell/`.env` | Compose engine (`docker compose config`) | gebaut (external tool) |
| API settings | host-side default connection strings | `apps/api/config.py::Settings` | gebaut |
| DB access (host path) | migrations and ORM engine | `apps/api/alembic/env.py`, `apps/api/database.py::engine` | gebaut |
| Salt startup guard | fail closed on weak salt in production | `apps/api/security_startup.py::validate_server_salt_config` | gebaut (dev = warn only, by design) |
| Compose exposure regression test | pin loopback-only datastore binding | — | offen |
| Production compose | prod stack | `infra/docker/docker-compose.prod.yml` | aufgeschoben (neighbour, out of scope; not on trace) |

## 4. Verdrahtung

- README Quick Start → dev compose: `docker compose up -d` from `infra/docker` starts `db`, `redis`, `api`.
- Compose interpolation → db/api: unset `DB_PASSWORD` yields the public dev literal for both `POSTGRES_PASSWORD` and `DATABASE_URL`, so they stay consistent.
- db.ports → host: `5432` published on every host interface (no `host_ip`).
- redis.ports → host: `6379` published on every host interface, no auth.
- api → db/redis: service DNS `db` / `redis` on network `default`; independent of `ports:`.
- api.ports → host: `8000` on every interface (API surface, has its own auth/rate limits).
- Host tools → db/redis: `config.py::Settings` defaults hit `localhost:5432` / `localhost:6379`; this is the legitimate reason the datastore ports are published at all.
- Compose `ENV=development` → salt guard: weak salt only logs a warning.

## 5. Widerspruch und Lücken

**Symptom:** any host on the same LAN/Wi-Fi/VPN (or the internet, on a cloud VM without a filtering firewall) can reach `<dev-host>:5432` and `<dev-host>:6379`.

**Ursache (separated):**
1. **Host publishing on all interfaces** — H3/H4: `ports` short syntax without `host_ip`. This is the root cause of reachability; the other two only determine impact.
2. **Weak DB fallback** — H2: `${DB_PASSWORD:-<dev literal>}`; the literal is public in the repo, so reachability ⇒ full DB login.
3. **Unauthenticated Redis** — H4: no `requirepass`; reachability ⇒ read/write of rate-limit and application state used by `rate_limit.py`, `routers/{identity,newsletter,notify,payments,public_api,contact}.py` and `main.py`.

**Source → Sink:** `README.md::Quick Start` → `docker-compose.yml::services.{db,redis}.ports` (no `host_ip`) → Docker port publisher on `0.0.0.0`/`::` → network client authenticates with the repo-public literal (DB) or no auth (Redis) → read/write of local dev data.

**Angreifervoraussetzung:** network-adjacent to the developer host (same L2/L3 segment, shared Wi-Fi, VPN, or public IP on a cloud dev VM), developer followed Quick Start without exporting `DB_PASSWORD`. No local code execution needed. Impact limited to dev data (seeded bills, local test identities); real production data is only at risk if a developer imports prod dumps locally. On Linux, Docker-published ports bypass UFW-style host rules — firewall itself is out of scope.

**Sicherheitsinvariante:** dev datastores whose credentials are repo-public or absent are never reachable from a non-loopback host interface; the API container keeps reaching them over the internal Compose network, and host tools keep reaching them over loopback.

**Legitimer lokaler Kontrollpfad (must keep working):**
- H8/H9: host alembic, seeds and host uvicorn via `localhost:5432` / `localhost:6379` (`config.py::Settings` defaults).
- H6: `api` container → `db`/`redis` by service DNS — unaffected by `ports:` changes.
- Host GUI/CLI clients (psql, redis-cli) on the developer machine via loopback.

**Nicht automatisch betroffen:**
- API port 8000 (H7): public-by-purpose HTTP surface with its own auth; LAN access may be used for device testing. Not part of EKA-18; leave as is (could be a separate hardening note).
- Internal service-DNS flows (H6): no host listener involved.
- `SERVER_SALT` dev fallback (H5/H10): only affects nullifier derivation of local dev identities; guarded fail-closed in production by `security_startup.py`. Not part of the exposure fix.

**Lücken / Widerspruch:**
- Audit EKA-18 says "note in README"; `README.md::Quick Start` contains no such note.
- No regression test pins the dev compose port binding (module `offen`).
- `apps/api/config.py::Settings.database_url` duplicates the same dev literal as the compose fallback. Changing the compose fallback to a required var (`${DB_PASSWORD:?}`) would break H8/H9 unless `config.py`/`.env` also change ⇒ that opens a second hop and is **not** the narrowest fix.
- Redis `requirepass` would break every host-side `redis://localhost:6379` default (`config.py`, `main.py`, several routers) ⇒ multi-file change, not narrowest; Redis-auth for production is out of scope anyway.
- IPv6: `127.0.0.1:` binds IPv4 loopback only; host tools resolving `localhost` to `::1` first fall back to IPv4 (asyncpg/redis-py try all addresses). Verify on the fix PR.

## 6. Diagrammdateien

- `docs/architecture/map.puml` (mindmap + component diagram)
- `docs/architecture/main-path.puml` (sequence of the trace)
- PlantUML not installed on the mapping host ⇒ sources written, not rendered.

```mermaid
mindmap
  root((Local dev stack: compose up to host listeners))
    Quick Start doc
      gebaut: README.md::Quick Start
      offen: shared-network note
    Dev Compose db
      gebaut: services.db ports 5432 all-interfaces
      gebaut: POSTGRES_PASSWORD dev fallback
    Dev Compose redis
      gebaut: services.redis ports 6379 all-interfaces no auth
    Dev Compose api
      gebaut: services.api env DATABASE_URL REDIS_URL SERVER_SALT
      gebaut: service DNS db redis
      gebaut: ports 8000
    API settings host path
      gebaut: config.py::Settings localhost defaults
      gebaut: alembic/env.py, database.py::engine
    Salt guard
      gebaut: security_startup.py::validate_server_salt_config
    Regression test
      offen: dev compose exposure test
```

## 7. Nächster Schritt (engste Reparaturgrenze)

**Modul:** Dev Compose (db, redis). **Hop:** H3 + H4 (`services.{db,redis}.ports`).

**Fix contract (for a later, separately approved run):**
1. `infra/docker/docker-compose.yml`: `db.ports` → `"127.0.0.1:5432:5432"`, `redis.ports` → `"127.0.0.1:6379:6379"`. Nothing else in the file (keep fallbacks, keep `api` 8000, keep `version`).
2. New focused test `apps/api/tests/test_dev_compose_exposure.py` (static YAML parse; PyYAML comes transitively via `uvicorn[standard]` — use `pytest.importorskip("yaml")`):
   - negative: every `ports` entry of `db` and `redis` has host IP `127.0.0.1` (short or long syntax `host_ip`); fail on missing host IP, `0.0.0.0`, `::`.
   - positive control (host tools): `db` publishes target 5432 and `redis` target 6379 on loopback (published port still present ⇒ `config.py` localhost defaults still work).
   - positive control (internal network): `api.environment.DATABASE_URL` host is `db`, `REDIS_URL` host is `redis`, and `api.depends_on` contains both.
   - out-of-scope guard: `api` ports are not asserted.
3. `README.md::Quick Start`: one note — datastores bind to loopback only; dev credentials are public, never run this compose on shared/prod hosts; set `DB_PASSWORD` for anything non-local.

**Vorher-Reproducer (static, no containers):**
```bash
cd infra/docker && env -u DB_PASSWORD docker compose -f docker-compose.yml config --format json \
 | python3 -c 'import json,sys; s=json.load(sys.stdin)["services"]; [print(n,[(p.get("host_ip","<all>"),p["published"],p["target"]) for p in s[n].get("ports",[])]) for n in ("db","redis","api")]'
# before fix: db/redis/api show host_ip <all>
# after fix:  db/redis show 127.0.0.1; api unchanged; api env still targets db / redis
```

**Unberührt bleiben:** `infra/docker/docker-compose.prod.yml`, `infra/docker/app.yml`, `infra/hetzner/*`, mirror compose, `apps/api/config.py`, `apps/api/main.py`, routers, `security_startup.py`, `.env*`, workflows, packages/lockfiles. Neighbour files enter scope only if a hop above proves they define H3/H4 — none do.

---

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

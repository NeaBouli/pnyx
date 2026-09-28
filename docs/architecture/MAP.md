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

# Architecture Map — EKA-24 Test-only Legacy Nullifier Helper Boundary

Basis: `origin/main 4cc11930f4be82ba2d012def487fb34abca9da26` · Task: T-509 · Mapping only, no product fix.
Node: Web Crypto / legacy v1 nullifier helper boundary.

The accepted EKA-18 map above stays unchanged. EKA-24 is appended as separate diagrams in the same files.

## 1. Grundidee

- Ekklesia.gr is an independent direct-democracy platform where Greek citizens inspect and cast informational votes on parliamentary and municipal matters (`README.md::What is Ekklesia?`).
- The Web client signs vote and relevance payloads locally with Ed25519 helpers from `apps/web/src/lib/crypto.ts`; production callers import signing and locally stored identity material, not phone-number nullifier derivation (`apps/web/src/app/[locale]/bills/[id]/page.tsx`, `components/RelevanceButtons.tsx`, `app/[locale]/sso-verify/page.tsx`, `lib/compass/useCompass.ts`).
- `crypto.ts::computeNullifier(phoneNumber, serverSalt)` nevertheless exposes the legacy v1 formula `SHA-256(phone + ":" + serverSalt)` from the product module (`apps/web/src/lib/crypto.ts`).
- Repository-wide symbol search at this base finds only `apps/web/src/lib/crypto.test.ts` importing and calling that export; no production caller supplies or receives a server salt.
- EKA-24 records this as an informational future-misuse risk: client code must not acquire `SERVER_SALT` or derive the server-owned v1 nullifier (`docs/community-audits/EKA_PNYX_Crypto_Deep_Audit_2026-09-15.md::EKA-24`).
- System boundary of this node: the single exported helper and its existing unit-test-only callers. Key storage (EKA-07), KDF harmonisation (EKA-21), EKA-22 KATs, API identity behavior and all production call sites are neighbours and remain unchanged.

## 2. Spur (one built trace, hops opened)

There is no user/runtime path to this symbol at the proven base. The only built path is the unit-test path below; the absent production edge is recorded as a gap and is not simulated.

| # | From → To | Datum over the edge |
| --- | --- | --- |
| N1 | `apps/web/package.json::test` → Vitest → `apps/web/src/lib/crypto.test.ts` | `vitest run` discovers the crypto unit suite |
| N2 | `crypto.test.ts` import list → `apps/web/src/lib/crypto.ts::computeNullifier` | named TypeScript export imported only by the test file |
| N3 | nullifier tests → `computeNullifier(phoneNumber, serverSalt)` | synthetic phone and salt strings; never environment or production values |
| N4 | `computeNullifier` → `TextEncoder` → `crypto.subtle.digest("SHA-256", ...)` | UTF-8 bytes of `${phoneNumber}:${serverSalt}` become a 32-byte digest |
| N5 | digest → `crypto.ts::bytesToHex` → assertions | lowercase 64-character hex checked for shape and input sensitivity |

Opened direct production neighbours: `bills/[id]/page.tsx`, `RelevanceButtons.tsx`, `sso-verify/page.tsx` and `useCompass.ts` import other `crypto.ts` symbols only. None imports or calls `computeNullifier`.

## 3. Module

| Modul | Eine Aufgabe | Einstieg | Stand |
| --- | --- | --- | --- |
| Web Crypto product module | Ed25519 conversion, signing and Beta local identity storage | `apps/web/src/lib/crypto.ts` | gebaut; `computeNullifier` is quarantäne because it has no production caller and accepts server-owned material |
| Web Crypto unit tests | exercise product crypto helpers | `apps/web/src/lib/crypto.test.ts` | gebaut; sole caller of `computeNullifier` |
| Web production callers | sign votes/relevance/SSO and read local identity material | paths listed above | gebaut; no nullifier-derivation edge |
| Web test runner | discovers and runs Vitest suites | `apps/web/package.json::test` | gebaut |
| EKA-22 cross-runtime KAT suite | pins current implementation-specific crypto formats | PR #397 / separate test files | aufgeschoben; separate draft, no file overlap with this node |
| Server nullifier derivation | owns the v1 salt-backed identity formula | API identity/crypto modules | aufgeschoben; direct neighbour, not opened for modification |

## 4. Verdrahtung

- `npm test` → Vitest → `crypto.test.ts`: the Web test command loads the unit suite.
- `crypto.test.ts` → `crypto.ts::computeNullifier`: the test imports a production export only to exercise the legacy v1 formula.
- `computeNullifier` → Web Crypto SHA-256 → `bytesToHex`: the helper hashes synthetic `phone:salt` bytes and returns lowercase hex.
- Production callers → other `crypto.ts` exports: voting, relevance, SSO and compass flows use signing/storage helpers but have no edge to `computeNullifier`.
- There is no repository edge from configuration or an API response to `serverSalt` in the Web client.

## 5. Widerspruch und Lücken

**Symptom:** server-owned v1 nullifier derivation is presented as a public export of the browser product module even though only unit tests call it.

**Ursache:** N2 crosses the test/product boundary: the test keeps its legacy formula helper in `crypto.ts` instead of test-only code.

**Security invariant:** no browser production path accepts, retrieves, embeds or derives with `SERVER_SALT`; server-owned nullifier/KDF behavior stays outside the client product API.

**Widerspruch:** the audit says the helper is “exported in the web bundle.” Static evidence proves an exported source symbol and zero production imports; it does not prove that the optimized Next build retains the unused named export. Tree-shaking may remove it. EKA-24 remains valid as API-surface/future-misuse hardening, not as evidence that the live bundle currently leaks the server salt or offers a callable UI path.

**Lücken / Grenzen:**

- The existing tests verify output shape, determinism and input sensitivity, but their “matches Python format” case does not pin a known digest. EKA-22 owns cross-runtime known-answer vectors and must not be duplicated here.
- `generateKeypair` is also not imported by current production files, but it does not accept server-owned material and is outside EKA-24.
- EKA-07 plaintext key storage and EKA-21 KDF design are explicitly Gio-gated and remain untouched.

## 6. Diagrammdateien

- `docs/architecture/map.puml` (EKA-24 mindmap + component diagram appended)
- `docs/architecture/main-path.puml` (unit-test-only built trace appended)
- Rendered SVGs: `map.svg`, `map_001.svg`, `map_002.svg`, `map_003.svg`, `main-path.svg`, `main-path_001.svg` (the `_002`/`_003` map pair and `_001` main path are EKA-24).
- Render command: `/Users/gio/.local/bin/plantuml -Playout=smetana -tsvg ...`; `smetana` is required on this host because Graphviz `dot` is absent.

```mermaid
mindmap
  root((Web Crypto: product exports vs test-only v1 nullifier helper))
    Web Crypto product module
      gebaut: signing and storage helpers
      quarantäne: crypto.ts::computeNullifier
    Web Crypto unit tests
      gebaut: crypto.test.ts nullifier cases
    Production callers
      gebaut: vote relevance SSO compass imports
      offen: no edge to computeNullifier
    Server nullifier domain
      aufgeschoben: server-owned salt and KDF
    EKA-22 KAT suite
      aufgeschoben: separate draft PR 397
```

## 7. Nächster Schritt (engste Reparaturgrenze)

**Modul:** Web Crypto product module + its unit test. **Hop:** N2 (`crypto.test.ts` import → `crypto.ts::computeNullifier`).

**Fix contract (for a later implementation run):**
1. `apps/web/src/lib/crypto.ts`: remove only the exported `computeNullifier` function and its comment; retain `bytesToHex` and every signing/storage symbol unchanged.
2. `apps/web/src/lib/crypto.test.ts`: remove the product import and keep any desired legacy-format check as a private test-only helper, or remove the weak shape-only block if the accepted EKA-22 KAT coverage supersedes it. Do not import PR #397 or modify its files in this task.
3. Verify the focused crypto suite, Web typecheck, production build, repository symbol search and built-output search for the legacy helper/test markers.

**Unberührt bleiben:** every other Web source file, API nullifier/identity code, Mobile, `packages/crypto`, EKA-22 vector/tests, KDF parameters, key storage, configs, dependencies, lockfiles, workflows, data, secrets, production and deployment.

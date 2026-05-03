# pnyx.ekklesia.gr Integration — Technical Answers

**Date:** 2026-04-27
**From:** ekklesia Core Team (V-Labs Development)
**For:** pnyx Forum Dev Team
**Source:** Live codebase + running server audit

---

## 1. Server & Infrastructure

| Item | Value |
|------|-------|
| **Provider** | Hetzner CX33, Helsinki |
| **Specs** | 4 vCPU / 8GB RAM / 80GB SSD |
| **RAM used** | ~2.3GB / 8GB (5.3GB available + 1GB swap) |
| **Disk used** | 18GB / 75GB (24%) |
| **OS** | Ubuntu 24.04.4 LTS |
| **Docker** | Yes — 9 containers active |
| **Reverse Proxy** | Traefik v3.6 (Docker Labels, no Nginx/Caddy) |
| **SSL** | Let's Encrypt via Traefik certresolver (auto-renew) |
| **Cloudflare** | DNS-only (not proxied). Direct IP: 135.181.254.229 |

### Active Containers

```
ekklesia-api       — FastAPI (port 8000 internal)
ekklesia-web       — Next.js 14 (port 3000 internal)
ekklesia-db        — PostgreSQL 15-alpine (port 5432 internal)
ekklesia-redis     — Redis 7-alpine (port 6379 internal)
ekklesia-ollama    — Ollama llama3.2:3b (port 11434 internal)
traefik-central    — Traefik v3.6 (ports 80, 443 external)
listmonk           — Newsletter (port 9000 internal)
listmonk-db        — Listmonk PostgreSQL
listmonk-postfix   — SMTP relay
```

### Bound Ports (external)

- 80 (HTTP → redirect to 443)
- 443 (HTTPS — Traefik handles TLS termination)
- 22 (SSH — PasswordAuth disabled, key-only)

All other ports are Docker-internal only (network: `net_ekklesia`).

### Traefik Config

No config files — everything via Docker Labels in `infra/docker/docker-compose.prod.yml`:

```yaml
labels:
  - traefik.http.routers.ekklesia-web.rule=Host(`ekklesia.gr`) || Host(`www.ekklesia.gr`)
  - traefik.http.routers.ekklesia-api.rule=Host(`api.ekklesia.gr`)
```

For `pnyx.ekklesia.gr`: add new container with Traefik label `Host(\`pnyx.ekklesia.gr\`)`.

---

## 2. Database (PostgreSQL)

| Item | Value |
|------|-------|
| **Version** | PostgreSQL 15-alpine |
| **Container** | `ekklesia-db` |
| **DB Name** | `ekklesia_prod` |
| **Connection** | `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}` |
| **Access** | TCP via Docker network `net_ekklesia` |
| **Tables** | 17 |
| **Total rows** | ~2,300 |

### Bills Table: `parliament_bills`

```sql
CREATE TABLE parliament_bills (
    id                     VARCHAR(50) PRIMARY KEY,  -- e.g. "GR-5293"
    title_el               TEXT NOT NULL,
    title_en               TEXT,
    pill_el                VARCHAR(200),              -- 1-sentence summary
    pill_en                VARCHAR(200),
    summary_short_el       TEXT,
    summary_short_en       TEXT,
    summary_long_el        TEXT,                      -- Full text (Jina Reader)
    summary_long_en        TEXT,
    categories             JSONB,                     -- e.g. ["Νομοθεσία"]
    party_votes_parliament JSONB,                     -- e.g. {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ"}
    status                 ENUM(ANNOUNCED, ACTIVE, WINDOW_24H, PARLIAMENT_VOTED, OPEN_END),
    governance_level       ENUM(NATIONAL, REGIONAL, MUNICIPAL, COMMUNITY),
    periferia_id           INTEGER REFERENCES periferia(id),
    dimos_id               INTEGER REFERENCES dimos(id),
    parliament_url         VARCHAR(500),
    parliament_vote_date   TIMESTAMP,
    arweave_tx_id          VARCHAR(100),
    ai_summary_reviewed    BOOLEAN DEFAULT FALSE,
    created_at             TIMESTAMP,
    updated_at             TIMESTAMP
);
```

### Geographic Structure

```sql
-- 13 Regions
CREATE TABLE periferia (
    id        SERIAL PRIMARY KEY,
    name_el   VARCHAR(100) NOT NULL,
    name_en   VARCHAR(100),
    code      VARCHAR(10) UNIQUE  -- e.g. "GR-ATT" (Attica)
);

-- 325 Municipalities
CREATE TABLE dimos (
    id            SERIAL PRIMARY KEY,
    name_el       VARCHAR(100) NOT NULL,
    name_en       VARCHAR(100),
    population    INTEGER,
    periferia_id  INTEGER REFERENCES periferia(id)
);
```

### Other Relevant Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `identity_records` | 7 | Verified citizens (nullifier_hash + public_key_hex) |
| `citizen_votes` | 0 | Votes on parliament bills |
| `diavgeia_decisions` | 101 | Municipal decisions from Diavgeia API |
| `diavgeia_votes` | 0 | Votes on Diavgeia decisions |
| `statements` | 44 | Political compass questions |
| `parties` | 8 | Greek parties (ND, SYRIZA, PASOK, KKE, EL, NIKI, PL, SPART) |
| `party_positions` | 0 | Party positions per statement |
| `dimos_diavgeia_orgs` | 1,775 | Mapping dimos ↔ Diavgeia organization UIDs |
| `periferia` | 13 | Greek regions |
| `dimos` | 325 | Greek municipalities |

### Alembic Migration Head

Current: `g001a2b3c4d5` (prepared but not deployed: `h101a2b3c4d5` for ADR-022 Tier-1)

---

## 3. Authentication & User System

### SMS Verification

- **Provider:** hlr-lookups.com (HLR Lookup, not SMS OTP)
- **Flow:** Phone → HLR check (is SIM active?) → Argon2id hash → nullifier_root → Ed25519 keypair
- **Phone number:** DELETED immediately after nullifier generation (never stored)

### Server-Side Storage per User

```python
class IdentityRecord:
    nullifier_hash   # SHA256 + Argon2id (64 hex chars, non-reversible)
    public_key_hex   # Ed25519 (128 hex chars)
    demographic_hash # Optional: SHA256(region + gender + salt)
    age_group        # Optional: AGE_18_25 .. AGE_65_PLUS
    region           # Optional: REG_ATTICA etc.
    gender_code      # Optional: GENDER_MALE etc.
    periferia_id     # Optional: FK → periferia
    dimos_id         # Optional: FK → dimos
    status           # ACTIVE / REVOKED
```

### Session/Token System

- **No traditional sessions.** Each vote is independently signed with Ed25519.
- **QR Login (POLIS):** Redis-backed session (5min TTL), challenge-response with Ed25519 signature.
- **Admin:** Static `admin_key` query parameter (ENV: `ADMIN_KEY`)

### Ed25519 Format

- Public key: **hex-encoded, 64 characters** (32 bytes)
- Private key: **hex-encoded, 128 characters** (64 bytes) — only returned once to client, never stored server-side
- Signature: **hex-encoded, 128 characters** (64 bytes)

### Auth Endpoints

```
POST /api/v1/identity/verify      — HLR verify → Ed25519 keypair
POST /api/v1/identity/revoke      — Revoke key
GET  /api/v1/identity/status      — Check key status
PATCH /api/v1/identity/profile/location — Sync dimos/periferia
```

---

## 4. Bills / Legislation Pipeline

### Bill Creation

- **File:** `apps/api/routers/parliament.py`
- **Function:** `create_bill()` — admin-only, POST `/api/v1/bills/admin/create`
- **Transition:** `transition_bill()` — POST `/api/v1/bills/{id}/transition`

### No Webhooks — APScheduler Jobs

All in `apps/api/main.py` (lines 31-100):

| Job | Interval | Function |
|-----|----------|----------|
| `parliament_scrape` | 12h | Fetch latest bills from Parliament API |
| `diavgeia_municipal` | 48h | Scrape municipal decisions from Diavgeia |
| `notify_new_bills` | 30min | Push notify on new ACTIVE bills |
| `notify_results` | 60min | Push notify on PARLIAMENT_VOTED |
| `compass_update` | 90 days | Generate new compass questions via Ollama |

### Bill JSON Format (API Response)

```json
{
    "id": "GR-5293",
    "title_el": "Ρυθμίσεις για τη βιώσιμη ανάπτυξη...",
    "title_en": null,
    "pill_el": "Ν. 5293: Ρυθμίσεις...",
    "categories": ["Νομοθεσία"],
    "status": "ANNOUNCED",
    "governance_level": "NATIONAL",
    "parliament_url": "https://www.hellenicparliament.gr/...",
    "relevance_score": 0
}
```

---

## 5. API

| Item | Value |
|------|-------|
| **Framework** | FastAPI (Python 3.12, fully async) |
| **Base URL** | `https://api.ekklesia.gr/api/v1` |
| **Public** | Yes, via Traefik (HTTPS) |
| **Endpoints** | 70+ across 22 modules |
| **Rate Limiting** | slowapi — 60 req/min/IP global, 5 req/min/IP for AI agent |
| **Admin Auth** | `?admin_key=...` query parameter |
| **CORS** | ekklesia.gr, www.ekklesia.gr, api.ekklesia.gr |

### Key Public Endpoints

```
GET  /health                          — Service health + module list
GET  /api/v1/health/modules           — Per-module status (ok/degraded/error)
GET  /api/v1/bills                    — List all bills
GET  /api/v1/bills/{id}               — Bill detail
GET  /api/v1/bills/{id}/summary       — AI summary (DeepL + Ollama)
POST /api/v1/vote                     — Cast vote (Ed25519 signed)
GET  /api/v1/vote/{id}/results        — Vote results + divergence
GET  /api/v1/vote/results/latest      — Most recent result
GET  /api/v1/mp/ranking               — Party alignment ranking
GET  /api/v1/municipal/{id}/voteable  — Voteable Diavgeia decisions
POST /api/v1/municipal/vote           — Vote on decision
POST /api/v1/agent/ask                — RAG Agent Q&A
GET  /api/v1/scraper/jobs             — Scraper status
GET  /api/v1/periferia                — 13 regions
GET  /api/v1/periferia/{id}/dimos     — Municipalities per region
GET  /api/v1/polis/qr-session         — QR login session
POST /api/v1/polis/qr-auth            — QR login verify
```

---

## 6. Ollama / AI Agent

| Item | Value |
|------|-------|
| **Model** | `llama3.2:3b` (Q4_K_M, 2GB) |
| **Deploy** | Docker container `ekklesia-ollama`, profile `ollama` |
| **Port** | 11434 (internal Docker network) |
| **RAM limit** | 5GB (`mem_limit` in compose) |
| **Actual RAM** | ~442MB idle, ~2.6GB during inference |

### AI Pipeline

```
Bill Summary:  Jina Reader → bill text → Ollama (EN summary) → DeepL (EN→EL) → Redis cache 7d
RAG Agent:     Greek question → DeepL (EL→EN) → Ollama → DeepL (EN→EL) → + disclaimer
Auto-Healing:  Scraper fails → Ollama analyzes HTML → suggests new CSS selector
Compass:       Recent bills → Ollama generates EN questions → DeepL → pending review
```

### DeepL Free API

- 500,000 chars/month, currently ~7,000 used (1.4%)
- Endpoint: `GET /api/v1/admin/deepl/usage` (public, no auth)

---

## 7. Domain & DNS

| Item | Value |
|------|-------|
| **DNS Provider** | Cloudflare (DNS-only, not proxied) |
| **Registrar** | External (domain owned by V-Labs Development) |
| **Active records** | `ekklesia.gr`, `api.ekklesia.gr`, `newsletter.ekklesia.gr` |
| **Wildcard SSL** | No — per-domain via Let's Encrypt/Traefik |

### Adding `pnyx.ekklesia.gr`

1. Add A record in Cloudflare: `pnyx → 135.181.254.229`
2. Add container in `docker-compose.prod.yml` with Traefik label:
   ```yaml
   labels:
     - traefik.http.routers.pnyx-forum.rule=Host(`pnyx.ekklesia.gr`)
     - traefik.http.routers.pnyx-forum.tls.certresolver=letsencrypt
   ```
3. Traefik auto-provisions SSL certificate

---

## 8. Code Structure

```
pnyx/
├── apps/
│   ├── api/                    → FastAPI backend
│   │   ├── routers/            → 18 route files (identity, voting, parliament, mp, ...)
│   │   ├── services/           → ollama_service, parliament_fetcher, scraper_healer, ...
│   │   ├── crypto/             → nullifier.py (Tier-1 vote validation)
│   │   ├── models.py           → SQLAlchemy models (17 tables)
│   │   ├── main.py             → FastAPI app + APScheduler + health endpoints
│   │   ├── alembic/versions/   → 8 migration files
│   │   └── requirements.txt
│   ├── web/                    → Next.js 14 (App Router)
│   │   ├── src/app/[locale]/   → /el/bills, /el/results, /el/mp, /el/admin, ...
│   │   ├── src/components/     → NavHeader, StatusBadge, CompassCard, QRCodeVoteStub, ...
│   │   ├── src/lib/            → api.ts, crypto.ts, compass/
│   │   ├── src/i18n/           → routing.ts, request.ts
│   │   ├── src/messages/       → el.json, en.json
│   │   └── public/             → favicon, pnx.png, manifest.json
│   └── mobile/                 → Expo React Native
│       ├── src/screens/        → 12 screens (Home, Bills, Vote, Compass, Onboarding, ...)
│       ├── src/lib/            → api.ts, crypto-native.ts, notifications.ts, compassStore.ts
│       ├── src/navigation/     → index.tsx (Stack + Tab navigator)
│       ├── src/compass/        → engine.ts, questions.ts, parties.ts, types.ts
│       └── app.json
├── packages/
│   ├── crypto/                 → Python + TypeScript Ed25519 + nullifier
│   └── db/                     → Alembic config
├── infra/docker/               → docker-compose.prod.yml (9 services)
├── docs/                       → Static HTML (landing, wiki, community, tickets, govgr-dimos)
│   ├── index.html              → Landing page (ekklesia.gr)
│   ├── community.html          → Community + donations + service tiles
│   ├── wiki/                   → 13 pages (api, modules, security, broadcasting, ...)
│   ├── tickets/                → POLIS ticket system
│   └── votes/                  → Redirects to /el/bills
├── metadata/                   → F-Droid Fastlane (en-US + el changelogs)
├── newsletter/templates/       → weekly-digest.html, monthly-digest.html
├── scripts/                    → build-play.sh, build-fdroid.sh, build-direct.sh
├── .github/workflows/          → ci.yml, security.yml, scraper.yml, deploy.yml
├── README.md                   → English, 22 modules documented
└── CLAUDE.md                   → Security audit system (in repo root)
```

### Package Managers & Lockfiles

- `apps/api/requirements.txt` (pip)
- `apps/web/package-lock.json` (npm)
- `apps/mobile/package-lock.json` (npm)

### Environment Variables

Server `.env.production` at `/opt/ekklesia/.env.production` contains:

```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
SERVER_SALT, SECRET_KEY
ADMIN_KEY
HLRLOOKUPS_USERNAME, HLRLOOKUPS_PASSWORD, HLRLOOKUPS_API_KEY, HLRLOOKUPS_API_SECRET
OLLAMA_URL, OLLAMA_MODEL
DEEPL_API_KEY
HF_API_KEY (HuggingFace fallback)
ARWEAVE_WALLET_PATH
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
BREVO_API_KEY, BREVO_SMTP_USER, BREVO_SMTP_PASS
LISTMONK_ADMIN_USER, LISTMONK_ADMIN_PASSWORD
```

---

## 9. Coordination

| Item | Value |
|------|-------|
| **Async channel** | GitHub Issues on `NeaBouli/pnyx-community` |
| **Stable branch** | `main` (production) |
| **Latest tag** | `pre-session-20260426` (HEAD: `0baf7f5`) |
| **Development** | Direct pushes to `main` (branch protection bypassed for owner) |

### Known Technical Debt

- 8 empty tables (no real user votes yet — alpha/beta)
- ADR-022 migration prepared but not deployed (v5 on 01.05)
- Mobile TypeScript: 5 errors (@noble/curves import)
- npm audit: 12 vulnerabilities via next-pwa → workbox
- HLR provider login issue (support ticket pending)
- party_positions table empty (no party positions mapped)

### What We Commit To

- Separate branch `feature/pnyx-forum` for forum work
- No direct pushes to `main` without team OK
- Infrastructure changes (Traefik, Postgres, env) communicated via GitHub Issue
- All code documented and tested

---

*Generated from live codebase + running server. All values verified.*
*© 2026 V-Labs Development — MIT License*

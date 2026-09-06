<!--
@wiki-page ARCHITECTURE
@update-hint Update on stack changes, new modules, new services.
@ai-anchor WIKI_ARCHITECTURE
-->

# Αρχιτεκτονική / Architecture

## Monorepo Structure
```
pnyx/
├── apps/
│   ├── api/        → Python FastAPI (Backend)
│   ├── dashboard/  → Next.js 16 (Role-aware Admin UI)
│   ├── mobile/     → Expo React Native (Android)
│   ├── monitor/    → Operations monitor
│   ├── representative/ → Expo representative app
│   └── web/        → Next.js 16 (Web Frontend)
├── packages/
│   ├── compass/    → Shared VAA compass package
│   └── crypto/     → Ed25519, Nullifier, HLR
├── infra/
│   └── docker/     → Docker Compose
└── docs/
    ├── ROADMAP.md  → Delivery roadmap
    ├── STATUS.md   → Current verified status
    └── TODO.md     → Current and historical tracking
```

## Stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | Python FastAPI | Async, typed, fast |
| Database | PostgreSQL 15+ | JSONB, reliable |
| Cache/PubSub | Redis 8.10 | Sessions, WebSocket relay |
| Migrations | Alembic | Versioned, async |
| Web Frontend | Next.js 16 | SSR, i18n, SEO |
| Styling | Tailwind CSS | Utility-first |
| Charts | Recharts | React-native charts |
| Crypto | PyNaCl + @noble/curves | Ed25519, battle-tested |
| Container | Docker Compose | Reproducible |
| CI/CD | GitHub Actions | Free for public repos |

## Municipal data boundary

The current municipal view reads regions, municipalities, decisions and
scraper health from the central Ekklesia API. It is read-only in the dashboard.
Independent Dimos nodes and federated registration are a future deployment
model, not a requirement or a live self-service feature today.

## Verified Autonomous Recovery

```
Alert -> allowlist check -> surgical repair -> read-only proof -> T1V
```

| Stage | Behavior |
|---|---|
| `parliament_source_lag` | Only allowlisted Phase 1 recovery. Runs forced Parliament catch-up. |
| Proof | After repair, monitor waits and compares latest source date with latest DB date. |
| Telegram | Only verified repair sends `Auto-Recovery verified`; failed proof remains an alert. |
| Cost | `0` AI tokens/run in Phase 1. Future paid-AI runbooks must appear in the Community live calculation before activation. |

## Bill Lifecycle State Machine
```
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END
```

| State | Voting | Change Allowed |
|---|---|---|
| ANNOUNCED | ❌ | — |
| ACTIVE | ✅ | ❌ locked |
| WINDOW_24H | ✅ | ✅ allowed |
| PARLIAMENT_VOTED | ❌ | — |
| OPEN_END | ✅ | ✅ always |

## V2 Planned

- `packages/crypto-rs` → Rust + WASM (ed25519-dalek, wasm-bindgen)
- Future TrueRepublic Bridge → Cosmos SDK / PnyxCoin (no current module ID)
- MOD-09 [gov.gr OAuth or holder-authenticated fresh challenge-bound QR/eSeal verification](https://github.com/NeaBouli/pnyx/blob/main/docs/GOVGR_DOCUMENT_VERIFICATION_ALPHA.md) (Alpha 0.1 design only; official integration, DPIA, migration design, independent review and sandbox canary required; not active in Beta)

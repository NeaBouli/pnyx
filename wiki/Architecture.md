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
│   ├── web/        → Next.js 16 (Web Frontend)
│   └── mobile/     → Expo React Native (Android)
├── packages/
│   ├── crypto/     → Ed25519, Nullifier, HLR
│   └── db/         → Alembic Migrations
├── infra/
│   └── docker/     → Docker Compose
└── docs/
    ├── CLAUDE.md   → AI Context Anchor
    ├── TODO.md     → Session-by-session tracking
    └── reports/    → Build reports
```

## Stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | Python FastAPI | Async, typed, fast |
| Database | PostgreSQL 15+ | JSONB, reliable |
| Cache/PubSub | Redis 7 | Sessions, WebSocket relay |
| Migrations | Alembic | Versioned, async |
| Web Frontend | Next.js 16 | SSR, i18n, SEO |
| Styling | Tailwind CSS | Utility-first |
| Charts | Recharts | React-native charts |
| Crypto | PyNaCl + @noble/curves | Ed25519, battle-tested |
| Container | Docker Compose | Reproducible |
| CI/CD | GitHub Actions | Free for public repos |

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
- MOD-08 TrueRepublic Bridge → Cosmos SDK / PnyxCoin
- MOD-09 [gov.gr OAuth or fresh QR/eSeal document verification](https://github.com/NeaBouli/pnyx/blob/main/docs/GOVGR_DOCUMENT_VERIFICATION_ALPHA.md) (Alpha design, not active)

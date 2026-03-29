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
│   ├── web/        → Next.js 14 (Web Frontend)
│   └── mobile/     → Expo React Native (TODO)
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
| Web Frontend | Next.js 14 | SSR, i18n, SEO |
| Styling | Tailwind CSS | Utility-first |
| Charts | Recharts | React-native charts |
| Crypto | PyNaCl + @noble/curves | Ed25519, battle-tested |
| Container | Docker Compose | Reproducible |
| CI/CD | GitHub Actions | Free for public repos |

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
- MOD-09 gov.gr OAuth2.0

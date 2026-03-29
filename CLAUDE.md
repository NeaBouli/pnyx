# CLAUDE.md — Ekklesia.gr / pnyx
# Copyright (c) 2026 Vendetta Labs — MIT License

## Identität
- Repo: /Users/gio/Desktop/pnyx (lokal) | https://github.com/NeaBouli/pnyx
- Produkt: Ekklesia.gr — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας
- Copyright: © 2026 Vendetta Labs (MIT License)
- Spec: v7.0 (vollständig, griechisch)
- Phase: Beta — SMS Verifikation, VAA, CitizenVote
- Letzte Aktualisierung: 2026-03-29

## Stack
- apps/api     → Python FastAPI (13 Endpoints, 4 Router)
- apps/web     → Next.js 14 (App Router, i18n el/en, Tailwind)
- apps/mobile  → Expo / React Native (TODO)
- packages/crypto → Ed25519, Nullifier, HLR (Python + PyNaCl)
- packages/db  → Alembic Migrations (9 Tabellen, 3 Enums)
- packages/i18n → el / en JSON (in apps/web/src/messages/)
- infra/docker → Docker Compose (PostgreSQL + Redis + API)

## V2 Technologie-Planung
- packages/crypto-rs → Rust + WASM (Ed25519-dalek, wasm-bindgen)
  → Krypto direkt im Browser, kein Server-Trust
- MOD-08 TrueRepublic → Cosmos SDK Bridge (PnyxCoin)
- MOD-09 gov.gr OAuth2.0 (Alpha-Phase, nach 500 Nutzern)

## Externe Referenz (READ ONLY)
- /Users/gio/TrueRepublic — Blockchain (Cosmos SDK, PnyxCoin)
- Bridge: MOD-08 (Stub, ENV-aktivierbar, Phase V2)

## API Endpoints (vollständig)
- MOD-01: /api/v1/identity/verify | revoke | status
- MOD-02: /api/v1/vaa/statements | parties | match
- MOD-03: /api/v1/bills | /trending | /{id} | /transition | /admin/create
- MOD-04: /api/v1/vote | /{id}/results | /{id}/relevance

## Bill Lifecycle
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END

## Tests (Stand: 2026-03-29)
- API: 40 passed + 4 xfail (kein lokales PG)
- Crypto: 12 passed
- CI: GitHub Actions GRÜN

## Git Status
- 12 Commits auf main
- Alle auf GitHub gepusht
- CI: grün (test-api + test-crypto + test-web)

## Sicherheitsprinzipien
- Kein Personenbezug gespeichert
- Telefonnummer sofort gelöscht nach Key-Generierung
- Ed25519 Private Key nur im Gerät (Secure Enclave)
- SHA256(Gruppe + SERVER_SALT) — Rohdaten per gc.collect() vernichtet

## TODO → docs/TODO.md
## ROADMAP → docs/ROADMAP.md
## REPORTS → docs/reports/

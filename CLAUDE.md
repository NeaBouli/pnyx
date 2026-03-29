# CLAUDE.md — Ekklesia.gr / pnyx
# Copyright (c) 2026 Vendetta Labs — MIT License
# Letzte Session: 2026-03-29

## Identität
- Repo lokal:  /Users/gio/Desktop/pnyx
- Repo remote: https://github.com/NeaBouli/pnyx
- Produkt:     Ekklesia.gr — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας
- Copyright:   © 2026 Vendetta Labs (MIT License)
- Spec:        v7.0 (15 Module, vollständig griechisch)
- Phase:       Beta — SMS Verifikation, VAA, CitizenVote

## Externe Referenz (READ ONLY — niemals verändern)
- /Users/gio/TrueRepublic — Cosmos SDK Blockchain, PnyxCoin
- Bridge geplant: MOD-08 (ENV-aktivierbar, Phase V2)

## Stack
- apps/api      → Python FastAPI + Alembic + PostgreSQL + Redis
- apps/web      → Next.js 14 (App Router, i18n el/en, Tailwind, recharts)
- apps/mobile   → Expo / React Native (TODO — nächste Phase)
- packages/crypto → Python + PyNaCl (Ed25519, Nullifier, HLR)
- packages/db   → Alembic Migrations (9 Tabellen, 3 Enums)
- infra/docker  → Docker Compose (PostgreSQL + Redis + FastAPI)

## V2 Technologie-Entscheidungen (in ROADMAP dokumentiert)
- packages/crypto-rs → Rust + WASM (ed25519-dalek, wasm-bindgen)
  → Krypto direkt im Browser, kein Server-Trust nötig
- MOD-08 TrueRepublic Bridge → Cosmos SDK / PnyxCoin
- MOD-09 gov.gr OAuth2.0 → Alpha nach 500 Nutzern + 3 NGOs

## API Endpoints (13 total — alle implementiert)
MOD-01: POST /api/v1/identity/verify | revoke | status
MOD-02: GET  /api/v1/vaa/statements | parties  /  POST /match
MOD-03: GET  /api/v1/bills | /trending | /{id}  /  POST /transition | /admin/create
MOD-04: POST /api/v1/vote  /  GET /{id}/results  /  POST /{id}/relevance
MOD-05: Divergence Score (integriert in /results)
MOD-14: Relevance Signal (integriert in /relevance)

## Web Seiten (5 total — alle gebaut + deployed auf GitHub)
/[locale]            → Homepage (Hero + Feature Cards)
/[locale]/vaa        → VAA Quiz (Intro → Quiz → Results + recharts)
/[locale]/bills      → Bills Feed (Filter + StatusBadge + Cards)
/[locale]/bills/[id] → Bill Detail (Summary + Abstimmung + Divergence)
/[locale]/verify     → Identity Verify (SMS → Key → Success)

## Components
NavHeader | StatusBadge | DivergenceCard | ProgressBar | VoteButton

## Bill Lifecycle
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END

## Tests (Stand: 2026-03-29)
- API:    40 passed + 4 xfail (kein lokales PG)
- Crypto: 12 passed
- CI:     GitHub Actions GRÜN (test-api + test-crypto)

## Git Stand
- 16 Commits auf main — alle auf GitHub
- CI: grün

## Sicherheitsprinzipien
- Telefonnummer: sofort nach Nullifier-Generierung gelöscht (gc.collect())
- Private Key: einmalig zurückgegeben, nie gespeichert
- Nullifier Hash: SHA256(phone + SERVER_SALT) — nicht umkehrbar
- Ed25519: Public Key auf Server, Private Key nur im Gerät
- Demographic Hash: SHA256(region + gender + SERVER_SALT)

## Seed-Daten (bereit für alembic upgrade head)
- 8 griechische Parteien (ΝΔ, ΣΥΡΙΖΑ, ΠΑΣΟΚ, ΚΚΕ, ΕΛ, ΝΙΚΗ, ΠΛ, ΣΠΑΡΤ)
- 15 VAA-Thesen (Υγεία, ΝΑΤΟ, Μισθός, ΑΠΕ, Παιδεία, Μετανάστευση...)
- 3 Gesetzentwürfe (2x OPEN_END, 1x ACTIVE)

## Nächste Session → docs/TODO.md

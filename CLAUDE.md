# CLAUDE.md — Ekklesia.gr / pnyx

## Identität
- Repo: /Users/gio/Desktop/pnyx (lokal) | https://github.com/NeaBouli/pnyx
- Produkt: Ekklesia.gr — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας
- Spec: v7.0 (vollständig, griechisch)
- Phase: Beta — SMS Verifikation, VAA, CitizenVote
- Letzte Aktualisierung: 2026-03-29

## Stack
- apps/api     → Python FastAPI
- apps/web     → Next.js 14 (App Router, i18n el/en)
- apps/mobile  → Expo / React Native
- packages/crypto → Ed25519, Nullifier, ZK
- packages/db  → Alembic Migrations, PostgreSQL Schemas
- packages/i18n → el / en JSON
- packages/types → Shared TypeScript + Pydantic Types
- infra/docker → Docker Compose (lokal + staging)
- infra/traefik → Reverse Proxy + Let's Encrypt

## Externe Referenz (READ ONLY)
- /Users/gio/TrueRepublic — Blockchain (Cosmos SDK, PnyxCoin)
- Bridge: MOD-08 (Stub, ENV-aktivierbar, Phase V2)

## Aktive Module (Beta)
- MOD-01 Identity (SMS HLR, Ed25519, Nullifier, Revokation)
- MOD-02 VAA (Thesis Matching)
- MOD-03 Parliament (Βουλή API + Bill Lifecycle)
- MOD-04 CitizenVote (Υπέρ/Κατά/Αποχή + WebSocket)
- MOD-05 Analytics (Divergence Score, k-Anonymität)
- MOD-12 Public API (REST + Embed + RSS)

## Bill Lifecycle States
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END

## Sicherheitsprinzipien
- Kein Personenbezug wird gespeichert
- Telefonnummer wird sofort nach Key-Generierung gelöscht
- Ed25519 Private Key lebt nur im Gerät (Secure Enclave)
- SHA256(Gruppe + Server-Salt) — Rohdaten per gc.collect() vernichtet

## TODO → docs/TODO.md

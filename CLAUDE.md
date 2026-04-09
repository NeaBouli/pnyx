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

## Web Seiten (10 Routes — alle gebaut)
/[locale]            → Homepage (Hero + Feature Cards)
/[locale]/vaa        → VAA Quiz (Intro → Quiz → Results + recharts) → seeds Compass
/[locale]/compass    → Liquid Compass Dashboard (4 Modelle, AES-256-GCM verschlüsselt)
/[locale]/bills      → Bills Feed (Filter + StatusBadge + Cards)
/[locale]/bills/[id] → Bill Detail (Summary + Abstimmung + Divergence) → feeds Compass
/[locale]/verify     → Identity Verify (SMS → Key → Success)
/[locale]/results    → Ergebnisse & Divergenz
/[locale]/analytics  → Analytische Daten
/[locale]/mp         → Parteien vs Bürger
/[locale]/admin      → Admin Panel

## Liquid Compass (lib/compass/)
- 4 Modelle: Party Match, Links-Rechts, 2D Kompass, Thematischer Radar
- User wählt Modell oder deaktiviert Kompass komplett
- VAA = freiwilliger Einstieg, Kompass aktualisiert sich bei jeder Abstimmung
- 100% clientseitig, AES-256-GCM verschlüsselt mit HKDF vom Ed25519 Key
- Niemals an Server gesendet — höchst persönlich, nur auf dem Gerät

## Smart Notifications (MOD-17 — GEPLANT)
- User wählt Kategorien (Βουλή, Δήμος, etc.) + Ton pro Kategorie
- Server sendet nur "Ping" (Topic-basiert), kein Inhalt im Push
- 3 Content-Modi: Manuell (Headline → Download), Automatisch, Headline-Only
- Templates lokal auf Gerät, lokaler Cache für Gesetze
- Privacy: Minimaler Datenverkehr, User kontrolliert alles

## Components
NavHeader | StatusBadge | DivergenceCard | ProgressBar | VoteButton | CompassCard

## Bill Lifecycle
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END

## Tests (Stand: 2026-04-09)
- Web:    29 passed (17 crypto + 12 cross-platform compat)
- API:    51 passed + 16 xfail (kein lokales PG)
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
- 38 VAA-Thesen (Υγεία, ΝΑΤΟ, Μισθός, Στέγαση, Τουρισμός, Δημογραφία, Τέμπη...)
- 3 Gesetzentwürfe (2x OPEN_END, 1x ACTIVE)

## Nächste Session → docs/TODO.md

## MOD-16 Municipal Governance (neu)
- Neue DB Tabellen: periferia, dimos, communities, decisions
- Router: apps/api/routers/municipal.py (Stub)
- Governance Levels: NATIONAL | REGIONAL | MUNICIPAL | COMMUNITY
- Parteien: skalierbar via seeds/parties_config.json
- Wiki Home: Live Ticker (3 Ticker × 3 Karten, auto-scroll 3s)

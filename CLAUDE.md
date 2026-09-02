# CLAUDE.md — Ekklesia.gr / pnyx
# Copyright (c) 2026 Vendetta Labs — MIT License
# Letzte Session: 2026-06-08

## Identität
- Repo lokal:  /Users/gio/Desktop/pnyx
- Repo remote: https://github.com/NeaBouli/pnyx
- Produkt:     Ekklesia.gr — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας
- Copyright:   © 2026 Vendetta Labs (MIT License)
- Spec:        v10.0 (25 Module, 23 live)
- Phase:       Beta — HLR SIM-Verifikation, VAA, CitizenVote, Politikoi Evaluation, Forum Sync, Self-Healing Monitor

## Multi-Agent Hierarchie
- Codex Sol = verantwortlicher Hauptagent und Orchestrator
- Kimi K3 = starker Senior-Partner für Implementierung und Review
- Claude Code = kleinerer Helfer für gezielte Prüfungen und Patches
- Alle Ergebnisse gehen an Sol zur Prüfung
- Keine autonomen Architektur- oder Security-Entscheidungen

## Externe Referenz (READ ONLY — niemals verändern)
- /Users/gio/TrueRepublic — Cosmos SDK Blockchain, PnyxCoin
- Bridge geplant: MOD-08 (ENV-aktivierbar, Phase V2)

## Stack
- apps/api      → Python FastAPI + Alembic + PostgreSQL + Redis
- apps/web      → Next.js 16 (App Router, i18n el/en, Tailwind, recharts)
- apps/mobile   → Expo / React Native (Android package `ekklesia.gr`, v1.0.31 / versionCode 60)
- packages/crypto → Python + PyNaCl (Ed25519, Nullifier, HLR)
- packages/db   → Alembic Migrations (9 Tabellen, 3 Enums)
- infra/docker  → Docker Compose (services: api, web, db, redis, ollama, monitor, dashboard, docker-proxy)

## V2 Technologie-Entscheidungen (in ROADMAP dokumentiert)
- packages/crypto-rs → Rust + WASM (ed25519-dalek, wasm-bindgen)
  → Krypto direkt im Browser, kein Server-Trust nötig
- MOD-08 TrueRepublic Bridge → Cosmos SDK / PnyxCoin
- MOD-09 gov.gr OAuth2.0 → Alpha 0.1 design-only; 500 Nutzer + 3 NGOs reichen nicht. Erforderlich sind alle offiziellen Holder-, DPIA-, Migration-, unabhängigen Review- und Sandbox-Canary-Gates sowie expliziter Runtime-Schalter, Credentials und starker Server-Salt.

## API Endpoints (70+ total — 23 Live-Module / Spec 25)
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
/[locale]/verify     → Identity Verify (HLR SIM check → Key → Success)
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

## Tests (Stand: 2026-06-08)
- Golden Path Regression: Source Resolver, 24h Banner, Quality Gate, Arweave Guards
- API focused: SSO + Voting `22 passed, 2 xfailed`
- Mobile focused: API pagination + source resolver `27 passed`
- Vollsuite lokal kann Redis/Admin-Key Test-Env benötigen; Ergebnis nicht ohne Kontext als Produktfehler werten.

## Git Stand
- main wird direkt gepusht; vor Änderungen immer `git status --short`
- Rollback-Tags vor riskanten Arbeiten setzen
- Aktueller Stand steht in `docs/agent-bridge/ACTION_LOG.md`

## Sicherheitsprinzipien
- Telefonnummer: sofort nach Nullifier-Generierung gelöscht (gc.collect())
- Private Key: einmalig zurückgegeben, nie gespeichert
- Nullifier Hash: SHA256(phone + SERVER_SALT) — phone not stored; depends on SERVER_SALT secrecy. If salt leaks, Greek phone numbers are brute-forceable; Argon2id/scrypt migration is a separate design task.
- Ed25519: Public Key auf Server, Private Key nur im Gerät
- Demographic Hash: SHA256(region + gender + SERVER_SALT)
- Voting: Ed25519 Signaturen, keine Accounts, keine E-Mail, keine Cookies — Anonymität nicht verhandelbar
- Arweave: append-only Archivierung

## Seed-Daten (bereit für alembic upgrade head)
- 8 griechische Parteien (ΝΔ, ΣΥΡΙΖΑ, ΠΑΣΟΚ, ΚΚΕ, ΕΛ, ΝΙΚΗ, ΠΛ, ΣΠΑΡΤ)
- 38 VAA-Thesen (Υγεία, ΝΑΤΟ, Μισθός, Στέγαση, Τουρισμός, Δημογραφία, Τέμπη...)
- 3 Gesetzentwürfe (2x OPEN_END, 1x ACTIVE)

## Nächste Session → docs/agent-bridge/TODO.md + WORKING_FEATURES.md lesen

## Rollback-Punkte
- `pre-session4-20260413` → HEAD `d7b09f4` (Session 3 komplett)
- `pre-session3-20260409` → HEAD `cd050e5` (pre-Session 3)

## Wichtige Hinweise
- CI/Install: `npm ci`, nicht `npm install`
- `.github/workflows/deploy.yml` = nur `workflow_dispatch` (kein auto-deploy)
- Compose-Service heißt `api`, nicht `ekklesia-api`
- Prod-Env laden: `set -a && source /opt/ekklesia/.env.production && set +a`
- Deploy-Guard: `docker compose stop api` zuerst, dann build/up
- Compass-Daten = 100% clientseitig, AES-256-GCM, nie auf Server
- axios: muss bei 1.14.0 oder darüber bleiben (Supply-Chain-Audit)
- .npmrc: ignore-scripts=true

## MOD-16 Municipal Governance (neu)
- Neue DB Tabellen: periferia, dimos, communities, decisions
- Router: apps/api/routers/municipal.py (Stub)
- Governance Levels: NATIONAL | REGIONAL | MUNICIPAL | COMMUNITY
- Parteien: skalierbar via seeds/parties_config.json
- Wiki Home: Live Ticker (3 Ticker × 3 Karten, auto-scroll 3s)

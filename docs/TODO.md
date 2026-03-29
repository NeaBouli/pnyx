# Ekklesia.gr — TODO
_Letzte Aktualisierung: 2026-03-29 — Auto-Sync nach jedem Build_

## ✅ Phase 0: Fundament (ABGESCHLOSSEN)
- [x] Monorepo-Struktur angelegt (apps/, packages/, infra/, docs/)
- [x] CLAUDE.md erstellt (persistenter Projektkontext)
- [x] .gitignore, README.md, LICENSE
- [x] Docker Compose: PostgreSQL + Redis + FastAPI
- [x] FastAPI Grundgerüst + /health Endpoint + Tests
- [x] Alembic Setup + Migration
- [x] Vollständiges DB-Schema v7 (9 Tabellen, 3 Enums)

## 🔄 Phase 1: Krypto-Fundament (AKTIV)
- [x] packages/crypto: Ed25519 Keypair (Python PyNaCl)
- [x] packages/crypto: Nullifier Hash (SHA256 + SERVER_SALT)
- [x] packages/crypto: HLR Lookup Stub (Twilio Interface)
- [ ] packages/crypto: Key Revokation Logik
- [x] packages/crypto: Unit Tests (100% Coverage)
- [x] MOD-01: POST /api/v1/identity/verify (SMS Beta)
- [x] MOD-01: POST /api/v1/identity/revoke
- [x] GitHub Actions: CI (test + lint)
- [x] GitHub Actions: Auto-Backup CLAUDE.md + TODO.md

## ⏳ Phase 2: VAA + Parliament (AUSSTEHEND)
- [ ] Seed-Daten: 6-8 griechische Parteien
- [ ] Seed-Daten: 15 Thesen (VAA)
- [ ] MOD-02: POST /api/v1/match (Matching-Algorithmus)
- [ ] MOD-03: GET /api/v1/bills (Βουλή API)
- [ ] MOD-03: Cron Job täglich 03:00
- [ ] MOD-03: Bill Lifecycle State Machine

## ⏳ Phase 3: CitizenVote (AUSSTEHEND)
- [ ] MOD-04: POST /api/v1/vote (Ed25519 Signatur-Validierung)
- [ ] MOD-04: WebSocket /ws/bill/{id} (Live-Counter)
- [ ] MOD-05: Divergence Score
- [ ] MOD-14: Up/Down Relevanz-Voting

## ⏳ Phase 4: Frontend (AUSSTEHEND)
- [ ] Next.js 14 Setup + i18n (el/en)
- [ ] VAA Quiz Flow
- [ ] Bill Feed + Abstimmungs-UI
- [ ] Expo / React Native App

## ⏳ Phase V2: Bridges (AUSSTEHEND)
- [ ] MOD-08: TrueRepublic Bridge (ENV-aktivierbar)
- [ ] MOD-09: gov.gr OAuth2.0 (Alpha-Phase)
- [ ] MOD-10/11: KI-Scraper + Zusammenfassung

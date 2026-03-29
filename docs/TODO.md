# Ekklesia.gr — TODO
# Copyright (c) 2026 Vendetta Labs — MIT License
# Letzte Aktualisierung: 2026-03-29

---

## ✅ ABGESCHLOSSEN

### Fundament
- [x] Monorepo-Struktur (apps/, packages/, infra/, docs/)
- [x] CLAUDE.md persistenter Kontext-Anker
- [x] MIT License © Vendetta Labs
- [x] Docker Compose (PostgreSQL + Redis + FastAPI)
- [x] GitHub Actions CI (grün: test-api + test-crypto + test-web)
- [x] GitHub Remote: https://github.com/NeaBouli/pnyx

### Backend API (apps/api — FastAPI + Python)
- [x] FastAPI Grundgerüst + /health + /docs
- [x] Alembic Migrations + vollständiges DB-Schema v7 (9 Tabellen, 3 Enums)
- [x] MOD-01 Identity: verify / revoke / status (Ed25519, HLR, Nullifier)
- [x] MOD-02 VAA: statements / parties / match (8 Parteien, 15 Thesen)
- [x] MOD-03 Parliament: bills / trending / lifecycle / admin/create
- [x] MOD-04 CitizenVote: vote (Ed25519 signiert) / results / relevance
- [x] MOD-05 Divergence Score (integriert in /results)
- [x] MOD-14 Relevance Up/Down Signal
- [x] Seed-Daten: 8 Parteien, 15 Thesen, 3 Gesetzentwürfe

### Krypto (packages/crypto — Python)
- [x] Ed25519 Keypair (generate / sign / verify)
- [x] Nullifier Hash (SHA256 + SERVER_SALT)
- [x] Demographic Hash (MOD-09 Alpha vorbereitet)
- [x] HLR Lookup Stub (Twilio-Interface bereit)

### Tests
- [x] 40 passed + 4 xfail (kein lokales PG) + 12 Crypto = 44 total
- [x] CI läuft auf GitHub Actions (grün)

### Web Frontend (apps/web — Next.js 14 + TypeScript)
- [x] Next.js 14 App Router Setup
- [x] i18n: Griechisch (el) + Englisch (en) via next-intl
- [x] Startseite (Hero + Feature Cards + Footer)
- [x] API Client (Axios + vollständige TypeScript Types)
- [x] Middleware für Locale-Routing
- [x] Build erfolgreich (97.3 kB First Load JS)

---

## 🔄 IN ARBEIT (aktuell)

### Web Frontend Pages
- [ ] VAA Quiz Seite (/vaa) — Thesen-Flow + Ergebnis
- [ ] Bills Feed Seite (/bills) — Lifecycle-Anzeige + Filter
- [ ] Bill Detail Seite (/bills/[id]) — Abstimmung + Divergence
- [ ] Identity/Verify Seite (/verify) — SMS Flow

---

## ⏳ AUSSTEHEND

### Web Frontend (Vervollständigung)
- [ ] Navigation Component (Header + Locale Switch)
- [ ] VAA Ergebnis-Seite (Balkendiagramm, recharts)
- [ ] Bill Abstimmungs-UI (Υπέρ/Κατά/Αποχή/Δεν γνωρίζω)
- [ ] Divergence Score Anzeige
- [ ] Mein Abgeordneter (MOD-13)
- [ ] Embeddable Widget (MOD-12)

### Mobile App (apps/mobile — Expo)
- [ ] Expo Setup (React Native + TypeScript)
- [ ] Biometrie-Flow (expo-local-auth)
- [ ] Secure Enclave Key Storage (expo-secure-store)
- [ ] Geteilte API-Logik mit Web

### Production
- [ ] Hetzner CX21 Setup
- [ ] Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] Environment Variables (Secrets)
- [ ] alembic upgrade head (gegen echte DB)

### V2 Roadmap
- [ ] packages/crypto-rs — Rust + WASM (Ed25519 im Browser)
- [ ] MOD-08 TrueRepublic Bridge (PnyxCoin, Cosmos SDK)
- [ ] MOD-09 gov.gr OAuth2.0 (Alpha-Phase)
- [ ] MOD-10/11 KI-Scraper (Crawl4AI + Claude API)
- [ ] MOD-13 Mein Abgeordneter
- [ ] WebSocket Live-Counter (WINDOW_24H)
- [ ] Commit-Reveal Abstimmung (Zero-Knowledge V2)
- [ ] Deliberation Layer (pol.is Modell)

### Technologie-Notiz (für V2)
- Rust (packages/crypto-rs): Ed25519-dalek + sha2 + wasm-bindgen
  → Krypto läuft direkt im Browser als WASM-Modul
  → Kein Server-Trust nötig für Signierung
  → Natürliche Wahl wenn Plattform wächst

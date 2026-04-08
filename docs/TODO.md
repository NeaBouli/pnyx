# Ekklesia.gr — TODO
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-03-29 — Session 1 abgeschlossen

---

## ✅ SESSION 1 KOMPLETT ABGESCHLOSSEN

### Fundament & DevOps
- [x] Monorepo-Struktur (apps/ packages/ infra/ docs/)
- [x] CLAUDE.md persistenter Kontext-Anker
- [x] MIT License © Vendetta Labs
- [x] .gitignore, README.md, ROADMAP.md
- [x] Docker Compose (PostgreSQL + Redis + FastAPI)
- [x] GitHub Actions CI (grün: test-api + test-crypto)
- [x] GitHub Remote: https://github.com/NeaBouli/pnyx
- [x] Prometheus-Style Reports (docs/reports/)

### Backend API (apps/api)
- [x] FastAPI Grundgerüst + /health + /docs (Swagger)
- [x] Alembic + vollständiges DB-Schema v7 (9 Tabellen, 3 Enums)
- [x] MOD-01 Identity: verify / revoke / status
- [x] MOD-02 VAA: statements / parties / match
- [x] MOD-03 Parliament: bills / trending / lifecycle / admin
- [x] MOD-04 CitizenVote: vote (Ed25519) / results / relevance
- [x] MOD-05 Divergence Score
- [x] MOD-14 Relevance Up/Down
- [x] Seed-Daten: 8 Parteien + 15 Thesen + 3 Bills

### Krypto (packages/crypto)
- [x] Ed25519 Keypair (generate / sign / verify)
- [x] Nullifier Hash (SHA256 + SERVER_SALT)
- [x] Demographic Hash (Alpha vorbereitet)
- [x] HLR Lookup Stub (Twilio-Interface)
- [x] 12 Unit Tests

### Web Frontend (apps/web)
- [x] Next.js 14 + TypeScript + Tailwind
- [x] i18n: el/en via next-intl
- [x] NavHeader (sticky, locale switch, GitHub icon)
- [x] Homepage / VAA Quiz / Bills Feed / Bill Detail / Verify
- [x] StatusBadge + DivergenceCard + ProgressBar + VoteButton
- [x] API Client (Axios + vollständige TS Types)
- [x] Build: erfolgreich (97–232 kB per page)

### Tests & CI
- [x] 44 Tests total (40 API + 4 xfail + 12 Crypto)
- [x] GitHub Actions: grün

---

## 🔄 SESSION 2 — NÄCHSTE SCHRITTE (Priorität)

### Kritisch (vor erstem Launch)
- [x] Doppelten Header in VAA/Bills Seiten entfernen (NavHeader ist im Layout) — Session 3
- [x] Ed25519 Signatur im Browser implementiert (@noble/curves) — war bereits komplett
- [x] Vote API call in Bill Detail /bills/[id] war bereits fertig — Session 1
- [ ] Docker Compose lokal starten + alembic upgrade head
- [ ] Seed-Script ausführen (python seeds/seed.py)
- [ ] End-to-End Test: API lokal → Frontend lokal → vollständiger Flow

### Mobile App (apps/mobile)
- [x] Expo Setup (React Native + TypeScript) — Session 2
- [x] expo-secure-store (Secure Enclave Key Storage) — Session 2
- [x] expo-local-auth (Biometrie für Stimmabgabe) — Session 2
- [x] Ed25519 Signing auf Mobile (@noble/curves) — Session 3
- [x] Nullifier Hash Bug gefixt (fehlender ":" Separator) — Session 3
- [ ] Geteilte API-Logik mit Web (packages/types)
- [ ] iOS + Android Build testen

### V2 Roadmap
- [ ] packages/crypto-rs (Rust + WASM: ed25519-dalek, wasm-bindgen)
- [ ] MOD-08 TrueRepublic Bridge (PnyxCoin, Cosmos SDK)
- [ ] MOD-09 gov.gr OAuth2.0 (nach 500 Nutzern + 3 NGOs)
- [ ] MOD-10/11 KI-Scraper (Crawl4AI + Claude API)
- [ ] MOD-13 Mein Abgeordneter
- [ ] WebSocket Live-Counter (WINDOW_24H)
- [ ] Commit-Reveal ZK Abstimmung

### Production (wenn Konzept vollumfänglich gebaut)
- [ ] Hetzner CX21 Setup
- [ ] Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] Environment Variables (Secrets Management)
- [ ] Domain: ekklesia.gr
- [ ] Externes Sicherheitsaudit

## ✅ Session 1.5 + 2.0 — Abgeschlossen
- [x] GitHub Pages live: ekklesia.gr
- [x] Landing Page (8 Sections, hell, animiert, el/en)
- [x] Wiki HTML (10 Seiten, identischer Style)
- [x] Whitepaper (13 Kapitel, vollständig)
- [x] MOD-16 Municipal Governance (DB Models + Router Stub)
- [x] Parteien skalierbar (parties_config.json)
- [x] Wiki Home Live Ticker (3 Ticker × auto-scroll)
- [x] Alembic Migration MOD-16

## ✅ Session 3 — Abgeschlossen (2026-04-09)
- [x] Rollback-Punkt: Tag `pre-session3-20260409` auf `cd050e5`
- [x] Doppelter Header: 9 redundante `<header>` aus 7 Seiten entfernt
- [x] Tailwind 4 PostCSS Fix: `@tailwindcss/postcss` + `@import "tailwindcss"`
- [x] Mobile Ed25519 Signing: `@noble/curves` auf Expo, `signVote()` + `verifyVote()`
- [x] Nullifier Hash Bug: fehlender `:` Separator in `computeNullifier()` gefixt
- [x] Cross-Platform Krypto-Tests: 12 neue Tests (Signatur-Kompatibilität Web↔Mobile↔Backend)
- [x] Alle Tests grün: Web 29/29, Python Crypto 12/12, API 51+16xfail

## 🔄 Session 4 — Nächste Schritte
- [ ] Docker lokal + alembic upgrade head + seed
- [ ] E2E Test vollständiger Flow
- [ ] Wiki Ticker → echte API-Daten verbinden
- [ ] iOS + Android Build testen (Expo EAS)
- [ ] Shared Types Package (packages/types)

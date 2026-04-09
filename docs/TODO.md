# Ekklesia.gr — TODO
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09 — Session 3 komplett (8 Commits gepusht)

---

## 🔴 OFFEN — Kritisch (vor erstem Launch)

### Infrastruktur
- [ ] Docker Compose lokal starten + `alembic upgrade head`
- [ ] Seed-Scripts ausführen (`seed.py` + `seed_real_bills.py` — 38 Thesen + 10 Bills)
- [ ] End-to-End Test: API → Web → Verify → Vote → Results
- [ ] VAA mit 38 Thesen im Browser durchspielen, Matching verifizieren

### Web
- [ ] Next.js 15 Upgrade (löst eslint Peer-Conflict + react@19 Warning)
- [ ] Secure Storage Hardening (localStorage → httpOnly Cookie o.ä.)

### Mobile
- [ ] iOS + Android Build testen (Expo EAS: `eas build --platform all`)
- [ ] Geteilte API-Typen: `packages/types/` für Web + Mobile

---

## 🟡 OFFEN — Vor Public Beta

### Plattform
- [ ] Hetzner CX21 Setup + Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose deployen
- [ ] Environment Variables / Secrets Management
- [ ] Domain ekklesia.gr → Hetzner (statt GitHub Pages)
- [ ] CORS-Config für Prod-Domain
- [ ] Externes Sicherheitsaudit

### Features
- [ ] Wiki Ticker → echte API-Daten verbinden
- [ ] MOD-16 Municipal Governance — Router-Implementierung
- [ ] WebSocket Live-Counter (WINDOW_24H Bills)
- [ ] VAA auf Mobile portieren (fehlt auf Expo)

---

## 🟢 GEPLANT — V2 / Alpha

### Krypto
- [ ] packages/crypto-rs (Rust + WASM: ed25519-dalek, wasm-bindgen)
- [ ] Commit-Reveal ZK Abstimmung

### Integrationen
- [ ] MOD-08 TrueRepublic Bridge (PnyxCoin, Cosmos SDK)
- [ ] MOD-09 gov.gr OAuth2.0 (nach 500 Nutzern + 3 NGOs)
- [ ] MOD-10/11 KI-Scraper + Zusammenfassung (Crawl4AI + Claude API)
- [ ] MOD-13 Mein Abgeordneter — Vollimplementierung

### Governance
- [ ] Deliberation (pol.is-Modell)
- [ ] Demographische Verifikation (Altersgruppe + Region)
- [ ] Sandbox-Anfrage an AADE/gov.gr

---

## ✅ ERLEDIGT

### Session 3 (2026-04-09) — 8 Commits

#### Ed25519 + Header + Tailwind
- [x] Rollback-Punkt: Tag `pre-session3-20260409` auf `cd050e5`
- [x] 9 doppelte `<header>` aus 7 Seiten entfernt
- [x] Tailwind 4 PostCSS Fix: `@tailwindcss/postcss` + `@import "tailwindcss"`
- [x] Mobile Ed25519 Signing: `@noble/curves`, `signVote()` + `verifyVote()`
- [x] Nullifier Hash Bug: fehlender `:` Separator in `computeNullifier()` gefixt
- [x] Cross-Platform Krypto-Tests: 12 neue Tests (Web ↔ Mobile ↔ Backend)

#### VAA Erweiterung 15 → 38 Thesen
- [x] 23 neue Statements basierend auf echten griechischen Debatten (2024-2026)
- [x] 304 Parteipositionen (8 Parteien × 38 Thesen), verifiziert
- [x] Alle Referenzen aktualisiert: Landing, Homepage, Wiki, README, FAQ, CLAUDE.md
- [x] Alle Tests grün: Web 29/29, Crypto 12/12, API 51+16xfail, VAA 6/6
- [x] 8 Commits gepusht auf Remote

### Session 2 (2026-04-07) — Dependencies
- [x] 10 Dependabot PRs gemergt (#11–#20)
- [x] TypeScript 5.9 → 6.0 Breaking Changes gefixt

### Session 1.5 + 2.0 — Docs & Features
- [x] GitHub Pages live: ekklesia.gr
- [x] Landing Page, Wiki HTML, Whitepaper
- [x] MOD-16 Municipal Governance (Stub + Alembic)
- [x] Mobile App: 7 Screens, Biometrie, Secure Enclave

### Session 1 (2026-03-29) — Foundation
- [x] Monorepo, CI/CD, 13 Router, 9 Tabellen
- [x] MOD-01 bis MOD-05 + MOD-14
- [x] Next.js Web: 5 Seiten + i18n

---

*Aktualisiert: 2026-04-09 — Session 3 komplett, alle Commits gepusht.*

# Ekklesia.gr — TODO
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09 — nach Session 3

---

## 🔴 OFFEN — Kritisch (vor erstem Launch)

### Infrastruktur
- [ ] Docker Compose lokal starten + `alembic upgrade head`
- [ ] Seed-Script ausführen (`python seeds/seed.py`)
- [ ] End-to-End Test: API → Web → Verify → Vote → Results
- [ ] 4 Commits auf Remote pushen (`git push origin main`)

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
- [ ] VAA auf Mobile portieren (7 Web-only Screens)

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

### Session 3 (2026-04-09) — Ed25519 + Header + Tailwind
- [x] Rollback-Punkt: Tag `pre-session3-20260409` auf `cd050e5`
- [x] 9 doppelte `<header>` aus 7 Seiten entfernt (NavHeader im Layout reicht)
- [x] Tailwind 4 PostCSS Fix: `@tailwindcss/postcss` + `@import "tailwindcss"`
- [x] Mobile Ed25519 Signing: `@noble/curves`, `signVote()` + `verifyVote()`
- [x] Nullifier Hash Bug: fehlender `:` Separator in `computeNullifier()` gefixt
- [x] Cross-Platform Krypto-Tests: 12 neue Tests (Web ↔ Mobile ↔ Backend)
- [x] Alle Tests grün: Web 29/29, Crypto 12/12, API 51+16xfail

### Session 2 (2026-04-07) — Dependencies
- [x] 10 Dependabot PRs gemergt (#11–#20)
- [x] TypeScript 5.9 → 6.0 Breaking Changes gefixt
- [x] `security` Label im GitHub Repo erstellt

### Session 1.5 + 2.0 — Docs & Features
- [x] GitHub Pages live: ekklesia.gr
- [x] Landing Page (8 Sections, hell, animiert, el/en)
- [x] Wiki HTML (10 Seiten, identischer Style)
- [x] Whitepaper (13 Kapitel, vollständig)
- [x] MOD-16 Municipal Governance (DB Models + Router Stub + Alembic)
- [x] Parteien skalierbar (parties_config.json)
- [x] Wiki Home Live Ticker (3 Ticker x auto-scroll)
- [x] Mobile App: 7 Screens, Biometrie, Secure Enclave

### Session 1 (2026-03-29) — Foundation
- [x] Monorepo-Struktur, CI/CD, GitHub Remote
- [x] FastAPI + Alembic + 9 Tabellen + 13 Router
- [x] MOD-01 bis MOD-05 + MOD-14 komplett
- [x] packages/crypto (Ed25519, Nullifier, HLR)
- [x] Next.js Web: 5 Seiten + i18n (el/en)
- [x] 44 Tests + CI grün

---

*Aktualisiert: 2026-04-09 — Session 3 abgeschlossen.*

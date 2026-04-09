# Ekklesia.gr — TODO
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09 — Session 3 komplett (10 Commits gepusht)

---

## 🔴 OFFEN — Kritisch (vor erstem Launch)

### Infrastruktur
- [ ] Docker Compose lokal starten + `alembic upgrade head`
- [ ] Seed-Scripts: `seed.py` (38 Thesen) + `seed_real_bills.py` (10 Bills + 304 Positionen)
- [ ] E2E Test: Verify → VAA (38 Fragen) → Compass-Seed → Vote → Compass-Update → Results

### Web
- [ ] Compass Engine Unit Tests (vitest) — engine.ts Berechnungen
- [ ] Next.js 15 Upgrade (eslint Peer-Conflict lösen)
- [ ] Secure Storage Hardening (localStorage → httpOnly Cookie)

### Mobile
- [ ] iOS + Android Build (Expo EAS)
- [ ] Compass auf Mobile portieren (useCompass → expo-secure-store)
- [ ] Shared Types: `packages/types/` für Web + Mobile

---

## 🟡 OFFEN — Vor Public Beta

### Plattform
- [ ] Hetzner CX21 + Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] Secrets Management
- [ ] Domain ekklesia.gr → Hetzner
- [ ] CORS für Prod-Domain
- [ ] Externes Sicherheitsaudit

### Features
- [ ] VAA auf Mobile portieren
- [ ] Wiki Ticker → echte API-Daten
- [ ] MOD-16 Municipal Governance — Router-Implementierung
- [ ] WebSocket Live-Counter (WINDOW_24H Bills)

---

## 🟢 GEPLANT — V2 / Alpha

- [ ] packages/crypto-rs (Rust + WASM)
- [ ] Commit-Reveal ZK Abstimmung
- [ ] MOD-08 TrueRepublic Bridge
- [ ] MOD-09 gov.gr OAuth2.0
- [ ] MOD-10/11 KI-Scraper
- [ ] MOD-13 Mein Abgeordneter
- [ ] Deliberation (pol.is-Modell)

---

## ✅ ERLEDIGT — Session 3 (2026-04-09, 10 Commits)

### Crypto & Bugs
- [x] 9 doppelte Headers entfernt
- [x] Tailwind 4 PostCSS Migration
- [x] Mobile Ed25519 Signing (`@noble/curves`)
- [x] Nullifier Hash `:` Separator Bug gefixt
- [x] 12 Cross-Platform Krypto-Tests

### VAA Erweiterung
- [x] 15 → 38 Thesen (echte griechische Debatten)
- [x] 304 Parteipositionen (8 × 38)
- [x] Alle Referenzen aktualisiert (Landing, Wiki, README, FAQ)

### Liquid Political Compass
- [x] 4 Modelle: Party Match, Links-Rechts, 2D, Thematischer Radar
- [x] AES-256-GCM Verschlüsselung (HKDF vom Ed25519 Key)
- [x] 100% clientseitig — nie auf Server
- [x] VAA seeds Compass, jeder Bill-Vote aktualisiert
- [x] User wählt Modell oder deaktiviert komplett
- [x] Dashboard-Seite: `/[locale]/compass`
- [x] CompassCard Widget auf Bill-Detail
- [x] NavHeader + Landing + Wiki + README aktualisiert
- [x] Privacy Banner auf Compass-Seite

### Previous Sessions
- [x] Session 2: 10 Dependabot PRs, TS 6.0 Fixes
- [x] Session 1.5+2.0: Landing, Wiki, Whitepaper, Mobile 7 Screens
- [x] Session 1: Foundation (13 Router, 9 Tabellen, CI/CD)

---

*Stand: 2026-04-09. 10 Commits gepusht. Remote synchron.*

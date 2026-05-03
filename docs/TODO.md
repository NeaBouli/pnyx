# Ekklesia.gr — TODO
# Copyright (c) 2026 V-Labs Development — MIT License
# Stand: 2026-04-13 — Session 3 komplett, Rollback pre-session4-20260413

---

## 🚀 STARTFLOW FÜR NÄCHSTE SESSION

> **Lies das hier zuerst, bevor du irgendetwas änderst.**

```
1. git log --oneline -5              → Prüfe HEAD (sollte d7b09f4 sein)
2. git status                        → Muss sauber sein
3. git tag -l "pre-session*"         → Rollback-Punkte prüfen
4. Lies CLAUDE.md                    → Projekt-Kontext, Stack, Architektur
5. Lies docs/STATUS.md               → Aktueller Modulstatus, Tests, Known Issues
6. Lies docs/HANDOVER-SESSION3.md    → Was zuletzt gemacht wurde
7. Lies DIESE DATEI (docs/TODO.md)   → Was als nächstes ansteht
8. cd apps/web && npx vitest run     → Tests müssen 29/29 grün sein
9. cd apps/api && .venv/bin/python -m pytest tests/ -v  → 51+16xfail
```

**Rollback:** `git reset --hard pre-session4-20260413` bringt dich auf `d7b09f4`.

**npm install:** Braucht `--legacy-peer-deps` wegen eslint Peer-Conflict.

**Deploy-Workflow:** `.github/workflows/deploy.yml` ist absichtlich deaktiviert
(nur `workflow_dispatch`). NICHT den `push`-Trigger wieder einfügen bevor
Hetzner-Secrets gesetzt sind.

**Prinzipien:**
- Modular, smart, light
- Datenschutz = höchste Priorität (Daten sind unser höchstes Gut)
- Kryptosicherheit wahren (Ed25519, AES-256-GCM, Nullifier)
- Keine Kollisions-gefährlichen Änderungen (DB-Schema, Infra) ohne Absprache
- Jeden Schritt dokumentieren (TODO, HANDOVER, STATUS, README, Wiki, Landing)

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

### Landing Page
- [x] App-Download-Buttons deaktiviert (2026-04-09) — alle 4 (App Store, Android, Google Play, F-Droid) auf "Σύντομα/Coming soon"
- [ ] App-Buttons reaktivieren wenn Mobile App komplett getestet + user-ready
- [ ] F-Droid Repo einrichten + APK publizieren

---

## 🟡 OFFEN — Vor Public Beta

### Plattform
- [ ] Hetzner CX21 + Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] GitHub Secrets setzen: `HETZNER_HOST`, `HETZNER_USER`, `HETZNER_SSH_KEY`
- [ ] `/opt/ekklesia` auf Server anlegen + initial `git clone`
- [ ] Deploy-Workflow reaktivieren: `push: branches: [main]` in `deploy.yml` (aktuell nur `workflow_dispatch`)
- [ ] Domain ekklesia.gr → Hetzner
- [ ] CORS für Prod-Domain
- [ ] Externes Sicherheitsaudit

### Features
- [ ] VAA auf Mobile portieren
- [ ] Wiki Ticker → echte API-Daten
- [ ] MOD-16 Municipal Governance — Router-Implementierung
- [ ] WebSocket Live-Counter (WINDOW_24H Bills)

### Smart Notifications & Content Delivery (MOD-17)
Prinzip: Minimaler Datenverkehr, maximale User-Kontrolle, Privacy-by-Design.

**Benachrichtigungen:**
- [ ] Kategorie-Filter (Βουλή, Δήμος, VAA, Compass) + Ton pro Kategorie
- [ ] Templates lokal auf Gerät gespeichert
- [ ] Server sendet nur Ping (Topic-basiert), keine Inhalte im Push

**Content Delivery (User wählt Modus):**
- [ ] Manuell: Headline → bewusster Download
- [ ] Automatisch: Gesetze + Abstimmungen auto-laden
- [ ] Headline-Only: Überschriften, Download bei Interesse

**Technik:**
- [ ] `expo-notifications` (FCM/APNs)
- [ ] NotificationPreferences + ContentDeliveryMode Screens
- [ ] Lokaler Cache (expo-file-system), Badge-Counter

### Partei-Synchronisation (nach Server-Migration)
- [ ] L1: Parlaments-Scraper (hellenicparliament.gr → Auto-Update Positionen)
- [ ] L2: Admin-Review Panel
- [ ] L3: Community "Position veraltet?" Flagging
- [ ] `party_position_history` DB-Table
- [ ] Automatische Partei-Erkennung (ΥΠΕΣ Register)
- [ ] KI Programm-Analyse → Human Review

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

## ✅ ERLEDIGT

### Session 3 (2026-04-09/10) — 15 Commits
- [x] Rollback: `pre-session3-20260409`, `pre-session4-20260413`
- [x] 9 doppelte Headers entfernt
- [x] Tailwind 4 PostCSS Migration
- [x] Mobile Ed25519 Signing + Nullifier `:` Bug Fix
- [x] 12 Cross-Platform Krypto-Tests
- [x] VAA: 15 → 38 Thesen (304 Parteipositionen)
- [x] Liquid Compass: 4 Modelle, AES-256-GCM, 100% clientseitig
- [x] MOD-17 Smart Notifications spezifiziert
- [x] App-Buttons deaktiviert + F-Droid hinzugefügt
- [x] Deploy-Workflow deaktiviert (fehlende Hetzner-Secrets)
- [x] STATUS, HANDOVER, README, Wiki, Landing, FAQ aktualisiert

### Session 2 (2026-04-07) — Dependencies
- [x] 10 Dependabot PRs, TS 6.0 Fixes

### Session 1 (2026-03-29) — Foundation
- [x] Monorepo, CI/CD, 13 Router, 9 Tabellen, 5 Web-Seiten

---

*Stand: 2026-04-13. HEAD `d7b09f4`. Rollback: `pre-session4-20260413`. Remote synchron.*

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

### Landing Page
- [x] App-Download-Buttons deaktiviert (2026-04-09) — PWA, APK, Store-Links alle auf "Σύντομα/Coming soon" gesetzt bis App user-ready ist
- [ ] App-Buttons reaktivieren wenn Mobile App komplett getestet + user-ready (App Store, Android APK, Google Play, F-Droid)
- [ ] F-Droid Repo einrichten + APK publizieren (FOSS-Kanal für Privacy-bewusste User)

---

## 🟡 OFFEN — Vor Public Beta

### Plattform
- [ ] Hetzner CX21 + Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] Secrets Management (HETZNER_HOST, HETZNER_USER, HETZNER_SSH_KEY in GitHub Secrets)
- [ ] `/opt/ekklesia` auf Server anlegen + initial git clone
- [ ] Deploy-Workflow reaktivieren: `push: branches: [main]` Trigger in `.github/workflows/deploy.yml` wieder einfügen (aktuell nur `workflow_dispatch` — deaktiviert 2026-04-10 wegen fehlender Secrets)
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

**Benachrichtigungs-Einstellungen (pro Kategorie):**
- [ ] Kategorie-Filter: User wählt welche Kategorien er empfängt (Βουλή, Περιφέρεια, Δήμος, VAA, Compass, etc.)
- [ ] Ton-Steuerung: pro Kategorie Ton an/aus, eigener Ton wählbar
- [ ] Vorgefertigte Templates: Benachrichtigungsvorlagen lokal auf Gerät gespeichert (kein Server-Rendering)
- [ ] Nur ein "Ping": Server sendet minimalen Push (nur Signal dass Neues anliegt), keine Inhalte im Push

**Content Delivery Mode (User wählt):**
- [ ] **Modus A: Manuell** — Nach Ping sieht User nur Überschrift, entscheidet selbst ob er die volle Gesetzesvorlage + Abstimmung herunterlädt
- [ ] **Modus B: Automatisch** — Neue Gesetze + Abstimmungen werden automatisch in die App geladen und angezeigt
- [ ] **Modus C: Headline-Only** — User sieht nur Überschriften, lädt bei Interesse die komplette Vorlage nach

**Technische Umsetzung:**
- [ ] `expo-notifications` für Push-Registrierung (FCM/APNs)
- [ ] Server: Nur Topic-basierte Pushes (Kategorie als Topic), Inhalt = `{type, id, title}` — kein Gesetzestext im Push
- [ ] App: `NotificationPreferences` Screen in Einstellungen
- [ ] App: `ContentDeliveryMode` Toggle (manuell/auto/headline)
- [ ] App: Lokaler Cache für heruntergeladene Gesetze (expo-file-system)
- [ ] App: Badge-Counter pro Kategorie

### Partei-Synchronisation (nach Server-Migration)
- [ ] **L1: Parlaments-Scraper** — hellenicparliament.gr Abstimmungen → Auto-Update Parteipositionen (objektiv, basierend auf echtem Stimmverhalten)
- [ ] **L2: Admin-Review** — Admin-Panel Tab für Partei-Verwaltung (neue Parteien, Positionsänderungen, Programm-Updates), Vorschläge aus L1 prüfen
- [ ] **L3: Community-Flagging** — "Position veraltet?" Button für User, triggert Admin-Review
- [ ] `party_position_history` DB-Table — Changelog wann/warum sich Positionen geändert haben
- [ ] Automatische Erkennung neuer/aufgelöster Parteien (ΥΠΕΣ / Άρειος Πάγος Register)
- [ ] KI-gestützte Programm-Analyse: Parteiprogramme → extrahierte Positionen → Human Review

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

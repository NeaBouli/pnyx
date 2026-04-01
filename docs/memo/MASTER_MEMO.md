# Ekklesia.gr — Master Memo
# Alle Architektur-Entscheidungen, TODOs, Specs
# Zuletzt aktualisiert: 2026-04-01

---

## ALPHA PHASE — ABGESCHLOSSEN
Tag: v0.3.0-alpha | Datum: 2026-04-01

### Alle 8 Alpha-Module gebaut:
- MOD-06: Analytics + Divergence Trends + k-Anonymity
- MOD-07: Push Notifications (SSE + WebSocket + Event Bus)
- MOD-09: gov.gr OAuth Stub (1/4 Gates)
- MOD-11: Public API + Rate Limiting + API Keys (CC BY 4.0)
- MOD-12: MP Comparison — Partei vs. Bürgermehrheit + Ranking
- MOD-13: Relevance Voting FE — RelevanceButtons + Trending
- MOD-14: Data Export CSV/JSON + Divergence + Parties
- MOD-15: Admin Panel — Dashboard + Bills CRUD + AI Review

### Stand: 13 Router, ~50 Endpoints, 7 Web Routes, Expo Mobile + APK

---

## PROJEKT INFO
- Name: Ekklesia.gr (εκκλησία)
- Codename: pnyx
- Org: NeaBouli
- Repo: github.com/NeaBouli/pnyx
- Domain: ekklesia.gr (Papaki, bis 29.03.2028)
- License: MIT © 2026 Vendetta Labs
- Kontakt: kaspartisan@proton.me (nie öffentlich)

---

## DESIGN REGELN
- Primärfarbe: #2563eb (Blau)
- Keine Emojis in Nav
- Kein Grün in Nav — nur Blau
- Logo: pnx.png (40×40px in Nav)
- Sprache: Griechisch default, EN Toggle
- Nav Landing: Πώς λειτουργεί | Χαρακτηριστικά | Ψηφοφορίες | Roadmap | Wiki | Community | Επικοινωνία
- Nav Wiki/Votes/Community: Αρχική | Ψηφοφορίες | Wiki | Community

---

## ARCHITEKTUR — STACK
- Backend: Python FastAPI (apps/api/) — 16 Endpoints
- Database: PostgreSQL 15 + Redis 7
- Frontend: Next.js 14 (apps/web/)
- Mobile: Expo React Native SDK 54 (apps/mobile/)
- Crypto Beta: PyNaCl + @noble/curves (Ed25519)
- Crypto V2: Rust + WASM (packages/crypto-rs) — geplant
- Static: GitHub Pages (docs/) → ekklesia.gr
- Infra: Hetzner CX21 + Traefik + SSL (geplant)

---

## MODULE STATUS

### Beta (aktiv)
- MOD-01: Identity — HLR Verifikation (KEIN SMS OTP)
- MOD-02: VAA Wahlkompass — 8 Parteien, 15 Thesen
- MOD-03: Parliament — Bill Lifecycle 5 Phasen
- MOD-04: CitizenVote — Ed25519 Signatur
- MOD-05: Divergence Score
- MOD-08: Arweave L2 — Full Audit Trail
- MOD-16: Municipal — Περιφέρεια/Δήμος/Κοινότητα

### Alpha (nach 500 Nutzern + NGOs)
- MOD-06: Analytics + Demographics
- MOD-07: Push Notifications
- MOD-09: gov.gr OAuth2.0
- MOD-10: AI Bill Scraper
- MOD-11: Public API
- MOD-12: MP Comparison
- MOD-13: Relevance Voting
- MOD-14: Data Export
- MOD-15: Admin Panel

### Community-aktivierbar (Stubs)
- MOD-17: LimeSurvey Integration
- MOD-18: pol.is Clustering (evaluieren wenn VAA UI fertig)

### V2
- MOD-08 V2: TrueRepublic Bridge
- MOD-19: Liquid Democracy (NUR mit gov.gr verifizierten Verwandten 1. Grades)
- packages/crypto-rs: Rust + WASM

---

## ARCHITEKTUR-ENTSCHEIDUNGEN

### Identity (MOD-01)
- HLR Verifikation — kein SMS OTP
- Griechische SIM (+30) = Ausweis-registriert per Gesetz
- HLR Provider: HLR Lookups / Melrose Labs / Telnyx (~$0.002/Query)
- Bezahlung: Community Crypto Wallet (öffentlich auf community.html)
- Beta → Alpha: gov.gr OAuth übernimmt

### Liquid Democracy
- NUR mit taxisnet/gov.gr verifizierten Verwandten 1. Grades
- Phase: Alpha (nach gov.gr Integration)
- Jetzt: nichts implementieren

### Arweave L2 (MOD-08)
- Öffentliche ekklesia.gr Arweave Wallet — community-funded
- Auto-publish bei PARLIAMENT_VOTED: FULL AUDIT TRAIL
  * Bill Metadata + Lifecycle
  * Aggregierte Citizen Votes (YES/NO/ABSTAIN/Total)
  * Divergence Score
  * Parliament Result
  * Governance Level
  * NIEMALS: Individual Votes, Nullifier Hashes
- TX-ID in parliament_bills.arweave_tx_id gespeichert
- Wallet Balance sichtbar auf community.html
- TrueRepublic Bridge: V2

### L1/L2/L3 Datenspeicherung
- L1: PostgreSQL (live, queryable) → Hetzner
- L2: Arweave (permanent, unveränderlich) → Full Audit Trail
- L3: TrueRepublic Chain (V2) → referenziert Arweave TX-IDs

### Community Wallets (auf community.html)
- Arweave Wallet: AR Token, öffentliche Adresse sichtbar
- HLR Wallet: Crypto, öffentliche Adresse sichtbar
- Server Relay (geplant, V2): Server liest Blockchain aus,
  berechnet aktuellen EUR-Betrag basierend auf Echtzeit-Kurs,
  zeigt auf community.html an (automatisch aktuell)

### LimeSurvey
- MOD-17 Stub — community-aktivierbar
- Für optionale Bürgerbefragungen
- Nicht Priorität

### pol.is Clustering
- Evaluieren wenn VAA UI gebaut wird
- Community entscheidet

### Hetzner Deploy
- CX21, Ubuntu 24.04, ~7€/Monat
- Traefik + SSL + Docker Compose Prod
- GitHub Actions Auto-Deploy bei git push
- Setup: bash infra/hetzner/setup.sh
- Anleitung: infra/hetzner/DEPLOY.md

---

## TODO — ABGEHAKT (Session 2)
- ~~PWA (Next.js) — iOS ohne App Store~~ — Service Worker + manifest + apple-touch-icon
- ~~VAA UI — Wahlkompass Seite~~ — Skip, Party Detail, Share, Top Match
- ~~Results Dashboard~~ — /results mit Divergence Übersicht + animierter DivergenceCard
- ~~HLR Provider aktivieren~~ — verify_greek_number() implementiert, Dry Run aktiv
- ~~Arweave Wallet erstellen~~ — 2hkK3Bcr6g...GdhBTs, community.html aktiviert
- ~~Parliament API Scraper~~ — MOD-10 Ollama L1 + HuggingFace L2 + Rule-based L3

---

## ALPHA MODULE — Bereit zum Bauen (kein Hetzner nötig)

### MOD-06: Analytics + Demographics
- Divergence Trends über Zeit (Chart)
- k-Anonymity >= 10 für demografische Auswertung
- Altersgruppen, Regionen, Governance Level
- Endpoint: GET /api/v1/analytics/divergence-trends
- Endpoint: GET /api/v1/analytics/demographics/{bill_id}

### MOD-07: Push Notifications
- WebSocket / SSE für Live-Updates im 24h-Fenster
- Bill Status Änderung -> Notification
- Stub: POST /api/v1/notifications/subscribe

### MOD-09: gov.gr OAuth2.0 Stub
- Stub-Endpoints für OAuth Flow
- Aktivierung nach: 500 Nutzer + 3 NGOs + publiziertes Roadmap
- Endpoint: GET /api/v1/auth/govgr/login
- Endpoint: GET /api/v1/auth/govgr/callback

### MOD-11: Public API + OpenAPI Docs
- Öffentliche REST API für NGOs, Journalisten, Forscher
- Rate Limiting (100 req/min anonym, 1000 mit API Key)
- API Key System (community-generiert, kein Konto nötig)

### MOD-12: MP Comparison
- "Dein Abgeordneter" — Wahlkreis auswählen
- Vergleich: Bürger-Stimme vs. Abgeordneten-Stimme
- Divergence Score pro MP
- Endpoint: GET /api/v1/mp/{mp_id}/comparison

### MOD-13: Relevance Voting
- Up/Down Voting für Bill-Wichtigkeit
- Backend fertig (BillRelevanceVote Tabelle), Frontend ausstehend
- Endpoint: POST /api/v1/bills/{id}/relevance

### MOD-14: Data Export
- CSV + JSON Download aller aggregierten Ergebnisse
- NIEMALS Individual-Votes oder Nullifier
- Endpoint: GET /api/v1/export/bills.csv
- Endpoint: GET /api/v1/export/results.json

### MOD-15: Admin Panel
- Bill Management (Create, Transition, Review)
- AI Summary Review (ai_summary_reviewed Flag)
- Endpoint: GET /api/v1/admin/bills

---

## TODO — ALPHA REIHENFOLGE

### Empfohlene Baufolge (alle lokal testbar)
1. MOD-11 Public API + OpenAPI -> sofort nützlich für NGOs
2. MOD-14 Data Export CSV/JSON -> Transparenz + Medien
3. MOD-06 Analytics + Trends   -> Divergence Visualisierung
4. MOD-12 MP Comparison        -> "Dein Abgeordneter"
5. MOD-09 gov.gr OAuth Stub    -> Vorbereitung Alpha
6. MOD-15 Admin Panel          -> Bill Management
7. MOD-07 Push Notifications   -> WebSocket/SSE
8. MOD-13 Relevance Voting FE  -> Frontend (Backend fertig)

---

## TODO — HETZNER (wenn bereit)
1. Server aktivieren (CX21, Ubuntu 24.04, ~7EUR/Monat)
2. bash infra/hetzner/setup.sh
3. .env.production ausfüllen
4. docker compose -f docker-compose.prod.yml up -d
5. docker exec ekklesia-ollama ollama pull llama3.2
6. GitHub Secrets: HETZNER_HOST, HETZNER_USER, HETZNER_SSH_KEY
7. SERVER_DUE_DATE in community.html setzen

---

## TODO — V2 (nach Alpha + Hetzner)
1. TrueRepublic Bridge (MOD-08 V2)
2. Rust crypto-rs + WASM
3. ZK Identity
4. MOD-10 V2 Crawl4AI Self-Healing Scraper
5. MOD-17 LimeSurvey Stub aktivieren
6. MOD-18 pol.is Clustering
7. MOD-19 Liquid Democracy (gov.gr + Verwandtschaft 1. Grades)
8. iOS App Store ($99/Jahr Apple Developer)
9. Mirror Server (DigitalOcean)
10. Server Relay für Blockchain-Preis-Berechnung

---

## ABGESCHLOSSEN
- Docker + PostgreSQL + Redis (lokal)
- API 16 Endpoints + Seed (8 Parteien, 15 Thesen, 3 Bills, 120 party_positions)
- Browser Ed25519 crypto.ts — 17 Tests
- Vote Flow Frontend + /verify
- POLIS Worker + OAuth + Repo + Labels
- Repo Security (Branch Protection, Dependabot, CODEOWNERS, SECURITY.md)
- Docker Prod + Traefik + GitHub Actions Deploy
- Hetzner Setup Scripts + DEPLOY.md
- Expo Mobile — 5 Screens + Biometric + Secure Enclave
- Android APK — EAS Build (kaspartisan/ekklesia-gr)
- MOD-08 Arweave L2 — Wallet aktiv, Dry Run
- MOD-10 AI Scraper — Ollama L1 + HuggingFace L2 + Rule-based L3
- MOD-01 HLR Provider — hlrlookups.com + Melrose Labs, Dry Run
- PWA — Service Worker + manifest + iOS installierbar
- Results Dashboard — /results + animierter DivergenceCard
- VAA Verbesserungen — Skip, Party Detail, Share, Top Match
- Landing: iOS PWA + Android APK Buttons
- Community: Arweave + HLR Kacheln aktiviert
- GitHub Pages — alle 15 Seiten live
- 28 Tests grün, Nacht-Durchlauf bestanden

---

## INFRASTRUKTUR KOSTEN
- Server (Hetzner CX21): 7€/Monat = 84€/Jahr
- Domain (ekklesia.gr): 9,30€/Jahr (bezahlt bis 29.03.2028)
- Arweave: ~$0.0001/Upload (community wallet)
- HLR: ~$0.002/Query (community wallet)
- EAS Build: kostenlos (30 builds/Monat)
- Expo: kostenlos
- GitHub: kostenlos
- Cloudflare Worker: kostenlos
- GESAMT: ~93,30€/Jahr + community wallets

---

## GEPLANT — SERVER RELAY (V2)
Server-seitiger Task der:
1. Blockchain Wallets ausliest (Arweave + HLR Crypto Wallet)
2. Aktuellen Kurs abruft (CoinGecko API oder ähnlich)
3. Betrag in EUR berechnet
4. community.html automatisch aktuell hält
→ Community sieht immer Echtzeit-Balance in EUR

---

## OFFENE PUNKTE — UX + DESIGN + CONTENT (alle erledigt)

### PWA iOS Button Fix
- Problem: iOS Button zeigt nur ekklesia.gr Homepage — keine echte PWA Installation
- Fix: Safari-spezifische Anleitung (Safari → Teilen → Zum Homescreen)
- Zusätzlich: Inaktiver "App Store iOS" Button (grau, "Σύντομα")
- Dateien: docs/index.html (Landing Download-Sektion)

### Contact Sektion — Community Driven Link
- Unter Kontaktformular auf Landing: Link "Community Driven — Πώς λειτουργεί;"
- Führt zu: wiki/community-driven.html
- Erklärt: POLIS Ticket System, GitHub Issues Backend, kein Team

### Logo Konsistenz — alle Plattformen
- Überall pnx.png (Eule schwarz/weiss) verwenden
- Android APK: app.json icon prüfen
- PWA manifest.json: icon prüfen
- Next.js: favicon + apple-touch-icon prüfen

### Wiki — Community Driven Seite (neu)
- Neue Seite: wiki/community-driven.html
- Inhalt: Wie funktioniert POLIS ohne Team?
  * GitHub Issues als Backend
  * OAuth via Cloudflare Worker
  * Keine Moderation — Community selbst
  * Wie erstelle ich ein Ticket?
  * Wie vote ich auf Tickets?

---

## OFFENE PUNKTE — CONTENT + DOCS (alle erledigt)

### ~~Security Wiki — Alpha Auth Methode~~ done
### ~~POLIS Ticket System — Landing Page~~ done
### ~~POLIS Ticket System — Wiki Verknüpfung~~ done
- Datei: docs/wiki/community-driven.html
- Direkter Link zum POLIS Ticket Board (tickets/)
- Direkter Link zu GitHub Issues (github.com/NeaBouli/pnyx-community)

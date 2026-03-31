# Ekklesia.gr — Master Memo
# Alle Architektur-Entscheidungen, TODOs, Specs
# Zuletzt aktualisiert: 2026-03-31

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

## TODO — OFFEN

### Nächste Schritte
1. PWA (Next.js) — iOS ohne App Store
2. VAA UI — Wahlkompass Seite
3. Results Dashboard — Divergence Score Visualisierung
4. HLR Provider aktivieren (HLR Lookups API Key)
5. Arweave Wallet erstellen + community.html Kacheln

### Bald
6. Parliament API — echte Gesetze (Hellenic Parliament API)
7. community.html — HLR + Arweave Wallet Balance Kacheln
8. Server Relay für Blockchain-Preis-Berechnung (V2)
9. Hetzner Server aktivieren
10. SERVER_DUE_DATE in community.html setzen

### Later
11. iOS App Store ($99/Jahr Apple Developer)
12. gov.gr OAuth (Alpha — nach 500 Nutzern)
13. TrueRepublic Bridge (V2)
14. Rust crypto-rs + WASM (V2)
15. MOD-17 LimeSurvey Stub
16. ZK Identity (V2)

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
- MOD-08 Arweave L2 — Dry Run aktiv
- GitHub Pages — alle 15 Seiten live

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

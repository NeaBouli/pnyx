# Ekklesia.gr — Öffentliche Roadmap
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09

## Phase Beta (aktuell)
Ziel: Eigenständige, leichtgewichtige Plattform ohne staatliche Abhängigkeit.

- [x] Backend API (FastAPI, PostgreSQL, Redis)
- [x] MOD-01 Identity (SMS HLR, Ed25519, Nullifier)
- [x] MOD-02 VAA (Wahlkompass, Matching)
- [x] MOD-03 Parliament (Bill Lifecycle, 5 States)
- [x] MOD-04 CitizenVote (signierte Abstimmung)
- [x] MOD-05 Divergence Score
- [x] MOD-14 Relevance (Up/Down)
- [x] Next.js Web Frontend (el/en) — 5 Seiten + NavHeader + i18n
- [x] Ed25519 Signing Web + Mobile (@noble/curves)
- [x] Expo Mobile App — 7 Screens, Biometrie, Secure Enclave
- [ ] Docker Production Deployment (Hetzner)
- [ ] Öffentlicher Launch Beta

## Phase Alpha
Voraussetzung: 500+ Nutzer, 3+ NGO-Partner, öffentliche Legitimation.

- [ ] MOD-09 gov.gr OAuth2.0 Integration
- [ ] Demographische Verifikation (Altersgruppe + Region)
- [ ] Sandbox-Anfrage an AADE/gov.gr
- [ ] Externe Sicherheitsaudit

## Phase V2
- [ ] MOD-08 TrueRepublic Bridge (PnyxCoin, Cosmos SDK)
- [ ] MOD-10/11 KI-Scraper + Zusammenfassung (Crawl4AI)
- [ ] MOD-13 Mein Abgeordneter
- [ ] Deliberation (pol.is-Modell)
- [ ] Commit-Reveal Abstimmung
- [ ] packages/crypto-rs (Rust + WASM)

## Transparenz
Monatliche Berichte in docs/reports/
Vollständig Open Source: https://github.com/NeaBouli/pnyx

## MOD-16: Municipal Governance (Beta+)
- Αποφάσεις Περιφερειακών Συμβουλίων
- Αποφάσεις Δημοτικών Συμβουλίων
- Κοινοτικές Αποφάσεις
- Ιεραρχική δομή: Περιφέρεια → Δήμος → Κοινότητα
- Φιλτράρισμα ανά επίπεδο, περιοχή, θέμα
- Divergence Score για κάθε επίπεδο

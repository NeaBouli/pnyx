# Ekklesia.gr — Öffentliche Roadmap
# Copyright (c) 2026 V-Labs Development — MIT License
# Stand: 2026-08-23

## Ekklesia V1 - Phase Beta (aktive Produktionsbasis)
Ziel: Eigenständige, leichtgewichtige Plattform ohne staatliche Abhängigkeit.

- [x] Backend API (FastAPI, PostgreSQL, Redis)
- [x] MOD-01 Beta credential (HLR Greek-number network-status check, Ed25519, Nullifier; not proof of SIM possession or identity)
- [x] MOD-02 VAA (Wahlkompass, Matching)
- [x] MOD-03 Parliament (Bill Lifecycle, 5 States)
- [x] MOD-04 CitizenVote (signierte Abstimmung)
- [x] MOD-05 Divergence Score
- [x] MOD-14 Relevance (Up/Down)
- [x] Next.js Web Frontend (el/en) — 5 Seiten + NavHeader + i18n
- [x] Ed25519 Signing Web + Mobile (@noble/curves)
- [x] Expo Mobile App — 7 Screens, Biometrie, Secure Enclave
- [x] Docker Production Deployment (Hetzner)
- [x] Öffentliche Beta-Verteilung über direkte APK, geschlossenen Google-Play-Test
      und F-Droid
- [ ] Vollständiger öffentlicher Beta-Launch über alle vorgesehenen Release-Kanäle

V1 wird unabhängig von jeder V2-Forschung oder -Implementierung weiter gepflegt.
V2 darf Laufzeit, Datenbank, Deployments, Abstimmung, Identität, Forum, Releases
oder Rollback-Pfade von V1 nicht verändern.

## Ekklesia V1 - Phase Alpha 0.1
Voraussetzung: 500+ Nutzer, 3+ NGO-Partner, offizielle Schnittstelle, Holder-Authentifizierung, DPIA, Credential-Migrationsplan, unabhängiger Security/Privacy-Review und Sandbox-Canary.

- [ ] MOD-09 gov.gr OAuth2.0 Integration
- [ ] [GH#141 privacy-preserving gov.gr document verification](GOVGR_DOCUMENT_VERIFICATION_ALPHA.md) (fresh nonce-bound QR/PDF, holder-authenticated official method, official API or full eSeal validation; all gates above required; Alpha 0.1 only, not live in Beta)
- [ ] Demographische Verifikation (Altersgruppe + Region)
- [ ] Sandbox-Anfrage an AADE/gov.gr
- [ ] Externe Sicherheitsaudit

## Ekklesia V1 - kontrollierte Weiterentwicklung

Dies sind additive Verbesserungen der bestehenden Architektur. Die historische
Bezeichnung "V2" für Semaphore benennt eine Stufe des Abstimmungsprotokolls,
nicht die neue Plattformgeneration.

- [ ] MOD-08 TrueRepublic Bridge (PnyxCoin, Cosmos SDK)
- [ ] MOD-10/11 KI-Scraper + Zusammenfassung (Crawl4AI)
- [ ] MOD-13 Mein Abgeordneter
- [ ] Deliberation (pol.is-Modell)
- [ ] Commit-Reveal Abstimmung
- [x] Semaphore ZK Voting — Android prover, hidden S10 canary, Security Review und erster öffentlicher One-Bill-Scope (`bill:GR-d4c62ed4`) bestanden. Guarded Parliament rollout ist live; ZK-Arweave-Auto-Publikation ist live für eligible öffentliche Parliament scopes ab `group_size >= 5`.
- [ ] packages/crypto-rs (Rust + WASM)

## Ekklesia Platform V2 - paralleler Minima-Zweig

Status: Architektur- und Nachweisplanung der Phase 0. Es ist weder eine
Produktimplementierung noch ein Rollout freigegeben.

- [x] Hybride Machbarkeit und V1-Isolationsplan dokumentiert
- [x] Architektur-Epic und begrenzte Arbeitspakete erstellt: [GH#216](https://github.com/NeaBouli/pnyx/issues/216)
- [ ] Maxima-Verhalten bei Offline-Betrieb, Wiederholung und Reihenfolge sowie Mobile-Node-Budgets messen ([GH#217](https://github.com/NeaBouli/pnyx/issues/217))
- [ ] Synthetische Empfangsbestätigungen, Wiederholungen und Deduplizierung nachweisen ([GH#218](https://github.com/NeaBouli/pnyx/issues/218))
- [ ] Sparsame KISS-Root-Verankerung und unabhängige Verifikation nachweisen ([GH#219](https://github.com/NeaBouli/pnyx/issues/219))
- [ ] Kompatibilität von Identität, Proofs und Schlüsseln entscheiden ([GH#220](https://github.com/NeaBouli/pnyx/issues/220))
- [ ] Bulletin Board, Federation und dauerhafte Verfügbarkeit spezifizieren ([GH#221](https://github.com/NeaBouli/pnyx/issues/221))
- [ ] Separates V2-Repository und CI erst nach Gate G1 erstellen ([GH#222](https://github.com/NeaBouli/pnyx/issues/222))
- [ ] V1-Parität, Migration, Rollback und Rollout-Gates nachweisen ([GH#223](https://github.com/NeaBouli/pnyx/issues/223))

Arbeitsrichtung: Maxima als möglicher Transport, unabhängig verifizierte
Off-Chain-Aggregation und sparsame Minima-Layer-1-Roots. Die Kompatibilität von
Ed25519 und Semaphore wird nicht vorausgesetzt. Omnia, Token/Incentives, ein
Discourse-Ersatz und verpflichtende Full Nodes sind keine Ziele von V2.0.

Details: [Ekklesia Platform V2 on Minima](architecture/EKKLESIA_V2_MINIMA.md)

### Verbindliche Rollout-Gates

1. G0: Architektur, Bedrohungs- und Datenschutzmodell geprüft.
2. G1: Alle synthetischen Maxima- und Minima-Realitäts-PoCs reproduzierbar.
3. G2: Isolierte Implementierungsgrenze und Protokoll-CI geprüft.
4. G3: Unabhängige Security-, Kryptografie- und Datenschutzprüfung bestanden.
5. G4: Vereinbarte V1/V2-Parität sowie Migrations- und Rollback-Übungen bestanden.
6. G5: Ausdrückliche Release-Freigabe des Inhabers. Erst danach darf die
   Rollout-Planung beginnen.

V1 bleibt bis zu einer separaten, reversiblen Stilllegungsentscheidung verfügbar,
selbst wenn V2 später alle Gates besteht.

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

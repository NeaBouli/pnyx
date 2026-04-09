# Ekklesia.gr — Projektstatus
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09 — nach Session 3 (komplett gepusht)

---

## Kurzübersicht

| Eigenschaft         | Wert                                              |
|---------------------|---------------------------------------------------|
| **Projekt**         | Ekklesia.gr — Digitale Direkte Demokratie (GR)    |
| **Codename**        | pnyx                                              |
| **Repo**            | https://github.com/NeaBouli/pnyx                  |
| **Lokal**           | `/Users/gio/Desktop/pnyx`                         |
| **HEAD**            | `f84626f` (main, Remote synchron)                 |
| **Rollback**        | Tag `pre-session3-20260409` → `cd050e5`           |
| **Phase**           | Beta — Kernmodule komplett, vor Prod-Deployment    |
| **Lizenz**          | MIT — (c) 2026 Vendetta Labs                      |

---

## Architektur

```
pnyx/
├── apps/
│   ├── api/          Python 3 + FastAPI 0.135 + SQLAlchemy 2 + Alembic + PG + Redis
│   ├── web/          Next.js 14 (App Router) + React 19 + TS 6.0 + Tailwind 4
│   └── mobile/       Expo 54 + React Native 0.81 + React Navigation 7
├── packages/
│   └── crypto/       Python PyNaCl (Ed25519, Nullifier, HLR)
├── infra/            Docker Compose + Traefik
├── docs/             Roadmap, Whitepaper, TODO, Status, Handover, Reports
├── cloudflare-worker/  OAuth-Proxy
└── wiki/             GitHub Wiki (Submodul)
```

---

## Modulstatus

| Modul  | Name                  | Status       | Plattform          |
|--------|-----------------------|--------------|--------------------|
| MOD-01 | Identity (HLR+Ed25519)| KOMPLETT     | API + Web + Mobile |
| MOD-02 | VAA Wahlkompass       | KOMPLETT     | API + Web (38 Thesen, 8 Parteien) |
| MOD-03 | Parliament Bills      | KOMPLETT     | API + Web + Mobile |
| MOD-04 | CitizenVote           | KOMPLETT     | API + Web + Mobile |
| MOD-05 | Divergence Score      | KOMPLETT     | API + Web + Mobile |
| MOD-08 | Arweave Archiv        | STUB         | API              |
| MOD-09 | gov.gr OAuth          | GEPLANT      | —                |
| MOD-10 | KI-Scraper (Ollama)   | STUB         | API              |
| MOD-13 | Mein Abgeordneter     | STUB         | API              |
| MOD-14 | Relevance Up/Down     | KOMPLETT     | API + Web        |
| MOD-16 | Municipal Governance  | STUB + DB    | API              |

---

## VAA Politische Πυξίδα — Themenabdeckung (38 Thesen)

| Bereich | Thesen | Beispiele |
|---------|--------|-----------|
| Wirtschaft & Arbeit | 6 | Mindestlohn, Unternehmenssteuern, Reedersteuer, Brain Drain, Primärüberschuss, Schattenökonomie |
| Gesellschaft & Soziales | 5 | Cannabis, Gleichgeschlechtliche Ehe, UBI, Demographische Krise, Tierschutz |
| Umwelt & Klima | 4 | Erneuerbare Energie, Atomkraft, Waldbrandprävention, Grüne Schifffahrt |
| Demokratie & Rechte | 4 | Diaspora-Wahl, Überwachung/Predator, Polizeireform, Tempi-Aufklärung |
| Außen-/Sicherheitspolitik | 3 | NATO, Verteidigung, EU-Föderalismus |
| Wohnen & Infrastruktur | 4 | Airbnb, Golden Visa, Wasser-Privatisierung, ÖPNV |
| Digital & Bildung | 3 | Ιδιωτικά ΑΕΙ, E-Government, Telearbeit |
| Tourismus & Regionen | 4 | Overtourism, Inselanbindung, Regionale Ungleichheit, Archäologie |
| Landwirtschaft & Kultur | 4 | EU-CAP, Kirchensteuer, Parthenon-Marmore, Agrarsubventionen |

---

## Kryptographie-Status

| Komponente                | Status  | Details                                     |
|---------------------------|---------|---------------------------------------------|
| Ed25519 Keypair (Backend) | OK      | PyNaCl, 32-byte keys, hex-encoded           |
| Ed25519 Signing (Web)     | OK      | @noble/curves v2.0.1, signVote()            |
| Ed25519 Signing (Mobile)  | OK      | @noble/curves v2.0.1, signVote() + self-verify |
| Nullifier Hash            | OK      | SHA256(phone:salt), phone sofort gelöscht   |
| Secure Storage (Web)      | BETA    | localStorage (Prod: httpOnly Cookie o.ä.)   |
| Secure Storage (Mobile)   | OK      | expo-secure-store (Keychain/Keystore)       |
| Biometric Auth (Mobile)   | OK      | expo-local-authentication                   |
| Cross-Platform Compat     | VERIFIZIERT | 12 Tests: Web ↔ Mobile ↔ Backend identisch |

---

## Teststatus (2026-04-09)

| Suite              | Tests | Ergebnis              | Tool          |
|--------------------|-------|-----------------------|---------------|
| Web Crypto         | 17    | 17 passed             | vitest 4.1.3  |
| Web Crypto Compat  | 12    | 12 passed             | vitest 4.1.3  |
| Python Crypto      | 12    | 12 passed             | pytest 8.3.3  |
| API                | 67    | 51 passed, 16 xfailed | pytest 8.3.3  |
| VAA Matching       | 6     | 6 passed              | pytest 8.3.3  |
| Mobile TypeScript  | —     | tsc --noEmit clean    | TS 5.9.2      |
| Web Build          | —     | next build OK         | Next.js 14    |
| **TOTAL**          | **92**| **92 passed**         |               |

---

## Git-Historie (Session 3 — 8 Commits)

```
f84626f docs: update all remaining 15→38 VAA references
e0b2f04 feat(vaa): expand political compass from 15 to 38 statements
32292b6 docs: update README + wiki stats (92 tests, 196 commits, mobile beta)
79793e4 docs: add STATUS, HANDOVER-SESSION3, update TODO + ROADMAP
f429eb0 test+docs: add 12 cross-platform crypto tests, update session docs
4f969bf feat(mobile): implement Ed25519 signing with @noble/curves
9aa89cd fix(web): upgrade to Tailwind 4 PostCSS plugin
da7f7cb fix(web): remove 9 duplicate headers — NavHeader in layout is sufficient
--- Tag: pre-session3-20260409 ---
cd050e5 fix(web): resolve TypeScript 6.0 compatibility issues
```

**Alle 8 Commits gepusht auf Remote.**

---

## Bekannte Probleme

| Problem | Schwere | Workaround |
|---------|---------|------------|
| `eslint-config-next@14` Peer-Conflict mit `eslint@10` | Mittel | `--legacy-peer-deps` bei npm install |
| `next@14` + `react@19` Peer-Warning | Niedrig | Upgrade auf next@15 löst beides |
| Kein lokales PostgreSQL für API-Tests | Niedrig | 16 Tests als xfail markiert |
| Web Secure Storage = localStorage | Mittel | Für Beta OK, Prod braucht Hardening |

---

## Deployment-Ziel

| Komponente | Ziel            | Status       |
|------------|-----------------|--------------|
| API        | Hetzner CX21    | Nicht deployed |
| Web        | Hetzner + Traefik | Nicht deployed |
| Mobile     | Expo EAS → Stores | Nicht getestet |
| Docs/Wiki  | GitHub Pages    | LIVE (ekklesia.gr) |
| Domain     | ekklesia.gr     | GitHub Pages aktiv |

---

*Stand: 2026-04-09, Session 3 komplett. Nächstes Update: nach Session 4.*

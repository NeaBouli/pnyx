# pnyx / Ekklesia.gr

> **εκκλησία** — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας για τον Έλληνα Πολίτη
> Digital Direct Democracy Platform for Greek Citizens

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/NeaBouli/pnyx/actions/workflows/ci.yml/badge.svg)](https://github.com/NeaBouli/pnyx/actions)

**Open Source · Anonymous · Privacy-First · Lightweight**

Copyright (c) 2026 [Vendetta Labs](https://github.com/NeaBouli)

---

## Αρχιτεκτονική / Architecture
pnyx/
├── apps/
│   ├── api/        → Python FastAPI (MOD-01 bis MOD-12)
│   ├── web/        → Next.js 14 (el/en, SSR)
│   └── mobile/     → Expo / React Native
├── packages/
│   ├── crypto/     → Ed25519, Nullifier, HLR
│   ├── db/         → Alembic Migrations
│   ├── i18n/       → el / en
│   └── types/      → Shared Types
└── infra/
└── docker/     → Docker Compose

## Ενεργά Modules / Active Modules (Beta)

| Module | Περιγραφή | Status |
|--------|-----------|--------|
| MOD-01 Identity | SMS HLR, Ed25519, Nullifier, Revokation | ✅ |
| MOD-02 VAA | Thesis Matching, 8 Parteien, 15 Thesen | ✅ |
| MOD-03 Parliament | Βουλή API, Bill Lifecycle (5 States) | ✅ |
| MOD-04 CitizenVote | Signierte Abstimmung, Stimmänderung | ✅ |
| MOD-05 Analytics | Divergence Score, k-Anonymität | ✅ |
| MOD-14 Relevance | Up/Down Relevanz-Signal | ✅ |
| MOD-08 TrueRepublic | Bridge Stub (ENV-aktivierbar) | 🔜 V2 |
| MOD-09 Demographics | gov.gr OAuth2.0 | 🔜 Alpha |

## API Endpoints
POST /api/v1/identity/verify     # SMS → Ed25519 Keypair
POST /api/v1/identity/revoke     # Key Revokation
POST /api/v1/identity/status     # Status prüfen
GET  /api/v1/vaa/statements      # 15 Thesen
GET  /api/v1/vaa/parties         # 8 Parteien
POST /api/v1/vaa/match           # Matching-Algorithmus
GET  /api/v1/bills               # Gesetzentwürfe
GET  /api/v1/bills/trending      # Nach Relevanz
GET  /api/v1/bills/{id}          # Detail + KI-Zusammenfassung
POST /api/v1/bills/{id}/transition # Lifecycle
POST /api/v1/vote                # Stimme abgeben (Ed25519)
GET  /api/v1/vote/{id}/results   # Ergebnisse + Divergence Score
POST /api/v1/vote/{id}/relevance # Up/Down Signal

## Datenschutz / Privacy

- Keine Telefonnummer wird gespeichert
- Private Key lebt nur im Gerät (Secure Enclave)
- Nur SHA256-Hashes + öffentliche Schlüssel auf dem Server
- Kein Personenbezug möglich

## Entwicklung / Development
```bash
# Lokale Umgebung starten
cd infra/docker
docker compose up -d

# API Tests
cd apps/api
python -m pytest tests/ -v

# Crypto Tests
cd packages/crypto
python -m pytest tests/ -v
```

## Lizenz / License

MIT © 2026 [Vendetta Labs](https://github.com/NeaBouli)

Dieses Projekt ist Open Source. Beiträge willkommen.
This project is open source. Contributions welcome.

## Roadmap

Siehe [docs/ROADMAP.md](docs/ROADMAP.md) | See [docs/TODO.md](docs/TODO.md)

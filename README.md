<!-- @ai-anchor README_ROOT -->
<!-- @update-hint Main repo file. Logo path: apps/web/public/pnx.png -->

<div align="center">

<img src="apps/web/public/pnx.png" alt="ekklesia logo" width="120" />

# ekklesia tou ethnous · Ekklesia.gr

### Digital Direct Democracy Platform for Greek Citizens

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/NeaBouli/pnyx/actions/workflows/ci.yml/badge.svg)](https://github.com/NeaBouli/pnyx/actions)
[![Modules](https://img.shields.io/badge/Modules-22-green)](https://ekklesia.gr/wiki/modules.html)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red)](https://github.com/NeaBouli/pnyx)

**© 2026 V-Labs Development �� MIT License**

[Website](https://ekklesia.gr) · [Wiki](https://ekklesia.gr/wiki/) · [API](https://api.ekklesia.gr/health) · [Download APK](https://ekklesia.gr/download/)

</div>

---

## What is Ekklesia?

The **ekklesia** was the popular assembly of ancient Athens — where every citizen had a voice. **Ekklesia.gr** is its digital revival: an independent, open-source platform where Greek citizens can vote on real parliamentary bills and municipal decisions.

- **Citizen Voting** — Vote on real bills from the Hellenic Parliament
- **Divergence Score** — See how Parliament votes vs. citizens
- **Party Comparison** — Which party votes like the people?
- **Municipal Governance** — Diavgeia decisions per region and municipality
- **AI Assistant** — Ollama-powered bill summaries and citizen Q&A
- **Full Anonymity** — Ed25519 signatures, nullifier hashes, zero personal data

> This platform is not affiliated with any government entity. All votes are informational only and carry no legal binding force.

## Data Sources

This project uses publicly available government data from:
- [Hellenic Parliament](https://www.hellenicparliament.gr/) — Bills, voting records
- [Diavgeia](https://diavgeia.gov.gr/) — Municipal and regional decisions (OpenData API)
- [data.gov.gr](https://data.gov.gr/) — Public datasets

---

## Features

| Feature | Description | Status |
|---|---|---|
| Citizen Voting | Ed25519 signed votes on real parliamentary bills | Beta |
| Divergence Score | Automatic comparison Parliament vs Citizens | Beta |
| Party Ranking | Which party agrees most with citizens | Beta |
| Municipal Governance | 13 regions, 325 municipalities, Diavgeia integration | Beta |
| AI Bill Summaries | Ollama (EN) + DeepL (EN→EL), cached in Redis | Beta |
| RAG Agent | Citizen Q&A: Ollama + DeepL translation | Beta |
| Auto-Healing Scraper | Ollama repairs broken CSS selectors | Beta |
| Newsletter | Listmonk + Brevo SMTP, 6 subscriber lists | Beta |
| Push Notifications | Expo Push API, APScheduler | Beta |
| Stripe Donations | Community-funded, auto-allocation | Beta |
| Mobile App | Expo React Native, Ed25519, Compass | Beta |
| Arweave Archive | Immutable vote audit trail | Beta |
| TrueRepublic Bridge | Cosmos SDK, PnyxCoin on-chain votes | Planned (V2) |

---

## Architecture

```
pnyx/
├���─ apps/
│   ├── api/          → Python FastAPI  (70+ endpoints, 22 modules)
│   ├��─ web/          → Next.js 14      (el/en, Tailwind, light theme)
│   └── mobile/       → Expo RN         (Android APK + Play Store)
├── packages/
│   ├── crypto/       → Ed25519 · Nullifier · HMAC Chain (47 tests)
│   └── db/           → Alembic Migrations (15+ tables)
��── infra/
│   └── docker/       → PostgreSQL · Redis · Ollama · Traefik
└── docs/             → Landing page + Wiki + Community
```

### Server Infrastructure (Hetzner CX33)
- **9 containers**: API, Web, DB, Redis, Ollama, Traefik, Listmonk (x3)
- **Ollama llama3.2:3b**: 2.6 GB RAM, 5 GB limit
- **Rate limiting**: 60 req/min/IP global, 5 req/min/IP for AI endpoints
- **Circuit breaker**: 3 errors → 24h pause, auto-reset
- **Auto-deploy**: GitHub Actions CI/CD

### Bill Lifecycle
```
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END
```

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.12+
- Node.js 20+

### Installation
```bash
# 1. Clone
git clone https://github.com/NeaBouli/pnyx && cd pnyx

# 2. Start services
cd infra/docker && docker compose up -d

# 3. Database
cd ../../apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head && python seeds/seed_real_bills.py

# 4. API
uvicorn main:app --reload

# 5. Web
cd ../web && npm ci && npm run dev
```

### Tests
```bash
# API Tests (106 passed)
cd apps/api && python -m pytest tests/ -v

# Crypto Tests (47 passed — nullifier + polis)
cd packages/crypto && npx vitest run

# Web Build
cd apps/web && npm run build
```

---

## Security & Privacy

| Data | Stored? |
|---|---|
| Mobile number | Deleted immediately after verification |
| Private key | Device only — never leaves your phone |
| Personal data | Never collected |
| Nullifier hash | SHA256 + Argon2id (non-reversible) |
| Public key | Ed25519 hex (anonymous) |
| Votes | Anonymized, Arweave-archived |

→ Details: [Security Wiki](https://ekklesia.gr/wiki/security.html)

---

## Status

| Metric | Value |
|---|---|
| Modules | 22 (MOD-01 through MOD-22) |
| API Endpoints | 70+ |
| DB Tables | 15+ (Alembic managed) |
| Containers | 9 (including Ollama) |
| CI | Green |
| Security Score | ~90/100 |

---

## Distribution

| Channel | Status | Link |
|---|---|---|
| Direct APK | Live | [ekklesia.gr/download](https://ekklesia.gr/download/) |
| GitHub Release | v1.0.0 | [Releases](https://github.com/NeaBouli/pnyx/releases) |
| Google Play | Closed Testing | [Play Store](https://play.google.com/store/apps/details?id=ekklesia.gr) |
| F-Droid | Pending Review | [MR #37087](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/37087) |

---

## Roadmap

| Phase | Trigger | Status |
|---|---|---|
| **Beta** | Now | Active |
| **Alpha** | 500 users + 3 NGOs + gov.gr OAuth | Upcoming |
| **V2** | TrueRepublic Bridge + PnyxCoin | Planned |

→ Details: [Roadmap](https://ekklesia.gr/wiki/roadmap.html)

---

## Documentation

| Document | Description |
|---|---|
| [Wiki](https://ekklesia.gr/wiki/) | Full technical documentation (12 pages) |
| [API Docs](https://ekklesia.gr/wiki/api.html) | 70+ endpoints, all modules |
| [Modules](https://ekklesia.gr/wiki/modules.html) | MOD-01 through MOD-22 |
| [Security](https://ekklesia.gr/wiki/security.html) | Ed25519, Nullifier, threat model |
| [Architecture](https://ekklesia.gr/wiki/architecture.html) | Stack, monorepo, lifecycle |
| [FAQ](https://ekklesia.gr/wiki/faq.html) | Frequently asked questions |

---

## Contributing

```bash
# Fork → Branch → PR
git checkout -b feat/your-feature
```

**Commit format:** `feat(module): description` | `fix(module): description`

→ Details: [Contributing Guide](https://ekklesia.gr/wiki/contributing.html)

---

## License

MIT License — Copyright (c) 2026 V-Labs Development

Free to use, modify and distribute.

---

<div align="center">

**Democracy is not a spectacle. It is action.**

[Star on GitHub](https://github.com/NeaBouli/pnyx) · [Report Issues](https://github.com/NeaBouli/pnyx/issues) · [Wiki](https://ekklesia.gr/wiki/)

</div>

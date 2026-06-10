<!-- @ai-anchor README_ROOT -->
<!-- @update-hint Main repo file. Logo path: apps/web/public/pnx.png -->

<div align="center">

<img src="apps/web/public/pnx.png" alt="ekklesia logo" width="120" />

# ekklesia tou ethnous &middot; Ekklesia.gr

### Digital Direct Democracy Platform for Greek Citizens

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/NeaBouli/pnyx/actions/workflows/ci.yml/badge.svg)](https://github.com/NeaBouli/pnyx/actions)
[![Modules](https://img.shields.io/badge/Modules-25-green)](https://ekklesia.gr/wiki/modules.html)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red)](https://github.com/NeaBouli/pnyx)

**&copy; 2026 V-Labs Development &mdash; MIT License**

[Website](https://ekklesia.gr) &middot; [Wiki](https://ekklesia.gr/wiki/) &middot; [API](https://api.ekklesia.gr/health) &middot; [Forum](https://pnyx.ekklesia.gr)

</div>

---

## What is Ekklesia?

The **ekklesia** was the popular assembly of ancient Athens &mdash; where every citizen had a voice. **Ekklesia.gr** is its digital revival: an independent, open-source platform where Greek citizens can vote on real parliamentary bills and municipal decisions.

- **Citizen Voting** &mdash; Vote on real bills from the Hellenic Parliament
- **Divergence Score** &mdash; See how Parliament votes vs. citizens
- **Party Comparison** &mdash; Which party votes like the people?
- **Municipal Governance** &mdash; Diavgeia decisions per region and municipality
- **Politician Evaluation** &mdash; Rate elected officials on transparency and performance
- **AI Assistant** &mdash; Ollama-powered citizen Q&A; reviewed summaries and official source text for bills
- **Privacy by Design** &mdash; Ed25519 signatures, nullifier hashes, no phone-number storage

> This platform is not affiliated with any government entity. All votes are informational only and carry no legal binding force.

## Data Sources

This project uses publicly available government data from:
- [Hellenic Parliament](https://www.hellenicparliament.gr/) &mdash; Bills, voting records
- [Diavgeia](https://diavgeia.gov.gr/) &mdash; Municipal and regional decisions (OpenData API)
- [data.gov.gr](https://data.gov.gr/) &mdash; Public datasets

---

## Features

| Feature | Description | Status |
|---|---|---|
| Citizen Voting | Ed25519 signed votes on real parliamentary bills | Beta |
| Divergence Score | Automatic comparison Parliament vs Citizens | Beta |
| Party Ranking | Which party agrees most with citizens | Beta |
| Municipal Governance | 13 regions, 325 municipalities, Diavgeia integration | Beta |
| Politician Evaluation | Citizen ratings for elected officials | Beta |
| Bill Text + Summaries | Official full text/PDF links plus reviewed short summaries | Beta |
| RAG Agent | Citizen Q&A: Ollama + DeepL translation | Beta |
| Auto-Healing Scraper | Ollama repairs broken CSS selectors | Beta |
| Newsletter + Telegram | Brevo SMTP + Telegram cross-publish | Beta |
| Push Notifications | Expo Push API, APScheduler | Beta |
| Stripe Donations | Community-funded, auto-allocation | Beta |
| Mobile App | Expo React Native, HLR SIM check, Ed25519, Compass | Beta |
| Representative App | Role-based bill visibility for elected officials | Beta |
| Discourse Forum | Automated topic sync per bill | Beta |
| Arweave Archive | Immutable vote audit trail | Beta |
| POLIS Tickets | Citizen issue tracker with Ed25519 auth | Beta |
| Dashboard | Admin panel with GitHub OAuth, 15+ pages | Beta |
| ZK Voting V2 | Optional Semaphore-based anonymous proofs | Android prover verified; production integration gated |

---

## Architecture

```
pnyx/
+-- apps/
|   +-- api/          -> Python FastAPI  (70+ endpoints, 25 modules)
|   +-- web/          -> Next.js 16      (el/en, Tailwind, light theme)
|   +-- mobile/       -> Expo RN         (Android APK + Play Store)
|   +-- dashboard/    -> Next.js 16      (Admin panel, GitHub OAuth)
|   +-- monitor/      -> Python          (3-tier auto-recovery)
|   +-- representative/ -> Web app       (Role-based bill visibility)
+-- packages/
|   +-- crypto/       -> Ed25519, Nullifier, HMAC Chain (47 tests)
|   +-- db/           -> Alembic Migrations (18+ tables)
+-- infra/
|   +-- docker/       -> PostgreSQL, Redis, Ollama, Traefik
+-- docs/             -> Landing page + Wiki (14 pages) + Community
```

### Server Infrastructure (Hetzner CX43)
- **11 containers**: API, Web, Dashboard, Monitor, DB, Redis, Ollama, Docker-Proxy, VR, Test-Node, ekprosopos
- **Ollama llama3.2:3b**: 2.6 GB RAM, 5 GB limit
- **Rate limiting**: 60 req/min/IP global, 5 req/min/IP for AI endpoints
- **Circuit breaker**: 3 errors &rarr; 24h pause, auto-reset
- **Discourse**: pnyx.ekklesia.gr &mdash; automated forum sync per bill

### Bill Lifecycle
```
ANNOUNCED -> ACTIVE -> WINDOW_24H -> PARLIAMENT_VOTED -> OPEN_END
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
# API Tests
cd apps/api && python -m pytest tests/ -v

# Crypto Tests (47 passed)
cd packages/crypto && npx vitest run

# Web Build
cd apps/web && npm run build
```

---

## Security & Privacy

| Data | Stored? |
|---|---|
| Mobile number | Used for HLR active-SIM verification, deleted immediately after verification |
| Private key | Device only &mdash; never leaves your phone |
| IP address | Limited to rate limiting / security; not linked to votes or identity |
| Nullifier hash | Server-salted SHA256 for Beta identity uniqueness; phone not stored; Argon2id v2 scaffold prepared but disabled |
| Public key | Ed25519 hex (anonymous) |
| Votes | Anonymized, Arweave-archived |

> Identity revocation is self-service only. The system does not store phone numbers after registration. Current Beta nullifiers depend on `SERVER_SALT` secrecy; a versioned Argon2id migration is tracked separately.

&rarr; Details: [Security Wiki](https://ekklesia.gr/wiki/security.html)

---

## Status

| Metric | Value |
|---|---|
| Modules | 25 (MOD-01 through MOD-25) |
| API Endpoints | 70+ |
| DB Tables | 18+ (Alembic managed) |
| Containers | 11 |
| CI | Green (Python API Tests + Crypto Package Tests) |
| JSON-LD | 17 pages with structured data |

---

## Distribution

| Channel | Status | Link |
|---|---|---|
| Direct APK | Live | [ekklesia.gr](https://ekklesia.gr) |
| Google Play | Review pending | Internal testing |
| F-Droid | MR pending review | [MR !38007](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007) |

---

## Roadmap

| Phase | Trigger | Status |
|---|---|---|
| **Beta** | Now | Active |
| **Alpha** | 500 users + 3 NGOs + gov.gr OAuth | Upcoming |
| **V2** | ZK Voting (Semaphore) + Federation | Android prover verified; production integration gated |

&rarr; Details: [Roadmap](https://ekklesia.gr/wiki/roadmap.html)

---

## Documentation

| Document | Description |
|---|---|
| [Wiki](https://ekklesia.gr/wiki/) | Full technical documentation (14 pages) |
| [API Docs](https://ekklesia.gr/wiki/api.html) | 70+ endpoints, all modules |
| [Modules](https://ekklesia.gr/wiki/modules.html) | MOD-01 through MOD-25 |
| [Security](https://ekklesia.gr/wiki/security.html) | Ed25519, Nullifier, threat model |
| [Architecture](https://ekklesia.gr/wiki/architecture.html) | Stack, monorepo, lifecycle |
| [FAQ](https://ekklesia.gr/wiki/faq.html) | Frequently asked questions |
| [llms.txt](https://ekklesia.gr/llms.txt) | Machine-readable project overview for AI crawlers |

---

## SEO & AI Indexing

- **robots.txt**: AI crawlers allowed (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)
- **llms.txt**: Machine-readable project description (71 lines)
- **JSON-LD**: Structured data on 17 pages (TechArticle, WebPage, FAQPage, WebApplication)
- **Sitemap**: 21 indexed URLs
- **Hreflang**: el/en on 17 pages

---

## Contributing

```bash
# Fork -> Branch -> PR
git checkout -b feat/your-feature
```

**Commit format:** `feat(module): description` | `fix(module): description`

&rarr; Details: [Contributing Guide](https://ekklesia.gr/wiki/contributing.html)

---

## License

MIT License &mdash; Copyright (c) 2026 V-Labs Development

Free to use, modify and distribute.

---

<div align="center">

**Democracy is not a spectacle. It is action.**

[Star on GitHub](https://github.com/NeaBouli/pnyx) &middot; [Report Issues](https://github.com/NeaBouli/pnyx/issues) &middot; [Wiki](https://ekklesia.gr/wiki/)

</div>

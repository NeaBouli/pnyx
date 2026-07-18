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
- **Municipal Governance** &mdash; Diavgeia decisions and aggregate consensus results by municipality, region, and nationwide
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
| Bill Text + Summaries | Official full text/PDF links plus short summaries or safe metadata context; reviewed/manual text is pinned | Beta |
| RAG Agent | Citizen Q&A: Ollama + DeepL translation | Beta |
| Auto-Healing Scraper | Ollama repairs broken CSS selectors | Beta |
| Newsletter + Telegram | Brevo SMTP + Telegram cross-publish | Beta |
| Push Notifications | Expo Push API, APScheduler | Beta |
| Stripe / PayPal Donations | Voluntary support; runtime intake and public links fail-closed | Paused pending legal/provider E2E |
| Mobile App | Expo React Native, HLR Greek-number network-status check, Ed25519, Compass | Beta |
| Representative App | Role-based bill visibility for elected officials | Beta |
| Discourse Forum | Automated topic sync per bill; moderator-edited first posts are checksum-protected from automation | Beta |
| Arweave Archive | Immutable vote audit trail | Beta |
| POLIS Tickets | Citizen issue tracker with Ed25519 auth | Beta |
| Dashboard | Admin panel with GitHub OAuth, 15+ pages | Beta |
| ZK Voting V2 | Optional Semaphore-based anonymous proofs | Guarded Parliament rollout live; ZK Arweave auto-publication live for eligible public Parliament scopes (min group size 5) |

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
| Mobile number | Used only for an HLR Greek-number network-status check; this does not prove SIM possession or identity. Deleted immediately after verification |
| Private key | Device only &mdash; never leaves your phone |
| IP address | Limited to rate limiting / security; not linked to votes or identity |
| Identity nullifiers | Argon2id v2 identity hash for new/reverified identities plus a legacy SHA256 compatibility anchor; phone not stored |
| Public key | Ed25519 hex (anonymous) |
| Votes | Anonymized, Arweave-archived |

> Identity revocation is self-service. The system does not store phone numbers after registration. Production identity KDF v2 is active: new and reverified identities receive a memory-hard Argon2id hash, while the existing SHA256 value remains as a compatibility anchor for established vote interfaces and migration lookup.

### Generated-content safety

New system-generated bill pills, short summaries, and forum first-post bodies carry a SHA-256 ownership digest. Automation may refresh them only while the live value still matches that digest. An admin review/edit or a Discourse moderator edit revokes automatic ownership, so manual content is preserved. Existing Beta content was not retroactively claimed; official long text and PDF links are outside this update path.

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
| Direct APK | v1.0.28 / vC57 live | [ekklesia.gr](https://ekklesia.gr/download/ekklesia-latest.apk) |
| Google Play | v1.0.28 / vC57 submitted for Closed Testing review | Closed Testing |
| GitHub Release | v1.0.28 / vC57 latest | [v1.0.28](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.28) |
| F-Droid | MR pending review | [MR !38007](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007) |

---

## Roadmap

| Phase | Trigger | Status |
|---|---|---|
| **Beta** | Now | Active |
| **Alpha 0.1** | 500 users + 3 NGOs + all official verification gates | Upcoming: holder-authenticated OAuth or fresh challenge-bound QR/eSeal verification is designed in [GH#141](https://github.com/NeaBouli/pnyx/issues/141). It requires an official integration, DPIA, credential-migration design, independent security/privacy review and a sandbox canary; it is not live in Beta |
| **V2** | ZK Voting (Semaphore) + Federation | Guarded Parliament rollout live; ZK Arweave auto-publication live for eligible public Parliament scopes (min group size 5) |

&rarr; Details: [Roadmap](https://ekklesia.gr/wiki/roadmap.html)

The future gov.gr verification path is documented as an Alpha-only security
design in [Gov.gr Document Verification](docs/GOVGR_DOCUMENT_VERIFICATION_ALPHA.md).
It is not active in Beta, and a document QR alone is never treated as proof of
the holder's identity. The public gov.gr validity check confirms a document,
not the identity or eligibility of the person presenting it.

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

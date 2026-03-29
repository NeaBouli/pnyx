<!-- @ai-anchor README_ROOT -->
<!-- @update-hint Main repo file. Logo path: apps/web/public/pnx.png -->
<!-- @seo Ekklesia.gr — Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας Ελλάδα -->

<div align="center">

<img src="apps/web/public/pnx.png" alt="εκκλησία logo" width="120" />

# εκκλησία · Ekklesia.gr

### Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας για τον Έλληνα Πολίτη
### Digital Direct Democracy Platform for Greek Citizens

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/NeaBouli/pnyx/actions/workflows/ci.yml/badge.svg)](https://github.com/NeaBouli/pnyx/actions)
[![Wiki](https://img.shields.io/badge/Wiki-9%20pages-green)](https://github.com/NeaBouli/pnyx/wiki)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red)](https://github.com/NeaBouli/pnyx)

**© 2026 Vendetta Labs — MIT License**

[🌐 Ekklesia.gr](https://ekklesia.gr) · [📖 Wiki](https://github.com/NeaBouli/pnyx/wiki) · [⚡ API Docs](http://localhost:8000/docs) · [📄 Whitepaper](docs/WHITEPAPER.md)

</div>

---

## 🏛️ Τι είναι η Ekklesia; / What is Ekklesia?

Η **εκκλησία** ήταν η λαϊκή συνέλευση της αρχαίας Αθήνας — εκεί όπου κάθε
πολίτης είχε φωνή. Η **Ekklesia.gr** είναι η ψηφιακή αναβίωσή της.

> The **ekklesia** was the popular assembly of ancient Athens — where every
> citizen had a voice. **Ekklesia.gr** is its digital revival.

- 🗳️ **Πολιτική Πυξίδα** — Συγκρίνετε θέσεις με 8 κόμματα / Compare positions with 8 parties
- 🏛️ **Ψηφοφορία Πολιτών** — Ψηφίστε για πραγματικά νομοσχέδια / Vote on real parliamentary bills
- 📊 **Δείκτης Απόκλισης** — Βουλή vs Πολίτες / Parliament vs Citizens
- 🔐 **Πλήρης Ανωνυμία** — Ed25519 · Nullifier Hash · Μηδενικά προσωπικά δεδομένα

---

## ✨ Χαρακτηριστικά / Features

| Χαρακτηριστικό | Περιγραφή | Κατάσταση |
|---|---|---|
| 🗳️ Πολιτική Πυξίδα | 15 θέσεις, 8 κόμματα, Matching Algorithm | ✅ Beta |
| 🏛️ Ψηφοφορία Πολιτών | Ed25519 signed, Bill Lifecycle (5 states) | ✅ Beta |
| 📊 Δείκτης Απόκλισης | Αυτόματη σύγκριση Βουλή vs Πολίτες | ✅ Beta |
| 🔐 ZK Identity | SMS HLR → Nullifier → Key → Delete | ✅ Beta |
| 📱 Mobile App | Expo React Native, Secure Enclave | 🔜 V2 |
| ⛓️ TrueRepublic | Cosmos SDK Bridge, PnyxCoin | 🔜 V2 |
| 🤖 AI Summarizer | Claude API, 3-level summaries | 🔜 V2 |
| 🦀 Rust Crypto | WASM, ed25519-dalek, browser-native | 🔜 V2 |

---

## 🏗️ Αρχιτεκτονική / Architecture
```
pnyx/
├── apps/
│   ├── api/          → Python FastAPI  (13 endpoints)
│   ├── web/          → Next.js 14      (5 pages, el/en)
│   └── mobile/       → Expo RN         (TODO)
├── packages/
│   ├── crypto/       → Ed25519 · Nullifier · HLR
│   └── db/           → Alembic Migrations
├── infra/
│   └── docker/       → PostgreSQL · Redis · API
├── wiki/             → 9 Wiki pages (backup)
└── docs/
    ├── CLAUDE.md     → AI Context Anchor
    ├── WHITEPAPER.md → Technical Whitepaper
    ├── TODO.md       → Session tracking
    └── reports/      → Build reports
```

### Bill Lifecycle
```
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END
```

---

## 🚀 Εκκίνηση / Quick Start

### Προαπαιτούμενα / Prerequisites
- Docker + Docker Compose
- Python 3.12+
- Node.js 20+

### Εγκατάσταση / Installation
```bash
# 1. Clone
git clone https://github.com/NeaBouli/pnyx
cd pnyx

# 2. Εκκίνηση υπηρεσιών / Start services
cd infra/docker && docker compose up -d

# 3. Βάση δεδομένων / Database
cd ../../apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python seeds/seed.py

# 4. API (http://localhost:8000/docs)
uvicorn main:app --reload

# 5. Web (http://localhost:3000)
cd ../web && npm install && npm run dev
```

### Tests
```bash
# API Tests (40 + 4 xfail)
cd apps/api && pytest tests/ -v

# Crypto Tests (12)
cd packages/crypto && pytest tests/ -v

# Web Build
cd apps/web && npm run build
```

---

## 🔐 Ασφάλεια & Ιδιωτικότητα / Security & Privacy

| Δεδομένο | Αποθηκεύεται; |
|---|---|
| Αριθμός κινητού | ❌ Διαγράφεται αμέσως |
| Ιδιωτικό κλειδί | ❌ Μόνο στη συσκευή |
| Προσωπικά δεδομένα | ❌ Ποτέ |
| Nullifier Hash | ✅ SHA256 (non-reversible) |
| Public Key | ✅ Ed25519 Hex |
| Ψήφοι | ✅ Anonymized |

→ Λεπτομέρειες: [Security Wiki](https://github.com/NeaBouli/pnyx/wiki/Security)

---

## 📊 Κατάσταση / Status

| Μετρική | Τιμή |
|---|---|
| Commits | 19+ |
| API Endpoints | 13 |
| DB Tables | 9 |
| Tests | 44 (40 + 4 xfail + 12 crypto) |
| Web Pages | 5 |
| Wiki Pages | 9 |
| CI Status | ✅ Green |

---

## 🗺️ Χάρτης Πορείας / Roadmap

| Φάση | Trigger | Κατάσταση |
|---|---|---|
| **Beta** | Τώρα | 🟢 Ενεργή |
| **Alpha** | 500 χρήστες + 3 NGOs | ⏳ Επερχόμενη |
| **V2** | Αποδεδειγμένη σταθερότητα | 📋 Σχεδιασμένη |

→ Λεπτομέρειες: [Roadmap Wiki](https://github.com/NeaBouli/pnyx/wiki/Roadmap)

---

## 📚 Τεκμηρίωση / Documentation

| Έγγραφο | Περιγραφή |
|---|---|
| [📖 Wiki](https://github.com/NeaBouli/pnyx/wiki) | Πλήρης τεκμηρίωση |
| [📄 Whitepaper](docs/WHITEPAPER.md) | Τεχνικό λευκό βιβλίο |
| [🗺️ Roadmap](docs/ROADMAP.md) | Χάρτης πορείας |
| [✅ TODO](docs/TODO.md) | Τρέχουσες εργασίες |
| [🔐 Security](https://github.com/NeaBouli/pnyx/wiki/Security) | Μοντέλο ασφαλείας |
| [🏗️ Architecture](https://github.com/NeaBouli/pnyx/wiki/Architecture) | Αρχιτεκτονική |

---

## 🤝 Συνεισφορά / Contributing
```bash
# Fork → Branch → PR
git checkout -b feat/your-feature
# Δείτε: https://github.com/NeaBouli/pnyx/wiki/Contributing
```

**Commit format:** `feat(module): description` | `fix(module): description`

---

## ⚖️ Άδεια / License
MIT License — Copyright (c) 2026 Vendetta Labs

Ελεύθερη χρήση, τροποποίηση και διανομή.
Free to use, modify and distribute.

---

<div align="center">

**Η δημοκρατία δεν είναι θέαμα. Είναι πράξη.**
*Democracy is not a spectacle. It is action.*

[⭐ Star on GitHub](https://github.com/NeaBouli/pnyx) · [🐛 Issues](https://github.com/NeaBouli/pnyx/issues) · [📖 Wiki](https://github.com/NeaBouli/pnyx/wiki)

</div>

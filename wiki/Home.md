<!--
@wiki-page HOME
@update-hint Wiki start page. Links to all sub-pages.
@ai-anchor WIKI_HOME
-->

# εκκλησία / Ekklesia.gr — Wiki

> **Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας για τον Έλληνα Πολίτη**
> Digital Direct Democracy Platform for Greek Citizens

**MIT License © 2026 Vendetta Labs** | [GitHub](https://github.com/NeaBouli/pnyx)

---

## 📚 Περιεχόμενα / Contents

| Σελίδα / Page | Περιγραφή / Description |
|---|---|
| [Architecture](Architecture) | Αρχιτεκτονική συστήματος / System architecture |
| [Security](Security) | Ασφάλεια & ιδιωτικότητα / Security & privacy model |
| [Modules](Modules) | Περιγραφή MOD-01 έως MOD-15 |
| [API](API) | REST API τεκμηρίωση / documentation |
| [Database](Database) | Σχήμα βάσης δεδομένων / DB schema |
| [Contributing](Contributing) | Οδηγός συμμετοχής / Contribution guide |
| [Roadmap](Roadmap) | Χάρτης πορείας / Development roadmap |
| [Privacy](Privacy) | Πολιτική απορρήτου / Privacy policy |

---

## 🚀 Γρήγορη Εκκίνηση / Quick Start
```bash
git clone https://github.com/NeaBouli/pnyx
cd pnyx
cd infra/docker && docker compose up -d
cd apps/api && alembic upgrade head && python seeds/seed.py
# API: http://localhost:8000/docs
# Web: http://localhost:3000
```

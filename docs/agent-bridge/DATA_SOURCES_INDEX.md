# Datenquellen-Index fuer Audit
## Stand: 2026-05-01 | Erstellt von Claude Code

Dieses Dokument listet ALLE Orte an denen Projektdaten zu finden sind.
Fuer Audit-Zwecke: Alle Dateien duerfen READ-ONLY gelesen werden.
Secrets (`.env`, Wallet-Dateien, API Keys) duerfen NICHT gelesen oder ausgegeben werden.

---

## 1. LOKALE MEMORY (Claude Code Session-Kontext)

Pfad: `/Users/gio/.claude/projects/-Users-gio/memory/`

| Datei | Inhalt | Aktuell |
|---|---|---|
| `MEMORY.md` | Master-Index aller Projekte | JA (01.05) |
| `pnyx-session-20260501-final.md` | **AKTUELLE SESSION** — alle heutigen Ergebnisse | JA (01.05) |
| `pnyx-status.md` | Projekt-Grunddaten (veraltet, 14.04) | NEIN |
| `pnyx-session-20260429.md` | Vorherige Session | Archiv |
| `pnyx-session-20260428-final.md` | Session 28.04 | Archiv |
| `pnyx-session-20260427.md` | Session 27.04 | Archiv |
| `pnyx-session-20260426.md` | Session 26.04 | Archiv |
| `pnyx-session-20260425.md` | Session 25.04 | Archiv |
| `pnyx-session-20260421.md` | Session 21.04 | Archiv |

**Startpunkt:** `pnyx-session-20260501-final.md` zuerst lesen.

---

## 2. AGENT-BRIDGE (Lokal im Repo)

Pfad: `/Users/gio/Desktop/repo/pnyx/docs/agent-bridge/`

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `README.md` | Bridge-Regeln, Sicherheitsregeln | Initial (Codex) |
| `PROJECT_STATE.md` | Repo-Fakten, Stack, Git, Server-Status | Beide |
| `PUBLIC_CONCEPT_CONTEXT.md` | Oeffentliche Doku (Website/Wiki) + Drift | Claude Code |
| `CLAUDE_TO_CODEX.md` | Vollstaendiges Handover (21 Sektionen) | Claude Code |
| `CODEX_TO_CLAUDE.md` | Codex-Analysen, Onboarding, Bestaetigung | Codex |
| `ACTION_LOG.md` | Chronologisches Aktionsprotokoll (20+ Eintraege) | Beide |
| `DECISIONS.md` | Arbeitsmodell, Prioritaeten, Tabu-Bereiche | Beide |
| `QUESTIONS.md` | 6 beantwortete Fragen, keine offenen | Beide |
| `DO_NOT_TOUCH.md` | Sperrbereiche (Secrets, Produktcode) | Initial (Codex) |
| `MASTER_AUDIT_PROMPT.md` | Umfassender Audit-Prompt fuer externen Agenten | Codex |
| `REPORT_CLAUDE_CODEX_COLLABORATION.md` | Bericht ueber Zusammenarbeit | Claude Code |
| `DATA_SOURCES_INDEX.md` | DIESE DATEI — Index aller Datenquellen | Claude Code |

---

## 3. REPO ROOT (Lokal)

Pfad: `/Users/gio/Desktop/repo/pnyx/`

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Projekt-Konfiguration, Security Audit System, Stack, Endpoints, Routes |
| `README.md` | Oeffentliche Projektbeschreibung |
| `SECURITY.md` | Security Policy |
| `.gitignore` | Ignorierte Dateien |
| `.gitleaks.toml` | Secret-Detection Regeln |

---

## 4. REPO CODE-STRUKTUR (Lokal)

```
apps/
├── api/                    Python FastAPI Backend
│   ├── main.py             Router-Registrierung, Scheduler, Middleware
│   ├── routers/            25 Router-Module (identity, vaa, parliament, voting, ...)
│   │   ├── app_version.py  NEU (01.05) — Version-Check Endpoint
│   │   └── identity.py     HLR Credits + Failover Status
│   ├── services/           discourse_sync.py, greek_topics_scraper.py (uncommitted)
│   ├── models.py           SQLAlchemy Models
│   ├── database.py         DB Connection
│   ├── requirements.txt    Python Dependencies
│   ├── Dockerfile.prod     Production Dockerfile
│   └── tests/              pytest Tests
├── web/                    Next.js 14 Frontend
│   ├── package.json        Dependencies (axios 1.14.0!)
│   ├── Dockerfile.prod     Production Dockerfile
│   └── src/app/            App Router (i18n el/en)
└── mobile/                 Expo React Native
    ├── app.json            versionCode 5, scheme ekklesia
    ├── eas.json            EAS Build Profiles
    ├── src/screens/        HomeScreen.tsx (Update-Banner)
    └── android/            Gradle Build Output

packages/
├── crypto/                 Ed25519, Nullifier, HLR (hlr.py — Failover)
└── compass/                Liquid Compass TypeScript

infra/
├── docker/
│   ├── docker-compose.yml      Lokal (db, redis, api)
│   └── docker-compose.prod.yml Production (api, web, db, redis, ollama, traefik)
└── hetzner/                    Deployment-Skripte

docs/
├── agent-bridge/           → Sektion 2
├── community.html          Community-Seite mit HLR Tabs + Spenden
└── (weitere Wiki/Docs)

.github/workflows/
├── ci.yml                  API + Crypto Tests
├── deploy.yml              Manueller SSH-Deploy (workflow_dispatch)
├── scraper.yml             Parliament Scraper (Schedule)
└── security-audit.yml      Gitleaks + Dependency Audit
```

---

## 5. SERVER MEMORY

Pfad: `root@135.181.254.229:/opt/hetzner-migration/memory/`

| Datei | Inhalt | Aktuell |
|---|---|---|
| `master_todo.md` | **MASTER TODO** — 62 erledigt, 77 offen | JA (01.05) |
| `pnyx-session-20260501.md` | **AKTUELLE SERVER-SESSION** | JA (01.05) |
| `known_issues.md` | Bekannte Issues (R-001 bis R-016, SEC-01 bis SEC-06) | JA (26.04) |
| `decisions.md` | ADR-001 bis ADR-022 | JA (21.04) |
| `GOV_DASHBOARD_ARCHITECTURE.md` | Admin + Behoerden Dashboard Architektur | JA (29.04) |
| `MULTI_PROJECT_ARCHITECTURE.md` | Multi-Projekt Server-Architektur | JA (28.04) |
| `MIRROR_CONCEPT.md` | Mirror-Server Konzept | JA (30.04) |
| `reference_hlr_api.md` | HLR API Referenz | JA (27.04) |
| `project_inventory.md` | Server-Inventar | Veraltet (18.04) |
| `audit_report_20260420.md` | Security Audit Report | Archiv |
| `audit_report_mobile_20260421.md` | Mobile Audit Report | Archiv |
| `pnyx-session-2026042[3-9].md` | Aeltere Sessions | Archiv |

---

## 6. SERVER ARCHITEKTUR

Pfad: `root@135.181.254.229:/opt/hetzner-migration/architecture/`

| Datei | Inhalt |
|---|---|
| `MIROFISCH_CONCEPT.md` | MiroFisch / vr.ekklesia.gr Konzept (01.05) |
| `README.md` | Architektur-Uebersicht |
| `federation/OVERVIEW.md` | Foederiertes Node-Netzwerk Gesamtkonzept |
| `federation/NODE-WIZARD.md` | Node Setup-Wizard Spezifikation |
| `federation/EMBED-SYSTEM.md` | Widget-Einbettung |
| `federation/DATA-FLOW.md` | Datenfluss App <-> Node <-> ekklesia.gr |
| `federation/BILLING-REDIRECT.md` | Ausgelagerte Bills Grayout + Redirect |
| `federation/TEST-NODE.md` | test.ekklesia.gr Testumgebung |

---

## 7. SERVER FORUM MEMORY

Pfad: `root@135.181.254.229:/opt/hetzner-migration/memory/pnyx-forum/`

| Datei | Inhalt |
|---|---|
| `FORUM-CC-START.md` | Forum-CC Neustart-Anleitung |
| `COORDINATION.md` | Koordination zwischen Agenten |
| `STATUS.md` | Forum-Status |

---

## 8. SERVER KONFIGURATION (NUR LESEN, KEINE SECRETS)

| Pfad | Inhalt | Zugriff |
|---|---|---|
| `/var/discourse/containers/app.yml` | Discourse Config (SMTP Creds drin!) | NUR Struktur lesen |
| `/opt/ekklesia/app/infra/docker/docker-compose.prod.yml` | Production Compose | Lesen OK |
| `/opt/ekklesia/app/infra/docker/docker-compose.yml` | Lokales Compose | Lesen OK |
| `/opt/ekklesia/.env.production` | **SECRETS — NICHT LESEN** | GESPERRT |
| `/opt/ekklesia/arweave-wallet.json` | **SECRET — NICHT LESEN** | GESPERRT |
| `/opt/ekklesia/app/.github/workflows/*.yml` | CI/CD Workflows | Lesen OK |

---

## 9. EXTERNE QUELLEN

| Quelle | URL | Zugriff |
|---|---|---|
| GitHub Repo | https://github.com/NeaBouli/pnyx | `gh` CLI |
| GitHub Wiki | https://github.com/NeaBouli/pnyx/wiki | WebFetch |
| Website | https://ekklesia.gr | WebFetch |
| Forum | https://pnyx.ekklesia.gr | WebFetch |
| F-Droid MR | https://gitlab.com/fdroid/fdroiddata/-/merge_requests/37087 | `glab` CLI |
| GitLab Fork | https://gitlab.com/TrueRepublic/fdroiddata | `glab` CLI |
| API Health | https://api.ekklesia.gr/health | curl |
| API Credits | https://api.ekklesia.gr/api/v1/identity/hlr/credits | curl |
| API Version | https://api.ekklesia.gr/api/v1/app/version | curl |

---

## 10. LIVE API ENDPOINTS (Audit-relevant)

```
GET  /health                              → 24 Module, Version
GET  /api/v1/app/version                  → Version-Check, force_update
GET  /api/v1/identity/hlr/credits         → HLR Credits (primary/fallback)
GET  /api/v1/bills                        → Bills Feed
GET  /api/v1/bills/trending               → Trending Bills
GET  /api/v1/vaa/statements               → VAA Thesen
GET  /api/v1/vaa/parties                   → Parteien
GET  /public/cplm                         → CPLM Aggregate (CC BY 4.0)
GET  /public/cplm/history                 → CPLM History
GET  /public/representation               → Representativeness
GET  /api/v1/mp/ranking                   → Party Ranking
GET  /api/v1/payments/status              → Payment Status
GET  /api/v1/newsletter/stats             → Newsletter Stats
POST /api/v1/identity/verify              → Identity Verify (HLR)
POST /api/v1/vote                         → Vote
POST /api/v1/claude/ask                   → AI Agent
GET  /api/v1/claude/budget                → AI Budget
```

---

## 11. AUDIT-REIHENFOLGE (Empfehlung)

1. `docs/agent-bridge/MASTER_AUDIT_PROMPT.md` — Audit-Scope + Checkliste
2. `docs/agent-bridge/PROJECT_STATE.md` — aktueller Zustand
3. `CLAUDE.md` — Projekt-Regeln + Stack
4. `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md` — Drift-Analyse
5. `docs/agent-bridge/DECISIONS.md` — Arbeitsmodell + Tabus
6. `docs/agent-bridge/ACTION_LOG.md` — was heute passiert ist
7. Server: `master_todo.md` — offene Punkte
8. Server: `known_issues.md` — bekannte Issues + Security Findings
9. Server: `decisions.md` — ADR-001 bis ADR-022
10. API Endpoints testen (curl, read-only)

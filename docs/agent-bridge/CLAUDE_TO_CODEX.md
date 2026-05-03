# Claude To Codex — Vollstaendiges Projekt-Handover

- **Datum:** 2026-05-01
- **Agent:** Claude Code
- **Zweck:** Komplettes Handover, damit Codex das Projekt versteht, bevor Aufgaben uebernommen werden.

---

## 1. Was ist dieses Projekt?

**ekklesia.gr** (Codename: **pnyx**) ist eine Privacy-first Plattform fuer digitale direkte Demokratie in Griechenland.

Buerger koennen anonym ueber echte Parlamentsgesetze abstimmen. Die Plattform vergleicht dann, wie die Buerger abgestimmt haben vs. wie das Parlament abgestimmt hat (**Divergence Score**). Zusaetzlich gibt es einen politischen Kompass (VAA), kommunale Governance, ein Discourse-Forum und eine Public API.

**Kernprinzip:** Vollstaendige Anonymitaet. Keine Accounts, keine E-Mails, keine Cookies. Identitaet wird per SMS verifiziert (Nummer wird sofort geloescht), danach signiert der Buerger mit Ed25519 — Private Key bleibt ausschliesslich auf dem Geraet.

**Owner:** Gio (Kaspartizan / NeaBouli), unabhaengiger Entwickler, Griechenland.
**Organisation:** V-Labs Development
**Lizenz:** MIT
**Repo:** https://github.com/NeaBouli/pnyx (oeffentlich)
**Lokaler Pfad:** `/Users/gio/Desktop/repo/pnyx`
**Live:** https://ekklesia.gr
**Forum:** https://pnyx.ekklesia.gr (Discourse)

---

## 2. Architektur / Stack

```
pnyx/
├── apps/
│   ├── api/          Python 3.12 FastAPI + Alembic + PostgreSQL + Redis
│   ├── web/          Next.js 14.2.35 + React 19 + TypeScript 6 + Tailwind 4
│   └── mobile/       Expo SDK 54 + React Native 0.81.5 (Android, versionCode 5)
├── packages/
│   ├── crypto/       Shared crypto (TS: @noble/curves, Python: PyNaCl)
│   └── compass/      Shared compass TypeScript
├── infra/
│   ├── docker/       docker-compose.yml (lokal) + docker-compose.prod.yml
│   └── hetzner/      Deployment-Skripte (NUR nach Freigabe)
├── cloudflare-worker/ OAuth Proxy Worker
├── docs/             Docs, Wiki, Agent-Bridge
├── wiki/             Wiki-Inhalte (eigenes .git)
├── scripts/          Utility-Skripte
├── metadata/         App Store Metadaten
├── fdroid/           F-Droid Metadaten
└── .github/workflows/ CI, Deploy, Scraper, Security Audit
```

### API-Abhaengigkeiten
FastAPI, Uvicorn, SQLAlchemy asyncio, Alembic, asyncpg, Redis, Pydantic, PyNaCl, cryptography, python-jose, Argon2, httpx, APScheduler, SlowAPI.

### Web-Abhaengigkeiten
Next.js 14, React 19, TypeScript 6, Tailwind CSS 4, next-intl (i18n el/en), TanStack Query, Recharts, lucide-react, Axios 1.14.0, Arweave SDK.

### Mobile-Abhaengigkeiten
Expo SDK 54, React Native 0.81.5, Expo SecureStore/Crypto/Notifications/LocalAuthentication, React Navigation.

### Infrastruktur (Produktion)
- **Server:** Hetzner CX33, Helsinki, Ubuntu 24.04.4 LTS (`root@135.181.254.229`)
- **Container:** ~10 (api, web, db, redis, traefik, listmonk x3, discourse, discourse-db) — UNSICHER, Server-Check noetig
- **Reverse Proxy:** Traefik
- **Newsletter:** Listmonk + Brevo SMTP (forum@ekklesia.gr)
- **AI:** Ollama llama3.2:3b (optional, 2.6 GB RAM)
- **Snapshot:** `ekklesia-gr-2026-04-21-stable`

---

## 3. Module (bekannt)

Die genaue Modulzahl ist UNSICHER (Drift zwischen 15/16/22/24 je nach Quelle — siehe `PUBLIC_CONCEPT_CONTEXT.md`). Hier die bekanntermassen implementierten:

| Modul | Funktion | Status |
|---|---|---|
| MOD-01 | Identity Verify (SMS → Nullifier → Ed25519 Key) | LIVE |
| MOD-02 | VAA (38 Thesen, 8 Parteien, 304 Positionen) | LIVE |
| MOD-03 | Bills (Feed, Detail, Lifecycle, Admin) | LIVE |
| MOD-04 | Voting (Ed25519, anonym, 3 Optionen) | LIVE |
| MOD-05 | Divergence Score (Buerger vs. Parlament) | LIVE |
| MOD-08 | TrueRepublic Bridge (Cosmos SDK) | GEPLANT (V2) |
| MOD-09 | gov.gr OAuth2.0 | GATED (500 User + 3 NGOs) |
| MOD-14 | Relevance Signal | LIVE |
| MOD-16 | Municipal Governance (13 Regionen, 325 Gemeinden) | TEILWEISE |
| MOD-17 | Smart Notifications | GEPLANT |
| — | Liquid Compass (4 Modelle, AES-256-GCM, client-only) | LIVE |
| — | CPLM (Citizens Political Liquid Mirror, Public API) | LIVE |
| — | QR-Code Vote (purpose-bound, bill_id) | LIVE |
| — | Deep-Link (ekklesia://polis-login) | LIVE |
| — | Bill Lifecycle Scheduler | LIVE |
| — | Vote Correction (einmalig in WINDOW_24H) | LIVE |
| — | Discourse Forum Sync | LIVE |
| — | Newsletter (Listmonk, 6 Listen) | LIVE |
| — | Stripe Donations | LIVE |
| — | Arweave Archiv | LIVE |

---

## 4. API Endpoints (aus CLAUDE.md)

```
MOD-01: POST /api/v1/identity/verify | revoke | status
MOD-02: GET  /api/v1/vaa/statements | parties  /  POST /match
MOD-03: GET  /api/v1/bills | /trending | /{id}  /  POST /transition | /admin/create
MOD-04: POST /api/v1/vote  /  GET /{id}/results  /  POST /{id}/relevance
MOD-05: Divergence Score (in /results)
MOD-14: Relevance Signal (in /relevance)
Public: GET /public/cplm | /public/cplm/history | /public/representation (CC BY 4.0)
```

Hinweis: CLAUDE.md sagt 13, Website sagt 16, Wiki sagt 70+ — Drift, siehe `PUBLIC_CONCEPT_CONTEXT.md`.

---

## 5. Web Routes (10)

```
/[locale]            Homepage (Hero + Feature Cards)
/[locale]/vaa        VAA Quiz → seeds Compass
/[locale]/compass    Liquid Compass Dashboard
/[locale]/bills      Bills Feed (Filter + StatusBadge)
/[locale]/bills/[id] Bill Detail + Abstimmung + Divergence
/[locale]/verify     Identity Verify (SMS → Key)
/[locale]/results    Ergebnisse + Divergenz
/[locale]/analytics  Analytische Daten
/[locale]/mp         Parteien vs. Buerger
/[locale]/admin      Admin Panel
```

---

## 6. Bill Lifecycle

```
ANNOUNCED → (14 Tage) → ACTIVE → (24h) → WINDOW_24H → (Snapshot) → PARLIAMENT_VOTED → (7 Tage) → OPEN_END
```

- Scheduler laeuft stuendlich
- Vote Correction: einmalig in WINDOW_24H (Migration k401a2b3c4d5)

---

## 7. Sicherheitsarchitektur

- **Telefonnummer:** sofort nach Nullifier-Generierung geloescht (gc.collect())
- **Private Key:** einmalig zurueckgegeben, NIE auf Server gespeichert
- **Nullifier Hash:** SHA256(phone + SERVER_SALT) — nicht umkehrbar
- **Ed25519:** Public Key auf Server, Private Key nur auf Geraet
- **Demographic Hash:** SHA256(region + gender + SERVER_SALT)
- **Compass-Daten:** 100% clientseitig, AES-256-GCM (HKDF vom Ed25519 Key), nie an Server
- **K-Anonymity:** Datenschutzmodell
- **Arweave:** Ergebnisse append-only archiviert
- **Rate Limiting:** 60 req/min/IP global, 5 req/min/IP fuer AI
- **Circuit Breaker:** 3 Fehler → 24h Pause

---

## 8. Scheduler Jobs (8 aktiv auf Server)

| Job | Intervall | Funktion |
|---|---|---|
| bill_lifecycle | 1h | Status-Transitionen (ANNOUNCED→ACTIVE→...) |
| cplm_refresh | 6h | CPLM Aggregate neu berechnen |
| greek_topics | 6h | News-Scraper (DEAKTIVIERT, Feature-Flag OFF) |
| parliament | 12h | Parlamentsdaten aktualisieren |
| diavgeia | 48h | OpenData API abfragen |
| notify-bills | 30min | Push-Benachrichtigungen (neue Gesetze) |
| notify-results | 1h | Push-Benachrichtigungen (Ergebnisse) |
| forum-sync | 10min | Discourse Bill-Sync |

---

## 9. Git-Status

- **Branch:** `main`
- **HEAD:** `a09ec74`
- **Tag:** `session-final-20260501`
- **Remote:** synchron mit GitHub
- **30 juengste Commits:** Alle Features der Session 29.04–01.05 (QR-Vote, Lifecycle, CPLM, SEO, Gov-Dimos, Deep-Link, etc.)

### Uncommitted Aenderungen (NICHT ANFASSEN)

1. `apps/api/services/discourse_sync.py` — reichere Bill-Topic-Formatierung (BEHALTEN, nach Test)
2. `apps/api/services/greek_topics_scraper.py` — RSS News-Scraper (DEAKTIVIERT LASSEN, rechtliche Klaerung noetig)

Bewertung: siehe vorherige Bridge-Eintraege und `CLAUDE_TO_CODEX.md` Archiv.

---

## 10. Was ist ERLEDIGT (Session 29.04–01.05)

- Deep-Link ekklesia://polis-login
- QR-Code Vote (purpose-bound, bill_id)
- Bill Lifecycle Scheduler (autonom)
- Vote Correction (WINDOW_24H)
- CPLM (Aggregate + Chart + Landing + Public API CC BY 4.0)
- govgr-dimos.html (5-Schritt Timeline, Server-Wahl, Kontaktformular)
- GSC Fixes (www→301, hreflang)
- Hybrid AI Agent (Ollama + Claude Haiku Fallback)
- SEO/GEO/AI-Readiness Optimierung
- Mirror Server Architecture Concept
- Knowledge Base Seed (17 Eintraege)
- versionCode 4→5

---

## 11. Was steht als NAECHSTES an

| # | Aufgabe | Prioritaet | Status |
|---|---|---|---|
| 1 | **v5 EAS Build** — AAB fuer Play Store bauen | HOCH | OFFEN (01.05) |
| 2 | ADR-022 Migration | MITTEL | OFFEN |
| 3 | F-Droid MR versionCode 5 | MITTEL | OFFEN |
| 4 | **dashboard.ekklesia.gr** — Admin Dashboard | HOECHSTE DEV-PRIO | ARCHITEKTUR FERTIG, CODE OFFEN |
| 5 | Embed-System (Phase 2) | MITTEL | ARCHITEKTUR FERTIG |
| 6 | test.ekklesia.gr aufsetzen | NIEDRIG | DNS GESETZT, KEIN CONTAINER |
| 7 | MOD-17 Smart Notifications | NIEDRIG | GEPLANT |
| 8 | Dokumentations-Drift bereinigen | MITTEL | IDENTIFIZIERT |

### Architektur-Dokumente (NUR Planung, auf Server)

- Foederiertes Node-Netzwerk: 7 Dokumente unter `/opt/hetzner-migration/architecture/federation/`
- dashboard.ekklesia.gr: Admin Dashboard
- gov.ekklesia.gr: Behoerden Dashboard

---

## 12. Build / Test / Dev Befehle

### API
```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                    # DB Migrationen
python seeds/seed_real_bills.py         # Seed-Daten
uvicorn main:app --reload               # Dev-Server
python -m pytest tests/ -v              # Tests
```

### Web
```bash
cd apps/web
npm ci                                  # NICHT npm install
npm run dev                             # Dev-Server
npm run build                           # Production Build
npm run lint                            # Linting
npx vitest run                          # Tests (Vitest als devDep, kein test-Script)
```

### Mobile
```bash
cd apps/mobile
npm ci
npm run start                           # Expo Dev
npm run android                         # Android
# EAS Build: apps/mobile/eas.json (development/preview/production)
# Production = app-bundle, remote credentials — NUR nach Freigabe
```

### Crypto Package
```bash
cd packages/crypto
npm test                                # TS Tests
# Python Tests auch vorhanden
```

### Docker (lokal)
```bash
cd infra/docker && docker compose up -d
```

---

## 13. Kritische Regeln (NICHT VERHANDELBAR)

1. **Keine .env-Dateien oeffnen oder lesen.** Nie.
2. **`arweave-wallet.json` NICHT oeffnen.** Secret.
3. **Kein Commit, Push, Deployment, SSH ohne explizite Nutzerfreigabe.**
4. **Uncommitted Aenderungen in `apps/api/services/` NICHT anfassen.**
5. **`npm ci` statt `npm install`.** Immer. CI-Regel.
6. **`ignore-scripts=true` in `.npmrc`.** Supply-Chain-Schutz.
7. **axios >= 1.14.0.** Versionen dazwischen enthalten Malware (plain-crypto-js).
8. **Kein ORM** in pnyx — raw SQL mit parametrisierten Queries (HINWEIS: SQLAlchemy asyncio ist als Dependency vorhanden — Codex soll pruefen, ob das ein Widerspruch ist).
9. **Ed25519 Voting ist Kern-Security** — Voting/Auth/Crypto-Code nur nach explizitem Task aendern.
10. **gov.gr OAuth ist GATED** — nicht als verfuegbar behandeln.
11. **Keine Secrets in Bridge-Dateien schreiben.**
12. **Deploy-Workflow ist workflow_dispatch** — kein Auto-Deploy.

---

## 14. Bekannte Risiken und offene Fragen

### Risiken
- `.env.production` im Repo-Root (gitignored, aber sensibel)
- `arweave-wallet.json` im Repo-Root (gitignored, Secret)
- SSH-Key fuer Hetzner aktuell nicht geladen
- `wiki/` hat eigenes `.git` — bei Git-Operationen beachten
- Server-Zustand (Container, Scheduler, Score) ist UNSICHER ohne SSH-Check
- Dokumentations-Drift: 6 Widersprueche identifiziert (siehe `PUBLIC_CONCEPT_CONTEXT.md`)

### Offene Fragen (von Codex an Nutzer, aus CODEX_TO_CLAUDE.md)
- Soll Codex beim v5 EAS Build nur vorbereiten oder auch `eas build` starten?

### Geklaearte Fragen
- Kanonischer Repo-Pfad: `/Users/gio/Desktop/repo/pnyx` (NICHT `~/Desktop/pnyx`)
- Server-Live-Status als UNSICHER markiert — erledigt

---

## 15. Dokumentations-Drift (Zusammenfassung)

Vollstaendige Drift-Analyse: siehe `PUBLIC_CONCEPT_CONTEXT.md`

| Metrik | Quellen | Status |
|---|---|---|
| Module | 15 / 16 / 22 / 24 | DRIFT |
| API Endpoints | 13 / 16 / 70+ | DRIFT |
| DB-Tabellen | 9 / 15+ | DRIFT |
| Tests | 51+12 vs 106+47 | DRIFT |
| Container | 9 / 10 | DRIFT |
| Score | 90 / 96 | DRIFT |
| Compass-Modelle | 4 / 4 | OK |
| gov.gr OAuth | deferred/gated | OK |

**Prioritaetsregel:** lokaler Code > Session Memory > Wiki > Website.

---

## 16. Seed-Daten

- 8 griechische Parteien: ND, SYRIZA, PASOK, KKE, EL, NIKI, PL, SPART
- 38 VAA-Thesen (Gesundheit, NATO, Lohn, Wohnen, Tourismus, Demografie, Tempi...)
- 3 Gesetzentwuerfe (2x OPEN_END, 1x ACTIVE)
- Knowledge Base: 17 Eintraege

---

## 17. CI/CD Workflows

| Workflow | Trigger | Funktion |
|---|---|---|
| `ci.yml` | Push/PR | API Tests + Crypto Tests |
| `deploy.yml` | workflow_dispatch (manuell) | SSH-Deploy auf Hetzner |
| `scraper.yml` | Schedule | Web Scraper |
| `security-audit.yml` | Push/PR/Schedule | Gitleaks + Dependency Audit |

---

## 18. Distribution

| Kanal | Status |
|---|---|
| APK direkt (ekklesia.gr/download) | LIVE |
| GitHub Releases v1.0.0 | LIVE |
| Google Play (Closed Testing) | AAB hochgeladen |
| F-Droid (MR #37087) | Pending Review |

---

## 19. Externe Referenzen (READ ONLY)

- **TrueRepublic:** `/Users/gio/TrueRepublic` — Cosmos SDK Blockchain, PnyxCoin. Bridge geplant (MOD-08, V2).
- **Inferno ($IFR):** Separates Projekt. NIEMALS in derselben Session mischen.

---

## 20. Kommunikationsprotokoll

### Fragen an den Nutzer (Gio)
- Codex stellt Fragen in `docs/agent-bridge/QUESTIONS.md`
- Format: Datum, Von, An, Frage, Kontext, Blockiert (ja/nein)

### Fragen an Claude Code
- Codex stellt Fragen in `docs/agent-bridge/QUESTIONS.md` (An: Claude Code)
- Oder in `docs/agent-bridge/CODEX_TO_CLAUDE.md` unter "Rueckfragen an Claude"

### Ergebnisse an Claude Code
- Codex dokumentiert Ergebnisse in `docs/agent-bridge/CODEX_TO_CLAUDE.md`

### Entscheidungen
- Werden in `docs/agent-bridge/DECISIONS.md` dokumentiert

### Aktionslog
- Jede Aktion wird in `docs/agent-bridge/ACTION_LOG.md` dokumentiert
- Pflichtfelder: Agent, Aktion, Geaenderte Dateien, Secrets gelesen (nein), Commit/Push/Deployment/SSH (nein)

### Datei-Routing

| Kontext | Datei |
|---|---|
| Repo-Fakten, Stack, Versionen, Server | `PROJECT_STATE.md` |
| Oeffentliche Doku (Website, Wiki) | `PUBLIC_CONCEPT_CONTEXT.md` |
| Aufgaben Claude → Codex | `CLAUDE_TO_CODEX.md` |
| Ergebnisse Codex → Claude | `CODEX_TO_CLAUDE.md` |
| Entscheidungen | `DECISIONS.md` |
| Offene Fragen | `QUESTIONS.md` |
| Aktionsprotokoll | `ACTION_LOG.md` |
| Sperrbereiche | `DO_NOT_TOUCH.md` |
| Bridge-Regeln | `README.md` |

---

## 21. Was Codex als Naechstes tun soll

Codex soll dieses Handover lesen und bestaetigen, dass der Projektkontext verstanden ist. Danach:

1. **Bestaetige in CODEX_TO_CLAUDE.md**, dass das Handover gelesen und verstanden wurde.
2. **Stelle Fragen in QUESTIONS.md**, falls etwas unklar ist.
3. **Warte auf eine konkrete Aufgabe** vom Nutzer oder von Claude Code.
4. **Aendere keinen Produktcode** ohne explizite Freigabe.

---

*Erstellt von Claude Code am 2026-05-01. Keine Secrets gelesen. Kein Produktcode geaendert.*

# DASHBOARD INVENTORY — ekklesia.gr / pnyx
**Generiert:** 2026-05-02
**Scope:** Alle Router, Services, Scheduler Jobs, .env-Konfigurationen, Infra-Container
**Zweck:** Vollständige Grundlage für Dashboard-Design (Haupt-Node + Subnode-Architektur)

---

## LEGENDE

**Auth-Typen:**
- `public` — kein Auth, frei zugänglich
- `admin_key` — Query-Parameter `?admin_key=` oder Header `X-Admin-Key`
- `nullifier` — Ed25519-Identität (verifizierter Bürger)
- `stripe_sig` — Stripe Webhook Signature
- `discourse_sso` — HMAC-basiertes Discourse SSO

**Dashboard-Kategorie:**
- `A` — Hauptknoten-Dashboard (single admin instance)
- `B` — Haupt + Node (pro Node-Instanz verwaltbar)
- `C` — Nur Node-spezifisch

**Dashboard-relevant:**
- `JA` — direkt steuerbar/anzeigbar
- `INFO` — nur Lesezugriff / Monitoring
- `NEIN` — kein Dashboard-Nutzen

---

## 1. ROUTER-ENDPOINTS

### MOD-01 · Identity (`/api/v1/identity`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/verify` | HLR-Verifikation → Ed25519 Keypair generieren | public | INFO | A |
| POST | `/revoke` | Schlüssel revozieren | nullifier | NEIN | A |
| POST | `/status` | Nullifier-Status prüfen (ACTIVE/REVOKED) | public | NEIN | A |
| GET | `/hlr/credits` | HLR-Credits beider Provider (primary + fallback) | public | **JA** | A |
| PATCH | `/profile/location` | Dimos/Periferia für Vote-Scope setzen | nullifier | NEIN | A |

---

### MOD-02 · VAA (`/api/v1/vaa`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/statements` | Aktive VAA-Thesen abrufen (el/en, random limit) | public | INFO | A |
| GET | `/parties` | Aktive Parteien abrufen | public | INFO | A |
| POST | `/match` | Party-Matching Algorithmus ausführen | public | NEIN | A |

---

### MOD-03 · Parliament Bills (`/api/v1/bills`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `` (root) | Alle Bills (Filter: status, category, limit) | public | INFO | A |
| GET | `/trending` | Bills nach Relevanz-Score sortiert | public | INFO | A |
| GET | `/{bill_id}` | Einzelnes Bill mit Details | public | INFO | A |
| GET | `/{bill_id}/summary` | AI-Zusammenfassung (Ollama, Redis-gecacht 7d) | public | INFO | A |
| POST | `/{bill_id}/transition` | Lifecycle-Übergang (ANNOUNCED→ACTIVE etc.) | admin_key | **JA** | A |
| POST | `/admin/create` | Neues Bill anlegen | admin_key | **JA** | A |

---

### MOD-04 · CitizenVote (`/api/v1/vote`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `` (root) | Abstimmung abgeben (Ed25519 signiert) | nullifier | INFO | A |
| PUT | `/{bill_id}/correct` | Einmalige Stimmkorrektur (nur WINDOW_24H) | nullifier | NEIN | A |
| GET | `/results/latest` | Letztes aktives Bill mit Votes (Landing Page) | public | INFO | A |
| GET | `/{bill_id}/results` | Ergebnisse + Divergence Score + Repräsentativität | public | INFO | A |
| POST | `/{bill_id}/relevance` | Up/Down Relevanz-Signal (+1/-1) | nullifier | NEIN | A |
| GET | `/{bill_id}/receipt` | ADR-008 VoteReceipt (HMAC chain proof) | nullifier (Header) | NEIN | A |

---

### MOD-06 · Analytics (`/api/v1/analytics`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/overview` | Plattform-Statistiken (Bills, Votes, Divergence) | public | **JA** | A |
| GET | `/divergence-trends` | Divergence Trends über Zeit (bis 365 Tage) | public | **JA** | A |
| GET | `/votes-timeline` | Abstimmungs-Zeitverlauf nach Tag aggregiert | public | **JA** | A |
| GET | `/top-divergence` | Top Bills nach Divergence Score | public | **JA** | A |
| GET | `/bill/{bill_id}` | Vollständige Analytik eines Bills | public | INFO | A |
| GET | `/representation` | Kumulative Repräsentation Parlament vs. Bürger | public | **JA** | A |
| GET | `/info` | Endpoint-Übersicht | public | NEIN | A |

---

### MOD-07 · Notifications SSE/WS (`/api/v1/notifications`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/stream` | SSE-Stream für Browser (Live-Events) | public | INFO | A |
| WS | `/ws` | WebSocket für Mobile App | public | INFO | A |
| POST | `/test/publish` | Test-Event publishen (DEV) | admin_key | **JA** | A |
| GET | `/status` | Subscriber-Count + Transport-Info | public | **JA** | A |

---

### MOD-08 · Arweave (`/api/v1/arweave`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/status` | Wallet-Status, AR-Balance | public | **JA** | A |
| GET | `/bill/{bill_id}` | TX-ID + Arweave-URL für ein Bill | public | INFO | A |

---

### MOD-09 · gov.gr OAuth (`/api/v1/auth/govgr`) — STUB

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/status` | Aktivierungsgates-Status (0/4 erfüllt) | public | **JA** | A |
| GET | `/login` | OAuth2-Login-Flow starten (gesperrt bis Gates erfüllt) | public | NEIN | A |
| GET | `/callback` | OAuth2-Callback (gesperrt) | public | NEIN | A |
| GET | `/family/verify` | Liquid Democracy Stub (inaktiv) | public | NEIN | A |
| GET | `/info` | Flow-Dokumentation | public | NEIN | A |

---

### MOD-10 · AI Scraper (`/api/v1/scraper`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/jobs` | Status aller Scraper-Jobs (Redis-backed) | public | **JA** | A |
| GET | `/status` | KI-Provider Status (Ollama/HuggingFace/rule-based) | public | **JA** | A |
| GET | `/test` | Scraper + KI ohne DB testen | public | **JA** | A |
| GET | `/parliament/latest` | Letzte Bills von hellenicparliament.gr scrapen | public | INFO | A |
| POST | `/fetch` | URL scrapen → KI → DB speichern | admin_key | **JA** | A |
| POST | `/import` | Bulk-Import strukturierter Bill-Daten (GitHub Actions) | admin_key | **JA** | A |

---

### MOD-11 · Public API (`/api/v1/public`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/keys/generate` | API-Key generieren (kein Account nötig) | public | INFO | A |
| GET | `/keys/status` | API-Key validieren | api_key (Header) | NEIN | A |
| GET | `/bills` | Alle Bills (CC BY 4.0, Rate-Limited) | public/api_key | NEIN | A |
| GET | `/bills/{id}/results` | Vote-Ergebnisse (CC BY 4.0) | public/api_key | NEIN | A |
| GET | `/stats` | Plattform-Statistiken (CC BY 4.0) | public/api_key | NEIN | A |
| GET | `/vaa/parties` | Parteien (CC BY 4.0) | public/api_key | NEIN | A |
| GET | `/cplm` | CPLM Aggregat (CC BY 4.0) | public/api_key | NEIN | A |
| GET | `/cplm/history` | CPLM Verlauf | public/api_key | NEIN | A |
| GET | `/representation` | Parlament-Repräsentativität | public/api_key | NEIN | A |
| GET | `/info` | API-Dokumentation | public | NEIN | A |

---

### MOD-12 · MP Comparison (`/api/v1/mp`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/parties` | Alle Parteien mit Parlamentspräsenz | public | INFO | A |
| GET | `/compare/{party_abbr}` | Bürger-Mehrheit vs. Parteistimme alle Bills | public | **JA** | A |
| GET | `/ranking` | Parteien-Rangliste nach Übereinstimmung | public | **JA** | A |
| GET | `/bill/{bill_id}` | Parteistimmen vs. Bürgermehrheit für ein Bill | public | INFO | A |
| GET | `/info` | Endpoint-Übersicht | public | NEIN | A |

---

### MOD-14 · Data Export (`/api/v1/export`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/bills.csv` | Alle Bills + Ergebnisse als CSV (CC BY 4.0) | public | INFO | A |
| GET | `/results.json` | Alle Ergebnisse als JSON | public | INFO | A |
| GET | `/divergence.csv` | Divergence Score Ranking als CSV | public | INFO | A |
| GET | `/parties.json` | Parteien als JSON | public | INFO | A |
| GET | `/info` | Endpoint-Übersicht | public | NEIN | A |

---

### MOD-15 · Admin Panel (`/api/v1/admin`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/dashboard` | Admin-Übersicht (counts, unreviewed AI, recent) | admin_key | **JA** | A |
| GET | `/bills` | Admin-Liste aller Bills (filter: status, reviewed) | admin_key | **JA** | A |
| POST | `/bills` | Neues Bill anlegen (vollständig) | admin_key | **JA** | A |
| PATCH | `/bills/{bill_id}` | Bill-Felder aktualisieren | admin_key | **JA** | A |
| POST | `/bills/{bill_id}/review` | AI-Summary als geprüft markieren | admin_key | **JA** | A |
| POST | `/bills/{bill_id}/party-votes` | Parteistimmen setzen `{"ΝΔ": "ΝΑΙ"}` | admin_key | **JA** | A |
| DELETE | `/bills/{bill_id}/votes` | DEV: Alle Votes eines Bills löschen (gesperrt in Prod) | admin_key | NEIN | A |
| GET | `/stats` | Vote-Statistiken (yes/no/abstain pct) + env info | admin_key | **JA** | A |
| POST | `/scraper/heal-status` | Ollama-Status + geheilte Scraper-Selektoren | admin_key | **JA** | A |
| POST | `/logs/explain` | Ollama analysiert Container-Logs | admin_key | **JA** | A |
| GET | `/deepl/usage` | DeepL API-Verbrauch | public | **JA** | A |
| POST | `/bills/{bill_id}/fetch-text` | Bill-Text via Jina Reader scrapen | admin_key | **JA** | A |
| POST | `/bills/{bill_id}/set-text` | Bill-Text manuell setzen | admin_key | **JA** | A |
| POST | `/compass/generate-questions` | Compass-Fragen aus aktuellen Bills (Ollama + DeepL) | admin_key | **JA** | A |
| GET | `/compass/pending-review` | Pendende Compass-Fragen zur Review | admin_key | **JA** | A |
| POST | `/compass/approve/{question_id}` | Compass-Frage aktivieren | admin_key | **JA** | A |
| POST | `/compass/reject/{question_id}` | Compass-Frage ablehnen | admin_key | **JA** | A |

---

### MOD-16 · Municipal Governance (`/api/v1`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/periferia` | 13 Regionen Griechenlands | public | INFO | B |
| GET | `/periferia/{id}/dimos` | Gemeinden einer Region | public | INFO | B |
| GET | `/decisions` | Decisions-Liste (Filter: level, periferia, dimos, status) | public | INFO | B |
| GET | `/municipal/{dimos_id}/voteable` | Abstimmbare Diavgeia-Entscheidungen eines Dimos | public | INFO | B |
| POST | `/municipal/vote` | Abstimmung auf Diavgeia-Entscheidung | nullifier | NEIN | B |

---

### MOD-18 · Donations (`/api/v1/payments`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/webhook` | Stripe Webhook (checkout.session.completed) | stripe_sig | INFO | A |
| GET | `/status` | Server/Domain/Reserve Kontostände (Transparenz) | public | **JA** | A |

---

### MOD-19 · Newsletter (`/api/v1/newsletter`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/lists` | Verfügbare Newsletter-Listen | public | INFO | A |
| POST | `/subscribe` | Anmelden mit Double Opt-in (Brevo) | public | NEIN | A |
| GET | `/confirm/{token}` | Subscription per E-Mail-Token bestätigen | public | NEIN | A |
| GET | `/stats` | Brevo-Stats + Subscriber-Count (gecacht 60min) | public | **JA** | A |
| POST | `/webhook/brevo` | Brevo Event-Webhook (sent/opened/bounced) | public | NEIN | A |

---

### MOD-20 · Push Notifications (`/api/v1/notify`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/register` | Device-Token registrieren (90 Tage TTL) | public | INFO | A |
| POST | `/send` | Push an alle Geräte senden (Expo) | admin_key (Header) | **JA** | A |

---

### MOD-21 · Diavgeia (`/api/v1/admin/diavgeia` + `/api/v1/municipal` + `/api/v1/regions`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/api/v1/admin/diavgeia/scrape` | Manueller Diavgeia-Scrape | admin_key | **JA** | A |
| POST | `/api/v1/admin/diavgeia/refresh-orgs-cache` | Async Org-Cache-Refresh starten (Job-ID) | admin_key | **JA** | A |
| GET | `/api/v1/admin/diavgeia/refresh-orgs-cache/{job_id}` | Job-Status pollen | admin_key | **JA** | A |
| GET | `/api/v1/municipal/{dimos_id}/decisions` | Diavgeia-Decisions einer Gemeinde | public | INFO | B |
| GET | `/api/v1/regions/{periferia_id}/decisions` | Diavgeia-Decisions einer Region | public | INFO | B |

---

### MOD-22 · Hybrid RAG Agent (`/api/v1/agent`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/ask` | Bürgerfrage (Ollama → Claude Haiku Fallback, 5/min Limit) | public | INFO | A |

---

### Claude Agent (`/api/v1/claude`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/budget` | Claude Token-Verbrauch (täglich/monatlich) | public | **JA** | A |
| POST | `/ask` | Claude Haiku Direkt-Endpoint (3/min Limit) | public | INFO | A |

---

### CPLM (`/api/v1/cplm`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/aggregate` | Aggregierter Gesellschafts-X/Y-Wert | public | **JA** | A |
| GET | `/history` | Historische Snapshots (bis 365 Tage) | public | **JA** | A |

---

### POLIS QR Auth (`/api/v1/polis`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/qr-session` | Neue QR-Session + Challenge (ticket/vote/forum_login) | public | NEIN | A |
| GET | `/qr-session/{session_id}` | Session-Status pollen | public | NEIN | A |
| POST | `/qr-auth` | App authentifiziert Browser-Session | nullifier | NEIN | A |

---

### Discourse SSO (`/api/v1/sso`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/discourse/initiate` | SSO-Flow von Discourse starten | discourse_sso | NEIN | A |
| POST | `/discourse/callback` | Identity bestätigen → Discourse-Payload | public | NEIN | A |

---

### Contact (`/api/v1/contact`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| POST | `/ngo` | NGO-Kontaktformular (Brevo, 3/IP/h Rate Limit) | public | INFO | A |

---

### App Version (`/api/v1/app`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/version` | Aktuelle App-Version + Release Notes + Store-Links | public | **JA** | A |
| GET | `/api/v1/version` (legacy) | Gleiche Daten wie `/app/version` | public | NEIN | A |

---

### System Health (`/`, `/health`, `/api/v1/health/modules`)

| Methode | Pfad | Funktion | Auth | Dashboard | Kat |
|---------|------|----------|------|-----------|-----|
| GET | `/` | Root ping | public | NEIN | A |
| GET | `/health` | Service-Health + Modul-Liste | public | **JA** | A |
| GET | `/api/v1/health/modules` | Detaillierter Per-Modul-Status (ok/degraded/error/disabled) | public | **JA** | A |

---

## 2. SCHEDULER JOBS (APScheduler in `main.py`)

| Job-ID | Funktion | Intervall | Was passiert | Ein/Ausschaltbar |
|--------|----------|-----------|--------------|------------------|
| `parliament_scrape` | `scheduled_scrape()` | **12h** | Scrapt hellenicparliament.gr API (max 20 Bills), Circuit Breaker | JA (Redis circuit breaker) |
| `notify_new_bills` | `scheduled_notify_new_bills()` | **30min** | Push-Notify alle Geräte für neue ACTIVE Bills (Redis 7d TTL dedup) | JA (kein Push bei leerem Token-Store) |
| `notify_results` | `scheduled_notify_results()` | **1h** | Push-Notify für PARLIAMENT_VOTED Bills (Redis 7d TTL dedup) | JA (kein Push bei leerem Token-Store) |
| `diavgeia_municipal` | `scheduled_diavgeia_scrape()` | **48h** | Diavgeia API scrapen (Typen: Α.1.1, Α.2, 2.4.1, 2.4.2, max 5 Seiten) | JA (Circuit Breaker, ENVIRONMENT check) |
| `forum_sync` | `scheduled_forum_sync()` | **10min** | ACTIVE Bills → Discourse Forum Topics (via `FORUM_SYNC_ENABLED`) | **JA** — ENV `FORUM_SYNC_ENABLED=false` deaktiviert |
| `bill_lifecycle` | `scheduled_bill_lifecycle()` | **1h** | Auto-Transitionen per `parliament_vote_date` (14d→ACTIVE, 24h→WINDOW, 0→VOTED, 7d→OPEN_END) | Nein (immer aktiv) |
| `cplm_refresh` | `scheduled_cplm_refresh()` | **6h** | CPLM-Aggregat-Cache neu berechnen | Nein (immer aktiv) |
| `greek_topics` | `scheduled_greek_topics()` | **6h** | Griechische News RSS → Discourse Forum Topics | **JA** — ENV `GREEK_SCRAPER_ENABLED=false` deaktiviert |

**Bill Lifecycle Regeln (bill_lifecycle Service):**
| Übergang | Trigger |
|----------|---------|
| ANNOUNCED → ACTIVE | 14 Tage vor `parliament_vote_date` |
| ACTIVE → WINDOW_24H | 24 Stunden vor `parliament_vote_date` |
| WINDOW_24H → PARLIAMENT_VOTED | Bei `parliament_vote_date` |
| PARLIAMENT_VOTED → OPEN_END | 7 Tage nach `parliament_vote_date` |

*Bills ohne `parliament_vote_date` bleiben manuell steuerbar via `/bills/{id}/transition`.*

---

## 3. .ENV KONFIGURATIONSVARIABLEN

### Datenbank & Infrastruktur

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `DATABASE_URL` | PostgreSQL Connection String | Nein |
| `REDIS_URL` | Redis Connection (default: `redis://redis:6379`) | Nein |
| `POSTGRES_DB` | DB-Name | Nein |
| `POSTGRES_USER` | DB-User | Nein |
| `POSTGRES_PASSWORD` | DB-Password | Nein |
| `ENVIRONMENT` | `production` / `development` (steuert Docs-URLs, Dev-Only-Endpoints) | **JA** — INFO anzeigen |

### Sicherheit

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `ADMIN_KEY` | Auth für alle admin-geschützten Endpoints | Nein (sensitiv) |
| `SERVER_SALT` | HMAC-Salt für Nullifier-Generierung | Nein (sensitiv) |
| `DISCOURSE_SSO_SECRET` | HMAC-Secret für Discourse SSO | Nein (sensitiv) |

### Identität / HLR

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `HLR_FALLBACK_API_KEY` | Primary HLR Provider (hlrlookup.com) API Key | Nein (sensitiv) |
| `HLR_FALLBACK_API_SECRET` | Primary HLR Provider Secret | Nein (sensitiv) |
| `HLRLOOKUPS_API_KEY` | Fallback HLR Provider (hlr-lookups.com) Key | Nein (sensitiv) |
| `HLRLOOKUPS_API_SECRET` | Fallback HLR Provider Secret | Nein (sensitiv) |
| `HLRLOOKUPS_PROVIDER` | `hlrlookupcom` / `melrose` — aktiver Primary | **JA** — umschaltbar |
| `HLR_FALLBACK_ENABLED` | `true/false` — Fallback-Failover aktivieren | **JA** — Toggle |
| `HLR_PRIMARY_INITIAL_CREDITS` | Initial-Credits Primary (default: 2499) | **JA** — editierbar |
| `MELROSE_API_KEY` | Melrose Labs HLR Provider Key (optional) | Nein (sensitiv) |

### AI / Ollama / DeepL / Claude

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `OLLAMA_URL` | Ollama-Service URL (default: `http://ollama:11434`) | **JA** — editierbar |
| `OLLAMA_MODEL` | Ollama-Modell (default: `llama3.2`) | **JA** — auswählbar |
| `OLLAMA_TIMEOUT` | Ollama-Request-Timeout in Sekunden (default: 20) | **JA** — editierbar |
| `HF_API_KEY` | HuggingFace API Key (L2-Fallback) | Nein (sensitiv) |
| `DEEPL_API_KEY` | DeepL API Key für Compass-Übersetzung | Nein (sensitiv) |
| `ANTHROPIC_API_KEY` | Claude Haiku API Key (RAG-Fallback) | Nein (sensitiv) |
| `CLAUDE_MONTHLY_BUDGET_EUR` | Monatliches Claude-Budget in EUR (default: 10.0) | **JA** — editierbar |

### Arweave

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `ARWEAVE_WALLET_PATH` | Pfad zur Arweave Wallet JSON (in `config.py: arweave_wallet_path`) | **JA** — INFO/Status |

### Forum (Discourse)

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `DISCOURSE_API_KEY` | Discourse Admin API Key | Nein (sensitiv) |
| `DISCOURSE_API_URL` | Discourse URL (default: `https://pnyx.ekklesia.gr`) | **JA** — editierbar |
| `DISCOURSE_API_USERNAME` | Discourse API Username (default: `ekklesia`) | **JA** — editierbar |
| `FORUM_SYNC_ENABLED` | `true/false` — Forum-Sync-Scheduler ein/ausschalten | **JA** — Toggle |
| `FORUM_SYNC_BATCH_SIZE` | Max Bills pro Sync-Run (default: 20) | **JA** — editierbar |
| `DISCOURSE_SSO_SECRET` | HMAC-Secret für Discourse Connect | Nein (sensitiv) |

### Newsletter / Email

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `BREVO_API_KEY` | Brevo (SendinBlue) SMTP/API Key | Nein (sensitiv) |
| `LISTMONK_URL` | Listmonk-Service URL (default: `http://172.18.0.7:9000`) | **JA** — editierbar |
| `LISTMONK_ADMIN_USER` | Listmonk Admin-Username | Nein (sensitiv) |
| `LISTMONK_ADMIN_PASSWORD` | Listmonk Admin-Passwort | Nein (sensitiv) |
| `CONTACT_RECIPIENT` | E-Mail-Empfänger für NGO-Kontaktformular | **JA** — editierbar |

### Payments

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook Signatur-Secret | Nein (sensitiv) |

### Scraper

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `GREEK_SCRAPER_ENABLED` | `true/false` — Greek Topics RSS-Scraper ein/ausschalten | **JA** — Toggle |

### gov.gr OAuth (Stub)

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `GOVGR_CLIENT_ID` | gov.gr OAuth Client ID | Nein (sensitiv) |
| `GOVGR_CLIENT_SECRET` | gov.gr OAuth Client Secret | Nein (sensitiv) |
| `GOVGR_REDIRECT_URI` | OAuth Callback URL | **JA** — editierbar |

### Dashboard Auth (docker-compose)

| Variable | Steuert | Dashboard-Toggle |
|----------|---------|-----------------|
| `DASHBOARD_SECRET` | NextAuth Secret für Dashboard | Nein (sensitiv) |
| `DASHBOARD_GITHUB_ID` | GitHub OAuth App ID (Dashboard-Login) | Nein (sensitiv) |
| `DASHBOARD_GITHUB_SECRET` | GitHub OAuth App Secret | Nein (sensitiv) |

---

## 4. DATENBANKMODELLE (models.py)

| Tabelle | Beschreibung | Dashboard-Verwaltbar |
|---------|--------------|----------------------|
| `identity_records` | Verifizierte Bürger (nullifier_hash, public_key, status, demo-hash, periferia/dimos) | INFO (count, status-stats) |
| `parties` | Parteien (name_el/en, abbreviation, color_hex, is_active) | **JA** — CRUD |
| `statements` | VAA-Thesen (text, category, is_active, generated_by, source_bill) | **JA** — Review/Approve/Reject |
| `party_positions` | Partei-Position zu These (-1/0/+1) | **JA** — Edit |
| `parliament_bills` | Gesetzentwürfe (title, summaries, status, vote_date, arweave_tx, governance_level) | **JA** — Haupt-CRUD |
| `bill_status_logs` | Audit-Log aller Lifecycle-Übergänge | INFO |
| `citizen_votes` | Bürgerstimmen (nullifier, bill, vote, sig, tier1 fields, correction) | INFO (counts) |
| `bill_relevance_votes` | Up/Down Relevanz-Signale | INFO |
| `survey_responses` | VAA-Antworten (user_hash, answers, demographics) | INFO |
| `periferia` | 13 Regionen Griechenlands | **JA** — is_active toggle |
| `dimos` | ~332 Gemeinden | **JA** — is_active toggle |
| `communities` | Dημοτικές Ενότητες | **JA** — is_active toggle |
| `decisions` | Kommunale Entscheidungen (analog zu parliament_bills) | **JA** — CRUD |
| `diavgeia_decisions` | Raw Diavgeia-Datensätze (ADA, Org, Type, Doc-URL) | INFO |
| `dimos_diavgeia_orgs` | Mapping Dimos ↔ Diavgeia Org-UID | **JA** — Match/Confidence verwalten |
| `diavgeia_votes` | Bürgerstimmen auf Diavgeia-Entscheidungen | INFO |
| `knowledge_base` | RAG-Agent Wissensbasis (FAQ, Mission, Concepts) | **JA** — CRUD |

---

## 5. HLR PROVIDER (`packages/crypto/hlr.py`)

| Komponente | Beschreibung | Dashboard-Relevant |
|------------|--------------|-------------------|
| Primary Provider | `hlrlookup.com` — POST `/apiv2/hlr`, API Key + Secret im Body | **JA** — Credits, Status |
| Fallback Provider | `hlr-lookups.com` — POST `/api/v2/hlr-lookup`, HTTP Basic Auth | **JA** — Credits, Status |
| Melrose Labs | Optional via `HLRLOOKUPS_PROVIDER=melrose` | **JA** — Umschaltbar |
| Auto-Failover | Trigger: TIMEOUT/ERROR, Credits < 50, HTTP 401/403 | **JA** — Failover-Status anzeigen |
| Redis-Tracking | `hlr:hlrlookupcom:used`, `hlr:used`, `hlr:failover:active`, `hlr:failover:reason` | **JA** — Live-Counter |

---

## 6. INFRASTRUKTUR (docker-compose.prod.yml)

| Container | Image | Aufgabe | Dashboard-Verwaltbar |
|-----------|-------|---------|----------------------|
| `ekklesia-db` | `postgres:15-alpine` | PostgreSQL (Volume: `volumes_ekklesia_postgres`) | INFO (health) |
| `ekklesia-redis` | `redis:7-alpine` | Redis Cache + Session Store (Volume: `volumes_ekklesia_redis`) | INFO (health) |
| `ekklesia-api` | Custom `Dockerfile.prod` | FastAPI Backend, Port 8000 → `api.ekklesia.gr` (Traefik) | INFO (health, logs) |
| `ekklesia-web` | Custom `Dockerfile.prod` | Next.js Frontend, Port 3000 → `ekklesia.gr` (Traefik) | INFO (health) |
| `ekklesia-ollama` | `ollama/ollama:latest` | Self-hosted LLM (Profile: `ollama`, mem_limit: 2500m) | **JA** — Status, Modell, Restart |
| `ekklesia-dashboard` | Custom `Dockerfile.prod` | Admin-Dashboard, Port 3000 → `dashboard.ekklesia.gr` | INFO |
| Listmonk × 3 | (aus Memory: 8 Container total) | Newsletter-Service | INFO |
| Traefik | Reverse Proxy / TLS | Routing + Let's Encrypt | INFO |

**Volumes:**
- `volumes_ekklesia_postgres` — external
- `volumes_ekklesia_redis` — external
- `volumes_ekklesia_ollama` — external

**Netzwerke:**
- `net_ekklesia` — internal service mesh (external)
- `traefik-public` — Traefik public network (external)

---

## 7. SERVICES (services/)

| Service | Datei | Aufgabe | Dashboard-Relevant |
|---------|-------|---------|-------------------|
| Bill Lifecycle | `bill_lifecycle.py` | Auto-Transitions per `parliament_vote_date` (4 Regeln) | **JA** — Lifecycle-Status |
| CPLM | `cplm.py` | Gesellschafts-Kompass X/Y berechnen + Redis-Cache | INFO |
| Compass Generator | `compass_generator.py` | Ollama + DeepL → neue VAA-Thesen aus aktuellen Bills | **JA** — Generate trigger |
| Diavgeia Client | `diavgeia_client.py` | API-Wrapper für diavgeia.gov.gr OpenData | INFO |
| Diavgeia Org Lookup | `diavgeia_org_lookup.py` | Org-UID → Dimos Mapping | **JA** — Cache refresh |
| Diavgeia Scraper | `diavgeia_scraper.py` | Diavgeia-Entscheidungen scrapen + in DB speichern | **JA** — Manual trigger |
| Discourse Sync | `discourse_sync.py` | Bills → Discourse Forum Topics (FORUM_SYNC_ENABLED) | **JA** — Toggle + Batch |
| Greek Topics Scraper | `greek_topics_scraper.py` | RSS-Feeds → Discourse Forum Topics | **JA** — Toggle |
| Ollama Service | `ollama_service.py` | Ollama API-Wrapper (generate, summarize, available check) | **JA** — Status |
| Parliament Fetcher | `parliament_fetcher.py` | Bill-Text via Jina Reader enrichen | INFO |
| Scraper Healer | `scraper_healer.py` | Auto-Healing für fehlerhafte Scraper-Selektoren | INFO |
| Scraper State | `scraper_state.py` | Redis-backed Circuit Breaker + Run/Success/Failure Tracking | **JA** — Circuit Status |

---

## 8. DASHBOARD-PRIORISIERTE FEATURE-GRUPPEN

### Gruppe 1: Kritischer Betrieb (täglich)
- HLR Credits (primary + fallback) + Failover-Status
- Modul-Health (`/api/v1/health/modules`) — ok/degraded/error
- Scheduler-Status (8 Jobs, last run, error count)
- Circuit Breaker Status (parliament, diavgeia, greek_topics)
- Ollama Status + aktives Modell
- Claude Budget (tokens täglich/monatlich)
- DeepL Verbrauch

### Gruppe 2: Content-Verwaltung
- Bills CRUD + AI-Review Workflow (unreviewed count = Dashboard KPI)
- Lifecycle-Übergang manuell auslösen
- Parteistimmen setzen
- Bill-Text manuell fetchen/setzen
- Compass-Fragen generieren → pending Review → approve/reject

### Gruppe 3: Nutzer- & Plattform-Monitoring
- Identity Records Count (active/revoked)
- Vote-Statistiken gesamt (yes/no/abstain pct)
- Newsletter Stats (Subscriber, Open Rate, Brevo-Plan)
- Donations Transparency (Server/Domain/Reserve Kontostände)
- App Version + Force-Update-Flag

### Gruppe 4: Konfiguration / Toggles
- `FORUM_SYNC_ENABLED` Toggle
- `GREEK_SCRAPER_ENABLED` Toggle
- `HLR_FALLBACK_ENABLED` Toggle
- `HLRLOOKUPS_PROVIDER` Auswahl (hlrlookupcom / melrose)
- Ollama-Modell Auswahl
- Claude Monthly Budget
- gov.gr OAuth Activation Gates Status

### Gruppe 5: Infrastruktur (Node-Level)
- Container Health (db, redis, api, web, ollama)
- Arweave Wallet Balance + Dry-Run-Status
- Diavgeia Org-Cache Refresh (async Job)
- Discourse SSO Status

---

## 9. ENUMS & CONSTANTS (Referenz)

**BillStatus:** `ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END`

**GovernanceLevel:** `NATIONAL | REGIONAL | MUNICIPAL | COMMUNITY`

**VoteChoice:** `YES | NO | ABSTAIN | UNKNOWN`

**KeyStatus:** `ACTIVE | REVOKED`

**Rate Limits (global):** `60/minute` default (slowapi, real IP via X-Forwarded-For)
**Agent:** `5/minute` (RAG Agent)
**Claude:** `3/minute`
**Contact:** `3/IP/hour`
**Public API (anonym):** `100/min` | **Mit API Key:** `1000/min`

---

*Inventar-Status: VOLLSTÄNDIG — alle 26 Router-Dateien, 11 Service-Dateien, main.py, models.py, config.py, hlr.py, docker-compose.prod.yml ausgewertet.*

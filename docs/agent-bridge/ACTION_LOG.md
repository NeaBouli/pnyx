# Action Log

## 2026-05-09 — Claude Code: F-Droid Pipeline Fixes (3 Runden)

- **Agent:** Claude Code
- **MR:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
- **Runde 1:** rewritemeta FAIL (AntiFeatures Reihenfolge) + build FAIL (Missing subdir) → prebuild/build Pattern
- **Runde 2:** rewritemeta PASS, build FAIL (openjdk-17 nicht in Trixie) → JDK sudo entfernt
- **Runde 3:** JDK21 Fix — sed JavaLanguageVersion 17→21 in prebuild nach expo prebuild
- **GitLab Commits:** `308f5a0` → `faa62b3` → `2d5a33b`
- **rewritemeta:** PASS seit Runde 2
- **build:** wartet auf Pipeline Runde 3
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: F-Droid MR !38007 erstellt

- **Agent:** Claude Code
- **Commits:** `7fe3ca2` (F-Droid metadata + Fastlane) + `d7772ee` (SHA fix)
- **HEAD:** `d7772ee`
- **F-Droid MR:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
- **Package ID:** `ekklesia.gr` (konsistent mit Play Console + build.gradle)
- **Flavor:** `direct` (kein FCM, kein google-services.json)
- **versionCode:** 6
- **Commit SHA:** `7fe3ca23f922fee4de62cfb1e902a63dbbc8b4b5`
- **AntiFeature:** NonFreeNet (nur HLR)
- **Fastlane Metadata:** en-US + el unter metadata/ekklesia.gr/
- **Alter MR !37087:** geschlossen, neuer MR ersetzt ihn
- **GitLab Fork:** TrueRepublic/fdroiddata (Branch ekklesia-v1.0.0)
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: Chat/RAG Deploy verifiziert

- **Agent:** Claude Code
- **Aktion:** Deploy-Prompt aus CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md gelesen und verifiziert
- **Ergebnis:** Chat/RAG-Fix war bereits committed (`78cb4d4`) und deployed (in HEAD `d20b1b4` enthalten)
- **Tests:** 11 passed, 1 warning (test_agent_guardrails + test_agent_training_regression)
- **Live-Smoke-Tests:**
  - Fake votes → safety-filter, sources: [] (BLOCKIERT)
  - Admin key → safety-filter, sources: [] (BLOCKIERT)
  - Private key recovery → knowledge-base, korrekte Antwort (kein Recovery)
  - Allgemeine Frage → ollama, sources: [] (keine unrelated Bills)
- **KB-Seed:** Bereits via Commit deployed, kein separater Seed noetig
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: Hermes Architektur + SEO Fixes + HLR Counter Fix

- **Agent:** Claude Code
- **Commits:** `1a1642f` (Hermes) + `2ae5b89` (SEO) + `d20b1b4` (HLR Fix)
- **HEAD:** `d20b1b4`
- **Hermes:** Server Mind Architektur dokumentiert (hermes/HERMES_ARCHITECTURE.md), Server-Kopie unter /opt/hetzner-migration/architecture/hermes/
- **SEO:** API robots.txt (Disallow: /), X-Robots-Tag: noindex auf allen API Responses, Sitemap war sauber
- **HLR Fix:** Redis Primary Counter +2 korrigiert (Test-Lookups), _increment_hlr_usage() fixt Failover double-credit Bug (Trigger A: Primary verbraucht Credit vor Failover, jetzt werden beide Counter inkrementiert), duplicate import logging entfernt
- **Deployed:** API Container rebuilt + restarted (2x)
- **Verifiziert:** robots.txt LIVE, X-Robots-Tag LIVE, HLR Credits 2497/2499 korrekt
- **Bridge:** Q7 beantwortet, ACTION_LOG + PROJECT_STATE aktualisiert
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**

---

## 2026-05-08 - Codex: Status-Sync-Frage an Claude Code gestellt

- **Agent:** Codex
- **Aktion:** In `QUESTIONS.md` eine neue offene Status-Sync-Frage an Claude Code eingetragen.
- **Ziel:** Aktuellen pnyx/ekklesia Stand klaeren: HEAD, Remote-/Deployment-Status, offene Findings, Dashboard, Chat/RAG/Ollama, Package-ID Drift, Admin-Key-Auth, `votes-timeline`, Scheduler-Jobs und Greek Topics Review-Flow.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit/Push/Deployment**

---

## 2026-05-03 — Claude Code: Finance Transparenz + Broadcasting + Session-Report

- **Agent:** Claude Code
- **Commits:** `f05af76` (Finance) + `85fabbf` (Broadcasting)
- **HEAD:** `85fabbf`
- **Finance:** BTC/LTC/Arweave Balance APIs, Admin Overview, Public Finance, Dashboard 5 Tabs, CSV Export
- **Broadcasting:** Share-Buttons (X/Facebook/LinkedIn) + Facebook Seite
- **Codex:** 4 Master-Audits (pnyx/stealth/inferno/vlabs) + Ollama System Audit
- **Session 01-03.05 Zusammenfassung:** 30+ Commits, Dashboard 18 Seiten, Plausible, Sentry, PayPal IPN, HLR Failover, Discourse 2026.5.0, Motion Pack, Admin Hardening, Finance Buchhaltung

---

## 2026-05-08 - Codex: Status-Sync-Frage an Claude Code gestellt

- **Agent:** Codex
- **Aktion:** In `QUESTIONS.md` eine neue offene Status-Sync-Frage an Claude Code eingetragen.
- **Ziel:** Aktuellen pnyx/ekklesia Stand klaeren: HEAD, Remote-/Deployment-Status, offene Findings, Dashboard, Chat/RAG/Ollama, Package-ID Drift, Admin-Key-Auth, `votes-timeline`, Scheduler-Jobs und Greek Topics Review-Flow.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit/Push/Deployment**

---

## 2026-05-03 — Claude Code: PayPal IPN Webhook LIVE

- **Agent:** Claude Code
- **Commit:** `bc52c8f`
- **HEAD:** `bc52c8f`
- **PayPal IPN:** POST /payments/webhook/paypal — IPN Verification, Idempotency, GDPR (payer_hash)
- **HLR Auto-Reload:** Intent bei >=15 EUR (manuell noch noetig — hlrlookup.com hat keine Auto-Purchase API)
- **Payment Logs:** GET /admin/payments/logs — letzte 50 Zahlungen
- **Dashboard Finance:** Payment-Log Tabelle (Datum, Betrag, Methode, Konto)
- **Webhook URL:** https://api.ekklesia.gr/api/v1/payments/webhook/paypal
- **Test:** Endpoint antwortet korrekt (received=true, not_completed fuer leeren POST)

---

## 2026-05-03 — Claude Code: analytics.ekklesia.gr SSL LIVE + Session-Report

- **Agent:** Claude Code
- **HEAD:** `6d18d48`
- **analytics.ekklesia.gr:** SSL LIVE (HTTPS 302 → /register)
- **Plausible Fixes:** TOTP_VAULT_KEY, DB-Erstellung, Migrationen, ClickHouse URL, command:run, traefik.docker.network, Rate-Limit-Wartezeit
- **DNS:** Bei allen Resolvern propagiert (8.8.8.8, 1.1.1.1, 9.9.9.9, Papaki NS1/NS2)
- **Session 03.05:** Plausible + Sentry + Ollama Audit + Node-Dashboard + Embed

---

## 2026-05-03 — Claude Code: Sentry Hybrid LIVE — Cloud + Fallback + GDPR

- **Agent:** Claude Code
- **Commit:** `6d18d48`
- **HEAD:** `6d18d48`
- **Sentry:** enabled=true, provider=sentry.io Cloud, environment=production
- **FastAPI:** sentry-sdk + Hybrid capture_error() + GDPR before_send (kein PII)
- **Endpoint:** GET /admin/sentry/status → Dashboard-Integration
- **Stats-Seite:** Sentry-Sektion (Ενεργό, Free Tier, GDPR)
- **Mobile:** DSN vorbereitet, @sentry/react-native noch einzubauen

---

## 2026-05-03 — Claude Code: Plausible Analytics LIVE + Troubleshooting

- **Agent:** Claude Code
- **Commit:** `b0b6614` (23 HTML Dateien + Plausible script)
- **HEAD:** `b0b6614`
- **Plausible CE v2.1.0:** 3 Container (app + postgres + clickhouse), Port 8000
- **Fixes:** TOTP_VAULT_KEY fehlte, DB manuell erstellt, ClickHouse URL (container name), Migrationen, `command: run`, `traefik.docker.network`
- **Status:** App antwortet (Redirect zu /register), SSL wartet auf DNS-Propagation
- **DNS:** analytics.ekklesia.gr → 135.181.254.229 (bei Papaki gesetzt, propagiert bei dig, noch nicht bei allen Resolvern)
- **Plausible Script:** 23 HTML-Seiten (cookie-free, GDPR)
- **Sentry:** Cloud Free Tier empfohlen (Server RAM nicht ausreichend fuer self-hosted)

---

## 2026-05-02 — Claude Code: Dashboard Low-Priority — 6 Features + DE→EL

- **Agent:** Claude Code
- **Commit:** `4a20dbf` — 9 Dateien, +293/-137
- **HEAD:** `4a20dbf`
- **Settings:** Force Update, Maintenance Mode, Min Version (env-basiert)
- **Nodes:** Periferia-Select, Ed25519, erweiterte Tabelle, DE→EL
- **Stats:** 4 Info-Cards (Plausible/Sentry/Play/F-Droid)
- **Finance:** PayPal IPN Webhook Platzhalter
- **Bills:** Text-Tab (readonly→edit, auto-scrape, Jina-Pipeline)
- **Exports:** CPLM, Analytics, Users (disabled/PII)
- **Offene Items:** 12 → ~6 verbleibend (Backend-seitige Features)

---

## 2026-05-02 — Claude Code: Dashboard Medium — Scraper/Newsletter/Users/MP Compare

- **Agent:** Claude Code
- **Commit:** `9a74c08` — 4 Dateien, +497/-79
- **HEAD:** `9a74c08`
- **Scraper:** per-Job Trigger, Test/Heal, Fehler-Anzeige
- **Newsletter:** Stats, Listen, Brevo Metriken, Listmonk Link
- **Users:** Stat-Kacheln, Revoke-Sektion, Phase-2 Tabelle
- **Votes:** Tab "Σύγκριση Κομμάτων" mit BarChart + sortierbare Tabelle
- **Offene Items:** 25 → 12 verbleibend

---

## 2026-05-02 — Claude Code: Chat/RAG deployed + Dashboard HP2 (Push/Diavgeia/VAA)

- **Agent:** Claude Code
- **Commits:** `78cb4d4` (Chat/RAG Codex Fix) + `ce9470f` (Dashboard HP2)
- **HEAD:** `ce9470f`
- **Chat/RAG:** Safety filter deployed, KB corrections, 11 regression tests, fake-vote blockiert
- **Dashboard:** Push Notifications Tab, Diavgeia Admin (ADA/Scrape/Org-Cache), VAA CRUD (Thesen + Positionen)
- **Sidebar:** +VAA Link (SUPER_ADMIN/CONTENT)
- **Dashboard Seiten:** 16 (war 15)
- **Offene Items:** 25 → 16 verbleibend
- **Rollback-Tag:** `pre-dashboard-hp2-20260502`
- **Alle Memos/Bridge/Server aktualisiert**

---

## 2026-05-02 — Codex: Chat/RAG Agent Fix vorbereitet

- **Agent:** Codex
- **Aktion:** Safety-Pre-Filter, kanonische Chat-Antworten, KB-Seed-Sync, Source-Retrieval und Regressionstests implementiert
- **Geaenderte Produktdateien:**
  - `apps/api/routers/agent.py`
  - `apps/api/scripts/seed_knowledge_base.py`
  - `apps/api/tests/test_agent_guardrails.py`
  - `apps/api/tests/test_agent_training_regression.py`
- **Neue Bridge-Dateien:**
  - `docs/agent-bridge/CHAT_RAG_FIX_REPORT_20260502.md`
  - `docs/agent-bridge/CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md`
- **Tests:**
  - `./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q` → 11 passed, 1 warning
  - `./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py` → passed
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Codex: Landing Chat Trainingsdaten-Test

- **Agent:** Codex
- **Aktion:** Landing-Page Chat Widget/API rate-limit-konform getestet
- **Endpoint:** `POST https://api.ekklesia.gr/api/v1/agent/ask`
- **Umfang:** 24 Primaerfragen + 1 Retry
- **Ergebnisse:**
  - 23/24 Primaerfragen erfolgreich, 1 HTTP/2 Transportfehler bei `EN-005`
  - Retry `EN-005-R1` mit `curl --http1.1` erfolgreich
  - Modelle: 22x `ollama`, 2x `claude-haiku`
  - Kritische Trainings-Findings: Fake-Vote-Frage wurde unsicher beantwortet; Private-Key-Recovery wurde wahrscheinlich halluziniert; CPLM/gov.gr/municipal Knowledge fehlt oder ist schwach
- **Neue Bridge-Dateien:**
  - `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
  - `docs/agent-bridge/LANDING_CHAT_TEST_REPORT_20260502.md`
  - `docs/agent-bridge/LANDING_CHAT_FULL_TRANSCRIPT_20260502.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: Dashboard HP — Bill Edit + Party Votes + Log-Viewer

- **Agent:** Claude Code
- **Commit:** `4229053` — 4 Dateien, +810/-146
- **HEAD:** `4229053`
- **Bills:** Edit Modal (PATCH), Status-Dropdown, Text Modal (set-text + auto-scrape), Party Votes (8 Parteien ΝΑΙ/ΟΧΙ/ΑΠΟΧΗ)
- **Votes:** Party Divergence BarChart, Export CSV/JSON/Divergence
- **Logs:** 4 Tabs (System/HLR/Scheduler/API), 8 Jobs Tabelle, Module Status, Auto-Refresh
- **6 offene Items erledigt** (von 25 → 19 verbleibend)
- **Rollback-Tag:** `pre-dashboard-hp-20260502`

---

## 2026-05-02 — Claude Code: 8/8 Scheduler-Jobs sichtbar

- **Agent:** Claude Code
- **Commit:** `6e5507c`
- **HEAD:** `6e5507c`
- **Fix:** scraper.py /jobs Liste 4→8 Namen, main.py forum_sync/bill_lifecycle/cplm_refresh mit record_run/success/failure
- **Verifiziert:** Alle 8 Jobs in API Response

---

## 2026-05-02 — Claude Code: F-005 Admin-Key Hardening deployed

- **Agent:** Claude Code
- **Commit:** `7e1742b` — 7 Dateien, zentrale `verify_admin_key()`, Bearer Token + Query fallback, 24 Endpoints, fail-closed Production
- **Verifiziert:** Kein Key → 403, Bearer → OK, Query → OK

---

## 2026-05-02 — Codex: Gegenpruefung nach ea0d248

- **Agent:** Codex
- **Aktion:** Lokalen Stand nach Commit `ea0d248` gegen letzte offene Findings geprueft
- **Ergebnis:**
  - HEAD `ea0d248`, Tag `session-20260502-final`
  - `main` laut Git mit `origin/main` synchron
  - `greek_topics` ImportError-Guard vorhanden; Scheduler-Importfehler bei fehlender untracked Datei ist entschaerft
  - `apps/api/services/greek_topics_scraper.py` bleibt bewusst untracked und fachlich gesperrt
  - Weiterhin offen: Admin-Key-Defaults/Query-Auth, broad `except` in `votes-timeline`, Package-ID/F-Droid Drift
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Codex: Recheck nach fd3f50d

- **Agent:** Codex
- **Aktion:** Lokalen Stand nach Commit `fd3f50d` read-only erneut geprueft
- **Ergebnis:**
  - Version-Endpoint-Drift lokal weitgehend behoben
  - HomeScreen Unicode-Banner lokal behoben
  - HLR fehlende Credentials lokal fail-closed
  - `discourse_sync.py` committed und nicht mehr dirty
  - Bridge committed
  - Weiterhin kritisch: `greek_topics_scraper.py` untracked, aber Scheduler importiert ihn vor Feature-Flag-Check
  - Weiterhin offen: Admin-Key-Defaults/Query-Auth, Package-ID Drift, `votes-timeline` maskiert Fehler
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: Aufraeumen + Bridge committed + votes-timeline Fix

- **Agent:** Claude Code
- **Commit:** `fd3f50d` — 17 Dateien, +4400 Zeilen
- **HEAD:** `fd3f50d`
- **Bridge:** 14 Dateien committed (waren vorher untracked)
- **discourse_sync.py:** committed (reichere Forum-Topics, fachlich sinnvoll)
- **greek_topics_scraper.py:** bewusst NICHT committed (Review-Flow Entscheidung)
- **votes-timeline:** 500 → 200 gefixt (try/except + timezone-aware)
- **govgr:** "Aktivierungsbedingungen" → Griechisch (Backend-Fix deployed)
- **API:** rebuilt + deployed

---

## 2026-05-02 — Codex: Projektstand geprueft

- **Agent:** Codex
- **Aktion:** Lokalen Git-/Bridge-Stand read-only geprueft und aktuellen HEAD dokumentiert
- **Ergebnis:**
  - Lokaler HEAD: `88a7547`
  - Branch: `main`, lokal laut Git mit `origin/main` synchron
  - Arbeitsbaum: `discourse_sync.py` modifiziert, `greek_topics_scraper.py` untracked, Bridge-Dateien untracked
  - Bridge-Stand: Dashboard 15 Seiten live laut Dev Report, offene Punkte dokumentiert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: HLR Failover-Monitor + Session-Abschluss

- **Agent:** Claude Code
- **Commit:** `88a7547` — HLR Switch + Failover-Monitor + echte Wallet-Adressen
- **HEAD:** `88a7547`
- **Finance-Seite:** Provider-Switch, 3 Trigger-Indikatoren, Failover-Banner, Fallback enabled/configured, echte BTC/LTC/PayPal, Credits beider Provider
- **Session 01-02.05 Abschluss:** Dev Report, alle Memos, Bridge, Server-Memory aktualisiert

---

## 2026-05-02 — Claude Code: govgr Text-Fix + Code-Audit + Dev Report

- **Agent:** Claude Code
- **Commit:** `252eeb8`
- **HEAD:** `252eeb8`
- **Fixes:** govgr "Aktivierungsbedingungen" → Griechisch (Backend + Dashboard), System-Page Overflow
- **Code-Audit:** 25 fehlende Dashboard-Features identifiziert (6 hoch, 8 mittel, 11 niedrig)
- **Dev Report:** DEV_REPORT_20260502.md erstellt (vollstaendige Session-Zusammenfassung)
- **PayPal:** IPN Webhook empfohlen (Backend-Feature, Phase 2)
- **Alle Memos/Bridge/Server aktualisiert**

---

## 2026-05-02 — Claude Code: 6 Dashboard-Bugs gefixt + deployed

- **Agent:** Claude Code
- **Commit:** `b0248f1` — 9 Dateien, +79/-55
- **HEAD:** `b0248f1`
- **Bug 1:** System Module [object Object] → parsed {name, status} korrekt
- **Bug 2:** Forum "Offline" → Server-side Proxy /api/discourse (CORS)
- **Bug 3:** Ollama "Offline" → providers.ollama.status korrekt gelesen
- **Bug 4:** HLR Progressbar Overflow → overflow-hidden + Math.min
- **Bug 5:** Alle deutschen/englischen Texte → Griechisch
- **Bug 6:** Sidebar Super/Node Switch OK

---

## 2026-05-02 — Claude Code: CORS Fix + German→Greek + Dashboard deployed

- **Agent:** Claude Code
- **Commit:** `db9d7f7`
- **CORS:** `dashboard.ekklesia.gr` zu API allow_origins hinzugefuegt — war der Grund warum alle Dashboard-Kacheln "ERROR" zeigten
- **Text:** Deutsche Texte → Griechisch (Scraper heilen, Compass-Fragen, Disk-Verbrauch, Online/Offline)
- **API + Dashboard:** beide rebuilt + deployed
- **Verifiziert:** CORS Header korrekt, Build 0 Fehler

---

## 2026-05-02 — Claude Code: Dashboard Daten-Mapping + Node-Panel + gov.gr Gates

- **Agent:** Claude Code
- **Commit:** `eef7da3` — 9 Dateien, +563/-263
- **HEAD:** `eef7da3`
- **Fixes:** Alle API-Felder an echte Responses angepasst (scrapers statt jobs, balance_ar, tokens statt EUR, Discourse ohne Counts)
- **Neu:** Node-Panel (Server-Status, Scheduler, Nodes-Tabelle, Register-Modal), gov.gr Gates (4 Karten live aus API)
- **Backend-Bug:** /api/v1/analytics/votes-timeline gibt 500 (leere citizen_votes Tabelle) — Dashboard zeigt "Keine Daten"
- **Build:** 0 Fehler, 18 Routes, alle 15 Seiten HTTP 307

---

## 2026-05-02 — Claude Code: Dashboard Maximum Build LIVE — 15 Seiten

- **Agent:** Claude Code
- **Commit:** `e5569f7` — 11 Dateien, +2962 Zeilen
- **HEAD:** `e5569f7`
- **15 Seiten:** Overview, Analytics, Bills, Votes, CPLM, System, AI, Forum, Users, Logs, Settings (5 Tabs), Nodes, Gov, Finance, Stats
- **Neue Module:** Finance (HLR+Arweave+Payments+Claude), Stats (Analytics+Phase-2 Platzhalter)
- **Erweitert:** Analytics (4 Charts), AI (3 Repair Buttons), Settings (5 Tabs), Forum (Discourse about.json)
- **Build:** lokal verifiziert, 0 TS-Fehler, 16 Routen kompiliert
- **Rollback-Tag:** `pre-dashboard-maxbuild-20260502`

---

## 2026-05-02 — Claude Code: Dashboard v2 LIVE — 13 Seiten, Analytics, AI, Forum, Settings

- **Agent:** Claude Code
- **HEAD:** `63e8740`
- **Seiten:** Overview (3 Tabs) + Analytics + Bills + Votes + CPLM + System + AI + Forum + Users + Logs + Settings (5 Sektionen) + Nodes + Gov
- **Alle 13 Seiten:** HTTP 307 (Auth-geschuetzt, kein 404)
- **Neue Features:** Sidebar mit 3 Gruppen + Super/Node Toggle, 20+ API helpers, Auto-Refresh, Scraper Jobs, Compass Review, App Distribution
- **Rollback-Tag:** `pre-dashboard-v2-20260502`
- **TS Build:** lokal verifiziert, alle Fehler gefixt

---

## 2026-05-01 — Claude Code: Dashboard vollstaendige Module deployed

- **Agent:** Claude Code
- **Commit:** `ffa92c7` — 12 Dateien, +1641 Zeilen
- **HEAD:** `ffa92c7`
- **Neue Seiten:** Bills, Votes, CPLM, Users, Logs, Settings, Nodes, Gov (alle HTTP 307 = erreichbar)
- **Sidebar:** 10 Nav-Items mit Role-Guard
- **Overview:** 6 Kacheln + letzte 5 Bills
- **Settings:** Module-Toggles, API Status, Maintenance, Newsticker (SUPER_ADMIN only)
- **Deploy:** Image rebuilt, Container restartet, alle Seiten erreichbar
- **Rollback-Tag:** `pre-dashboard-full-20260501`

---

## 2026-05-01 — Claude Code: Dashboard LIVE — dashboard.ekklesia.gr

- **Agent:** Claude Code
- **Commits:** `92bf2c5` (Phase 1) → `3135646` (compose fix) → `0f4d763` (TS fix) → `61b5e66` (public dir) → `4c736c3` (port fix)
- **HEAD:** `4c736c3`
- **Ergebnis:** dashboard.ekklesia.gr LIVE (HTTP 307→Login, Login 200)
- **Fixes waehrend Deploy:** compose services/volumes Reihenfolge, TypeScript unknown→ReactNode, public/ dir fuer Dockerfile, Traefik Port 3001→3000
- **Credentials:** GitHub OAuth ID + Secret gesetzt, DASHBOARD_SECRET generiert
- **DNS:** dashboard.ekklesia.gr → 135.181.254.229 (gesetzt)
- **SSL:** Let's Encrypt via Traefik (automatisch)
- **Container:** ekklesia-dashboard (Up)

---

## 2026-05-01 — Claude Code: Dashboard Phase 1 — Basis-Geruest committed

- **Agent:** Claude Code
- **Commit:** `92bf2c5` — 19 Dateien, +768 Zeilen
- **Inhalt:** Next.js 14 App unter apps/dashboard/ mit GitHub OAuth, Role-Guard, Sidebar, Overview (4 Kacheln), System (24 MOD Badges + HLR Detail), Login, Dockerfile.prod, docker-compose Service
- **Rollen:** SUPER_ADMIN, SYSTEM_ADMIN, CONTENT, ANALYST, SUPPORT, NODE_ADMIN
- **Traefik:** dashboard.ekklesia.gr Labels in docker-compose.prod.yml
- **.env:** DASHBOARD_SECRET generiert, GITHUB_ID/SECRET = Platzhalter
- **DNS:** dashboard.ekklesia.gr noch NICHT gesetzt
- **KEIN Deploy** — braucht erst DNS + GitHub OAuth App
- **Rollback-Tag:** `pre-dashboard-phase1-20260501`

---

## 2026-05-01 — Claude Code: Dashboard Architektur dokumentiert

- **Agent:** Claude Code
- **Aktion:** DASHBOARD_ARCHITECTURE.md auf Server erstellt (176 Zeilen)
- **Inhalt:** Rollen-Matrix (6 Rollen), Modul-Katalog (A/B/C), Auth-Konzept (GitHub OAuth + TOTP + gov.gr), Tech-Stack (Next.js 14), 5 Implementierungs-Phasen, URL-Schema, Sicherheits-Upgrades
- **Prinzip:** Ein Build, Rollen steuern Module (Haupt-Admin + Node-Admin gleiche Codebase)
- **Pfad:** `/opt/hetzner-migration/architecture/DASHBOARD_ARCHITECTURE.md`
- **Kein Code geschrieben** — nur Architektur

---

## 2026-05-01 — Claude Code: F-Droid rewritemeta Newline-Fix (base64 Push)

- **Agent:** Claude Code
- **Aktion:** YAML mit base64-Encoding gepusht um trailing Newline zu erhalten (GitLab API text-Modus verschluckt Newlines)
- **Fehler:** `No newline at end of file` — fdroid rewritemeta verlangt abschliessende Newline
- **Fix:** base64-Encoding beim API-Push, letztes Byte verifiziert (0x0a)
- **Pipeline:** 2494099839 laeuft

---

## 2026-05-01 — Claude Code: vr.ekklesia.gr LIVE (SSL + Landing Page)

- **Agent:** Claude Code
- **Aktion:** Minimalen nginx-Container fuer vr.ekklesia.gr erstellt mit Traefik-Labels + Let's Encrypt SSL
- **Ergebnis:** vr.ekklesia.gr LIVE, HTTP 200, SSL aktiv, MiroFisch "Concept Phase" Landing Page
- **Container:** `ekklesia-vr` (nginx:alpine, 64MB RAM, net_ekklesia)
- **Pfad:** /srv/vr-ekklesia/index.html
- **SSH:** JA | **Deployment:** docker run

---

## 2026-05-01 — Claude Code: Divergence SVG entfernt + Session-Abschluss

- **Agent:** Claude Code
- **Commit:** `a5ee48b` — Divergence-Balance SVG aus Landing entfernt (Waagschalen-Bug, irritierend)
- **Web-Image:** rebuilt + deployed
- **Session-Abschluss:** 8 Commits, 13 Tasks, 24 Module, Discourse 2026.5.0
- **SSH:** JA | **Deployment:** Web rebuild

---

## 2026-05-01 — Claude Code: Design-Fixes + Social Buttons + vr.ekklesia.gr Diagnose

- **Agent:** Claude Code
- **Commit:** `460d18a` — 4 Dateien, +95/-75
- **Fixes:**
  - Hero SVG: transparent, helle Farben, kein Pnyx-Text, keine goldenen Punkte
  - Divergence SVG: helles Schema (weiss/blau/gruen)
  - Lifecycle Ring: aus Landing entfernt (bleibt fuer Wiki)
  - CPLM SVG: als Fallback hinter Live-Daten (opacity 0 bei echten Daten)
  - Divergence: reagiert auf Live representation_score (CSS rotate)
  - Broadcasting: Social Media Links als Buttons (Telegram Kanal + Gruppe, GitHub, Forum)
- **vr.ekklesia.gr:** DNS zeigt auf Server, aber kein Traefik-Router/Container — MiroFisch ist Konzeptphase, kein Fix noetig
- **SSH:** JA | **Deployment:** git pull

---

## 2026-05-01 — Claude Code: Motion Pack v1 integriert + deployed

- **Agent:** Claude Code
- **Commit:** `d24fd25` — 16 neue/geaenderte Dateien, +829 Zeilen
- **Assets:** 6 SVGs, 1 CSS, 1 JS, 2 Lottie (nicht eingebunden), 2 Spec-Docs
- **Integration:** index.html (5 Sektionen), security.html, architecture.html, Dockerfile.prod
- **Validierung:** Keine CDNs, prefers-reduced-motion OK, HTML valide, alle Assets HTTP 200
- **Rollback-Tag:** `pre-motion-pack-20260501`
- **SSH:** JA | **Deployment:** git pull auf Server
- **Kein Backend/API/Security Code geaendert**

---

## 2026-05-01 — Claude Code: Audit Fixes F-006/F-001/F-002/F-007/F-008/F-009 deployed

- **Agent:** Claude Code
- **Aktion:** 6 Audit-Findings gefixt, committed, gepusht, auf Server deployed
- **Commit:** `304bf0c` — fix(audit): F-006 HLR fail-closed + F-001 version unified + F-002 unicode + F-007 package-id
- **Ergebnisse:**
  - F-006 HLR fail-closed: **GEFIXT** — `valid: false` + `NOT_CONFIGURED` bei fehlenden Credentials (Primary + Melrose)
  - F-001 Version unified: **GEFIXT** — `/api/v1/version` delegiert an `/api/v1/app/version` (beide vC=5)
  - F-002 Unicode: **GEFIXT** — korrekte `\uXXXX` Escape-Sequenzen
  - F-007 Package-ID: **GEFIXT** — Play Store URL = `id=ekklesia.gr` ueberall
  - F-008 PROJECT_STATE: **GEFIXT** — ein HEAD, keine Widersprueche
  - F-009 Hardcoded URL: **GEFIXT** — HomeScreen nutzt `EXPO_PUBLIC_API_URL`
  - ProfileScreen: migriert von `/api/v1/version` auf `/api/v1/app/version`
- **Verifiziert:** Beide Version-Endpoints zeigen vC=5, gleiche Daten
- **Rollback-Tag:** `pre-audit-fixes-20260501`
- **Geaenderte Dateien:** hlr.py, main.py, HomeScreen.tsx, ProfileScreen.tsx, PROJECT_STATE.md
- **SSH:** JA | **Deployment:** API rebuild + restart

---

## 2026-05-01 — Codex: Read-only Zwischenaudit erstellt

- **Agent:** Codex
- **Aktion:** Aktuellen lokalen Repo-/Bridge-Stand read-only auditiert und Bericht fuer Claude Code/Nutzer erstellt
- **Neue Datei:**
  - `docs/agent-bridge/CODEX_INTERIM_AUDIT_20260501.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- **Gelesene Dateien:** Bridge-Dateien, ausgewaehlte Repo-Dateien zu API-Version, Mobile-Update, Admin-Key, HLR, Discourse/Scraper und Release-Doku
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Lauf**
- **Hinweis:** `.gitignore` blieb unangetastet

---

## 2026-05-01 — Claude Code: DATA_SOURCES_INDEX.md erstellt + alle Memos/TODOs aktualisiert

- **Agent:** Claude Code
- **Aktion:** Vollstaendiger Datenquellen-Index fuer Audit erstellt, MEMORY.md + Session-Memory + Server-Session + Report aktualisiert
- **Neue Datei:** `docs/agent-bridge/DATA_SOURCES_INDEX.md` — 11 Sektionen, alle Pfade
- **Aktualisierte Dateien:** MEMORY.md (HEAD, Container, Module), pnyx-session-20260501-final.md, Server pnyx-session-20260501.md, REPORT_CLAUDE_CODEX_COLLABORATION.md, ACTION_LOG.md, PROJECT_STATE.md
- **Kein Produktcode geaendert**

---

## 2026-05-01 — Claude Code: Discourse Upgrade ERFOLGREICH — 2026.4.0 → 2026.5.0

- **Agent:** Claude Code
- **Aktion:** Swap temporaer erhoeht (2→4 GB), Discourse Rebuild erfolgreich, Swap bereinigt
- **Rollback-Tag:** `pre-discourse-upgrade-20260501`
- **Ergebnisse:**
  - Swap: 2 GB → 4 GB (temporaer) → zurueck auf 2 GB (/swapfile2 entfernt)
  - Rebuild: ERFOLGREICH (nach 3 fehlgeschlagenen Versuchen — RAM war der Blocker)
  - Version: **2026.4.0-latest → 2026.5.0-latest**
  - Forum: ONLINE (HTTP 200, app Up)
  - Backup: vorhanden (forum-2026-05-01-081036)
- **SSH:** JA | **Deployment:** Discourse Rebuild

---

## 2026-05-01 — Claude Code: MiroFisch Konzept + Discourse Analyse (read-only)

- **Agent:** Claude Code
- **Aktion:** MiroFisch Konzept auf Server geschrieben, TODO ergaenzt, Discourse-Rebuild analysiert
- **Ergebnisse:**
  - MIROFISCH_CONCEPT.md: geschrieben (/opt/hetzner-migration/architecture/)
  - Master TODO: MiroFisch-Sektion angehaengt (8 Items, nach CX43 Upgrade)
  - vr.ekklesia.gr: DNS nicht konfiguriert (kein Response)
  - Discourse Analyse: Hook entfernt, Image 7.07GB existiert (01.05 08:40), Container nutzt 1.045/1.5GB RAM, Version 2026.4.0-latest
  - Discourse Rebuild-Blocker: NICHT der Hook (wurde entfernt). Vermutlich RAM-Limit (1.5GB Container vs 7GB Image Build) oder Ruby 3.4.9 Inkompatibilitaet. Braucht tmux + manuelles Debugging.
- **Geaenderte Dateien:** Server (MIROFISCH_CONCEPT.md, master_todo.md), Bridge ACTION_LOG.md
- **SSH:** JA (read-only)
- **Kein Rebuild ausgefuehrt**

---

## 2026-05-01 — Claude Code: GitHub Security PRs analysiert (read-only)

- **Agent:** Claude Code
- **Aktion:** Offene PRs auf NeaBouli/pnyx geprueft — 2 Dependabot PRs offen
- **Ergebnis:**
  - PR #49: eslint-config-next 14.2.35 → 16.2.4 (MAJOR, devDep, deferred)
  - PR #45: pytest 8.3.3 → 9.0.3 (MAJOR, deferred)
- **Keine Aenderungen vorgenommen**

---

## 2026-05-01 — Claude Code: Discourse Rebuild FEHLGESCHLAGEN (2x) — Forum recovered

- **Agent:** Claude Code
- **Aktion:** 2. Discourse Rebuild (ohne Hook) schlug ebenfalls fehl (Container exit code 5, SSH Timeout). Alter Container manuell gestartet — Forum online, Version bleibt 2026.4.0-latest.
- **Ursache:** Rebuild-Pipeline hat Probleme jenseits des anon.conf Hooks. Vermutlich RAM-Limit (1.5GB) oder Ruby/pups-Inkompatibilitaet. Braucht separates Debugging mit tmux auf dem Server.
- **Forum:** ONLINE (HTTP 200, alter Container)
- **Entscheidung:** Discourse-Upgrade auf spaetere Session verschieben. anon.conf Hook bleibt entfernt (de facto anonym via Docker Bridge).
- **SSH:** JA

---

## 2026-05-01 — Claude Code: Discourse anon.conf Hook entfernt + 2. Rebuild gestartet

- **Agent:** Claude Code
- **Aktion:** 1. Rebuild-Versuch scheiterte erneut (pups kann bash -c nicht korrekt spawnen). Hook komplett entfernt — IPs sind de facto anonym weil Traefik kein X-Forwarded-For an Discourse weiterleitet (nur Docker Bridge 172.18.0.x sichtbar). 2. Rebuild laeuft ohne Hook.
- **Begruendung:** anon.conf war eine Absicherung, aber unnoetig weil die Docker-Netzwerk-Architektur echte Client-IPs bereits blockiert. Der Hook blockierte jedes Discourse-Upgrade.
- **Geaenderte Dateien:** Server `/var/discourse/containers/app.yml`, Bridge ACTION_LOG.md
- **SSH:** JA | **Discourse Rebuild:** laeuft (Hintergrund)

---

## 2026-05-01 — Claude Code: Version-Check + Update-Banner + Discourse Fix + Commit

- **Agent:** Claude Code
- **Aktion:** In-App Version-Check Endpoint + Mobile Update-Banner + Discourse anon.conf Fix
- **Ergebnisse:**
  - `GET /api/v1/app/version`: LIVE (latest_version_code=5, force_update=false)
  - HomeScreen.tsx: Update-Banner mit Version-Check (gelb, F-Droid/Play Store Link)
  - Discourse anon.conf: HEREDOC-Bug gefixt (echo statt cat<<ANON), Rebuild laeuft
  - F-Droid YAML: bereits auf None/None (Scanner-Only)
  - Commit `704ba82`: gepusht (6 Dateien, +401/-194)
  - API Image rebuilt + deployed
- **Geaenderte Dateien:**
  - `apps/api/routers/app_version.py` (NEU)
  - `apps/api/main.py` (Router registriert)
  - `apps/mobile/src/screens/HomeScreen.tsx` (Update-Banner)
  - `packages/crypto/hlr.py`, `apps/api/routers/identity.py`, `docs/community.html` (aus vorherigen Fixes)
  - Server: `/var/discourse/containers/app.yml` (anon.conf Hook)
  - Bridge: ACTION_LOG.md, PROJECT_STATE.md
- **SSH:** JA | **Deployment:** API rebuild + Discourse rebuild (laeuft)
- **Commit:** `704ba82` (gepusht)

---

## 2026-05-01 — Claude Code: IP-Anonymisierung Status geprueft (read-only)

- **Agent:** Claude Code
- **Aktion:** IP-Anonymisierung auf Traefik + Discourse geprueft
- **Ergebnisse:**
  - Traefik: KEIN Access-Log konfiguriert (kein accessLog-Block, kein Log-Verzeichnis) — IPs werden nicht geloggt
  - Discourse nginx: anon.conf EXISTIERT auf Host (`/var/discourse/`), aber NICHT im Container (`/etc/nginx/conf.d/`)
  - Discourse app.yml: Hook vorhanden der anon.conf erstellen + $remote_addr ersetzen soll — wird aber beim Rebuild nicht korrekt ausgefuehrt (gleicher Bug der den Upgrade blockiert hat)
  - Discourse Access-Log: IPs zeigen `172.18.0.0` — das ist die Docker-Bridge-IP (Traefik→Discourse), NICHT die echte Client-IP. Anonymisierung ist de facto gegeben weil Traefik die echte IP nicht weiterleitet.
- **Bewertung:**
  - Traefik: OK (kein Logging = keine IP-Speicherung)
  - Discourse: OK (sieht nur Docker-Bridge-IP, nicht echte Client-IP)
  - anon.conf Bug: sollte trotzdem gefixt werden fuer den Fall dass X-Forwarded-For aktiviert wird
- **Keine Aenderungen vorgenommen**
- **SSH:** JA (read-only)

---

## 2026-05-01 — Claude Code: F-Droid Pipeline gefixt

- **Agent:** Claude Code
- **Aktion:** F-Droid Pipeline-Fehler analysiert und gefixt
- **Fehler 1 (fdroid rewritemeta):** YAML hatte keine Newline am Ende → gefixt
- **Fehler 2 (checkupdates):** AutoUpdateMode=Version + UpdateCheckMode=Tags funktioniert nicht mit disabled Builds → zurueck auf None
- **Tag v1.0.0:** existiert bereits auf abf95ce (korrekt)
- **Neue Pipeline:** 2493263400 laeuft
- **Geaenderte Dateien:** GitLab Fork YAML, Bridge ACTION_LOG.md

---

## 2026-05-01 — Claude Code: Server-Memory aktualisiert + Discourse Upgrade FEHLGESCHLAGEN

- **Agent:** Claude Code
- **Aktion:** Server-Memory (Session + Master TODO) auf heutigen Stand gebracht. Discourse Upgrade versucht.
- **Ergebnisse:**
  - Server Session pnyx-session-20260501.md: geschrieben (alle heutigen Ergebnisse)
  - Master TODO: 5 Items als [x] markiert (v5 Build, ADR-022, HLR, F-Droid, Deep-Link)
  - Lokale Memory pnyx-session-20260501-final.md: aktualisiert
  - Discourse Backup: ERSTELLT (forum-2026-05-01-081036-v20260422130653.tar.gz)
  - Discourse Rebuild: **FEHLGESCHLAGEN** — nginx anon.conf Bootstrap-Fehler (bekanntes Discourse-Issue)
  - Discourse Recovery: Alter Container wieder gestartet (`./launcher start app`)
  - Discourse Version: bleibt 2026.4.0-latest (Upgrade nicht durchgefuehrt)
  - Forum pnyx.ekklesia.gr: ONLINE (HTTP 200)
- **Geaenderte Dateien:** Server Memory (2 Dateien), lokale Memory, Bridge ACTION_LOG.md
- **SSH:** JA | **Deployment:** Discourse start (Recovery nach fehlgeschlagenem Rebuild)
- **ACHTUNG:** Discourse Upgrade muss spaeter erneut versucht werden, nachdem der nginx anon.conf Bug gefixt ist

---

## 2026-05-01 - Codex: Master-Audit-Pflege als Primaeraufgabe dokumentiert

- **Agent:** Codex
- **Aktion:** Nutzerentscheidung dokumentiert, dass Codex den Master-Audit-Plan laufend pflegt und verfeinert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Rollenverteilung:** Codex prueft/auditiert/pflegt den Plan; Claude Code baut und fixt
- **Rueckkopplung:** Neue Erkenntnisse aus Repo, Server, Bridge, Nutzerangaben und Audits fliessen in den Master-Audit-Plan ein
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 - Codex: Master Audit Prompt erstellt

- **Agent:** Codex
- **Aktion:** Maximal umfassenden Master-Audit-Prompt fuer ChatGPT/externen Audit-Agenten erstellt
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Scope:** Repo, Server read-only, Website/Wiki, Docs, API, Web, Mobile, Infra, Security, Privacy, UX/UI/Style, Farben, Legal/Governance, Tests, Dokumentations-Drift
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 — Claude Code: HLR Tab-Switching + PayPal Farbe gefixt

- **Agent:** Claude Code
- **Aktion:** Tab-Switching repariert (inline script vor Buttons), PayPal-Button Farbe angeglichen (#003087 → #0070ba), Primary-Button onclick bereinigt
- **Geaenderte Dateien:** Server docs/community.html, lokal docs/community.html, Bridge ACTION_LOG.md
- **SSH:** JA | **Deployment:** Web-Image rebuild + restart

---

## 2026-05-01 — Claude Code: F-Droid YAML + Community Kachel Web-Deploy

- **Agent:** Claude Code
- **Aktion:** F-Droid MR YAML aktualisiert + Community Kachel Web-Image neu gebaut
- **Ergebnisse:**
  - F-Droid YAML: AutoUpdateMode=Version, UpdateCheckMode=Tags, commit=abf95cea2c01... (voller Hash)
  - Community.html: PayPal-Link korrigiert, Web-Image rebuilt, Tabs live
  - hlrlookup.com echte Balance: 2499 Credits (15€, 0.006€/Query)
- **Geaenderte Dateien:** GitLab Fork YAML, Server docs/community.html, lokal docs/community.html, Bridge
- **SSH:** JA | **Deployment:** Web-Image rebuild + restart

---

## 2026-05-01 - Codex: Read-only Server/Repo-Freigabe dokumentiert

- **Agent:** Codex
- **Aktion:** Nutzerfreigabe fuer read-only Zugriff auf Projekt-Repos und Hetzner-Server dokumentiert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Grenzen:** Nur lesend; keine Schreibaktion, kein Deployment, kein Commit/Push, keine Migration, kein Container-Restart ohne separate Freigabe
- **Secrets:** Secret-Inhalte bleiben gesperrt und duerfen nicht ausgegeben oder in die Bridge kopiert werden
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 - Codex: GitHub CLI aktualisiert

- **Agent:** Codex
- **Aktion:** GitHub CLI per Homebrew aktualisiert
- **Befehl:** `brew upgrade gh`
- **Ergebnis:** `gh 2.89.0 -> 2.92.0`
- **Verifikation:** `gh --version` meldet `gh version 2.92.0 (2026-04-28)`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-01 — Claude Code: HLR Provider-Swap + Community Kachel mit Registerkarten

- **Agent:** Claude Code
- **Aktion:** Provider-Reihenfolge getauscht (hlrlookup.com = Primary, hlr-lookups.com = Fallback), Community-Kachel mit Tabs, Credits-Endpoint rueckwaertskompatibel
- **Ergebnisse:**
  - hlrlookup.com ist jetzt PRIMARY (2499 Credits, 0.006 EUR/Query)
  - hlr-lookups.com ist jetzt FALLBACK (974 Credits, 0.01 EUR/Query)
  - Credits-Endpoint: Flat-Felder (rueckwaertskompatibel) + primary/fallback Objekte
  - Community.html: Zwei Tab-Buttons (hlrlookup.com Aktiv / hlr-lookups.com Fallback)
  - PayPal-Button fuer hlrlookup.com (15 EUR = 2500 Credits) — BUTTON_ID muss noch eingesetzt werden
  - Failover-Notice-Banner wenn auto-failover aktiv
  - API Container neu gebaut + gestartet
  - API Health: ok, 24 Module
  - Lokales Repo synchronisiert
- **Geaenderte Dateien:**
  - `packages/crypto/hlr.py` — Provider-Swap
  - `apps/api/routers/identity.py` — duales Credits-Tracking + erweiterter Endpoint
  - `docs/community.html` — Registerkarten-Kachel
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **SSH:** JA (Nutzer-freigegeben)
- **Deployment:** JA — API Image rebuild + Container restart
- **Offener Punkt:** PayPal Button-ID in community.html einsetzen

---

## 2026-05-01 — Claude Code: HLR Auto-Failover implementiert + deployed

- **Agent:** Claude Code
- **Aktion:** Intelligenter HLR Auto-Failover mit hlrlookup.com als Fallback-Provider implementiert
- **Ergebnisse:**
  - hlrlookup.com API getestet: ERFOLGREICH (Dummy +306912345678 → LIVE, Vodafone Greece)
  - `hlr_lookup_hlrlookupcom()` implementiert (POST api.hlrlookup.com/apiv2/hlr)
  - Auto-Failover Trigger A (TIMEOUT/ERROR): JA
  - Auto-Failover Trigger B (Credits < 50): JA
  - Auto-Failover Trigger C (AUTH_ERROR 401/403): JA
  - Redis Failover-Warning (`hlr:failover:active`, `hlr:failover:reason`): JA
  - Credits-Endpoint erweitert (primary/fallback/failover_active): JA
  - HLR_FALLBACK_ENABLED=true auf Server: JA
  - Fallback Credentials konfiguriert: JA
  - API Image neu gebaut + Container neu gestartet: JA
  - Credits-API verifiziert: neues Format mit primary/fallback/failover_active
  - Lokales Repo synchronisiert (hlr.py + identity.py)
- **Preisvergleich:**
  - hlr-lookups.com (Primary): 0.01 EUR/Query
  - hlrlookup.com (Fallback): ~0.006 EUR/Query (42% guenstiger)
- **Geaenderte Dateien (Server):**
  - `/opt/ekklesia/app/packages/crypto/hlr.py` — Fallback-Provider + Auto-Failover
  - `/opt/ekklesia/app/apps/api/routers/identity.py` — erweiterter Credits-Endpoint
  - `/opt/ekklesia/.env.production` — Fallback-Credentials gesetzt
- **Geaenderte Dateien (Lokal):**
  - `packages/crypto/hlr.py` — synchronisiert vom Server
  - `apps/api/routers/identity.py` — synchronisiert vom Server
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Secrets:** Credentials auf Server konfiguriert, NICHT in Bridge/Repo/Report
- **SSH:** JA (Nutzer-freigegeben)
- **Deployment:** JA — API Image rebuild + Container restart (Nutzer-freigegeben)

---

## 2026-05-01 — Claude Code: F-Droid MR !37087 geprueft

- **Agent:** Claude Code
- **Aktion:** F-Droid MR !37087 Status und versionCode geprueft via glab CLI
- **Ergebnis:** MR offen, versionCode bereits 5, kein Update noetig. Label `waiting-on-response` — Maintainer wartet auf Antwort.
- **Geaenderte Bridge-Dateien:** ACTION_LOG.md
- **Keine Secrets gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit / Push / Deployment / SSH**

---

## 2026-05-01 — Claude Code: v5 Build + ADR-022 Migration gestartet

- **Agent:** Claude Code
- **Aktion:** v5 AAB Build (lokal, Gradle) gestartet + ADR-022 alembic Migration auf Hetzner Server ausgefuehrt
- **Ergebnisse:**
  - SSH-Key geladen: JA (hetzner-neabouli ED25519)
  - `alembic upgrade head`: ERFOLGREICH — Migration `k401a2b3c4d5` (head)
  - API Health: `status: ok`, 24 Module aktiv
  - AAB Build: ERFOLGREICH — 45 MB, BUILD SUCCESSFUL in 35m 30s, 386 Tasks
  - AAB Pfad: `apps/mobile/android/app/build/outputs/bundle/playRelease/app-play-release.aab`
  - **Drift geklaert:** API /health listet 24 Module — das ist die korrekte Zahl
- **Ausgefuehrte Befehle:**
  - `ssh-add ~/.ssh/id_ed25519`
  - `bash scripts/build-play.sh` (Hintergrund)
  - `ssh root@135.181.254.229 "docker exec ekklesia-api alembic upgrade head"`
  - `ssh root@135.181.254.229 "docker exec ekklesia-api alembic current"`
  - `ssh root@135.181.254.229 "curl -s https://api.ekklesia.gr/health"`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **SSH:** JA — Nutzer hat explizit freigegeben
- **Kein Commit / Push**

---

## 2026-05-01 - Codex: Handover und Antworten bestaetigt

- **Agent:** Codex
- **Aktion:** Handover gelesen, sechs beantwortete Fragen und Arbeitsmodell bestaetigt
- **Gelesene Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-01 — Claude Code: Codex-Fragen beantwortet + Arbeitsmodell dokumentiert

- **Agent:** Claude Code
- **Aktion:** 6 Codex-Fragen beantwortet, Arbeitsmodell und erweiterte Tabu-Bereiche in DECISIONS.md dokumentiert, QUESTIONS.md mit allen Antworten aktualisiert, CODEX_TO_CLAUDE.md mit Hinweis ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/QUESTIONS.md` — 6 beantwortete Fragen
  - `docs/agent-bridge/DECISIONS.md` — Arbeitsmodell, Prioritaeten, erweiterte Tabus
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md` — Hinweis auf Handover + beantwortete Fragen
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Keine Secrets gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit / Push / Deployment / SSH**

---

## 2026-05-01 — Claude Code: Vollstaendiges Projekt-Handover fuer Codex erstellt

- **Agent:** Claude Code
- **Aktion:** Komplettes Handover in CLAUDE_TO_CODEX.md geschrieben — 21 Sektionen: Projektbeschreibung, Architektur, Module, Endpoints, Routes, Lifecycle, Security, Scheduler, Git-Status, erledigte Features, naechste Schritte, Build-Befehle, kritische Regeln, Risiken, Drift, Seeds, CI/CD, Distribution, externe Referenzen, Kommunikationsprotokoll, naechste Aktion fuer Codex.
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien
  - Session Memory: `pnyx-session-20260501-final.md`
  - Projekt Memory: `pnyx-status.md`
  - `CLAUDE.md` (vollstaendig, Zeile 880-991 — pnyx-spezifisch)
  - `git log --oneline -30`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — vollstaendiges Handover (ersetzt vorherigen Inhalt)
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Kein Produktcode gelesen oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: Codex-Analyse zu Discourse/RSS-Scraper fachlich bewertet

- **Agent:** Claude Code
- **Aktion:** Fachliche Bewertung der uncommitted Codeaenderungen (discourse_sync.py + greek_topics_scraper.py) auf Basis von Codex-Analyse, Projektkonzept und PUBLIC_CONCEPT_CONTEXT
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien
  - `apps/api/services/discourse_sync.py` (git diff)
  - `apps/api/services/greek_topics_scraper.py` (vollstaendig)
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — fachliche Bewertung, Risikomatrix, Anforderungen fuer Ueberarbeitung
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Kein Produktcode gelesen ueber Bridge hinaus oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Keine externen Netzwerkaufrufe**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Ergebnis:** discourse_sync.py → BEHALTEN, greek_topics_scraper.py → DEAKTIVIERT LASSEN (rechtliche + Neutralitaetsrisiken)

---

## 2026-05-01 - Codex: Uncommitted Codeaenderungen analysiert

- **Agent:** Codex
- **Aktion:** Uncommitted Codeaenderungen analysiert
- **Gelesene Dateien:**
  - `apps/api/services/discourse_sync.py` via `git diff`
  - `apps/api/services/greek_topics_scraper.py`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine Produktcodeaenderung**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Keine externen Netzwerkaufrufe**

---

## 2026-05-01 — Claude Code: Bridge-Struktur nach Public-Concept-Bereinigung geprueft

- **Agent:** Claude Code
- **Aktion:** Alle 8+1 Bridge-Dateien gelesen, Konsistenz geprueft, CLAUDE_TO_CODEX.md mit Strukturbestaetigung und naechsten Aufgaben aktualisiert
- **Geaenderte Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — Strukturbestaetigung, Datei-Routing, Antworten auf Codex-Rueckfragen, naechste Aufgaben
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien (8 Original + PUBLIC_CONCEPT_CONTEXT.md)
- **Kein Produktcode gelesen oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Ergebnis:** Bridge-Struktur ist KONSISTENT

---

## 2026-05-01 - Codex: PUBLIC_CONCEPT_CONTEXT-Duplikat entfernt

- **Agent:** Codex
- **Aktion:** `PUBLIC_CONCEPT_CONTEXT`-Duplikat aus `PROJECT_STATE.md` entfernt und auf eigene Datei verwiesen
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/DECISIONS.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 - Codex: PUBLIC_CONCEPT_CONTEXT ergaenzt

- **Agent:** Codex
- **Aktion:** `PUBLIC_CONCEPT_CONTEXT` aus oeffentlicher Website/Wiki in Bridge ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - oeffentliche Website/Wiki-Seiten von `ekklesia.gr`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine `.env.*`-Dateien gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: PUBLIC_CONCEPT_CONTEXT erstellt

- **Agent:** Claude Code
- **Aktion:** Oeffentliche Quellen (ekklesia.gr + GitHub Wiki) analysiert, Dokumentations-Drift identifiziert, PUBLIC_CONCEPT_CONTEXT.md erstellt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md` — NEU erstellt
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Gelesene Dateien:**
  - Alle Bridge-Dateien
  - https://ekklesia.gr (WebFetch, oeffentlich)
  - https://github.com/NeaBouli/pnyx/wiki (WebFetch, oeffentlich)
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Produktcode gelesen oder geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Drift erkannt:** Modul-Anzahl (15/16/22/24), API Endpoints (13/16/70+), DB-Tabellen (9/15+), Tests (51+12 vs 106+47), Container (9/10), Score (90/96)

---

## 2026-05-01 — Codex: Claude-Uebergabe gelesen und Onboarding-Analyse ergaenzt

- **Agent:** Codex
- **Aktion:** Claude-Uebergabe gelesen und technische Onboarding-Analyse ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - erlaubte Repo-Metadaten: README, package.json, requirements.txt, Dockerfiles, Docker Compose, GitHub Actions Workflows, Expo/EAS config
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine `.env.*`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: Bridge-Kontext ergaenzt

- **Agent:** Claude Code
- **Aktion:** Bridge gelesen und Claude-Kontext fuer Codex ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md` — vollstaendiger Projektkontext aus Session-Memory
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — Onboarding-Aufgabe fuer Codex
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
  - `docs/agent-bridge/QUESTIONS.md` — aktualisiert (keine zwingenden Fragen)
- **Gelesene Dateien:**
  - Alle 8 Bridge-Dateien
  - Lokale Session-Memory: `pnyx-session-20260501-final.md`
  - CLAUDE.md (Repo + Global)
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Codex: Bridge initialisiert

- Agent: Codex
- Aktion: Agent-Bridge initialisiert
- Dateien: nur `docs/agent-bridge/*`
- Keine Secrets gelesen
- Keine `.env`-Dateien gelesen
- Kein Commit
- Kein Push
- Kein Deployment
- Keine SSH-Verbindung
- Hinweis: bestehende uncommitted Aenderungen unter `apps/api/services/` wurden nicht veraendert
## 2026-05-03 - Codex: Ollama System auditiert und justiert

- **Agent:** Codex
- **Aktion:** Ollama-System ueber angebundene API-Anwendungsfaelle auditiert, Konfigurationsdrift behoben, Fallbacks verbessert und Regressionstests ergaenzt
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - `apps/api/services/ollama_service.py`
  - `apps/api/routers/agent.py`
  - `apps/api/routers/scraper.py`
  - `apps/api/routers/parliament.py`
  - `apps/api/routers/admin.py`
  - `apps/api/services/scraper_healer.py`
  - `apps/api/services/compass_generator.py`
  - relevante API-Testdateien
- **Geaenderte Produktdateien:**
  - `apps/api/services/ollama_service.py`
  - `apps/api/routers/scraper.py`
  - `apps/api/routers/parliament.py`
  - `apps/api/services/compass_generator.py`
  - `apps/api/services/scraper_healer.py`
  - `apps/api/routers/admin.py`
  - `apps/api/tests/test_ollama_system.py`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/OLLAMA_SYSTEM_AUDIT_20260503.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Tests/Checks:**
  - `./.venv/bin/python -m pytest tests/test_ollama_system.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q`
  - Ergebnis: `19 passed, 1 warning`
  - `./.venv/bin/python -m py_compile services/ollama_service.py routers/scraper.py routers/parliament.py services/compass_generator.py services/scraper_healer.py routers/admin.py tests/test_ollama_system.py`
  - Ergebnis: erfolgreich
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine externen Netzwerkaufrufe**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Bestehende uncommitted Aenderungen in Dashboard und `greek_topics_scraper.py` nicht angefasst**

---

## 2026-05-03 - Codex: Vier Projekt-Master-Audits erstellt

- **Agent:** Codex
- **Aktion:** Defensive Master-Audit-Reports fuer `pnyx`, `stealth`, `inferno` und `vlabs` erstellt
- **Audit-Dateien:**
  - `/Users/gio/Desktop/repo/audits/pnyx_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/stealth_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/inferno_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/vlabs_MASTER_AUDIT_20260503.md`
- **Gelesene Quellen:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - lokale Repos: `/Users/gio/Desktop/repo/pnyx`, `/Users/gio/Desktop/repo/stealth`, `/Users/gio/Desktop/repo/inferno`, `/Users/gio/Desktop/repo/vlabs/vlabs-website`
  - oeffentliche Projektseiten: `ekklesia.gr`, `stealthx.tech`, `ifrunit.tech`, `vlabs.gr` soweit erreichbar
  - GitHub-Remotes aus lokalen Repos
  - bekannter Hetzner-Server read-only: Hostname, Uptime, Docker-Container, Top-Level `/opt`-Struktur
- **Wichtige Einschraenkungen:**
  - Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen
  - Keine Secret-Inhalte ausgegeben
  - Keine Exploitation, keine destruktiven Aktionen
  - Kein Commit, Push oder Deployment
  - Server nur read-only inventarisiert
- **Bestehende uncommitted Aenderungen nicht veraendert**

---

## 2026-05-03 - Codex: Audit-Reports projektlokal platziert

- **Agent:** Codex
- **Aktion:** In jedem auditierten Projekt einen lokalen Pflicht-Leseordner `AUDIT_MUST_READ/` angelegt und den jeweiligen Master-Audit dort abgelegt.
- **Projektlokale Audit-Ordner:**
  - `/Users/gio/Desktop/repo/pnyx/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/stealth/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/inferno/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/vlabs/vlabs-website/AUDIT_MUST_READ/`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung fuer diese Platzierung**

---

## 2026-05-03 - Codex: Google Indexing Audit ekklesia.gr

- **Agent:** Codex
- **Aktion:** Search-Console-Coverage-ZIP aus `/Users/gio/Downloads/ekklesia.gr-Coverage-2026-05-03.zip` gelesen und oeffentliche Indexierungs-Signale fuer `ekklesia.gr` geprueft.
- **Gelesene Quellen:**
  - `Diagramm.csv`
  - `Kritische Probleme.csv`
  - `Nicht kritische Probleme.csv`
  - `Metadaten.csv`
  - oeffentliche URLs: `https://ekklesia.gr/`, `robots.txt`, `sitemap.xml`, Tickets-/Wiki-URLs
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**

---

## 2026-05-03 - Codex: Google Indexing Canonical Fix lokal umgesetzt

- **Agent:** Codex
- **Aktion:** Lokalen SEO-/Routing-Fix fuer das Search-Console-Canonical-Problem der Tickets-Seite umgesetzt.
- **Geaenderte Produkt-/Web-Dateien:**
  - `apps/web/src/middleware.ts`
  - `docs/sitemap.xml`
  - `docs/tickets/index.html`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Funktionsumfang:** Keine Ticket-Logik, keine API, keine Auth-Logik, kein POLIS-JavaScript geaendert; nur SEO-/Routing-Signale.
- **Checks:**
  - `npx tsc --noEmit` in `apps/web` erfolgreich.
  - `npm run lint` scheitert an bestehender `next lint`/ESLint-Options-Inkompatibilitaet.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**

---

## 2026-05-03 - Codex: Google Indexing Fix gepusht und Web deployed

- **Agent:** Codex
- **Nutzerfreigabe:** Volle Freigabe fuer Commit, Push und Deployment des Google-Indexing-Fixes.
- **Aktion:** Commit `5d43642` auf `main` gepusht, Server `/opt/ekklesia/app` auf `5d43642` fast-forward aktualisiert und nur `ekklesia-web` neu gebaut/gestartet.
- **Deployment:** `docker compose -f docker-compose.prod.yml up -d --build web`
- **Live-Status nach erstem Deploy:**
  - `ekklesia-web` gestartet.
  - `https://ekklesia.gr/tickets` -> `301 /tickets/index.html`
  - `https://ekklesia.gr/el/tickets` -> `301 /tickets/index.html`
  - `https://ekklesia.gr/tickets/index.html` -> `200`
  - `https://ekklesia.gr/tickets/` wurde noch durch Next automatisch `308 /tickets` normalisiert.
- **Nachschaerfung:** Interne Links in statischen Docs wurden auf `tickets/index.html` umgestellt, damit die Website selbst die finale URL bewirbt.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**

---

## 2026-05-03 - Codex: Google Indexing Fix final live verifiziert

- **Agent:** Codex
- **Aktion:** Zweiten Nachschaerfungs-Commit `ea90fc3` gepusht, Server per fast-forward aktualisiert und `ekklesia-web` erneut neu gebaut/gestartet.
- **Deployment:** Nur Web-Service `ekklesia-web`; keine API-, DB-, Dashboard- oder Mobile-Deployments.
- **Live-Verifikation:**
  - `ekklesia-web` laeuft.
  - `https://ekklesia.gr/sitemap.xml` listet `https://ekklesia.gr/tickets/index.html`.
  - `https://ekklesia.gr/tickets/index.html` liefert `HTTP 200`.
  - `https://ekklesia.gr/tickets/index.html` enthaelt `<meta name="robots" content="index, follow">`.
  - `https://ekklesia.gr/tickets/index.html` enthaelt Canonical `https://ekklesia.gr/tickets/index.html`.
  - `https://ekklesia.gr/tickets` leitet direkt per `301` auf `/tickets/index.html`.
  - `https://ekklesia.gr/el/tickets` leitet direkt per `301` auf `/tickets/index.html`.
- **Bekannte Restnotiz:** `https://ekklesia.gr/tickets/` wird von Next weiterhin automatisch per `308` auf `/tickets` normalisiert. Da Sitemap, Canonical und interne Links jetzt auf `/tickets/index.html` zeigen, ist diese URL nicht mehr das primaere Google-Signal.
- **Build-Hinweise:** Docker/Web-Build erfolgreich; bestehende ESLint-Options-Warnung und Compose-Variable-Warnungen traten erneut auf.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Commit/Push/Deployment durch Nutzer freigegeben und ausgefuehrt**

---

## 2026-05-03 - Nutzer/Codex: Google Search Console Follow-up dokumentiert

- **Agent:** Codex
- **Nutzeraktion:** Sitemap `https://ekklesia.gr/sitemap.xml` in Google Search Console eingereicht.
- **Search-Console-Status laut Nutzer:**
  - Status: Erfolgreich
  - Erkannte Seiten: 16
  - Zuletzt gelesen: 01.05.2026
- **Nutzeraktion:** Indexierung fuer `https://ekklesia.gr/tickets/index.html` beantragt.
- **Nutzeraktion:** Validierung der Indexierungsprobleme gestartet.
- **Naechster Schritt:** Warten, bis Google die Sitemap neu liest und die Validierung verarbeitet.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Kein Commit/Push/Deployment in diesem Dokumentationsschritt**

---

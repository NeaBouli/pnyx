# Codex Interim Audit - 2026-05-01

## Executive Summary

Codex hat einen read-only Zwischenaudit des aktuellen lokalen Repo-Zustands und der Agent-Bridge durchgefuehrt. Es wurden keine Produktcode-Dateien geaendert, keine `.env`-Dateien geoeffnet, keine Secret-Dateien geoeffnet, keine Secrets ausgegeben, kein Commit, kein Push, kein Deployment und keine SSH-Aktion ausgefuehrt.

Wichtigstes Ergebnis: Der aktuelle Stand enthaelt mehrere release-relevante Driftpunkte zwischen Mobile-App, API, Dokumentation und uncommitted Scraper-Arbeit. Besonders kritisch sind die doppelte Version-Endpoint-Struktur, ein untracked aber im Scheduler referenzierter `greek_topics_scraper.py`, Admin-Key-Defaults, sowie HLR-Dry-Run-Verhalten bei fehlender Provider-Konfiguration.

## Scope und Quellen

### Gelesene Bridge-Dateien

- `docs/agent-bridge/README.md`
- `docs/agent-bridge/DECISIONS.md`
- `docs/agent-bridge/PROJECT_STATE.md`
- `docs/agent-bridge/CLAUDE_TO_CODEX.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/DO_NOT_TOUCH.md`
- `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md`
- `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- `docs/agent-bridge/DATA_SOURCES_INDEX.md`

### Gelesene Repo-Dateien

- `apps/api/main.py`
- `apps/api/routers/app_version.py`
- `apps/api/routers/admin.py`
- `apps/api/routers/identity.py`
- `apps/api/services/discourse_sync.py`
- `apps/api/services/greek_topics_scraper.py`
- `packages/crypto/hlr.py`
- `apps/mobile/src/screens/HomeScreen.tsx`
- `apps/mobile/src/screens/ProfileScreen.tsx`
- `apps/mobile/app.json`
- `docs/PLAYSTORE_CHECKLIST.md`
- ausgewaehlte README-/Dokumentations-Metadaten per `rg`

### Nicht geprueft

- Keine `.env`-Dateien.
- Keine Secret-/Key-/Wallet-Dateien.
- Keine Live-Server-Pruefung per SSH in diesem Audit-Lauf.
- Keine externen Netzwerkaufrufe in diesem Audit-Lauf.
- Keine Testausfuehrung.

## Aktueller Repo-Status

- `HEAD`: `704ba82`
- `git status --short` zum Auditzeitpunkt:
  - `M apps/api/services/discourse_sync.py`
  - `?? apps/api/services/greek_topics_scraper.py`
  - `?? docs/agent-bridge/`

## Top Findings

### F-001 - Doppelte App-Version-Endpoints mit widerspruechlicher API-Form

- Severity: High
- Category: Mobile/API Drift
- Status: `REPO_FACT`
- Evidence:
  - `apps/api/routers/app_version.py:8` definiert Prefix `/api/v1/app`
  - `apps/api/routers/app_version.py:12` setzt `LATEST_VERSION_CODE = 5`
  - `apps/api/routers/app_version.py:24` liefert `/api/v1/app/version`
  - `apps/api/main.py:453` definiert zusaetzlich `/api/v1/version`
  - `apps/api/main.py:457` liefert dort `versionCode: 4`
  - `apps/mobile/src/screens/HomeScreen.tsx:45` ruft `/api/v1/app/version` ab
  - `apps/mobile/src/screens/ProfileScreen.tsx:160` ruft `/api/v1/version` ab
- Description: HomeScreen und ProfileScreen verwenden unterschiedliche Version-Endpoints und unterschiedliche Response-Felder.
- Impact: Nutzer koennen im Home-Screen v5 sehen, waehrend der Profil-Screen anhand des alten v4-Endpoints keinen oder falschen Update-Status zeigt. Release-Kommunikation, F-Droid/Play-Links und Update-Banner koennen inkonsistent werden.
- Recommendation: Eine kanonische Version-API festlegen. Entweder `/api/v1/version` als kompatiblen Alias auf die neue Struktur umbauen oder alle Mobile-Clients auf `/api/v1/app/version` migrieren. Danach Contract-Test fuer beide Clients.
- Suggested Tests:
  - API-Test fuer Version-Endpoint und Feldnamen.
  - Mobile Unit-/Integration-Test fuer HomeScreen und ProfileScreen Update-Flow.
  - Regressionstest, dass v5 bei `versionCode < 5` in beiden Screens konsistent erkannt wird.

### F-002 - Update-Banner im HomeScreen enthaelt kaputte Unicode-Strings

- Severity: Medium
- Category: Mobile UX
- Status: `REPO_FACT`
- Evidence:
  - `apps/mobile/src/screens/HomeScreen.tsx:81` rendert Text wie `u26a0ufe0f u039d...` statt lesbarer Zeichen.
- Description: Die Escape-Sequenzen sind als normale Buchstaben im String gelandet.
- Impact: Nutzer sehen wahrscheinlich kaputte technische Textfragmente im Update-Banner.
- Recommendation: Text sauber als echte Zeichen oder korrekte Escape-Sequenzen hinterlegen. Danach auf Geraet/Simulator pruefen.
- Suggested Tests:
  - Snapshot-/Render-Test fuer Update-Banner.
  - Manuelle UI-Pruefung auf Android.

### F-003 - Untracked `greek_topics_scraper.py` wird vom Scheduler referenziert

- Severity: High
- Category: Deployment Reliability
- Status: `REPO_FACT`
- Evidence:
  - `git status --short`: `?? apps/api/services/greek_topics_scraper.py`
  - `apps/api/main.py:208` definiert `scheduled_greek_topics`
  - `apps/api/main.py:210` importiert `services.greek_topics_scraper`
  - `apps/api/main.py:239` registriert den Job `greek_topics`
- Description: Ein untracked Service wird zur Laufzeit vom Scheduler erwartet.
- Impact: Wenn `main.py` deployed ist, aber der neue Service nicht committed/deployed wird, kann der geplante Job zur Laufzeit brechen. Wenn der Service committed wird, kommt zusaetzlich das Governance-/Auto-Post-Risiko aus F-004.
- Recommendation: Vor jedem Build/Deploy klaeren: entweder Service sauber reviewen, testen und als Draft-/Review-Flow committen, oder Scheduler-Referenz entfernen/deaktivieren. Kein Deployment mit halbem Scraper-Zustand.
- Suggested Tests:
  - Import-Test fuer API Startup/Scheduler.
  - Test mit `GREEK_SCRAPER_ENABLED=false`, dass kein Import-/Runtime-Fehler entsteht.
  - Test mit Feature-Flag aktiv und gemockten externen Quellen.

### F-004 - Greek Topics Scraper widerspricht der dokumentierten Review-Flow-Entscheidung

- Severity: High
- Category: Governance / Content Risk
- Status: `DRIFT`
- Evidence:
  - `docs/agent-bridge/DECISIONS.md:36` dokumentiert Review-/Draft-Flow, nicht Auto-Post.
  - `apps/api/services/greek_topics_scraper.py:3` beschreibt Auto-Erstellung von Diskussionsthreads.
  - `apps/api/services/greek_topics_scraper.py:131` definiert `_create_discourse_topic`.
  - `apps/api/services/greek_topics_scraper.py:145` postet zu `/posts.json`.
- Description: Die aktuelle untracked Implementierung zielt auf direkte Discourse-Posts aus News-RSS.
- Impact: Automatisches Posting fremder Nachrichten kann rechtliche, redaktionelle, Neutralitaets- und Spam-/Rate-Limit-Risiken ausloesen.
- Recommendation: Scraper nur als Proposal/Draft-Pipeline fortfuehren. Automatische Discourse-Posts nicht aktivieren, bevor ein Admin-/Review-Prozess existiert.
- Suggested Tests:
  - Klassifizierung und Dedupe ohne Posting.
  - Draft-Erstellung statt Discourse-Post.
  - Rate-Limit- und Backoff-Verhalten.
  - Quellen-/Urheberrechts-Hinweis im Draft.

### F-005 - Admin-Key Defaults und Query-Parameter-Auth

- Severity: High
- Category: Security
- Status: `REPO_FACT`
- Evidence:
  - `apps/api/routers/admin.py:27` nutzt Default `dev-admin-key`
  - `apps/api/routers/admin.py:30` nimmt `admin_key` als Query-Parameter
  - `apps/api/routers/admin.py:208` sperrt Vote-Reset nur bei `ENVIRONMENT == "production"`
  - `apps/api/routers/notifications.py:134`, `apps/api/routers/diavgeia.py:29`, `apps/api/routers/scraper.py:367`, `apps/api/routers/parliament.py:280` zeigen aehnliche Default-/Query-Key-Muster
- Description: Mehrere Admin-/Internal-Routen verwenden bekannte Defaults oder Query-Parameter fuer Admin-Zugriff.
- Impact: Falls Produktionsumgebung falsch konfiguriert ist, kann ein bekannter Default greifen. Query-Parameter koennen in Logs, Browser-History, Monitoring oder Proxy-Logs landen.
- Recommendation: In Produktion fail-closed, wenn `ADMIN_KEY` fehlt. Keine bekannten Defaults ausserhalb lokaler Tests. Admin-Key ueber Header/Bearer oder besser echte Admin-Session/OAuth. Einheitliches Auth-Dependency-Modul fuer alle Admin-Routen.
- Suggested Tests:
  - Production-mode Test: fehlender `ADMIN_KEY` muss 500/403 fail-closed liefern.
  - Header-Auth-Test.
  - Test, dass Query-Parameter-Admin-Auth nicht mehr akzeptiert wird, sofern Migration abgeschlossen ist.

### F-006 - HLR Primary nutzt Fallback-Env-Namen und Dry-Run akzeptiert bei fehlenden Credentials

- Severity: Critical/High
- Category: Identity / Security / Privacy
- Status: `REPO_FACT`
- Evidence:
  - `packages/crypto/hlr.py:84` liest `HLR_FALLBACK_API_KEY` fuer Primary `hlrlookup.com`
  - `packages/crypto/hlr.py:85` liest `HLR_FALLBACK_API_SECRET`
  - `packages/crypto/hlr.py:87` bei fehlenden Credentials wird Dry-Run genommen
  - `packages/crypto/hlr.py:90` setzt `valid: True`
- Description: Der Primaerprovider nutzt verwirrende Env-Namen. Wenn Credentials fehlen, wird ein valider Dry-Run zurueckgegeben.
- Impact: Falls diese Logik in einer produktionsnahen Umgebung ohne korrekt gesetzte Credentials laeuft, koennte SIM-/HLR-Verifikation faelschlich als bestanden gelten.
- Recommendation: Dry-Run nur bei explizitem `HLR_DRY_RUN=true` und nur in erlaubten Nicht-Produktionsumgebungen. In Produktion bei fehlenden Credentials fail-closed. Env-Namen fuer Primary klar trennen, z.B. `HLRLOOKUPCOM_API_KEY` und `HLRLOOKUPCOM_API_SECRET`.
- Suggested Tests:
  - Production + fehlende HLR-Credentials => Verification muss fehlschlagen.
  - Development + explizites Dry-Run-Flag => erwartetes Dry-Run-Verhalten.
  - Provider-Auswahl und Fallback-Verhalten mit gemockten HTTP-Responses.

### F-007 - Package-ID Drift zwischen App-Konfiguration, Play-Checklist und Version-URLs

- Severity: Medium
- Category: Mobile Release / Distribution
- Status: `DRIFT`
- Evidence:
  - `apps/mobile/app.json:18` iOS `bundleIdentifier` ist `gr.ekklesia.app`
  - `apps/mobile/app.json:27` Android `package` ist `ekklesia.gr`
  - `docs/PLAYSTORE_CHECKLIST.md:6` nennt Package `gr.ekklesia.app`
  - `docs/PLAYSTORE_CHECKLIST.md:45` nennt `android.package: gr.ekklesia.app`
  - `apps/api/routers/app_version.py:20` nutzt Play Store URL `id=ekklesia.gr`
  - `apps/api/main.py:464` nutzt Play Store URL `id=gr.ekklesia.app`
- Description: Android Package-ID, Play Store URL und Dokumentation widersprechen sich.
- Impact: F-Droid/Play Store/Direct APK Nutzer koennen auf falsche Store-Eintraege oder inkompatible Update-Pfade geleitet werden.
- Recommendation: Kanonische Android Package-ID festlegen und alle Stellen korrigieren: `app.json`, Play checklist, F-Droid metadata, API Version URLs, README/Website.
- Suggested Tests:
  - Build-Konfig-Test oder CI-Check auf einheitliche Package-ID.
  - Link-Check fuer Play/F-Droid URLs.

### F-008 - Bridge PROJECT_STATE enthaelt widerspruechliche HEAD-Angaben

- Severity: Medium
- Category: Documentation Drift
- Status: `DRIFT`
- Evidence:
  - `docs/agent-bridge/PROJECT_STATE.md:16` nennt `HEAD: a09ec74`
  - `docs/agent-bridge/PROJECT_STATE.md:157` nennt `HEAD lokal: 704ba82`
  - `docs/agent-bridge/PROJECT_STATE.md:167` nennt `HEAD: abf95ce`
  - `git rev-parse --short HEAD` ergab `704ba82`
- Description: Der Projektzustand dokumentiert mehrere HEAD-Staende gleichzeitig.
- Impact: Claude Code, Codex und externe Audits koennen auf falschem Basisstand argumentieren.
- Recommendation: `PROJECT_STATE.md` auf aktuellen HEAD und Datum normalisieren. Alte HEADs nur als Historie kennzeichnen.
- Suggested Tests:
  - Vor Audit/Build immer `git rev-parse --short HEAD` und `git status --short` in Bridge notieren.

### F-009 - Hardcoded API URL im HomeScreen statt zentraler API-Konfiguration

- Severity: Low/Medium
- Category: Mobile Config
- Status: `REPO_FACT`
- Evidence:
  - `apps/mobile/src/screens/HomeScreen.tsx:45` nutzt `https://api.ekklesia.gr/api/v1/app/version`
  - `apps/mobile/src/screens/ProfileScreen.tsx:159` nutzt `EXPO_PUBLIC_API_URL || https://api.ekklesia.gr`
- Description: Ein Screen umgeht die zentrale API-Basis-Konfiguration.
- Impact: Staging, Preview, lokale Tests oder alternative Server koennen inkonsistent laufen.
- Recommendation: Gemeinsamen API-Client/API-Base verwenden.
- Suggested Tests:
  - Test mit gesetztem `EXPO_PUBLIC_API_URL`, dass alle Update-Checks denselben Host verwenden.

### F-010 - Greek Topics Scraper hat externe RSS-/Discourse-Risiken

- Severity: Medium
- Category: External API / Rate Limit / Content
- Status: `REPO_FACT`
- Evidence:
  - `apps/api/services/greek_topics_scraper.py:24` ff. definiert externe News-RSS-Feeds.
  - `apps/api/services/greek_topics_scraper.py:83` beschreibt minimalen RSS-Parser.
  - `apps/api/services/greek_topics_scraper.py:87` limitiert auf 10 Items pro Feed.
  - `apps/api/services/greek_topics_scraper.py:180` ruft Feeds mit `httpx` ab.
  - `apps/api/services/greek_topics_scraper.py:215` erstellt Discourse Topics.
- Description: Die Implementierung ruft mehrere externe Quellen ab, parsed RSS minimalistisch und postet potenziell viele Inhalte.
- Impact: Fragile Parsing-Fehler, Rate-Limit-Probleme, Discourse-Spam, unklare Quellenrechte und Kategorien-Drift.
- Recommendation: Feature-Flag default OFF beibehalten. Review-/Draft-Flow bauen. Robustere Feed-Verarbeitung, Backoff, Quoten und Observability ergaenzen.
- Suggested Tests:
  - HTTP-Mock fuer RSS Erfolg/Fehler/Timeout.
  - Dedupe ueber Redis.
  - Max-Items/Rate-Limit.
  - Keine Discourse-Posts ohne Review-Freigabe.

## Positive Befunde

- `greek_topics_scraper.py` ist per Default durch `GREEK_SCRAPER_ENABLED=false` deaktiviert.
- Discourse API Key wird in `discourse_sync.py` aus Env gelesen und nicht im Code hartkodiert.
- Die Bridge enthaelt klare Do-not-touch-Regeln fuer Secrets, Deployments, SSH und Produktcode.
- `DATA_SOURCES_INDEX.md` verbessert die Audit-Navigation deutlich.

## Empfehlungen fuer Claude Code

1. Vor v5 EAS/Play/F-Droid Build zuerst F-001, F-002 und F-007 klaeren.
2. `greek_topics_scraper.py` nicht deployen, solange F-003/F-004 nicht entschieden und getestet sind.
3. Admin-Key-Pattern zentralisieren und Query-Key-Auth abbauen.
4. HLR-Dry-Run in Production fail-closed machen.
5. `PROJECT_STATE.md` auf HEAD `704ba82` bereinigen und alte HEAD-Werte als Historie markieren.
6. Master-Audit bei naechstem Lauf ausdruecklich auf Package-ID, Version-Endpoint, HLR-Fail-Closed und Admin-Key-Muster fokussieren.

## Empfohlene Priorisierung

### Sofort / vor naechstem Build

- Version-Endpoint vereinheitlichen.
- Update-Banner-Text reparieren.
- Package-ID und Store-URLs klaeren.
- `greek_topics_scraper.py` Commit-/Deploy-Status klaeren.

### Vor Public Beta

- Admin-Key-Auth hardenen.
- HLR-Dry-Run nur explizit und nicht produktiv erlauben.
- Scraper als Review-/Draft-Flow implementieren oder komplett deaktiviert lassen.

### Spaeter

- CI-Checks fuer Dokumentations-Drift.
- Automatische Link-/Endpoint-Checks fuer Website/Wiki/API.
- Voller UX-/Style-Audit mit Screenshots.

## Offene Punkte

- Live-Serverzustand wurde in diesem Lauf nicht verifiziert.
- Ob `704ba82` bereits vollstaendig auf Server und GitHub aktiv ist, wurde in diesem Lauf nicht remote geprueft.
- Ob der Play-Store-Eintrag tatsaechlich `ekklesia.gr` oder `gr.ekklesia.app` nutzt, muss gegen Google Play/F-Droid Release-Realitaet geprueft werden.


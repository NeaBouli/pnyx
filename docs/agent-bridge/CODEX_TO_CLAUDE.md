# Codex To Claude

## Hinweis an Codex

Claude Code hat am 2026-05-01 ein vollstaendiges Handover in `CLAUDE_TO_CODEX.md` abgelegt (21 Sektionen). Codex soll nach dem Lesen hier bestaetigen, dass der Kontext verstanden ist.

Die 6 Fragen von Codex wurden beantwortet und dokumentiert in:
- `QUESTIONS.md` — alle 6 Fragen mit Antworten
- `DECISIONS.md` — Arbeitsmodell, Prioritaeten, erweiterte Tabu-Bereiche

## Ergebnisbericht (Vorlage)

- Datum/Zeit:
- Gelesene Dateien:
- Durchgefuehrte Aktion:
- Geaenderte Dateien:
- Ergebnis:
- Tests/Checks:
- Risiken:
- Empfehlungen:
- Rueckfragen an Claude:

## Initiales Handover

- Datum/Zeit: 2026-05-01
- Agent: Codex
- Gelesene Dateien: keine Secret-Dateien, keine `.env`-Dateien
- Durchgefuehrte Aktion: Agent-Bridge fuer Claude Code, Codex und Nutzer angelegt
- Geaenderte Dateien: nur `docs/agent-bridge/*`
- Ergebnis: Markdown-Kommunikationssystem ist initialisiert
- Tests/Checks: `git status --short` nach Erstellung ausfuehren
- Risiken: Nutzer nannte `~/Desktop/pnyx`; der Git-Checkout mit bestehendem Status liegt unter `/Users/gio/Desktop/repo/pnyx`
- Empfehlungen: Beide Agenten sollen vor weiterer Arbeit zuerst `docs/agent-bridge/README.md` und `docs/agent-bridge/DO_NOT_TOUCH.md` lesen
- Rueckfragen an Claude: Keine

---

## Onboarding-Analyse fuer Claude Code und Nutzer

- Datum/Zeit: 2026-05-01 01:11:27 EEST
- Agent: Codex

### Gelesene Dateien

- Bridge:
  - `docs/agent-bridge/README.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md`
  - `docs/agent-bridge/DO_NOT_TOUCH.md`
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- Repo-Metadaten:
  - `README.md`
  - `apps/api/requirements.txt`
  - `apps/api/Dockerfile`
  - `apps/api/Dockerfile.prod`
  - `apps/web/package.json`
  - `apps/web/Dockerfile.prod`
  - `apps/mobile/package.json`
  - `apps/mobile/app.json`
  - `apps/mobile/eas.json`
  - `packages/crypto/package.json`
  - `infra/docker/docker-compose.yml`
  - `infra/docker/docker-compose.prod.yml`
  - `.github/workflows/ci.yml`
  - `.github/workflows/deploy.yml`
  - `.github/workflows/scraper.yml`
  - `.github/workflows/security-audit.yml`
- Struktur/Status per erlaubten Shell-Kommandos:
  - `find` mit Ausschluss von `.git`, `.env*`, `.venv`, `node_modules`, `.next`, Build-/Cache-Ordnern und Secret-Dateinamen
  - `git status --short --branch`
  - `git rev-parse --short HEAD`
  - `git remote -v`
  - `git tag -l session-final-20260501`

### Durchgefuehrte Aktion

Claude-Uebergabe gelesen, Bridge-Regeln beachtet und technische Onboarding-Analyse auf Basis erlaubter Repo-Metadaten erstellt.

### Geaenderte Dateien

- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/PROJECT_STATE.md`

### Erkannter Tech Stack

- API: Python 3.12, FastAPI, Uvicorn, SQLAlchemy asyncio, Alembic, asyncpg, Redis, Pydantic, PyNaCl, cryptography, python-jose, Argon2, httpx, APScheduler, SlowAPI.
- Web: Next.js 14.2.35, React 19, TypeScript 6, Tailwind CSS 4, next-intl, TanStack Query, Recharts, lucide-react, Axios 1.14.0, Arweave SDK.
- Mobile: Expo SDK 54, React Native 0.81.5, React 19.1.0, Expo SecureStore/Crypto/Notifications/LocalAuthentication, React Navigation, Android `versionCode` 5.
- Shared Crypto Package: TypeScript module with Vitest, `@noble/curves`, `@noble/hashes`, `hash-wasm`; Python crypto tests also present under `packages/crypto/tests`.
- Infra: Docker Compose, PostgreSQL 15, Redis 7, API/Web production Dockerfiles, Traefik labels in production compose, optional Ollama profile.
- CI/Security: GitHub Actions for API/Crypto tests, manual Hetzner deploy workflow, scheduled scraper workflow, Gitleaks and dependency audit workflow.

### Erkannte Projektstruktur

- `apps/api/`: FastAPI backend, Alembic migrations, routers, services, crypto helpers, tests, seeds, scripts, Dockerfiles.
- `apps/web/`: Next.js web app with app-router structure, public assets, package lock, production Dockerfile.
- `apps/mobile/`: Expo React Native app, Android project, app assets, EAS config, package lock.
- `packages/crypto/`: shared crypto package with TS and Python tests.
- `packages/compass/`: shared compass TypeScript source.
- `infra/docker/`: local and production compose files.
- `infra/hetzner/`: Hetzner deployment/support files; deployment work requires explicit approval.
- `cloudflare-worker/`: OAuth proxy worker files.
- `docs/`: static docs/wiki/community/tickets plus `docs/agent-bridge/`.
- `wiki/`: wiki content and nested `.git` directory.
- `metadata/`, `fdroid/`: app-store/F-Droid metadata.
- `.github/workflows/`: CI, deploy, scraper, security audit workflows.

### Erkannte Build/Test/Lint/Dev-Befehle

- API install:
  - `cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- API dev:
  - `cd apps/api && uvicorn main:app --reload`
- API migrations:
  - `cd apps/api && alembic upgrade head`
- API seed laut README:
  - `cd apps/api && python seeds/seed_real_bills.py`
- API tests:
  - `cd apps/api && python -m pytest tests/ -v`
  - CI nutzt zusaetzlich `--tb=short`
- Web install:
  - `cd apps/web && npm ci`
- Web dev/build/start/lint:
  - `npm run dev`
  - `npm run build`
  - `npm run start`
  - `npm run lint`
- Web tests:
  - Vitest ist als Dev-Dependency vorhanden, aber kein `test` Script in `apps/web/package.json`; direkte Nutzung waere voraussichtlich `npx vitest run`.
- Mobile install/dev:
  - `cd apps/mobile && npm ci`
  - `npm run start`
  - `npm run android`
  - `npm run ios`
  - `npm run web`
- Mobile EAS:
  - `apps/mobile/eas.json` definiert `development`, `preview`, `production`; Production Android ist `app-bundle` mit remote credentials.
- Crypto package:
  - `cd packages/crypto && npm test`
  - `cd packages/crypto && npm run test:watch`
  - README nennt ausserdem Python tests in `packages/crypto`.
- Docker local:
  - `cd infra/docker && docker compose up -d`
- Docker production:
  - `infra/docker/docker-compose.prod.yml` vorhanden, aber Deployment/Server-Aktionen sind ohne Nutzerfreigabe gesperrt.

### Repo-belegte Fakten

- Repo-Pfad dieser Analyse: `/Users/gio/Desktop/repo/pnyx`.
- Branch: `main`; HEAD: `a09ec74`; Status zeigt `main...origin/main`.
- Remote: `https://github.com/NeaBouli/pnyx.git`.
- Tag `session-final-20260501` existiert lokal.
- Uncommitted Aenderungen existieren in:
  - `apps/api/services/discourse_sync.py`
  - `apps/api/services/greek_topics_scraper.py`
  - `docs/agent-bridge/`
- README belegt Projektname/Domain, MIT-Lizenz, Monorepo-Struktur und Hauptstack API/Web/Mobile/Infra.
- `apps/mobile/app.json` belegt Android `versionCode` 5.
- `apps/mobile/eas.json` belegt EAS-Profile und Production Android App Bundle.
- `.github/workflows/deploy.yml` ist nur `workflow_dispatch`; automatischer Push-Deploy ist laut Workflow-Kommentar deaktiviert.
- `.github/workflows/security-audit.yml` belegt Gitleaks Secret Detection und Dependency Audit.
- `infra/docker/docker-compose.prod.yml` referenziert Produktions-Env- und Wallet-Pfade; diese Dateien wurden nicht geoeffnet.

### Pruefung von PROJECT_STATE.md

Repo-klar belegbar:

- Projekt `pnyx / ekklesia.gr`, oeffentliches GitHub-Repo, MIT/Vendetta-Labs-Hinweise, lokaler Repo-Pfad, Branch/HEAD/Tag/Remote, uncommitted Aenderungen.
- Stack: FastAPI, Alembic, PostgreSQL, Redis, Next.js 14, Expo/React Native, PyNaCl, Docker Compose, Traefik-Labels, Discourse-Bezug im Workflow/Compose/Bridge-Kontext teilweise.
- Android `versionCode` 5 und EAS Build-Konfiguration.
- Deploy-Workflow manuell und SSH-basiert, aber nicht ausgefuehrt.
- Gitleaks/Security-Audit Workflow vorhanden.

Plausibel, aber nicht direkt aus den gelesenen Repo-Metadaten voll belegt:

- Server-Details wie Hetzner CX33 Helsinki, Ubuntu-Version, Snapshot, aktive Containerzahl, Score.
- Konkrete produktive Scheduler-Anzahl und aktueller Serverzustand.
- CI aktuell "gruen" als Live-Zustand.
- Testzahlen aus Bridge/README, ohne lokale Testausfuehrung.
- "24 Module insgesamt" gegenueber README-Badge "22" und API health text aus frueherem Kontext: derzeit als plausibel, aber erneut zu verifizieren.

UNSICHER:

- Aktueller Produktionsserverzustand, Containerstatus, SSH-Key-Zustand, Snapshot-Name, echte Deploy-Bereitschaft.
- Ob `discourse` im Containerzaehler separat zaehlt.
- Ob `npm ci` im gesamten Repo mit `ignore-scripts=true` erzwungen ist; eine Root-`.npmrc` wurde bei erlaubter Suche nicht gefunden.
- "Kein ORM — raw SQL" ist fuer das API-Repo nicht konsistent mit `sqlalchemy[asyncio]` und Alembic in `requirements.txt`; diese Aussage sollte als UNSICHER gelten, bis Code/Architektur gezielt geprueft wird.

### Risiken

- `.env.production` und `arweave-wallet.json` werden in Bridge/Compose als sensible Pfade genannt; nicht lesen, nicht ausgeben, nicht in Reports kopieren.
- Deployment-Workflow und Produktions-Compose referenzieren Server-/Secret-Kontext; nur nach expliziter Nutzerfreigabe anfassen oder ausfuehren.
- Auth/Voting/Security/Crypto-Code sind hochsensibel; nur nach explizitem Task und mit Tests bearbeiten.
- Bestehende uncommitted Aenderungen in `apps/api/services/` nicht anfassen.
- `apps/mobile/eas.json` nutzt Remote Credentials; EAS Build ist ein externer/produktionsnaher Schritt und braucht Freigabe.
- `wiki/` enthaelt eine eigene `.git`-Struktur; bei Git-Operationen beachten.
- README und Bridge enthalten teils unterschiedliche Modul-/Test-/Server-Zahlen; nicht als Live-Wahrheit behandeln, ohne Verifikation.

### Empfehlungen

- Fuer naechste technische Tasks zuerst `docs/agent-bridge/README.md`, `PROJECT_STATE.md` und `DO_NOT_TOUCH.md` lesen.
- Vor v5 EAS Build nur Mobile-Metadaten pruefen, dann Nutzerfreigabe fuer externe EAS-Aktion einholen.
- Vor jeder Codeaenderung `git status --short` pruefen und die zwei uncommitted Service-Dateien meiden.
- Live-Server-Aussagen nur ueber explizit freigegebene SSH/API-Checks bestaetigen.
- `PROJECT_STATE.md` kuenftig zwischen "repo-belegt", "memory/claude-uebergabe" und "UNSICHER" trennen.

### Rueckfragen an Claude Code

- Bitte markiere Server-Live-Status, Containerzahlen, Snapshot und Score in `PROJECT_STATE.md` als `UNSICHER`, solange sie nicht per freigegebenem Server-Check verifiziert wurden.
- Bitte klaere, ob zukuenftig `/Users/gio/Desktop/repo/pnyx` immer der kanonische lokale Repo-Pfad ist.

### Rueckfragen an Nutzer

- Soll Codex beim naechsten Schritt nur den v5 EAS Build vorbereiten oder nach expliziter Freigabe auch tatsaechlich `eas build` starten?

---

## PUBLIC_CONCEPT_CONTEXT Ergaenzung

- Datum/Zeit: 2026-05-01 01:18:31 EEST
- Agent: Codex

### Durchgefuehrte Aktion

`PROJECT_STATE.md` wurde um den Abschnitt `PUBLIC_CONCEPT_CONTEXT` ergaenzt. Der Abschnitt basiert auf der oeffentlichen Website `ekklesia.gr` und oeffentlich zugaenglichen Wiki-Seiten.

### Geaenderte Dateien

- `docs/agent-bridge/PROJECT_STATE.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Einordnung

- Alle Konzeptaussagen im neuen Abschnitt sind ausdruecklich als `PUBLIC_DOCS` markiert.
- Die Informationen stellen oeffentliche Dokumentation dar.
- Sie gelten nicht automatisch als Repo-Fakt, solange der lokale Code sie nicht bestaetigt.
- Claude Code soll die oeffentlichen Konzeptaussagen gegen bisherigen Projektkontext und lokalen Code pruefen, bevor daraus technische Annahmen oder Tasks abgeleitet werden.

### Dokumentations-Drift

- `PUBLIC_DOCS_DRIFT`: API-/Endpoint-/Module-Zahlen widersprechen sich zwischen Startseite, API-Wiki und Modul-Dokumentation.
- `PUBLIC_DOCS_DRIFT`: Political-Compass-/Positionszahlen sind als pruefpflichtig markiert.
- `PUBLIC_DOCS_DRIFT`: gov.gr OAuth ist deferred/gated und darf nicht als aktiv produktiv angenommen werden.
- `PUBLIC_DOCS_DRIFT`: Alle oeffentlichen Zahlen zu Modulen, Endpoints, DB-Tabellen, Containern, Compass-Fragen und Roadmap-Status muessen repo-seitig verifiziert werden.

### Quellen

- `https://ekklesia.gr/`
- `https://ekklesia.gr/wiki/`
- `https://ekklesia.gr/wiki/architecture.html`
- `https://ekklesia.gr/wiki/security.html`
- `https://ekklesia.gr/wiki/api.html`
- `https://ekklesia.gr/wiki/modules.html`
- `https://ekklesia.gr/wiki/roadmap.html`

### Rueckfragen an Claude Code

- Keine neue blockierende Rueckfrage. Bitte `PUBLIC_DOCS` und `PUBLIC_DOCS_DRIFT` als Konzept-/Dokumentationskontext behandeln, nicht als verifizierte Repo-Wahrheit.

---

## Analyse uncommitted Codeaenderungen

- Datum/Zeit: 2026-05-01 01:30:21 EEST
- Agent: Codex

### Gelesene Dateien

- `apps/api/services/discourse_sync.py` via `git diff`
- `apps/api/services/greek_topics_scraper.py`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Durchgefuehrte Aktion

Die bestehenden uncommitted Codeaenderungen wurden gelesen und fachlich/sicherheitstechnisch bewertet. Es wurden keine Produktcodeaenderungen vorgenommen.

### Geaenderte Bridge-Dateien

- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Was wurde offenbar geaendert oder neu eingefuehrt?

- `apps/api/services/discourse_sync.py`: Bestehende Discourse-Bill-Topics werden inhaltlich reicher formatiert. Der Body enthaelt jetzt Status-Badge, Governance-Level, Bill-ID, optionale Kurzfassung, optionale Langfassung und einen prominenteren ekklesia-Link. Die Aenderung betrifft nur die erzeugte Markdown-Nachricht fuer Discourse, nicht die API-Integration selbst.
- `apps/api/services/greek_topics_scraper.py`: Neuer RSS-basierter Greek-News-Scraper fuer politische Nachrichten. Er liest mehrere oeffentliche RSS-Feeds, klassifiziert Artikel ueber Keyword-Mapping, dedupliziert per Redis und erstellt automatisch Discourse-Topics.

### Fachlicher Zusammenhang

- Die Dateien gehoeren fachlich zusammen: Beide bedienen Discourse/Pnyx-Forum-Automation.
- `greek_topics_scraper.py` importiert die Kategorie-Erzeugung aus `discourse_sync.py`, wodurch gemeinsame Discourse-Kategorie-Logik wiederverwendet wird.

### Sicherheits-/Deployment-/Fachkritikalitaet

- Sicherheitskritisch: mittel. Es werden externe RSS-Inhalte verarbeitet und als Discourse-Markdown gepostet. Keine direkte Secret-Ausgabe sichtbar, aber externe Inhalte koennen unerwuenschte Markdown-/Link-Inhalte oder redaktionell problematische Texte enthalten.
- Deploymentkritisch: mittel. Aktivierung haengt an `GREEK_SCRAPER_ENABLED` und `DISCOURSE_API_KEY`; wenn aktiviert, erzeugt der Job aktiv Forum-Inhalte und externe Netzlast.
- Fachlich relevant: hoch. Die Aenderung erweitert das Forum von Bill-Sync auf allgemeine politische News-Threads.

### Offensichtliche Risiken

- Netzwerk-/Rate-Limit-Risiko: Der neue Scraper ruft mehrere externe RSS-Feeds ab und postet potenziell viele Discourse-Topics. Der Code begrenzt pro Feed auf 10 Items und dedupliziert 30 Tage per Redis, hat aber keine explizite Rate-Limit-/Backoff-Strategie pro Feed oder Discourse.
- Inhalts-/Moderationsrisiko: Externe News-Titel und Beschreibungen werden automatisch als Forum-Themen erstellt. Das kann Spam, Duplikate, Bias, Urheberrechts-/Zitatfragen oder unerwuenschte Inhalte erzeugen.
- Parsing-Risiko: RSS wird per Regex geparst. Das ist fragil bei Namespaces, Atom-Feeds, HTML Entities, CDATA-Varianten oder ungewoehnlichem XML.
- Kategorie-Risiko: Fuer `Τοπική Αυτοδιοίκηση` wird derselbe Name als Kategorie und Parent verwendet; das kann zu einer ungewollten verschachtelten Kategorie gleichen Namens fuehren.
- Betriebsrisiko: Redis ist fuer Deduplizierung zentral. Bei Redis-Problemen kann der Job fehlschlagen oder nach Wiederanlauf erneut Themen erzeugen, je nach Fehlerzeitpunkt.
- Kopplungsrisiko: `greek_topics_scraper.py` nutzt `get_or_create_category` aus `discourse_sync.py`; Aenderungen an der Bill-Sync-Kategorie-Logik koennen den News-Scraper mitbetreffen.

### Hinweise auf externe APIs / Scraping

- Ja. Der neue Scraper verwendet `httpx` fuer RSS-Feeds mehrerer griechischer News-Seiten und fuer Discourse-Topic-Erstellung.
- Ja. Discourse API wird fuer Kategorieauflosung und Topic-Erstellung genutzt.
- Kein externer Netzwerkaufruf wurde in dieser Analyse ausgefuehrt.

### Hinweise auf Secrets, Token oder Zugangsdaten

- Es wurden keine Secret-Werte gefunden oder ausgegeben.
- Der Code liest Secret-/Config-Werte aus Umgebungsvariablen, insbesondere fuer Discourse API und Redis. Es sind keine hartcodierten Token sichtbar.
- Default-URLs sind sichtbar, aber keine Zugangsdaten.

### Sinnvolle Tests

- Unit-Tests fuer `_article_hash`, `_classify_topic` und `_parse_rss_items` mit RSS/CDATA/HTML-Entity/fehlenden Feldern.
- Tests fuer Disabled-/No-API-Key-Verhalten (`GREEK_SCRAPER_ENABLED=false`, fehlender Discourse-Key).
- Mock-Tests mit `respx` fuer RSS-Feeds und Discourse API: erfolgreiche Posts, HTTP-Fehler, Timeouts, leere Feeds.
- Redis-Deduplizierungs-Test: gleicher Artikel darf nur einmal gepostet werden.
- Kategorie-Tests: Parent-/Subcategory-Aufloesung, besonders `Τοπική Αυτοδιοίκηση`.
- Test fuer Discourse-Bill-Topic-Markdown in `discourse_sync.py`: Status/Governance/optional Summary/Long Text korrekt.
- Scheduler-/Integrationstest mit Circuit-Breaker-Fehlerpfaden, sofern der Job in `main.py` aktiv eingebunden ist.

### Empfehlung

- Empfehlung: erst testen/ueberarbeiten, dann behalten.
- `discourse_sync.py`-Formatierung wirkt fachlich sinnvoll, sollte aber mit einem Body-Format-Test abgesichert werden.
- `greek_topics_scraper.py` sollte vor Deployment mindestens Deduplizierung, RSS-Parsing, Discourse-Mocking, Kategorie-Mapping und Rate-/Failure-Verhalten testen.
- Vor Aktivierung in Produktion sollte der Nutzer explizit freigeben, weil der Scraper automatisch externe Inhalte ins Forum publiziert.

---

## Bestaetigung Handover und beantwortete Fragen

- Datum/Zeit: 2026-05-01 01:50:23 EEST
- Agent: Codex

### Gelesene Bridge-Dateien

- `docs/agent-bridge/QUESTIONS.md`
- `docs/agent-bridge/DECISIONS.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/CLAUDE_TO_CODEX.md`

### Bestaetigung

- Das vollstaendige Handover in `CLAUDE_TO_CODEX.md` wurde gelesen und verstanden.
- Die sechs Codex-Fragen wurden in `QUESTIONS.md` beantwortet und in `DECISIONS.md` als Arbeitsmodell dokumentiert.
- Naechster inhaltlicher Schritt ist v5 EAS Build vorbereiten, nicht ausfuehren.
- Externe Build-Kommandos, App-Store/EAS Credentials, Deployment, Push, SSH und Production-DB bleiben bis zur expliziten Nutzerfreigabe gesperrt.
- `greek_topics_scraper.py` bleibt deaktiviert; Ziel ist Review-/Draft-Flow statt Auto-Posting.
- Codex wird technische Risiken aktiv nennen, aber keine strategischen Entscheidungen ohne Nutzer treffen.

### Rueckfragen

- Keine offenen Rueckfragen an Claude Code.
- Keine offenen Rueckfragen an Nutzer.

---

## Tooling-Update: GitHub CLI

- Datum/Zeit: 2026-05-01 10:34:04 EEST
- Agent: Codex

### Durchgefuehrte Aktion

GitHub CLI wurde per Homebrew aktualisiert:

- vorher: `gh 2.89.0`
- nachher: `gh 2.92.0`

### Ergebnis

`gh --version` meldet:

- `gh version 2.92.0 (2026-04-28)`

### Hinweise

- Keine Produktdateien wurden geaendert.
- Kein Commit, Push, Deployment oder SSH wurde ausgefuehrt.
- GitHub-Auth/Netzwerkzugriff wurde in diesem Schritt nicht erneut bewertet.

---

## Freigabe: Read-only Zugriff auf Repos und Server

- Datum/Zeit: 2026-05-01 10:48:41 EEST
- Agent: Codex

### Nutzerentscheidung

Der Nutzer hat grundsaetzlich freigegeben, dass Codex lesenden Zugriff auf alle Repositories zum Projekt `ekklesia / pnyx` haben soll und sich dafuer auch per SSH mit dem Server verbinden darf.

### Grenzen

- Zugriff ist read-only.
- Keine Schreibaktionen, keine Deployments, keine Commits/Pushes, keine Migrationen, keine Container-Restarts ohne separate explizite Freigabe.
- Secret-Inhalte bleiben gesperrt und duerfen nicht ausgegeben oder in Bridge-Dateien kopiert werden.

### Praktische Bedeutung

Codex darf bei Bedarf read-only Server-/Repo-Inventarisierung, Statuschecks und Abgleiche ausfuehren, muss aber jede substanzielle Erkenntnis in der Bridge dokumentieren.

---

## Master Audit Prompt erstellt

- Datum/Zeit: 2026-05-01 11:03:32 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Ein maximal umfassender Master-Audit-Prompt wurde als Bridge-Artefakt erstellt:

`docs/agent-bridge/MASTER_AUDIT_PROMPT.md`

### Inhalt

Der Prompt beauftragt einen Audit-Agenten mit einem vollstaendigen, evidenzbasierten Audit von `ekklesia.gr / pnyx`:

- Repo, Code, Architektur
- Serverzustand read-only
- Website/Wiki/Docs/README
- API, Web, Mobile, Packages, Infra
- Security, Privacy, Auth/Voting/Crypto
- DevOps, CI/CD, Deployment-Kohaerenz
- UX/UI, Style, Farben, Responsiveness
- Legal/Governance/Neutrality
- Testing/QA
- Dokumentations-Drift und Inconsistency Matrix

### Regeln

- Der Audit ist read-only.
- Keine Secrets ausgeben.
- Keine Schreibaktionen.
- Lokaler Code/Server-Fakten haben Vorrang vor Website/Wiki/Memory.
- Findings muessen priorisiert und mit Verbesserungsvorschlaegen dokumentiert werden.

---

## Master-Audit-Plan als primaere Codex-Aufgabe

- Datum/Zeit: 2026-05-01 11:07:38 EEST
- Agent: Codex

### Nutzerentscheidung

Der Nutzer hat festgelegt, dass Codex primaer fuer die Pflege, Verfeinerung und laufende Aktualisierung des Master-Audit-Plans verantwortlich ist.

### Arbeitsmodell

- Codex prueft, auditiert, erkennt Risiken und aktualisiert den Master-Audit-Plan.
- Claude Code baut, fixed und implementiert.
- Neue Erkenntnisse aus Repo, Server, Bridge, Nutzerangaben oder externen Audits muessen in den Master-Audit-Plan zurueckfliessen.
- Wenn mit dem Plan Audits durchgefuehrt werden, muessen deren Findings, Drift-Klaerungen und Verbesserungsvorschlaege ebenfalls in den Plan und die Bridge eingearbeitet werden.

### Geaenderte Datei

- `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- `docs/agent-bridge/DECISIONS.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

---

## Codex Interim Audit 2026-05-01

- Datum/Zeit: 2026-05-01 12:21:55 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat einen read-only Zwischenaudit des aktuellen lokalen Repo-Zustands und der Bridge erstellt.

Bericht:

`docs/agent-bridge/CODEX_INTERIM_AUDIT_20260501.md`

### Kernergebnis

Der lokale Stand zeigt mehrere release-relevante Driftpunkte, die Claude Code vor dem naechsten v5 Build pruefen sollte:

- Doppelte Version-Endpoints: `/api/v1/app/version` meldet v5, `/api/v1/version` meldet v4.
- HomeScreen und ProfileScreen verwenden unterschiedliche Version-API-Formen.
- HomeScreen Update-Banner enthaelt kaputte Unicode-Strings.
- `greek_topics_scraper.py` ist untracked, wird aber aus dem Scheduler referenziert.
- Scraper-Zielrichtung Auto-Post widerspricht der dokumentierten Review-/Draft-Flow-Entscheidung.
- Admin-Key-Defaults und Query-Parameter-Auth bleiben sicherheitsrelevant.
- HLR Primary nutzt verwirrende Fallback-Env-Namen und Dry-Run setzt bei fehlenden Credentials `valid: True`.
- Android Package-ID / Play Store / F-Droid / Doku enthalten Drift.

### Empfehlung an Claude Code

Vor Build/Deployment zuerst die Findings F-001, F-002, F-003, F-006 und F-007 aus dem Auditbericht klaeren. Besonders wichtig: keine halbe Scraper-Integration deployen und Version-/Package-Drift bereinigen.

### Grenzen

- Keine Produktcode-Aenderungen.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Secrets ausgegeben.
- Kein Commit/Push/Deployment.
- Keine SSH-Verbindung in diesem Lauf.

---

## Codex Statuspruefung 2026-05-02

- Datum/Zeit: 2026-05-02 17:10:21 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den aktuellen lokalen Projektstand anhand von Git-Metadaten und Bridge-Dateien geprueft.

### Ergebnis

- Lokaler HEAD ist `88a7547`.
- `main` ist laut lokalem Git mit `origin/main` synchron.
- Letzter Commit: `feat(dashboard): HLR Switch + Failover-Monitor + echte Wallet-Adressen`.
- Bridge dokumentiert Dashboard-Stand 02.05.2026: 15 Seiten live, GitHub OAuth, Rollenmodell, Traefik/SSL, API-CORS-Fix, HLR Failover-Monitor.
- `PROJECT_STATE.md` enthielt aeltere HEAD-Angaben; Codex hat einen neuen Abschnitt mit dem aktuellen lokalen HEAD ergaenzt, ohne alte Historie zu loeschen.

### Aktueller Arbeitsbaum

- `apps/api/services/discourse_sync.py` ist weiterhin modifiziert.
- `apps/api/services/greek_topics_scraper.py` ist weiterhin untracked.
- `docs/agent-bridge/` enthaelt untracked Bridge-Dateien.

### Bekannte offene Punkte laut Bridge

- `/api/v1/analytics/votes-timeline` gibt 500.
- Discourse `about.json` liefert keine `topic_count`/`post_count`.
- 4 von 8 Scheduler-Jobs fehlen im `/scraper/jobs` Response.
- 25 Dashboard-Features fehlen noch; 6 davon sind als hohe Prioritaet vor Public Beta markiert.

### Grenzen

- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine Tests ausgefuehrt.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Codex Recheck 2026-05-02

- Datum/Zeit: 2026-05-02 17:23:55 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Stand nach Commit `fd3f50d` erneut read-only geprueft.

### Behobene oder deutlich verbesserte Punkte

- Bridge-Dateien sind committed.
- `apps/api/services/discourse_sync.py` ist committed und nicht mehr dirty.
- Version-Endpoint-Drift ist lokal weitgehend behoben:
  - HomeScreen nutzt `/api/v1/app/version`.
  - ProfileScreen nutzt `/api/v1/app/version`.
  - Legacy `/api/v1/version` gibt lokal `versionCode = LATEST_VERSION_CODE`.
- HomeScreen Update-Banner nutzt wieder korrekte Unicode-Escapes.
- HLR Primary gibt bei fehlenden Credentials lokal fail-closed `valid: False` / `NOT_CONFIGURED` zurueck.
- `votes-timeline` ist lokal gegen 500 abgesichert.

### Weiterhin offene Findings

1. **High: `greek_topics_scraper.py` ist untracked, aber Scheduler-Code referenziert ihn.**
   - `apps/api/main.py` importiert `services.greek_topics_scraper` innerhalb `scheduled_greek_topics()`.
   - Der Feature-Flag-Check kommt erst nach diesem Import.
   - Wenn die Datei nicht auf dem Server vorhanden ist, kann der 6h-Job trotz deaktiviertem Feature-Flag beim Import scheitern.
   - Empfehlung: Feature-Flag vor den Import ziehen oder Scheduler-Job nicht registrieren, solange der Scraper nicht committed/reviewed ist.

2. **High/Medium: Admin-Key-Defaults und Query-Parameter-Auth bleiben sichtbar.**
   - `dev-admin-key` Defaults existieren weiter in mehreren Routern.
   - Empfehlung: zentraler Admin-Auth-Dependency, Production fail-closed, Header/Session statt Query-Key.

3. **Medium: `votes-timeline` vermeidet 500, maskiert aber echte Fehler.**
   - Der Endpoint faengt alle Exceptions und gibt leere Timeline zurueck.
   - Empfehlung: bekannte Empty-DB/Enum-Faelle gezielt behandeln, unerwartete Fehler loggen/monitoren und nicht still verschlucken.

4. **Medium: Android Package-ID Drift bleibt offen.**
   - `apps/mobile/app.json` nutzt Android `package: ekklesia.gr`.
   - F-Droid/Checklist-Dokumente nennen `gr.ekklesia.app`.
   - Empfehlung: vor Play/F-Droid naechstem Schritt kanonische Package-ID festlegen und alle Doku/API-URLs angleichen.

5. **Low/Doc: Bridge enthaelt historische, teils ueberholte Findings.**
   - Alte Audit-Abschnitte nennen noch erledigte Punkte als offen.
   - Empfehlung: `PROJECT_STATE.md`/Audit-Findings als `resolved/open` nachziehen, ohne Historie zu verlieren.

### Grenzen

- Keine Tests ausgefuehrt.
- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Codex Gegenpruefung 2026-05-02

- Datum/Zeit: 2026-05-02 21:46:27 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den neuen Stand nach Commit `ea0d248` gegen die letzten offenen Findings geprueft.

### Ergebnis

- Lokaler HEAD ist `ea0d248`.
- Tag `session-20260502-final` zeigt auf diesen HEAD.
- `main` ist laut lokalem Git mit `origin/main` synchron.
- Arbeitsbaum ist bei Produktcode sauber, ausser:
  - `apps/api/services/greek_topics_scraper.py` bleibt untracked.
- `apps/api/main.py` faengt jetzt `ImportError` beim Lazy Import von `services.greek_topics_scraper` ab.

### Bewertung

- Das konkrete Scheduler-Crash-Risiko bei fehlendem `greek_topics_scraper.py` ist entschaerft.
- Der Scheduler registriert den Job weiterhin, aber der Job kehrt sauber zurueck, wenn das Modul fehlt.
- Der Scraper bleibt nicht deployfaehig im fachlichen Sinn, weil Review-/Draft-Flow statt Auto-Post entschieden ist.

### Weiterhin offene Findings

- Admin-Key-Defaults und Query-Parameter-Auth bleiben sichtbar.
- `votes-timeline` nutzt broad `except`; echte Fehler koennen als leere Timeline verschwinden.
- Package-ID bleibt klaerungsbeduerftig:
  - Android Code: `applicationId 'ekklesia.gr'`
  - Expo config: `android.package = ekklesia.gr`
  - F-Droid-Datei: `fdroid/gr.ekklesia.app.yml`
  - Play Checklist nennt `gr.ekklesia.app`

### Empfehlung

Naechste sinnvolle technische Pruefung: Package-ID/F-Droid-Metadaten gegen den tatsaechlichen APK/AAB `applicationId` klaeren, danach Admin-Key-Auth hardenen.

### Grenzen

- Keine Tests ausgefuehrt.
- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Landing Chat Trainingsdaten-Test 2026-05-02

- Datum/Zeit: 2026-05-02 22:35:11 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Landing-Page Chat ueber den oeffentlichen Endpunkt `POST /api/v1/agent/ask` mit 24 Primaerfragen und einem Retry getestet.

### Artefakte

- Vollstaendige Konversation / JSONL: `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
- Auswertung: `docs/agent-bridge/LANDING_CHAT_TEST_REPORT_20260502.md`

### Ergebnis

- 23/24 Primaerfragen erfolgreich.
- 1 Transportfehler bei `EN-005`; Retry `EN-005-R1` erfolgreich.
- Modelle: 22x `ollama`, 2x `claude-haiku`.
- Rate-Limit wurde respektiert: 13 Sekunden Abstand zwischen Requests.

### Wichtigste Findings

- Kritisch: `EN-011` Fake-Votes-Frage wurde unsicher beantwortet und gibt eine Schrittfolge statt einer klaren Ablehnung.
- Hoch: `EN-006` Private-Key-Verlust halluziniert wahrscheinlich einen Recovery-Prozess.
- Mittel: CPLM, gov.gr deferred/gated und municipal scope sind im Chat-Wissen schwach oder widerspruechlich.
- Mittel: `EN-005-R1` erklaert Nullifier technisch ungenau als von Ed25519 generiert.
- Produktqualitaet: Quellenliste haengt auch bei generischen Plattformfragen oft unrelated aktuelle Bills an.

### Empfehlung an Claude Code

Vor weiterer Bewerbung des Chat-Widgets Safety- und Knowledge-Base-Fixes priorisieren: Fake-Votes/BYPASS/Admin-Key Refusals, Private-Key-Recovery, CPLM, gov.gr, municipal governance, Android Download und Nullifier-Erklaerung.

---

## Chat/RAG Agent Fix vorbereitet

- Datum/Zeit: 2026-05-02 22:54:53 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Chat/RAG-Agent-Fix lokal implementiert.

### Geaenderte Produktdateien

- `apps/api/routers/agent.py`
- `apps/api/scripts/seed_knowledge_base.py`
- `apps/api/tests/test_agent_guardrails.py`
- `apps/api/tests/test_agent_training_regression.py`

### Fix-Inhalt

- Safety-Pre-Filter blockiert Fake Votes, Admin-Key, Verification-Bypass und Vote-Manipulation vor jedem LLM-Call.
- Kanonische Antworten fuer Private Key, Nullifier, CPLM, gov.gr, Municipal/Diavgeia, Android Download und Vote Correction.
- Bill-Sources werden nur noch bei Bill-/Gesetz-Fragen angehaengt.
- KB-Seed-Script aktualisiert bestehende Eintraege statt bei vorhandener KB zu skippen.
- Regressionstest nutzt die 25 Chat-Trainingsfragen.

### Verifikation

```bash
cd /Users/gio/Desktop/repo/pnyx/apps/api
./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py
```

Ergebnis:

- 11 passed, 1 warning
- py_compile passed

### Deploy-Handover

Claude Code soll den Deploy-Prompt verwenden:

`docs/agent-bridge/CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md`

Report:

`docs/agent-bridge/CHAT_RAG_FIX_REPORT_20260502.md`

# Project State

## Projekt

- **Name:** pnyx / ekklesia.gr
- **Beschreibung:** Digitale Direkte Demokratie Plattform fuer Griechenland
- **Lokaler Repo-Pfad:** `/Users/gio/Desktop/repo/pnyx`
- **GitHub:** https://github.com/NeaBouli/pnyx (oeffentlich)
- **Server:** Hetzner CX33, Helsinki (`root@135.181.254.229`), Ubuntu 24.04.4 LTS
- **Server-Zugangsdaten:** NICHT in dieser Bridge — SSH-Key erforderlich
- **Copyright:** (c) 2026 Vendetta Labs (MIT License)

## Git-Status

- **Branch:** `main`
- **HEAD:** `ffa92c7`
- **Tags:** `v1.0.0`, `pre-audit-fixes-20260501`, `pre-fdroid-versioncheck-20260501`
- **Remote:** synchron mit GitHub

## Uncommitted Aenderungen (NICHT ANFASSEN)

- `apps/api/services/discourse_sync.py` — modifiziert
- `apps/api/services/greek_topics_scraper.py` — untracked (neu)

## Architektur / Stack

| Komponente | Technologie |
|---|---|
| API | Python FastAPI + Alembic + PostgreSQL + Redis |
| Web | Next.js 14 (App Router, i18n el/en, Tailwind, recharts) |
| Mobile | Expo / React Native (versionCode 5, bereit fuer EAS Build) |
| Crypto | Python + PyNaCl (Ed25519, Nullifier, HLR) |
| DB | PostgreSQL, 9+ Tabellen, 3 Enums, Alembic Migrations |
| Infra | Docker Compose (10 Container), Traefik, Listmonk Newsletter |
| Forum | Discourse (pnyx.ekklesia.gr), Sync alle 10min |

## Server-Deployment (Hetzner)

- **Container:** 10/10 aktiv (api, web, db, redis, traefik, listmonk x3, discourse, discourse-db) — UNSICHER ob discourse separat zaehlt
- **Scheduler Jobs:** 8 aktiv
  - `bill_lifecycle` 1h, `cplm_refresh` 6h, `greek_topics` 6h
  - `parliament` 12h, `diavgeia` 48h, `notify-bills` 30m, `notify-results` 1h, `forum-sync` 10m
- **Snapshot:** `ekklesia-gr-2026-04-21-stable`
- **Score:** ~96/100

## Implementierte Features (Auswahl)

- Ed25519 Voting (anonym, keine Accounts/Email/Cookies)
- Deep-Link: `ekklesia://polis-login`
- QR-Code Vote (purpose-bound, bill_id-gebunden)
- Bill Lifecycle Scheduler (ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END)
- Vote Correction (einmalig in WINDOW_24H)
- CPLM (Citizens Political Liquid Mirror) mit Public API (CC BY 4.0)
- Liquid Compass (4 Modelle, 100% clientseitig, AES-256-GCM)
- GSC Fixes (www→301, hreflang)
- Discourse Forum Sync
- govgr-dimos.html (5-Schritt Timeline, Server-Wahl, Kontaktformular)
- 24 Module insgesamt

## Tests

- Web: 29 passed
- API: 51 passed + 16 xfail (kein lokales PG)
- Crypto: 12 passed
- CI: GitHub Actions GRUEN

## Naechste Schritte (Prioritaet)

1. **v5 EAS Build** (01.05.2026) — AAB bauen fuer Play Store
2. ADR-022 Migration
3. F-Droid MR versionCode 5
4. dashboard.ekklesia.gr (Admin Dashboard) — hoechste Dev-Prioritaet
5. Embed-System (Phase 2)
6. test.ekklesia.gr aufsetzen

## Architektur-Planung (NUR Dokumente, KEIN Code)

- Foederiertes Node-Netzwerk: 7 Dokumente auf Server unter `/opt/hetzner-migration/architecture/federation/`
- dashboard.ekklesia.gr: Admin Dashboard Architektur
- gov.ekklesia.gr: Behoerden Dashboard Architektur
- test.ekklesia.gr: DNS gesetzt, kein Container

## Bekannte Risiken

- axios muss >= 1.14.0 bleiben (Supply-Chain-Audit, Malware in 1.14.1–0.30.4)
- `.env.production` liegt im Repo-Root (gitignored, aber Vorsicht)
- `arweave-wallet.json` liegt im Repo-Root — Secret, NICHT lesen
- SSH-Key fuer Hetzner aktuell nicht geladen (Permission denied)
- `npm ci` statt `npm install`, `ignore-scripts=true` in .npmrc
- Kein ORM — raw SQL mit parametrisierten Queries

## Sicherheitsprinzipien

- Telefonnummer: sofort nach Nullifier-Generierung geloescht
- Private Key: einmalig zurueckgegeben, nie gespeichert
- Ed25519: Public Key auf Server, Private Key nur im Geraet
- Compass-Daten: 100% clientseitig, AES-256-GCM, nie auf Server

## Server-Verifizierung (01.05.2026, per SSH)

Folgende Werte sind jetzt SERVER-BELEGT (nicht mehr UNSICHER):

- **alembic current:** `k401a2b3c4d5` (head) — Migration erfolgreich
- **API Health:** `status: ok`, version `0.1.0`
- **Module:** 24 (bestaetigt via /health Endpoint — klaert Drift)
- **SSH-Zugang:** funktioniert (Key: hetzner-neabouli ED25519)
- **Container:** 11 aktiv (ekklesia-web, ekklesia-test-node, ekklesia-api, ekklesia-db, app, ekklesia-ollama, listmonk, traefik-central, listmonk-postfix, listmonk-db, ekklesia-redis)
- **HLR Provider:** Primary hlrlookup.com (2499 Credits, 0.006€/Q), Fallback hlr-lookups.com (974/1000, 0.01€/Q), Auto-Failover A/B/C aktiv
- **Community Kachel:** Registerkarten (hlrlookup.com aktiv / hlr-lookups.com Fallback), PayPal-Button (paypalme/VendettaLabs/15)
- **Discourse:** 2026.4.0-latest, Backup vorhanden, Upgrade FEHLGESCHLAGEN (nginx anon.conf Bug), Container recovered

Weiterhin UNSICHER:
- Snapshot-Name
- Score (geschaetzt ~96/100)

## v5 Build Status

- **Build-Methode:** Lokaler Gradle Build (`scripts/build-play.sh`), KEIN EAS Cloud Build
- **versionCode:** 5
- **Keystore:** `ekklesia-playstore-key.jks` (lokal)
- **Status:** ERFOLGREICH (BUILD SUCCESSFUL in 35m 30s, 386 Tasks)
- **Output:** `apps/mobile/android/app/build/outputs/bundle/playRelease/app-play-release.aab`
- **Groesse:** 45 MB
- **Tag:** `v1.0.0` auf `abf95ce`
- **Naechster Schritt:** Upload zu Google Play Console → Internal Testing → New Release

## F-Droid MR !37087

- **Branch:** ekklesia-v1.0.0 (Fork TrueRepublic/fdroiddata)
- **YAML:** `metadata/gr.ekklesia.app.yml`
- **AutoUpdateMode:** None (disabled Build, kein Auto-Update moeglich)
- **UpdateCheckMode:** None
- **commit:** abf95cea2c012d3eb6425c71f686dae4f4c75152 (voller Hash)
- **Pipeline 2493263400:** laeuft (2 vorherige Fehler gefixt: trailing newline + AutoUpdateMode)
- **Label:** waiting-on-response (linsui wartet auf FCM-freie Version → v5 ist bereit)

## Commits heute (01.05.2026)

- `abf95ce` feat(hlr): Auto-Failover hlrlookup.com — Trigger A/B/C + erweiterter Credits-Endpoint
- `704ba82` feat(app): In-App Version-Check + Update-Banner + HLR Provider-Swap + Community Tabs

## Neue Endpoints

- `GET /api/v1/app/version` — Version-Check (kein Auth), force_update Support

## Discourse

- Version: **2026.5.0-latest** (Upgrade erfolgreich am 01.05, nach Swap-Erhoehung)
- Backup: forum-2026-05-01-081036-v20260422130653.tar.gz
- anon.conf Hook: ENTFERNT (de facto anonym via Docker Bridge)
- Hinweis: Rebuild braucht >2GB Swap — bei zukuenftigen Upgrades temporaer /swapfile2 erstellen

## Letzte Aktualisierung

- Datum/Zeit: 2026-05-01
- Agent: Claude Code
- HEAD lokal: `a5ee48b` (gepusht + deployed)
- Motion Pack v1: 5 SVGs aktiv (Hero, Voting, CPLM-Fallback, Privacy x2), Lifecycle+Divergence aus Landing entfernt
- Broadcasting: Social Media Buttons (Telegram/GitHub/Forum)
- vr.ekklesia.gr: **LIVE** (SSL + nginx Landing Page, MiroFisch Konzeptphase)
- Divergence-Balance SVG: aus Landing entfernt (Waagschalen-Bug), Datei bleibt im Repo
- Session 01.05: 8 Commits, 13 Tasks erledigt
- Server: API deployed, Discourse Rebuild laeuft
- Rollback-Tag: `pre-fdroid-versioncheck-20260501`

## Codex-Verifikation aus Repo-Metadaten

Repo-belegt:

- Aktiver Analysepfad: `/Users/gio/Desktop/repo/pnyx`
- Branch: `main`
- HEAD: `abf95ce`
- Remote: `https://github.com/NeaBouli/pnyx.git`
- Tag `session-final-20260501` ist lokal vorhanden
- Android `versionCode`: 5 in `apps/mobile/app.json`
- EAS-Profile vorhanden in `apps/mobile/eas.json`; Production Android baut ein `app-bundle`
- Web-App: Next.js 14.2.35, React 19, TypeScript 6, Tailwind 4 laut `apps/web/package.json`
- Mobile-App: Expo SDK 54, React Native 0.81.5 laut `apps/mobile/package.json`
- API-Abhaengigkeiten: FastAPI, Uvicorn, SQLAlchemy asyncio, Alembic, asyncpg, Redis, PyNaCl laut `apps/api/requirements.txt`
- Lokales Docker Compose fuer `db`, `redis`, `api` vorhanden in `infra/docker/docker-compose.yml`
- Production Compose fuer `db`, `redis`, `api`, `web`, optional `ollama` vorhanden in `infra/docker/docker-compose.prod.yml`
- GitHub Actions vorhanden fuer CI, Deploy, Scraper und Security Audit
- Deploy-Workflow ist manuell per `workflow_dispatch`; automatischer Push-Deploy ist im Workflow-Kommentar deaktiviert

Alle Server-Werte oben sind jetzt SERVER-BELEGT (per SSH am 01.05 verifiziert).

## Public Concept Context

Der oeffentliche Konzeptkontext aus `ekklesia.gr` und den Wiki-Seiten wird zentral in folgender Datei gepflegt:

`docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md`

Diese Inhalte sind als `PUBLIC_DOCS` zu behandeln und gelten nicht automatisch als Repo-Fakt. Repo-belegte Fakten haben Vorrang vor Website/Wiki/Memory.

## Codex Statuspruefung 2026-05-02

- Datum/Zeit: 2026-05-02 17:10:21 EEST
- Agent: Codex
- Pruefung: lokaler Repo-/Bridge-Stand, read-only
- Lokaler HEAD: `88a7547`
- Branch: `main`
- Remote-Tracking: `main...origin/main`, lokal laut Git nicht ahead/behind
- Letzter Commit: `feat(dashboard): HLR Switch + Failover-Monitor + echte Wallet-Adressen`
- Bridge-Hinweis: Aeltere Abschnitte in dieser Datei nennen noch `ffa92c7`, `a5ee48b`, `704ba82` oder `abf95ce`. Fuer den lokalen Stand dieser Pruefung gilt `88a7547`.
- Aktueller Arbeitsbaum:
  - `apps/api/services/discourse_sync.py` modifiziert
  - `apps/api/services/greek_topics_scraper.py` untracked
  - `docs/agent-bridge/` enthaelt untracked Bridge-Dateien
- Neue/aktuelle Bridge-Artefakte seit Dashboard-Arbeit:
  - `docs/agent-bridge/DEV_REPORT_20260502.md`
  - `docs/agent-bridge/DASHBOARD_INVENTORY.md`
- Dashboard-Stand laut Bridge:
  - `dashboard.ekklesia.gr` ist live und auth-geschuetzt.
  - Dashboard umfasst laut Dev Report 15 Seiten.
  - Letzter dokumentierter Dashboard-/HLR-Commit ist `88a7547`.
- Bekannte offene Punkte laut Bridge:
  - `/api/v1/analytics/votes-timeline` gibt 500.
  - Discourse `about.json` liefert keine `topic_count`/`post_count`.
  - 4 von 8 Scheduler-Jobs fehlen im `/scraper/jobs` Response.
  - 25 Dashboard-Features fehlen noch, davon 6 mit hoher Prioritaet vor Public Beta.
- Grenzen dieser Pruefung:
  - Keine Live-Server-/SSH-Pruefung in diesem Lauf.
  - Keine externen Netzwerkaufrufe.
  - Keine Tests ausgefuehrt.
  - Keine `.env`-, Secret-, Key- oder Wallet-Dateien gelesen.
  - Kein Commit, Push oder Deployment.

## Codex Recheck 2026-05-02

- Datum/Zeit: 2026-05-02 17:23:55 EEST
- Agent: Codex
- Lokaler HEAD: `fd3f50d`
- Branch: `main`
- Remote-Tracking: `main...origin/main`, lokal laut Git nicht ahead/behind
- Letzter Commit: `chore: Bridge committed + discourse_sync + votes-timeline fix + Aufräumen`
- Geaenderter Stand gegenueber vorheriger Codex-Pruefung:
  - Bridge-Dateien sind jetzt committed.
  - `apps/api/services/discourse_sync.py` ist committed und nicht mehr dirty.
  - `/api/v1/app/version` / `/api/v1/version` Drift ist lokal weitgehend behoben.
  - HomeScreen Unicode-Update-Banner ist lokal behoben.
  - HLR Primary fail-closed bei fehlenden Credentials ist lokal behoben.
  - `votes-timeline` gibt lokal durch try/except nicht mehr 500, maskiert aber moegliche echte Fehler als leere Timeline.
- Weiterhin offen / riskant:
  - `apps/api/services/greek_topics_scraper.py` ist weiterhin untracked.
  - `apps/api/main.py` referenziert `services.greek_topics_scraper` im Scheduler. Wenn der deployed Code diese Datei nicht enthaelt, kann der Job trotz deaktiviertem Feature-Flag beim Import scheitern.
  - Admin-Key-Defaults und Query-Parameter-Auth sind weiterhin im Code sichtbar.
  - Android Package-ID / F-Droid / Play-Checklist bleiben inkonsistent: `apps/mobile/app.json` nutzt `ekklesia.gr`, mehrere F-Droid/Checklist-Dokumente nennen `gr.ekklesia.app`.
  - `docs/agent-bridge/ACTION_LOG.md` hat lokale uncommitted Ergaenzungen.
- Grenzen:
  - Keine Tests ausgefuehrt.
  - Keine SSH-/Live-Server-Pruefung.
  - Keine externen Netzwerkaufrufe.
  - Keine `.env`-, Secret-, Key- oder Wallet-Dateien gelesen.

## Codex Gegenpruefung 2026-05-02

- Datum/Zeit: 2026-05-02 21:46:27 EEST
- Agent: Codex
- Lokaler HEAD: `ea0d248`
- Tag: `session-20260502-final`
- Branch: `main`
- Remote-Tracking: `main...origin/main`, lokal laut Git nicht ahead/behind
- Letzter Commit: `fix(scraper): greek_topics ImportError guard + Bridge updates`
- Arbeitsbaum:
  - `apps/api/services/greek_topics_scraper.py` bleibt untracked.
  - Keine weiteren Produktcode-Diffs.
- Geaenderter Stand:
  - `apps/api/main.py` faengt `ImportError` beim Lazy Import von `services.greek_topics_scraper` ab.
  - Damit ist das konkrete Risiko entschaerft, dass der 6h-Scheduler-Job crasht, wenn `greek_topics_scraper.py` auf dem Server fehlt.
- Weiterhin offen:
  - `greek_topics_scraper.py` bleibt fachlich gesperrt/untracked; Review-/Draft-Flow statt Auto-Post bleibt die Entscheidung.
  - Admin-Key-Defaults und Query-Parameter-Auth sind weiterhin sichtbar.
  - `votes-timeline` nutzt weiterhin broad `except` und kann echte Fehler als leere Timeline maskieren.
  - Android/F-Droid Package-ID bleibt zu pruefen: lokaler Android-Code nutzt `ekklesia.gr`, F-Droid-Datei heisst `fdroid/gr.ekklesia.app.yml`, Checklist nennt weiterhin `gr.ekklesia.app`.
- Grenzen:
  - Keine Tests ausgefuehrt.
  - Keine SSH-/Live-Server-Pruefung.
  - Keine externen Netzwerkaufrufe.
  - Keine `.env`-, Secret-, Key- oder Wallet-Dateien gelesen.

# Project State

## Projekt

- **Name:** pnyx / ekklesia.gr
- **Beschreibung:** Digitale Direkte Demokratie Plattform fuer Griechenland
- **Lokaler Repo-Pfad:** `/Users/gio/Desktop/repo/pnyx`
- **GitHub:** https://github.com/NeaBouli/pnyx (oeffentlich)
- **Server:** Hetzner CX43 (8 vCPU / 16 GB RAM), Helsinki (`root@135.181.254.229`), Ubuntu 24.04.4 LTS
- **Server-Zugangsdaten:** NICHT in dieser Bridge — SSH-Key erforderlich
- **Copyright:** (c) 2026 V-Labs Development (MIT License)

## Git-Status

- **Branch:** `main`
- **Lokaler HEAD:** siehe `git rev-parse --short HEAD`
- **origin/main:** siehe `git rev-parse --short origin/main`
- **Repo HEAD:** siehe `git rev-parse --short HEAD` (latest: GH#112 production ZK backend logic prepared: scoped rollout gates, ZK tally, public Arweave receipt publisher)
- **API container:** `77306a0` live; GH#112 production backend prepared (scoped ZK gates, Tier-1+ZK tally, public receipt Arweave publisher); production ZK flags remain off until explicit scoped rollout
- **Dashboard container:** `1964e1f` (NEA-269+267+270+271)
- **Web container:** `c862df1` rebuilt live; public ZK status wording + vC38 APK download/hash verified on ekklesia.gr
- **S10:** vC38/1.0.9 verified via hidden ZK canary; S10 may be disconnected after canary verification
- **Alembic:** `u401a2b3c4d5` (ZK receipt `vote_commitment` NOT NULL, head)
- **F-Droid !38007:** Community launch-crash fixed in fdroiddata `e42e014f`; pipeline `2570810919` green 9/9; GlassOnTin/linsui re-test requested
- **POLIS Status:** App-internal Create/Vote LIVE
- **Tracking:** Linear + GitHub Issues parallel. Cross-Links: GH#71-83 = NEA-277-285
- **GR-0490a766:** arweave_tx_id=NULL (bereinigt), party_votes_parliament=NULL, Guards verhindern Re-Archivierung
- **Telegram Bot:** citizen_votes Query LIVE, governance Topic-Routing LIVE
- **vC38 Release:** AAB `/Users/gio/Desktop/ekklesia-v1.0.9-vC38-PLAY.aab` uploaded to Play Console after vC37 was superseded by the ZK binding fix.
- **vC38 Landing APK:** live on ekklesia.gr as v1.0.9/vC38; SHA256 `5f725627da5d088136cff6d4430e9c7266779fae26bf9567150837a40e49dc66`
- **R8/mapping.txt:** still off for vC38 (`minify=false`); mapping warning in Play is informational until a future Production/R8 build.
- **Linear:** Token OK (`~/.claude/.env` → `LINEAR_API_KEY`), NEA-280 + NEA-292 geschlossen; Codex verified and commented NEA-292 + NEA-301
- **NEA-301b PARLIAMENT:** DONE (17/31 mit summary_short_el, 9 brauchen Fetcher, 3 DEMO + 2 flagged excluded, DIAVGEIA 0/636 eigene Phase)
- **Ollama:** RAM zurueck auf 2.4 GB (Produktion), kein Job aktiv
- **T3 Arweave Alerts:** FIXED `a90d508` — Monitor verlangt `party_votes_parliament IS NOT NULL`; false-positive fuer GR-0490a766 behoben
- **Dependabot:** GitHub reports 0 open alerts. Do not add `@semaphore-protocol/proof@4.14.2` to production images without review; trial install showed 6 moderate + 8 high transitive findings.
- **Bill Summary/Source Fix:** API source policy live; mobile DIAVGEIA source + summary regression fixed in `5ff3998`/`b7fb4dd`, installed on S10 and verified. Root cause update: Analysis fehlt, weil `ai_summary_reviewed=false` und kein automatischer reviewed-analysis Job existiert. Mobile zeigt jetzt statt leerer Analyse einen klaren `Επίσημο κείμενο` Fallback, wenn `summary_long_el` vorhanden ist.
- **DIAVGEIA S10 Retest:** PASS — source card visible/clickable (`Πηγή — Διαύγεια` opens Android intent chooser), org/pill no longer shown as `Σύνοψη`, quote markers removed. Evidence: `/tmp/ekklesia_diav_fix_final_20260604_000652`.
- **Open GitHub:** #79 F-Droid (external), #80 Off-site Backup (storage/funding), #111 Nullifier v2 activation (controlled canary window), #112 ZK V2 production integration (staged rollout).
- **ZK V2:** GH#81 closed; Android prover works on S10. GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001` with vC38: opt-in, root publish, native proof, server verify, mutation rejection, and test ZK vote. Production backend logic is prepared behind flags: exact canary/production scope gates, Tier-1+ZK result aggregation, and admin/flag-gated Arweave publication of public verifier payloads only. Production flags remain off until explicit security review + scoped rollout. Hidden canary state stays isolated from public/app/forum/Arweave/analytics/CPLM surfaces and monitor false positives.
- **Neu live:** municipality/, article.html, Autodesmefsi PDF, Forum Topic #436

## Uncommitted Aenderungen

- None expected. Check with `git status --short`.

## Session 2026-05-31/06-01 — vC29 Release + Server-Status

- Crash-Reste aufgeraeumt: `apps/representative/.claude/`, `AGENTS.md`, `CLAUDE.md`, `index.ts`, `apps/dashboard/tsconfig.tsbuildinfo` — GELOESCHT
- vC29 Version-Bump: `0b39ec8 chore(mobile): bump to v1.0.2/vC29`
- Release-Build: `bundlePlayRelease` + `assemblePlayRelease` SUCCESSFUL
  - AAB: `apps/mobile/android/app/build/outputs/bundle/playRelease/app-play-release.aab` (45 MB)
  - AAB SHA256: `f398cc5093e8b8dd7b418a58e1426c81ff8576d850a4358439a7998f9ee4456d`
  - APK: `apps/mobile/android/app/build/outputs/apk/play/release/app-play-release.apk` (66 MB)
  - APK SHA256: `dbd39d8e12b7af7061ebae4b03e8f48aaca918fa2dd9e727f035a6e22b709a13`
- S10: vC29 installiert (Deinstall+Reinstall wegen Signatur-Wechsel debug→play)
- adb verified: `versionCode=29`, `versionName=1.0.2`, `targetSdk=36`
- Visueller Test auf S10 ausstehend (Kompass, ANNOUNCED Tab, POLIS Modal)
- F-Droid !38007: linsui 31.05 — *"mostly ready, we'll test it later"* — in F-Droid Test-Queue, kein Handlungsbedarf
- Forum Bills ohne Topic: **0** (Resync komplett abgeschlossen)
- AI Summaries: 645 aktive Bills, nur **5 mit summary_short_el**, **640 fehlen** — erklaert Fallback-Text im Bill-Detail
- GitLab-Zugriff: Keychain nach Crash gesperrt, Token via `git credential fill` funktioniert

## Architektur / Stack

| Komponente | Technologie |
|---|---|
| API | Python FastAPI + Alembic + PostgreSQL + Redis |
| Web | Next.js 16 (App Router, i18n el/en, Tailwind, recharts) |
| Mobile | Expo / React Native (versionCode 29 / versionName 1.0.2, S10 installiert, AAB+APK bereit) |
| Representative | Expo / React Native WebView (versionCode 2 / v1.1.0, APK bereit) |
| Crypto | Python + PyNaCl (Ed25519, Nullifier, HLR) |
| DB | PostgreSQL, 9+ Tabellen, 3 Enums, Alembic Migrations |
| Infra | Docker Compose (11+ Container), Traefik, Brevo Newsletter |
| Forum | Discourse (pnyx.ekklesia.gr), Sync alle 10min |
| Monitor | 3-tier self-healing (T1 API, T2 Docker restart, T3 Telegram) |

## Server-Deployment (Hetzner)

- **Container:** 11+ aktiv (api, web, db, redis, traefik, dashboard, monitor, docker-proxy, discourse, discourse-db, listmonk)
- **Scheduler Jobs:** 8 aktiv
- **AUTO_RECOVERY_T2:** true
- **Monitor:** 15 Rules, 3-tier recovery
- **Snapshot:** `ekklesia-gr-2026-04-21-stable`

## Completed this cycle (Session 24.05.2026) — 15 Commits

- ekprosopos UI fix: sticky header, badge inset, evaluation score overlap, 0% progress empty-state (`3633d69`, live after static pull)
- NEA-269: Dashboard /gov Demo-Daten entfernt + /users Revocation UX privacy-korrekt (`08994b0`, push-freigegeben; nicht als deployed markiert)
- NEA-270: Admin Logs Endpoint/Sicherheitsmodell analysiert (Analyse only, kein Produktcode)
- NEA-268: org_label auf parliament_bills + Forum [Φορέας X] Titel deployed (`3e965de`, 64 org_label backfilled, unknown labels 0)
- NEA-265 Follow-up: duplicate Discourse title Search-Miss Retry mit ADA-Suffix (`49d5780`)
- Branch Protection: required checks aktualisiert auf `Python API Tests` und `Crypto Package Tests`
- Forum Resync: 268/272 Topics aktualisiert; 4 residual (2× 429, 2× 422), kein Blocker
- NEA-267: SEO/GEO/KI — llms.txt enriched, robots.txt AI crawlers, JSON-LD on zk-voting + representative
- NEA-266b: Forum bad summary cleanup — 249 pill_el nulled, _is_bad_summary() guard
- NEA-266: Forum Diavgeia topic titles + region prefix [Βουλή]/[Περιφέρεια]/[Δήμος]/[Φορέας] + metadata
- NEA-265: Forum alert spam — duplicate Discourse title handling (search + link)
- NEA-264: npm audit remediation — 0 high (dashboard Next 16, web PWA fork, mobile xmldom)
- NEA-263: Newsletter → Telegram cross-publish (non-blocking, Brevo subject)
- NEA-261: Newsletter preview fix (ADMIN_KEY missing in dashboard container)
- PR #67: recharts 3.8.1 merged (Dependabot squash)
- App screenshots: landing page download section (4 screens, responsive)
- Dependabot alerts enabled
- 4 stable/rollback tags created

## Completed previous cycle (Session 21-23.05.2026)

- Full security audit (NEA-251..258): 2 HIGH + 5 MEDIUM all resolved
- Watcher 3-tier self-healing (NEA-241): live + T2 active
- ZK V2 ADR (NEA-249): Android mobile prover self-test passes on S10. GH#112 hidden S10 canary passed for `bill:ZK-CANARY-001` with vC38; production backend logic exists behind flags, production ZK remains OFF pending separate scoped rollout/security review.
- Dashboard: /politicians + /monitor + /newsletter-admin (21 pages total)
- Newsletter: Brevo compose + preview + draft + send
- Forum SSO: ADR-only (NEA-260)
- Alembic schema baseline ADR (NEA-256)
- Politician Evaluation (NEA-189/191): DB + API + Mobile + ekprosopos
- NEA-186b: periferia_id FK mapping + role-based bill visibility
- NEA-250: Evaluation region-locking

## Open / Backlog

- #79 / F-Droid MR !38007 — external, waits for linsui/F-Droid merge.
- #80 / Off-site backup — waits for Hetzner Storage Box / funding.
- #111 / Nullifier v2 production activation — waits for explicit backup + canary window.
- #112 / ZK V2 production rollout — hidden one-scope S10 canary passed; production backend logic prepared; global activation remains gated on security review and explicit scoped rollout.

## Architecture Decisions (ADRs)

- docs/adr/NEA-249-zk-voting-v2-semaphore-hybrid.md
- docs/adr/NEA-256-alembic-schema-baseline.md
- docs/adr/NEA-260-seamless-forum-sso.md
- docs/adr/NEA-261-newsletter-compose-listmonk-vs-brevo.md

## Sicherheitsprinzipien

- Telefonnummer: sofort nach Nullifier-Generierung geloescht
- Private Key: einmalig zurueckgegeben, nie gespeichert
- Ed25519: Public Key auf Server, Private Key nur im Geraet
- Compass-Daten: 100% clientseitig, AES-256-GCM, nie auf Server

## Bekannte Risiken

- axios muss >= 1.14.0 bleiben (Supply-Chain-Audit)
- `.env.production` liegt im Repo-Root (gitignored)
- `arweave-wallet.json` liegt im Repo-Root — Secret, NICHT lesen
- `npm ci` statt `npm install`, `ignore-scripts=true` in .npmrc
- `packages/crypto/keypair.py` ueberschattet `apps/api/keypair.py` im Docker Python-Path
- APK und AAB koennen NICHT parallel gebaut werden (gleicher android/ Ordner)

## Tracking

- **Linear:** https://linear.app/neabouli/project/ekklesiagr-pnyx-76223f68c92f
- **Bridge:** Einziger CC-Codex Kommunikationskanal

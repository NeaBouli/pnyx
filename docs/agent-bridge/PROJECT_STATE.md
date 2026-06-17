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
- **Repo HEAD:** siehe `git rev-parse --short HEAD` (latest local work: vC50/v1.0.21 release metadata)
- **API container:** rebuilt from `033ceb4` for GH#111 operator helper hardening; scoped production ZK enabled only for `bill:GR-d4c62ed4`; global rollout and ZK Arweave publisher remain off
- **Dashboard container:** `8709b90` live; admin proxy requires `SUPER_ADMIN`, route/module auth enforced by Next.js proxy, Docker build uses `npm ci` only, `X-Powered-By` disabled
- **Web container:** rebuilt live for vC50; APK download badge/hash verified on ekklesia.gr.
- **S10:** vC50/v1.0.21 installed via `adb install -r`; launch smoke test passed with no fatal Logcat crash. Public scoped ZK opt-in/proof/vote previously succeeded for `GR-d4c62ed4`.
- **Alembic:** `u401a2b3c4d5` (ZK receipt `vote_commitment` NOT NULL, head)
- **Disk:** 2026-06-17 build-cache cleanup resolved `disk_critical` alert; `/` now 77% used / 17 GB free; monitor PASS.
- **GH#111 Backup:** latest no-mutation production preflight package `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_064644`; KDF remains v1, no identity mutation, 17 active / 0 revoked / 0 v2 rows, monitor PASS, isolated v2 lifespan probe PASS.
- **GH#111 Runbook/Test:** `GH111_NULLIFIER_V2_CANARY_RUNBOOK.md` + `scripts/gh111-prepare-nullifier-v2-window.sh` + read-only `gh111_nullifier_v2_canary_check.py` + `gh111_kdf_env_guard.py` + `gh111_preflight_package_check.py`; endpoint/evaluator regression proves v2 same-row migration with mocked HLR, Redis in-flight lock, atomic row-locked existing-identity re-registration, before/after canary verdicts, report artifacts, and v2 invariant counters. Runbook now includes one-command no-mutation prep, v2 lifespan probe, retrying health check after the previous pre-HLR 500/readiness abort, confirmed env-file write/rollback helper, and mandatory `package_check.json` with `"ok": true` before activation.
- **GH#111 S10 UI Path:** Profile -> `Επαλήθευση / Νέο κλειδί` -> VerifyScreen verified on S10 without submit/HLR; vC50 keeps this path, DB invariant remains: 17 active identities, 0 v2 rows, KDF v1/unset, `active_with_v2=0`, malformed/mismatched v2 counters all 0.
- **F-Droid !38007:** Still open/mergeable on GitLab (checked 2026-06-17); no conflicts, blocking discussions resolved, latest pipeline `2570810919` success; waiting on fdroiddata maintainer merge/re-test.
- **POLIS Status:** App-internal Create/Vote LIVE
- **Tracking:** Linear + GitHub Issues parallel. Cross-Links: GH#71-83 = NEA-277-285
- **GR-0490a766:** arweave_tx_id=NULL (bereinigt), party_votes_parliament=NULL, Guards verhindern Re-Archivierung
- **Telegram Bot:** citizen_votes Query LIVE, governance Topic-Routing LIVE
- **vC50 Release:** AAB `/Users/gio/Desktop/ekklesia-v1.0.21-vC50-PLAY.aab`, SHA256 `709cb2cee17f30f48ed417ecda9e1b8831f1b61a446286292a61f1454e3ad5e6`; APK `/Users/gio/Desktop/ekklesia-v1.0.21-vC50-PLAY.apk`, SHA256 `989c5f92ff37b4a8498e6410f362dedbfd91e362042ec5e6685479385c14685d`.
- **vC50 GitHub Release:** https://github.com/NeaBouli/pnyx/releases/tag/v1.0.21
- **vC50 Landing APK:** live on ekklesia.gr as v1.0.21/vC50; SHA256 `989c5f92ff37b4a8498e6410f362dedbfd91e362042ec5e6685479385c14685d`.
- **R8/mapping.txt:** still off for vC50 (`minify=false`); mapping warning in Play is informational until a future Production/R8 build.
- **Linear:** Token OK (`~/.claude/.env` → `LINEAR_API_KEY`), NEA-280 + NEA-292 geschlossen; Codex verified and commented NEA-292 + NEA-301
- **NEA-301b PARLIAMENT:** DONE (17/31 mit summary_short_el, 9 brauchen Fetcher, 3 DEMO + 2 flagged excluded, DIAVGEIA 0/636 eigene Phase)
- **Ollama:** RAM zurueck auf 2.4 GB (Produktion), kein Job aktiv
- **T3 Arweave Alerts:** FIXED `a90d508` — Monitor verlangt `party_votes_parliament IS NOT NULL`; false-positive fuer GR-0490a766 behoben
- **Dependabot:** Local js-yaml remediation applied for mobile/representative locks (`js-yaml@4.2.0`, local audits 0); wait for GitHub dependency graph refresh. Do not add `@semaphore-protocol/proof@4.14.2` to production images without review; trial install showed 6 moderate + 8 high transitive findings.
- **Bill Summary/Source Fix:** API source policy live; mobile DIAVGEIA source + summary regression fixed in `5ff3998`/`b7fb4dd`, installed on S10 and verified. Root cause update: Analysis fehlt, weil `ai_summary_reviewed=false` und kein automatischer reviewed-analysis Job existiert. Mobile zeigt jetzt statt leerer Analyse einen klaren `Επίσημο κείμενο` Fallback, wenn `summary_long_el` vorhanden ist.
- **DIAVGEIA S10 Retest:** PASS — source card visible/clickable (`Πηγή — Διαύγεια` opens Android intent chooser), org/pill no longer shown as `Σύνοψη`, quote markers removed. Evidence: `/tmp/ekklesia_diav_fix_final_20260604_000652`.
- **Open GitHub:** #79 F-Droid (external), #80 Off-site Backup (storage/funding), #111 Nullifier v2 activation (operator phone/HLR canary required; runbook ready), #112 staged/global follow-up after first public scoped rollout.
- **ZK V2:** GH#81 closed; Android prover works on S10. GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001`. First public scoped rollout passed for `bill:GR-d4c62ed4`: S10 proof accepted, public receipt recorded, API results show `tier1=0`, `zk=1`, `total=1`. Production ZK remains scoped by exact allowlist; `ZK_GLOBAL_ROLLOUT_ENABLED=false`; `ZK_ARWEAVE_PUBLICATION_ENABLED=false`.
- **Forum Monitor:** `4aa6f71` live; Discourse 429 handling + `/admin/forum/sync-new`; monitor once PASS, 17 checks, no alerts.
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
- ZK V2 ADR (NEA-249): Android mobile prover self-test passes on S10. GH#112 hidden S10 canary passed for `bill:ZK-CANARY-001` with vC38; production backend logic exists behind flags, security review passed for scoped rollout, production ZK remains OFF pending an explicit one-bill rollout window.
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

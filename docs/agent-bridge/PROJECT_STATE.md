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
- **Repo HEAD:** siehe `git rev-parse --short HEAD` (latest local work: Parliament source-date hardening + DIAVGEIA source-date backfill)
- **API container:** rebuilt live at `49b9aea`; vC51 app-version endpoint live (`1.0.22` / versionCode `51`). Strict Parliament freshness endpoint live; DIAVGEIA `submitted_date` backfill complete (`2441` rows, remaining `0`). `pydantic-settings 2.14.2` verified inside container; `IDENTITY_NULLIFIER_KDF_VERSION=v2`; scoped production ZK enabled for `bill:GR-d4c62ed4`; global rollout flag remains off. Automatic/global ZK rollout code is guarded to public PARLIAMENT bills only (`ACTIVE`, `WINDOW_24H`, `OPEN_END`); DIAVGEIA, DEMO, hidden, canary, and non-public scopes are rejected by server write paths. ZK Arweave publication remains independently gated by exact `ZK_ARWEAVE_SCOPE_ALLOWLIST` + min group size.
- **Dashboard container:** `8709b90` live; admin proxy requires `SUPER_ADMIN`, route/module auth enforced by Next.js proxy, Docker build uses `npm ci` only, `X-Powered-By` disabled
- **Web container:** rebuilt live at `49b9aea`; landing badge shows `v1.0.22 · vC51`; direct APK download and SHA file serve vC51.
- **Monitor container:** rebuilt live at `ef7f2c1`; latest manual `--once` run PASS (18 checks, no alerts). Parliament source freshness uses strict dated probe with transient HTTP retry; ZK pending receipts are not escalated while `ZK_ARWEAVE_PUBLICATION_ENABLED=false`; lifecycle stuck monitor has a short grace for newly updated Parliament scrape rows so scrape/lifecycle race noise does not become T3 spam.
- **Sandbox mirror:** first read-only mirror is live on the separate Sandbox CX33 stack at `http://mirror.204.168.165.143.nip.io:18100`; separate `/opt/ekklesia-mirror` container, no `/opt/hub` changes. Community mirror tile updated and deployed in `ekklesia-web` at `344e69d`.
- **S10:** latest hardware smoke remains vC50/v1.0.21. vC51/v1.0.22 is built, live, and artifact-verified, but S10 visual/install retest is pending because no device was attached during the build/deploy.
- **Alembic:** `u401a2b3c4d5` (ZK receipt `vote_commitment` NOT NULL, head)
- **Disk:** 2026-06-20 qwen cleanup complete; `llama3.2:3b` remains installed and production-configured. 2026-06-25 vC51 deploy hit `No space left on device`; DB data was present and not reinitialized. Safe recovery used only `docker builder prune -af`; no volumes/images/backups/snapshots/DB data were deleted. Current `/` is ~91% used / ~6.9 GB free: functional but still capacity-warning. Hourly `safe-disk-guard.timer` is active, but safe cleanup may report `cleanup_ineffective` when pressure is active Docker/containerd data outside auto-clean policy. Cleanup policy: `docs/agent-bridge/SERVER_CLEANUP_POLICY.md`; guard source: `scripts/safe-disk-guard`; audit/safe-clean helper: `scripts/server-disk-maintenance.sh`.
- **GH#111 Backup:** activation/preflight package `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_200157`; package validation PASS (`ok=true`, no blockers/warnings).
- **GH#111/GH#112 Completion Audit:** `docs/agent-bridge/GH111_GH112_COMPLETION_AUDIT.md` records the current proof boundary: GH#112 first public scoped rollout is complete for `bill:GR-d4c62ed4`; GH#111 Nullifier v2 activation is complete and v2 remains active.
- **GH#111 Runbook/Test:** `GH111_NULLIFIER_V2_CANARY_RUNBOOK.md` + `scripts/gh111-prepare-nullifier-v2-window.sh` + guarded activation/rollback helper `scripts/gh111-activate-nullifier-v2-window.sh` + read-only post-verify helper `scripts/gh111-postverify-nullifier-v2-window.sh` + read-only `gh111_nullifier_v2_canary_check.py` + `gh111_kdf_env_guard.py` + `gh111_preflight_package_check.py`; endpoint/evaluator regression proves v2 same-row migration with mocked HLR, Redis in-flight lock, atomic row-locked existing-identity re-registration, before/after canary verdicts, report artifacts, and v2 invariant counters. Runbook now includes one-command no-mutation prep, v2 lifespan probe, retrying health check after the previous pre-HLR 500/readiness abort, confirmed env-file write/rollback helper, mandatory `package_check.json` with `"ok": true`, emergency rollback attempt if activation fails after KDF write, and read-only compare/monitor helper after real S10 verification.
- **GH#111 Status Helper:** `scripts/gh111-status-nullifier-v2-window.sh` reports KDF env, API health, package verdict, and live preflight snapshot without writes/rebuild/HLR.
- **GH#111 Operator Checklist:** `docs/agent-bridge/GH111_NULLIFIER_V2_OPERATOR_CHECKLIST.md` is the short handoff sheet for the real S10/HLR window; it does not replace the runbook.
- **GH#111 S10 HLR Canary:** Profile -> `Επαλήθευση / Νέο κλειδί` -> VerifyScreen completed on S10 with real HLR. Post-verify mode `new-registration`: before 17 active / 0 v2, after 18 active / 1 v2, compare `ok=true`, monitor PASS, no fatal Logcat crash. Sensitive input is not recorded.
- **F-Droid !38007:** Still open/mergeable. Sed feedback was addressed in fdroiddata commit `2bf46a733` and pipeline `2630143862` passed. Latest linsui ABI feedback is addressed in fdroiddata commits `c23b4b2cd7` + `116cbe6a23`: four ABI-specific builds `511-514`, `abiFilters`, `mips/mips64` removal, `VercodeOperation`, `CurrentVersionCode=514`, then exact `fdroid rewritemeta` formatting. Pipeline `2634045842` failed only the formatter comparison before the follow-up; new pipeline `2634051871` is running. #79 waits on pipeline + linsui/F-Droid review + merge.
- **POLIS Status:** App-internal Create/Vote LIVE
- **Tracking:** Linear + GitHub Issues parallel. Cross-Links: GH#71-83 = NEA-277-285
- **GH#117 / NEA-393:** DONE. Public recovery transparency docs live on Community + Wiki. They document verified autonomous recovery boundaries, 0 AI token cost for Phase 1 `parliament_source_lag`, proof-before-success (`T1V`), and forbidden writes. Commit `2f27fab`; rollback tag `rollback-pre-recovery-transparency-docs-20260623`; live curl + Chrome desktop/mobile PASS; production monitor PASS (18 checks, no alerts).
- **GR-0490a766:** arweave_tx_id=NULL (bereinigt), party_votes_parliament=NULL, Guards verhindern Re-Archivierung
- **Telegram Bot:** citizen_votes Query LIVE, governance Topic-Routing LIVE
- **vC51 Release:** LIVE on ekklesia.gr + GitHub release `v1.0.22`; AAB `/Users/gio/Desktop/ekklesia-release-vC51/ekklesia-v1.0.22-vC51-PLAY.aab`, SHA256 `a0176d4597d8da1d2862a66f08aeb84deeaf516287a51ed422dcc2ecadeb45eb`; Direct APK `/Users/gio/Desktop/ekklesia-release-vC51/ekklesia-v1.0.22-vC51-DIRECT.apk`, SHA256 `e83a310d0fa932bdfa53ac87286e6a58bba5a98e9eee0259a142303e74b44b83`.
- **vC51 Release Notes:** `docs/agent-bridge/PLAY_RELEASE_NOTES_v1.0.22_vC51.md`.
- **vC51 Channel Audit:** Direct APK embeds `distributionChannel=direct`, `buildFlavor=direct`, versionCode 51; Play AAB embeds `distributionChannel=play`, `buildFlavor=play`, versionCode 51. Direct APK is signed with upload-key digest `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec`.
- **R8/mapping.txt:** still off for vC51 (`minify=false`); mapping warning in Play is informational until a future Production/R8 build.
- **Linear:** Token OK (`~/.claude/.env` -> `LINEAR_API_KEY`). 2026-06-22 cleanup: `NEA-286` and `NEA-133` moved to Done; sync comments added to `NEA-249`, `NEA-301`, `NEA-59`, `NEA-65`. GitHub + Bridge remain primary truth for active work.
- **NEA-301b PARLIAMENT:** DONE (17/31 mit summary_short_el, 9 brauchen Fetcher, 3 DEMO + 2 flagged excluded, DIAVGEIA 0/636 eigene Phase)
- **Ollama:** RAM zurueck auf 2.4 GB (Produktion), kein Job aktiv
- **T3 Arweave Alerts:** FIXED `a90d508` — Monitor verlangt `party_votes_parliament IS NOT NULL`; false-positive fuer GR-0490a766 behoben
- **Dependabot / Security Audit:** 2026-06-23 GitHub `Security Audit` was red on `undici<=6.26.0` in `apps/mobile` + `apps/representative`; local fix pins `undici@6.27.0` in both locks. Exact audit loop over all package-locks PASS with 0 high vulnerabilities. Later Dependabot alert `#19` (`pydantic-settings <2.14.2`) was fixed by bumping `2.14.0` -> `2.14.2`; focused API config tests PASS (11 passed), isolated target-version import test PASS, GitHub CI/Security/Dependency Graph/Dependabot workflows PASS on `b34d30d`, and production API rebuilt live. Do not add `@semaphore-protocol/proof@4.14.2` to production images without review; trial install showed 6 moderate + 8 high transitive findings.
- **Bill Summary/Source Fix:** API source policy live; mobile DIAVGEIA source + summary regression fixed in `5ff3998`/`b7fb4dd`, installed on S10 and verified. Root cause update: Analysis fehlt, weil `ai_summary_reviewed=false` und kein automatischer reviewed-analysis Job existiert. Mobile zeigt jetzt statt leerer Analyse einen klaren `Επίσημο κείμενο` Fallback, wenn `summary_long_el` vorhanden ist.
- **DIAVGEIA S10 Retest:** PASS — source card visible/clickable (`Πηγή — Διαύγεια` opens Android intent chooser), org/pill no longer shown as `Σύνοψη`, quote markers removed. Evidence: `/tmp/ekklesia_diav_fix_final_20260604_000652`.
- **Open GitHub:** #122 vC51 S10 visual retest pending, #79 F-Droid (external), #80 Off-site Backup (storage/funding), #112 staged/global follow-up after first public scoped rollout.
- **Open Linear:** `NEA-389` / GH#113 lifecycle catch-up is Done/closed; do not treat old #113 notes below as active.
- **Forum Missing Alerts:** 2026-06-17 Telegram `forum_missing` counts were transient sync/backfill progress. Current DB check: `public_missing_forum=0`; only `ZK-CANARY-001` lacks a forum topic and is `admin_hidden=true` by design.
- **ZK V2:** GH#81 closed; Android prover works on S10. GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001`. First public scoped rollout passed for `bill:GR-d4c62ed4`: S10 proof accepted, public receipt recorded, API results show `tier1=0`, `zk=1`, `total=1`. Production ZK remains scoped by exact allowlist; `ZK_GLOBAL_ROLLOUT_ENABLED=false`; `ZK_ARWEAVE_PUBLICATION_ENABLED=false`. Automatic/global rollout is code-ready but server-enforced Parliament-only; ZK Arweave publishing is separately guarded by `ZK_ARWEAVE_SCOPE_ALLOWLIST` and `ZK_ARWEAVE_MIN_GROUP_SIZE`.
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

- Mirror #1: `1.ekklesia.gr` live-tracked on `community.html` via public read-only API endpoint (`/api/v1/public/mirrors/status`), green/yellow/red status dot, code `e19900d`, live.
- Full security audit (NEA-251..258): 2 HIGH + 5 MEDIUM all resolved
- Watcher 3-tier self-healing (NEA-241): live + T2 active
- ZK V2 ADR (NEA-249): Android mobile prover self-test passes on S10. GH#112 hidden S10 canary passed for `bill:ZK-CANARY-001` with vC38. Superseded current truth: first public scoped production rollout passed for `bill:GR-d4c62ed4`; global rollout and ZK-Arweave remain gated/off.
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
- #112 / ZK V2 production rollout — hidden one-scope S10 canary passed; production backend logic prepared; global activation remains gated on security review and explicit scoped rollout.

## Completed 2026-06-23

- Parliament source-date hardening + DIAVGEIA source-date backfill — fix `ef7f2c1` deployed live; strict freshness endpoint PASS (`count=5`, `dated_count=5`, latest `2026-06-23`); DIAVGEIA date backfill `2441` rows, remaining `0`; monitor `--once` PASS, 18 checks, no alerts.
- #116 / NEA-392 Verified autonomous recovery Phase 1 — fix `6c98126` deployed live; monitor `--once` PASS, read-only proof PASS, first daemon run PASS; GitHub closed completed, Linear Done.

## Completed 2026-06-22

- #115 / NEA-391 Parliament source-lag forced catch-up — production mitigated manually, fix `15148d8` deployed live; forced endpoint PASS, monitor PASS, GitHub closed completed, Linear Done.
- #114 / NEA-390 Monitor startup grace — fix `da025c4` deployed live; API health PASS, `--once` PASS, first daemon run after 90s PASS; GitHub closed completed, Linear Done.
- #113 / NEA-389 Lifecycle catch-up no-skip — root cause confirmed, fix `8bd6871` deployed live; API health PASS, monitor 18 checks PASS, last-24h fast-forward probe `0`; GitHub closed completed, Linear Done.

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

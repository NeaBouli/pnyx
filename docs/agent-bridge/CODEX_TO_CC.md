# CC Context — Current pnyx status after vC51 release

Mode: support/review when asked. Do not assume old vC35/vC37/vC38/vC41 tasks are current.

Current state:
- Mobile vC51 / v1.0.22 is live on ekklesia.gr and GitHub release `v1.0.22`.
- Commit `49b9aea` is pushed and deployed for API/Web.
- App version endpoint returns `latest_version=1.0.22`, `latest_version_code=51`, and direct APK URL `https://ekklesia.gr/download/ekklesia-latest.apk`.
- Landing badge shows `v1.0.22 · vC51`.
- Live direct APK SHA256 is `e83a310d0fa932bdfa53ac87286e6a58bba5a98e9eee0259a142303e74b44b83`.
- GitHub release assets uploaded: `ekklesia-v1.0.22-vC51-DIRECT.apk` and `ekklesia-v1.0.22-vC51-PLAY.aab`.
- Production monitor `--once` after vC51 deploy: PASS, 18 checks, no alerts.
- vC51 S10 visual/install retest is still pending; do not mark GH#122 fully hardware-verified until a device test is done.
- Deploy incident to remember: first server attempt used `docker-compose.yml` instead of `docker-compose.prod.yml`, briefly creating an accidental dev API container. Production recovery used `docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml ...`.
- During vC51 deploy recovery, DB failed with `No space left on device`; DB data was present and not reinitialized. Safe cleanup was `docker builder prune -af` only. Current disk is about 91% used / 6.9 GB free, so capacity remains a warning.
- GH#117 / NEA-393 is complete: public Community/Wiki transparency docs are live and describe verified autonomous recovery, proof-before-success, forbidden writes, and 0 AI tokens/run for Phase 1 `parliament_source_lag`. Commit `2f27fab` deployed to web only; rollback tag `rollback-pre-recovery-transparency-docs-20260623`; live Chrome desktop/mobile and monitor once passed.
- Current repo/server git HEAD: latest `main`; API/monitor containers were rebuilt from code commit `ef7f2c1`.
- Parliament source-date hardening is live: monitor uses `/api/v1/scraper/parliament/freshness` strict dated probe with retries, scheduled Parliament scrape requires dated rows, and DIAVGEIA imported bills now receive the public `publish_timestamp` as `submitted_date`.
- DIAVGEIA source-date backfill completed: backup CSV `/opt/ekklesia/backups/diavgeia_submitted_date_pre_20260623-213409.csv`, rows backfilled `2441`, remaining eligible rows `0`.
- Completion boundary audit added: `docs/agent-bridge/GH111_GH112_COMPLETION_AUDIT.md`.
- GH#112 first public scoped rollout is proven complete for `bill:GR-d4c62ed4`; staged/global rollout and ZK Arweave publication remain gated/off.
- Automatic/global ZK rollout is code-ready but server-enforced to public PARLIAMENT bill scopes only (`ACTIVE`, `WINDOW_24H`, `OPEN_END`). DIAVGEIA, DEMO, hidden, canary, and non-public scopes must not become opt-in/root/vote scopes through the global flag.
- ZK Arweave publication has its own exact scope allowlist (`ZK_ARWEAVE_SCOPE_ALLOWLIST`) and minimum group-size guard (`ZK_ARWEAVE_MIN_GROUP_SIZE`, default 5); do not rely on `ZK_GLOBAL_ROLLOUT_ENABLED` for Arweave publishing.
- Monitor policy now follows the same gates: pending ZK receipts only alert when `ZK_ARWEAVE_PUBLICATION_ENABLED=true` and the scope is in `ZK_ARWEAVE_SCOPE_ALLOWLIST`; when publisher is off, pending receipts are expected and no T3 alert is sent.
- GH#111 is complete; production KDF is `v2` after a real S10/HLR canary and clean post-verify compare.
- Mobile vC51 / v1.0.22 includes GH#122 (`Ενεργά` includes `WINDOW_24H`) and the safer Direct/Play update-channel separation.
- AAB ready for Google Play Closed Testing: `/Users/gio/Desktop/ekklesia-release-vC51/ekklesia-v1.0.22-vC51-PLAY.aab`, SHA256 `a0176d4597d8da1d2862a66f08aeb84deeaf516287a51ed422dcc2ecadeb45eb`.
- Direct APK ready for ekklesia.gr/GitHub: `/Users/gio/Desktop/ekklesia-release-vC51/ekklesia-v1.0.22-vC51-DIRECT.apk`, SHA256 `e83a310d0fa932bdfa53ac87286e6a58bba5a98e9eee0259a142303e74b44b83`.
- Channel audit: Direct APK embeds `distributionChannel=direct`, `buildFlavor=direct`; Play AAB embeds `distributionChannel=play`, `buildFlavor=play`; both are versionCode 51 / versionName 1.0.22.
- Direct APK signer SHA-256 digest: `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec`.
- R8/minify is still OFF for vC51; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- S10 install/visual retest for vC51 is pending because no device was attached during the build/deploy.
- Monitor Telegram Bot API URL logging is redacted live. Do not repeat raw Telegram tokens from terminal logs.
- GH#112 hidden S10 canary passed earlier for `bill:ZK-CANARY-001`.
- GH#112 first public scoped rollout passed for `bill:GR-d4c62ed4`; latest hardware install/launch smoke test remains vC50.
- vC51 checks passed: API version syntax, API app/parliament tests 13 passed/2 xfailed, mobile TypeScript PASS, mobile Vitest 92 passed, Play AAB build PASS, Direct APK build PASS, APK/AAB channel audit PASS, API/Web live checks PASS.
- 2026-06-23 Security Audit correction: run `27986334575` failed on `undici<=6.26.0` in `apps/mobile` + `apps/representative`. Minimal override/lockfile fix pins `undici@6.27.0`; exact local Security Audit loop over all package-locks PASS with 0 high vulnerabilities; mobile + representative `tsc --noEmit` PASS.
- Public scoped ZK result for `GR-d4c62ed4`: `total_votes=1`, `tier1_vote_count=0`, `zk_vote_count=1`, `yes_count=1`.
- Public receipt exists with `vote_commitment=YES`, `arweave_pending=true`, `arweave_tx_id=null`.
- Production ZK is currently scoped to exactly `bill:GR-d4c62ed4` through `ZK_PRODUCTION_SCOPE_ALLOWLIST`.
- `ZK_GLOBAL_ROLLOUT_ENABLED=false`.
- `ZK_ARWEAVE_PUBLICATION_ENABLED=false`.
- `ZK_CANARY_ENABLED=false`.
- ZK Arweave publication policy still needs review before enabling any publisher; code now also requires dedicated Arweave scope allowlist + min anonymity threshold.
- Forum/monitor fix `4aa6f71` is live: Discourse 429 handling, `/api/v1/admin/forum/sync-new`, monitor recovery remapped to sync-new, DIAVGEIA backlog grace 6h.
- Monitor once after latest monitor deploy (`74ea10f`): PASS, 17 checks, no alerts.
- Post-scrape lifecycle catch-up is live; two newly scraped Parliament rows with past vote dates (`GR-d71e9b04`, `GR-4a8dba43`) were advanced to `PARLIAMENT_VOTED`. Monitor lifecycle check has a short grace for freshly updated scraper rows to prevent scrape/lifecycle race alerts.
- CI + Security Audit are green for `4aa6f71` and `f51dbf0`.
- F-Droid !38007 is still open/mergeable. Latest linsui feedback ("Please use sed instead of inline python code") is addressed in fdroiddata commit `2bf46a733`: inline Python prebuild edits were replaced with `sed`/shell commands. MR-event pipeline `2630143862` PASS (`fdroid lint`, `fdroid rewritemeta`, `fdroid build`, `check apk`); comment posted at https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007#note_3494920439. Play/Direct pnyx vC50 runtime unchanged; #79 is now external/waiting on linsui/F-Droid merge.
- GH#111 Nullifier v2 canary completed on 2026-06-17 with real S10/HLR verification. Keep `IDENTITY_NULLIFIER_KDF_VERSION=v2` active.
- vC51 keeps the controlled Profile -> Verify entrypoint; GH#111 is already complete and remains on KDF v2.
- GH#111 activation package: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_200157` (package validation PASS with `ok=true` and no blockers/warnings).
- GH#111 post-verify mode: `new-registration`; compare `ok=true`, `blockers=[]`, `warnings=[]`; before 17 total / 17 active / 0 v2, after 18 total / 18 active / 1 v2; malformed/mismatched v2 counters all 0; monitor PASS.
- GH#111 runbook exists: `docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`; it now includes the preferred host-side prep command `scripts/gh111-prepare-nullifier-v2-window.sh`, guarded activation/rollback helper `scripts/gh111-activate-nullifier-v2-window.sh`, read-only post-verify helper `scripts/gh111-postverify-nullifier-v2-window.sh`, an isolated v2 lifespan probe before any env flip, a retrying external health check after API rebuild, `gh111_kdf_env_guard.py` for env-file plan/write/rollback with explicit `GH111-KDF-WRITE` confirmation, and mandatory `package_check.json` with `"ok": true` before activation.
- GH#111 read-only status helper exists: `scripts/gh111-status-nullifier-v2-window.sh`; it reports current KDF, API health, latest package verdict, and live preflight snapshot without env writes, DB writes, rebuilds, or HLR. Package/snapshot read failures are reported as blockers instead of crashing the helper. It only prints the activation-ready next step if KDF is v1, API health is ok, live preflight is ok, and package verdict is ok; focused tests cover ready state and each blocking condition.
- GH#111 short operator checklist exists: `docs/agent-bridge/GH111_NULLIFIER_V2_OPERATOR_CHECKLIST.md`; use it as the handoff sheet during the real S10/HLR window, but keep the runbook as source of truth.
- GH#111 focused tests exist: `tests/test_identity_nullifier_v2_endpoint.py` proves same-row v1->v2 migration, Redis in-flight locking, and atomic row-locked existing-identity re-registration with mocked HLR; `scripts/gh111_nullifier_v2_canary_check.py` snapshots/compares real before/after canary counts and v2 invariants; `scripts/gh111_kdf_env_guard.py` edits only the KDF env key with backup and no shell-source; `scripts/gh111_preflight_package_check.py` validates the preflight evidence package; `scripts/gh111-prepare-nullifier-v2-window.sh` creates the no-mutation backup/preflight package and writes `package_check.json`. Latest focused set passed: 59 GH#111 tests.
- GH#111 S10 UI path was verified without mutation: Profile -> `Επαλήθευση / Νέο κλειδί` opens VerifyScreen with warning; no phone submitted, no HLR call, DB remains 17 active / 0 v2 / KDF unset.
- GH#111 v2 health diagnosis: production API image passes one-off Argon2/v2 generation and full FastAPI lifespan `/health` under `IDENTITY_NULLIFIER_KDF_VERSION=v2`; previous live 500 is treated as rebuild/readiness timing until contradicted.
- Disk-critical alerts were rechecked again on 2026-06-23/24. Cause was `/var/lib` Docker footprint, with Build Cache as the only safe reclaim target. Safe cleanup only (`docker builder prune -af`; no volumes/images/backups/data deleted) moved `/` from 91% used / 6.9 GB free to 84% used / 12 GB free after rebuild; monitor passed 18/18.
- Forum missing Telegram alerts from 2026-06-17 were transient sync/backfill progress. Current DB: `public_missing_forum=0`; only hidden `ZK-CANARY-001` has no forum topic, by design.
- 2026-06-23 Dependabot #19: `pydantic-settings` moderate alert fixed in source by bumping `2.14.0` -> `2.14.2`; focused API config tests passed (11 passed) and isolated target-version import test passed. `b34d30d` CI/Security/Dependency Graph/Dependabot workflows passed; production API was rebuilt and now verifies `pydantic-settings 2.14.2` inside `ekklesia-api`; monitor PASS 18/18.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not enable global ZK rollout without Gio's explicit instruction, fresh backup, and staged rollout plan. The code guard is Parliament-only, but the flag is still off.
3. Do not run Arweave publication for ZK proofs until the public-payload policy is reviewed and `ZK_ARWEAVE_SCOPE_ALLOWLIST` is set to the exact approved scope.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and vote/source/ZK paths are verified.
5. Keep production ZK scoped by exact allowlist; do not wildcard scopes.
6. GH#111 is complete. Do not roll back to v1 unless a concrete production blocker appears.
7. Do not record operator phone numbers, raw nullifiers, or private keys in Bridge/GitHub/Linear/docs/log excerpts.
8. Keep monitoring v2 invariant counters; any malformed/mismatched v2 row is a T3 issue.
9. If Parliament freshness alerts recur, check the strict freshness endpoint first: it should return `dated_count > 0` and `source_latest`; title-only fallback rows are no longer accepted as healthy.

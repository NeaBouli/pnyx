# CC Context — Current pnyx status after vC50 release

Mode: support/review when asked. Do not assume old vC35/vC37/vC38/vC41 tasks are current.

Current state:
- GH#117 / NEA-393 is complete: public Community/Wiki transparency docs are live and describe verified autonomous recovery, proof-before-success, forbidden writes, and 0 AI tokens/run for Phase 1 `parliament_source_lag`. Commit `2f27fab` deployed to web only; rollback tag `rollback-pre-recovery-transparency-docs-20260623`; live Chrome desktop/mobile and monitor once passed.
- Current repo/server git HEAD: latest `main`; API/monitor containers were rebuilt from code commit `74ea10f`.
- Completion boundary audit added: `docs/agent-bridge/GH111_GH112_COMPLETION_AUDIT.md`.
- GH#112 first public scoped rollout is proven complete for `bill:GR-d4c62ed4`; staged/global rollout and ZK Arweave publication remain gated/off.
- Automatic/global ZK rollout is code-ready but server-enforced to public PARLIAMENT bill scopes only (`ACTIVE`, `WINDOW_24H`, `OPEN_END`). DIAVGEIA, DEMO, hidden, canary, and non-public scopes must not become opt-in/root/vote scopes through the global flag.
- ZK Arweave publication has its own exact scope allowlist (`ZK_ARWEAVE_SCOPE_ALLOWLIST`) and minimum group-size guard (`ZK_ARWEAVE_MIN_GROUP_SIZE`, default 5); do not rely on `ZK_GLOBAL_ROLLOUT_ENABLED` for Arweave publishing.
- Monitor policy now follows the same gates: pending ZK receipts only alert when `ZK_ARWEAVE_PUBLICATION_ENABLED=true` and the scope is in `ZK_ARWEAVE_SCOPE_ALLOWLIST`; when publisher is off, pending receipts are expected and no T3 alert is sent.
- GH#111 is complete; production KDF is `v2` after a real S10/HLR canary and clean post-verify compare.
- Mobile vC50 / v1.0.21 is the current prepared Play/direct build. Gio asked for `vC40`, but Play requires monotonic versionCode; vC50 is the safe next code after vC49.
- AAB ready for Google Play Closed Testing: `/Users/gio/Desktop/ekklesia-v1.0.21-vC50-PLAY.aab`.
- Direct APK is live on ekklesia.gr as the play-signed vC50 APK; SHA256 `989c5f92ff37b4a8498e6410f362dedbfd91e362042ec5e6685479385c14685d`.
- GitHub latest release: https://github.com/NeaBouli/pnyx/releases/tag/v1.0.21.
- APK SHA256: `989c5f92ff37b4a8498e6410f362dedbfd91e362042ec5e6685479385c14685d`.
- AAB SHA256: `709cb2cee17f30f48ed417ecda9e1b8831f1b61a446286292a61f1454e3ad5e6`.
- R8/minify is still OFF for vC50; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- Monitor Telegram Bot API URL logging is redacted live. Do not repeat raw Telegram tokens from terminal logs.
- GH#112 hidden S10 canary passed earlier for `bill:ZK-CANARY-001`.
- GH#112 first public scoped rollout passed for `bill:GR-d4c62ed4`; vC50 S10 install/launch smoke test passed.
- vC50 live deploy checks passed: API version 1.0.21/50, landing badge vC50, live APK hash match, GitHub release assets hash match, S10 install/launch smoke test. Latest production monitor `--once` now reports 18 checks/no alerts.
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
- F-Droid !38007 is still open/mergeable and was updated to vC50/v1.0.21 on 2026-06-18. MR commit `d711780bf`; manual branch pipeline `2609790099` was success, but current MR-event head pipeline `2609789968` is failed. Inspect/fix the GitLab MR pipeline if maintainers require it before merge.
- GH#111 Nullifier v2 canary completed on 2026-06-17 with real S10/HLR verification. Keep `IDENTITY_NULLIFIER_KDF_VERSION=v2` active.
- vC50 keeps the controlled Profile -> Verify entrypoint; it was used for the GH#111 real HLR canary.
- GH#111 activation package: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_200157` (package validation PASS with `ok=true` and no blockers/warnings).
- GH#111 post-verify mode: `new-registration`; compare `ok=true`, `blockers=[]`, `warnings=[]`; before 17 total / 17 active / 0 v2, after 18 total / 18 active / 1 v2; malformed/mismatched v2 counters all 0; monitor PASS.
- GH#111 runbook exists: `docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`; it now includes the preferred host-side prep command `scripts/gh111-prepare-nullifier-v2-window.sh`, guarded activation/rollback helper `scripts/gh111-activate-nullifier-v2-window.sh`, read-only post-verify helper `scripts/gh111-postverify-nullifier-v2-window.sh`, an isolated v2 lifespan probe before any env flip, a retrying external health check after API rebuild, `gh111_kdf_env_guard.py` for env-file plan/write/rollback with explicit `GH111-KDF-WRITE` confirmation, and mandatory `package_check.json` with `"ok": true` before activation.
- GH#111 read-only status helper exists: `scripts/gh111-status-nullifier-v2-window.sh`; it reports current KDF, API health, latest package verdict, and live preflight snapshot without env writes, DB writes, rebuilds, or HLR. Package/snapshot read failures are reported as blockers instead of crashing the helper. It only prints the activation-ready next step if KDF is v1, API health is ok, live preflight is ok, and package verdict is ok; focused tests cover ready state and each blocking condition.
- GH#111 short operator checklist exists: `docs/agent-bridge/GH111_NULLIFIER_V2_OPERATOR_CHECKLIST.md`; use it as the handoff sheet during the real S10/HLR window, but keep the runbook as source of truth.
- GH#111 focused tests exist: `tests/test_identity_nullifier_v2_endpoint.py` proves same-row v1->v2 migration, Redis in-flight locking, and atomic row-locked existing-identity re-registration with mocked HLR; `scripts/gh111_nullifier_v2_canary_check.py` snapshots/compares real before/after canary counts and v2 invariants; `scripts/gh111_kdf_env_guard.py` edits only the KDF env key with backup and no shell-source; `scripts/gh111_preflight_package_check.py` validates the preflight evidence package; `scripts/gh111-prepare-nullifier-v2-window.sh` creates the no-mutation backup/preflight package and writes `package_check.json`. Latest focused set passed: 59 GH#111 tests.
- GH#111 S10 UI path was verified without mutation: Profile -> `Επαλήθευση / Νέο κλειδί` opens VerifyScreen with warning; no phone submitted, no HLR call, DB remains 17 active / 0 v2 / KDF unset.
- GH#111 v2 health diagnosis: production API image passes one-off Argon2/v2 generation and full FastAPI lifespan `/health` under `IDENTITY_NULLIFIER_KDF_VERSION=v2`; previous live 500 is treated as rebuild/readiness timing until contradicted.
- Disk-critical alerts were rechecked again on 2026-06-23. Cause was Docker Build Cache, not snapshots/backups. Safe cleanup only (`docker builder prune -af`; no volumes/images/backups/data deleted) moved `/` from 90% used / 7.5 GB free to 82% used / 14 GB free; monitor passed 18/18.
- Forum missing Telegram alerts from 2026-06-17 were transient sync/backfill progress. Current DB: `public_missing_forum=0`; only hidden `ZK-CANARY-001` has no forum topic, by design.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not enable global ZK rollout without Gio's explicit instruction, fresh backup, and staged rollout plan. The code guard is Parliament-only, but the flag is still off.
3. Do not run Arweave publication for ZK proofs until the public-payload policy is reviewed and `ZK_ARWEAVE_SCOPE_ALLOWLIST` is set to the exact approved scope.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and vote/source/ZK paths are verified.
5. Keep production ZK scoped by exact allowlist; do not wildcard scopes.
6. GH#111 is complete. Do not roll back to v1 unless a concrete production blocker appears.
7. Do not record operator phone numbers, raw nullifiers, or private keys in Bridge/GitHub/Linear/docs/log excerpts.
8. Keep monitoring v2 invariant counters; any malformed/mismatched v2 row is a T3 issue.

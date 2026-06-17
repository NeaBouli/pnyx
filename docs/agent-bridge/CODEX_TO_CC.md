# CC Context — Current pnyx status after vC50 release

Mode: support/review when asked. Do not assume old vC35/vC37/vC38/vC41 tasks are current.

Current state:
- Completion boundary audit added: `docs/agent-bridge/GH111_GH112_COMPLETION_AUDIT.md`.
- GH#112 first public scoped rollout is proven complete for `bill:GR-d4c62ed4`; staged/global rollout and ZK Arweave publication remain gated/off.
- GH#111 is prepared but not complete; production KDF remains `v1` and no real S10/HLR v2 activation has run.
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
- vC50 live deploy checks passed: API version 1.0.21/50, landing badge vC50, live APK hash match, GitHub release assets hash match, S10 install/launch smoke test, monitor once 17/17, CI + Security Audit green.
- Public scoped ZK result for `GR-d4c62ed4`: `total_votes=1`, `tier1_vote_count=0`, `zk_vote_count=1`, `yes_count=1`.
- Public receipt exists with `vote_commitment=YES`, `arweave_pending=true`, `arweave_tx_id=null`.
- Production ZK is currently scoped to exactly `bill:GR-d4c62ed4` through `ZK_PRODUCTION_SCOPE_ALLOWLIST`.
- `ZK_GLOBAL_ROLLOUT_ENABLED=false`.
- `ZK_ARWEAVE_PUBLICATION_ENABLED=false`.
- `ZK_CANARY_ENABLED=false`.
- ZK Arweave publication policy still needs review before enabling any publisher.
- Forum/monitor fix `4aa6f71` is live: Discourse 429 handling, `/api/v1/admin/forum/sync-new`, monitor recovery remapped to sync-new, DIAVGEIA backlog grace 6h.
- Monitor once after deploy: PASS, 17 checks, no alerts.
- CI + Security Audit are green for `4aa6f71` and `f51dbf0`.
- F-Droid !38007 is still open/mergeable, latest pipeline success, waiting on fdroiddata maintainer.
- GH#111 Nullifier v2 canary remains separate and is NOT activated.
- vC50 keeps the controlled Profile -> Verify entrypoint for a real HLR re-verification canary; it does NOT activate Nullifier v2 by itself.
- GH#111 latest no-mutation production preflight ran on 2026-06-17 06:46 UTC: production KDF still v1; `identity_records` 17 total / 17 active / 0 revoked / 0 v2; `active_with_v2=0`, `v2_without_version=0`, `version_without_v2=0`, `malformed_v2=0`; monitor PASS; isolated v2 lifespan probe PASS with scheduler no-op.
- GH#111 latest preflight package exists: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_064644` (monitor, KDF plan, snapshot/report, identity/audit/alembic dump, v2-lifespan-probe, SHA256 recorded in `ACTION_LOG.md`, remote `package_check.json` PASS with `ok=true` and no blockers/warnings).
- GH#111 runbook exists: `docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`; it now includes the preferred host-side prep command `scripts/gh111-prepare-nullifier-v2-window.sh`, guarded activation/rollback helper `scripts/gh111-activate-nullifier-v2-window.sh`, read-only post-verify helper `scripts/gh111-postverify-nullifier-v2-window.sh`, an isolated v2 lifespan probe before any env flip, a retrying external health check after API rebuild, `gh111_kdf_env_guard.py` for env-file plan/write/rollback with explicit `GH111-KDF-WRITE` confirmation, and mandatory `package_check.json` with `"ok": true` before activation.
- GH#111 read-only status helper exists: `scripts/gh111-status-nullifier-v2-window.sh`; it reports current KDF, API health, latest package verdict, and live preflight snapshot without env writes, DB writes, rebuilds, or HLR. Package/snapshot read failures are reported as blockers instead of crashing the helper.
- GH#111 short operator checklist exists: `docs/agent-bridge/GH111_NULLIFIER_V2_OPERATOR_CHECKLIST.md`; use it as the handoff sheet during the real S10/HLR window, but keep the runbook as source of truth.
- GH#111 focused tests exist: `tests/test_identity_nullifier_v2_endpoint.py` proves same-row v1->v2 migration, Redis in-flight locking, and atomic row-locked existing-identity re-registration with mocked HLR; `scripts/gh111_nullifier_v2_canary_check.py` snapshots/compares real before/after canary counts and v2 invariants; `scripts/gh111_kdf_env_guard.py` edits only the KDF env key with backup and no shell-source; `scripts/gh111_preflight_package_check.py` validates the preflight evidence package; `scripts/gh111-prepare-nullifier-v2-window.sh` creates the no-mutation backup/preflight package and writes `package_check.json`. Latest focused set passed: 59 GH#111 tests.
- GH#111 S10 UI path was verified without mutation: Profile -> `Επαλήθευση / Νέο κλειδί` opens VerifyScreen with warning; no phone submitted, no HLR call, DB remains 17 active / 0 v2 / KDF unset.
- GH#111 v2 health diagnosis: production API image passes one-off Argon2/v2 generation and full FastAPI lifespan `/health` under `IDENTITY_NULLIFIER_KDF_VERSION=v2`; previous live 500 is treated as rebuild/readiness timing until contradicted.
- Disk-critical alert was resolved by pruning Docker build cache only: `/` went from 94% used / 4.4 GB free to 77% used / 17 GB free; monitor then passed 17/17.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not enable global ZK rollout without Gio's explicit instruction, fresh backup, and staged rollout plan.
3. Do not add Arweave publication for ZK proofs until the public-payload policy is reviewed.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and vote/source/ZK paths are verified.
5. Keep production ZK scoped by exact allowlist; do not wildcard scopes.
6. GH#111 Nullifier v2 is a separate canary with HLR/identity re-registration risk; do not mix it into GH#112 rollout work.
7. Do not activate `IDENTITY_NULLIFIER_KDF_VERSION=v2` from DB/admin-test data alone. The proof requires a real phone/HLR verify or re-registration path so same-row v1->v2 migration can be observed. Follow `GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`.
8. During the real GH#111 window, first run `scripts/gh111-prepare-nullifier-v2-window.sh` on the production host and use its printed `GH111_BACKUP_DIR` as `BACKUP_DIR`. After the HLR step, run `compare --before /tmp/gh111_before_snapshot.json --mode existing-reregistration|new-registration --report-output /tmp/gh111_compare_report.json`.
9. Do not hand-edit `/opt/ekklesia/.env.production` during GH#111. Use `python3 apps/api/scripts/gh111_kdf_env_guard.py plan ...` first, then `write ... --confirm GH111-KDF-WRITE`.

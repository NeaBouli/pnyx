# CC Context — Current pnyx status after vC45 / GH#111 re-verification prep

Mode: support/review when asked. Do not assume old vC35/vC37/vC38/vC41 tasks are current.

Current state:
- Mobile vC45 / v1.0.16 is the current Play/direct build.
- AAB ready for Google Play Closed Testing: `/Users/gio/Desktop/ekklesia-v1.0.16-vC45-PLAY.aab`.
- Direct APK is live on ekklesia.gr as v1.0.16 / vC45; SHA256 `770c947cecd273f4b08b1d3f967ff8ff954a28132c699116ddfcb9bfec8f0621`.
- GitHub latest release target is live: https://github.com/NeaBouli/pnyx/releases/tag/v1.0.16
- APK SHA256: `770c947cecd273f4b08b1d3f967ff8ff954a28132c699116ddfcb9bfec8f0621`.
- AAB SHA256: `fc5694c37a7e21d721acd4963a4713e9b872388b02d80a5b1fbb1ed8aebcbf95`.
- R8/minify is still OFF for vC45; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- GH#112 hidden S10 canary passed earlier for `bill:ZK-CANARY-001`.
- GH#112 first public scoped rollout passed for `bill:GR-d4c62ed4`; vC45 S10 install/launch smoke test passed and verified-account state was preserved.
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
- vC45 adds a controlled Profile -> Verify entrypoint for a real HLR re-verification canary; it does NOT activate Nullifier v2 by itself.
- GH#111 preflight on 2026-06-17: production KDF still v1; `identity_records` 17 total / 17 active / 0 v2; Argon2id v2 helper works in API container at about 131 ms per derivation.
- GH#111 identity backup exists: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_004847`.
- GH#111 runbook exists: `docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`.
- GH#111 focused tests exist: `tests/test_identity_nullifier_v2_endpoint.py` proves same-row v1->v2 migration with mocked HLR; `scripts/gh111_nullifier_v2_canary_check.py` snapshots/compares real before/after canary counts; latest focused set passed `8 passed`.
- Disk-critical alert was resolved by pruning Docker build cache only: `/` went from 94% used / 4.4 GB free to 77% used / 17 GB free; monitor then passed 17/17.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not enable global ZK rollout without Gio's explicit instruction, fresh backup, and staged rollout plan.
3. Do not add Arweave publication for ZK proofs until the public-payload policy is reviewed.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and vote/source/ZK paths are verified.
5. Keep production ZK scoped by exact allowlist; do not wildcard scopes.
6. GH#111 Nullifier v2 is a separate canary with HLR/identity re-registration risk; do not mix it into GH#112 rollout work.
7. Do not activate `IDENTITY_NULLIFIER_KDF_VERSION=v2` from DB/admin-test data alone. The proof requires a real phone/HLR verify or re-registration path so same-row v1->v2 migration can be observed. Follow `GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`.
8. During the real GH#111 window, use `python scripts/gh111_nullifier_v2_canary_check.py snapshot --preflight --output /tmp/gh111_before.json` before the flag flip and `compare --mode existing-reregistration|new-registration` after the HLR step.

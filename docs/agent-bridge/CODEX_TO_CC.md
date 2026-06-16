# CC Context — Current pnyx status after vC39 / GH#112 public-scope preflight

Mode: support/review when asked. Do not assume old vC35/vC37/vC38 tasks are current.

Current state:
- Mobile vC39 / v1.0.10 is the current Play/direct build.
- Gio uploaded `/Users/gio/Desktop/ekklesia-v1.0.10-vC39-PLAY.aab` to Google Play.
- Direct APK is regenerated from the vC39 play release APK and staged at `docs/download/ekklesia-latest.apk`.
- R8/minify is still OFF for vC39; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001`; production ZK flags are OFF again.
- Nothing from the hidden canary was published to Arweave.
- GH#112 security review passed for scoped rollout readiness; global ZK rollout remains disabled.
- New prep: `apps/api/scripts/preflight_zk_public_scope.py` + `docs/agent-bridge/GH112_PUBLIC_SCOPED_ROLLOUT_RUNBOOK.md`.
- Current public candidates are real `OPEN_END` Parliament bills; newest Bouli bills are `ANNOUNCED` and must not be activated for ZK until lifecycle opens voting.
- js-yaml Dependabot remediation is local: mobile/representative locks now use `js-yaml@4.2.0`; wait for GitHub dependency graph refresh after push.
- F-Droid !38007 is still open/mergeable, latest pipeline success, waiting on fdroiddata maintainer.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not flip production ZK flags without Gio's explicit instruction and a fresh backup.
3. Do not add Arweave publication for ZK proofs until the public-payload policy is reviewed.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and ZK paths are verified.
5. For first public ZK rollout, use exactly one scope in `ZK_PRODUCTION_SCOPE_ALLOWLIST`; keep `ZK_GLOBAL_ROLLOUT_ENABLED=false`.

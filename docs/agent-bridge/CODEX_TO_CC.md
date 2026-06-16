# CC Context — Current pnyx status after vC41 / GH#112 scoped ZK UI

Mode: support/review when asked. Do not assume old vC35/vC37/vC38 tasks are current.

Current state:
- Mobile vC41 / v1.0.12 is the current Play/direct build.
- Gio should upload `/Users/gio/Desktop/ekklesia-v1.0.12-vC41-PLAY.aab` to Google Play if not already uploaded.
- Direct APK is live on ekklesia.gr as v1.0.12 / vC41.
- GitHub latest release is `v1.0.12` with APK+AAB assets.
- APK SHA256: `e558eac36afedadc09baf05d4149cc240911949d926fc81f490590f5811d6468`.
- AAB SHA256: `59d28635408589dc026d530771e1cd6025994101ee6be715d690269370d75958`.
- R8/minify is still OFF for vC41; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001`; production ZK flags are OFF again.
- Nothing from the hidden canary was published to Arweave.
- GH#112 security review passed for scoped rollout readiness; global ZK rollout remains disabled.
- New vC41 prep: public scoped ZK UI behind exact server allowlist + read-only scope status endpoint.
- Live API endpoint: `GET /api/v1/zk/scopes/{vote_scope_id}/status`.
- Invalid scopes now return HTTP 400, not 500.
- Current public candidates are real `OPEN_END` Parliament bills; newest Bouli bills are `ANNOUNCED` and must not be activated for ZK until lifecycle opens voting.
- GitHub CI + Security Audit are green at `5ea7518`.
- F-Droid !38007 is still open/mergeable, latest pipeline success, waiting on fdroiddata maintainer.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not flip production ZK flags without Gio's explicit instruction and a fresh backup.
3. Do not add Arweave publication for ZK proofs until the public-payload policy is reviewed.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and ZK paths are verified.
5. For first public ZK rollout, use exactly one scope in `ZK_PRODUCTION_SCOPE_ALLOWLIST`; keep `ZK_GLOBAL_ROLLOUT_ENABLED=false`.
6. For the first public ZK scope, vC41 must be installed on the S10 because older builds do not contain the scoped public ZK UI.

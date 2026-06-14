# CC Context — Current pnyx status after vC38 / GH#112 canary

Mode: support/review when asked. Do not assume old vC35/vC37 tasks are current.

Current state:
- Mobile vC38 / v1.0.9 is the current Play/direct build.
- Gio uploaded `/Users/gio/Desktop/ekklesia-v1.0.9-vC38-PLAY.aab` to Google Play.
- Direct APK is regenerated from the vC38 play release APK and staged at `docs/download/ekklesia-latest.apk`.
- R8/minify is still OFF for vC38; no `mapping.txt` exists. Play's no-mapping warning is informational for this artifact.
- GH#112 hidden S10 canary passed end-to-end for `bill:ZK-CANARY-001`; production ZK flags are OFF again.
- Nothing from the hidden canary was published to Arweave.
- Global ZK rollout remains gated on security review, public verifier payload / Arweave publication policy, tally/UI policy, and staged release.

If asked to continue:
1. Prefer review/diagnosis first.
2. Do not flip production ZK flags without Gio's explicit instruction and a fresh backup.
3. Do not add Arweave publication for ZK proofs until the public-payload policy is reviewed.
4. Do not enable R8/ProGuard unless the resulting build is installed on S10 and ZK paths are verified.

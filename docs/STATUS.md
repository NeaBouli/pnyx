# Ekklesia.gr - Project Status

Last verified: 2026-07-17

## Current release

| Item | Status |
|---|---|
| Phase | Beta |
| Android | v1.0.27 / versionCode 56 |
| Direct APK | Live; signed and verified on Samsung S10 and through the public download URL |
| Google Play | Play-signed AAB built and verified; Closed Testing upload pending |
| iOS | Preparation only; no public build |
| F-Droid | External MR !38007 pending |

## Verified product behavior

- Parliament bills remain visible nationwide.
- Municipality and region bills follow the location locked to the active anonymous identity.
- The server enforces vote eligibility independently of the client filters.
- A missing, revoked or unverifiable identity fails closed and never grants additional local voting rights.
- Tier-1 and valid Semaphore ZK receipts are counted once in aggregate results.
- The guarded Parliament Semaphore rollout and eligible-scope Arweave publication remain controlled by server-side policy and minimum group size.
- The direct APK and Google Play channels are kept separate so each channel receives compatible updates.
- During a primary outage the mobile app can use the HTTPS mirror for read-only data; voting stays disabled until the primary is healthy.

## vC56 release gate (passed)

- Mobile Vitest: 144/144 passed.
- Mobile TypeScript: passed.
- Samsung S10: update-in-place passed; verified municipality/region loaded; Parliament and local filters rendered; no fatal runtime exception.
- Direct APK: v1.0.27 (56), `direct` channel, v2 signature valid, native Semaphore library present.
- Play AAB: v1.0.27 (56), `play` channel, JAR signature valid, native Semaphore library present.
- Canonical identity storage uses only `ekklesia_nullifier`; invalid legacy SecureStore keys are not accessed.
- GitHub CI and Security Audit passed; Production API/Web deploy, database invariants, public download hash, Forum and all three mirrors were verified.

## Deliberately gated or external

- Alpha 0.1 official gov.gr holder verification is design-only (GH#141), pending official integration, DPIA, migration design, independent review and sandbox canary.
- Off-site backup currently uses the separated sandbox fallback until funded dedicated storage is available.
- F-Droid publication depends on external review and merge.
- R8/ProGuard remains disabled; therefore no mapping file is produced for vC56. A future R8 production build requires a separate native/ZK regression gate and `mapping.txt` publication.

Operational details and rollback history are maintained in the local, non-public agent bridge.

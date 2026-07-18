# Ekklesia.gr - Project Status

Last verified: 2026-07-18

## Current release

| Item | Status |
|---|---|
| Phase | Beta |
| Android | v1.0.28 / versionCode 57 released |
| Direct APK | Live on ekklesia.gr; SHA-256 verified |
| Google Play | AAB submitted to Closed Testing review |
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

## vC57 release verification

- Mobile Vitest: 149/149 passed; TypeScript passed.
- Direct APK: v1.0.28 (57), `direct` channel, v2 signature valid, native ARM64 Semaphore library present.
- Play AAB: v1.0.28 (57), `play` channel, JAR signature valid, native ARM64 Semaphore library present.
- GitHub CI and Security Audit passed for the release commit.
- Production API and web were rebuilt from the tagged commit; health, bills, forum, download hashes and unchanged DB counters were verified after deployment.
- GitHub Release v1.0.28 is published as latest with checksum-verified APK and AAB assets.
- The vC57 AAB is submitted to Google Play Closed Testing review; production access still depends on Google's tester and duration requirements.
- The vC57 scope is limited to clearer Semaphore ZK vote-state UX plus the already-tested Parliament metadata synchronization hardening.
- The local Pixel 5 AVD remained offline after cold boot; a fresh vC57 S10 visual pass is therefore still recommended. The unchanged native prover and production Canary were already verified on S10 before this UI-only release.

## Deliberately gated or external

- Alpha 0.1 official gov.gr holder verification is design-only (GH#141), pending official integration, DPIA, migration design, independent review and sandbox canary.
- Off-site backup currently uses the separated sandbox fallback until funded dedicated storage is available.
- F-Droid publication depends on external review and merge.
- R8/ProGuard remains disabled; therefore no mapping file is produced for vC57. A future R8 production build requires a separate native/ZK regression gate and `mapping.txt` publication.

Operational details and rollback history are maintained in the local, non-public agent bridge.

# Ekklesia.gr - Project Status

Last verified: 2026-08-20

## Current release

| Item | Status |
|---|---|
| Phase | Beta |
| Android | v1.0.29 / versionCode 58 released |
| Direct APK | GitHub Release published; SHA-256 and upgrade signature verified |
| Google Play | vC58 available to selected Closed Testing users since 2026-08-06 |
| iOS | Preparation only; no public build |
| F-Droid | v1.0.29 / versionCode 584 published in the main F-Droid repository |

## Verified product behavior

- Parliament bills remain visible nationwide.
- Municipality and region bills follow the location locked to the active anonymous identity.
- The server enforces vote eligibility independently of the client filters.
- A missing, revoked or unverifiable identity fails closed and never grants additional local voting rights.
- Tier-1 and valid Semaphore ZK receipts are counted once in aggregate results.
- The guarded Parliament Semaphore rollout and eligible-scope Arweave publication remain controlled by server-side policy and minimum group size.
- The direct APK and Google Play channels are kept separate so each channel receives compatible updates.
- During a primary outage the mobile app can use the HTTPS mirror for read-only data; voting stays disabled until the primary is healthy.

## vC58 release verification

- Mobile Vitest: 168/168 passed; TypeScript passed.
- Direct APK: v1.0.29 (58), `direct` channel, v2 signature valid, native ARM64 Semaphore library present.
- Direct APK signing certificate matches vC57, preserving the direct-install upgrade path.
- Play AAB: v1.0.29 (58), `play` channel, JAR signature valid, native ARM64 Semaphore library present.
- GitHub CI and Security Audit passed for the release commit.
- GitHub Release v1.0.29 is published as latest with checksum-verified APK and AAB assets.
- Google Play confirms release 58 (1.0.29) was published to the Closed Testing Alpha track on 2026-08-06 and is available to selected testers.
- The vC58 mobile artifact scope is limited to Greek mobile-number input normalization plus already-merged dependency security updates; voting and ZK policy are unchanged.
- The server-side Greek HLR status-normalization fix was deployed separately on 2026-08-08 and required no new APK or AAB.
- No Android emulator was attached during the artifact verification; runtime confirmation continues through the active Closed Testing track.

## Deliberately gated or external

- Alpha 0.1 official gov.gr holder verification is design-only (GH#141), pending official integration, DPIA, migration design, independent review and sandbox canary.
- Off-site backup currently uses the separated sandbox fallback until funded dedicated storage is available.
- F-Droid MR !38007 is merged and v1.0.29 (584) is publicly available from the main repository.
- R8/ProGuard remains disabled; therefore no mapping file is produced for vC58. A future R8 production build requires a separate native/ZK regression gate and `mapping.txt` publication.

Operational details and rollback history are maintained in the local, non-public agent bridge.

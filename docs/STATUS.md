# Ekklesia.gr - Project Status

Last verified: 2026-07-18

## Current release

| Item | Status |
|---|---|
| Phase | Beta |
| Android | v1.0.28 / versionCode 57 release candidate |
| Direct APK | Build and artifact verification pending |
| Google Play | AAB build and Closed Testing upload pending |
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

## vC57 release gate (in progress)

- Mobile Vitest and TypeScript must pass before artifacts are published.
- Emulator runtime and visual checks are required because the S10 is not currently connected.
- Direct APK and Play AAB signatures, channels, versions and native Semaphore library must be audited before publication.
- GitHub CI and Security Audit must pass before production metadata and downloads are updated.
- The vC57 scope is limited to clearer Semaphore ZK vote-state UX plus the already-tested Parliament metadata synchronization hardening.

## Deliberately gated or external

- Alpha 0.1 official gov.gr holder verification is design-only (GH#141), pending official integration, DPIA, migration design, independent review and sandbox canary.
- Off-site backup currently uses the separated sandbox fallback until funded dedicated storage is available.
- F-Droid publication depends on external review and merge.
- R8/ProGuard remains disabled; therefore no mapping file is produced for vC57. A future R8 production build requires a separate native/ZK regression gate and `mapping.txt` publication.

Operational details and rollback history are maintained in the local, non-public agent bridge.

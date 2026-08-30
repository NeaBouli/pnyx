# Ekklesia.gr - Project Status

Repository and external gates reviewed: 2026-08-30.
Released-artifact evidence below remains the 2026-08-20 baseline; this review
does not imply a new deployment or app publication.

## Current integration and release gates

- The bounded web cleanup is merged in [PR #259](https://github.com/NeaBouli/pnyx/pull/259)
  (`54ff2fc`). It removed 19 of 20 lint warnings while preserving the
  existing SSO initialization for the dedicated GH#258 follow-up below.
  QR session cleanup additionally rejects stale/expired poll completions and
  prevents duplicate authentication callbacks. Web tests (40), typecheck and
  production build pass. Synthetic browser checks cover filters and QR
  lifecycle races; the latter are not yet CI DOM tests. This is not a
  live-rollout claim.
  Kimi and Sol reviewed the patch; CodeRabbit was rate-limited, not a completed
  review. Main CI and Security Audit passed after both code merges.

- GH#258 now has 29 deterministic SSO lifecycle regressions covering hydration,
  missing/changed parameters, browser keys, StrictMode replay, retries, expiry
  and stale callbacks/redirects. Stalled initial and QR completion requests
  return to the existing retry UI after a 15-second request deadline.
  The client fix preserves the server protocol
  and eligibility policy. Web tests (69), lint (zero warnings), typecheck,
  build and npm audit (zero findings) pass. Kimi independently reproduced the
  original 11 failing cases and reviewed the fix; Sol added the suggested
  edge cases and verified Greek desktop/mobile layouts. This code verification
  is not a new production-login canary. See the
  [separate Web rollout gate](operations/forum-sso-lifecycle.md).

- Send-only mail intent is confirmed by the owner. The reply-routing patch in
  [PR #262](https://github.com/NeaBouli/pnyx/pull/262) retains Brevo senders,
  lists, DOI and schedules, routes new newsletter replies to the published
  external operator contact, and preserves explicit contact-form recipient
  overrides. No mailbox, DNS or provider configuration is changed. Production
  override/delivery verification is still required before declaring it live.
  [GH#261](https://github.com/NeaBouli/pnyx/issues/261) separately tracks the
  unverified Redis/Listmonk-to-Brevo subscriber handoff; campaign implementation
  alone is not evidence of end-to-end subscriber delivery.

- GH#253: signed personal evaluation reads and mobile integration are merged
  in [PR #257](https://github.com/NeaBouli/pnyx/pull/257) (`9ec3591`).
  The migration is not complete until API readiness, a new app
  release, signed-read/write adoption, and the separately approved cutoff are
  verified. Released clients remain compatible before cutoff. See
  [the migration runbook](security/EVALUATION_READ_MIGRATION.md).
- Four `image-size` Dependabot alerts remain visible. Both official advisories
  still list no patched release; the checked local backport remains in place
  and its seven installed-package security regressions pass. Do not replace it
  with upstream 2.0.2, which is still affected:
  [GHSA-w3rx-r6r6-pgpr](https://github.com/advisories/GHSA-w3rx-r6r6-pgpr),
  [GHSA-5p2g-fcmc-qvqq](https://github.com/advisories/GHSA-5p2g-fcmc-qvqq).
- `arweave-python-client` 1.0.19 still depends on `python-jose`; 3.5.0 still
  requires `ecdsa`. No compatible removal or patched `ecdsa` release was found.
  The existing narrowly documented audit exception is unchanged, not resolved.
  Verification-only use is outside the reported signing/key-generation path;
  this is not a blanket claim that the dependency is safe. See the
  [official advisory](https://github.com/pypa/advisory-database/blob/main/vulns/ecdsa/PYSEC-2026-1325.yaml).
- TypeScript 7 remains a future upgrade gate: official
  [typescript-eslint support](https://typescript-eslint.io/users/dependency-versions/)
  currently excludes it. Existing supported versions are retained.
- Google Play production access is still blocked by its closed-test criteria.
  The console requires at least 12 opted-in testers and a qualifying 14-day
  test. Enrollment is not proof of daily activity; current private counts are
  recorded in the local bridge, not inferred from the email allowlist.
- DMARC: the private catalog still contains one report / one passing message,
  not a complete monthly evidence set. Review starts no earlier than September
  1 and waits for delayed August 31 reports and sender-path evidence. Inbound
  intent is now confirmed as send-only; actual routing must still be verified.
  [Observation gate](operations/dmarc-observation-gate.md), NEA-422.
- No production, database, DNS, secret, IAM or Google Play publication change
  is part of this integration review.

## Backlog classification

- GitHub #253 is active staged security migration work.
- GitHub #216-#223 (parallel Minima V2) and #138/#141 (gov.gr identity) remain
  future gated work, not regressions in the running V1 release.
- Linear NEA-262 is a weekly-newsletter proposal, distinct from the implemented
  monthly scheduler NEA-160 and subscriber-delivery follow-up GH#261.
  No schedule change is implied.
- Linear NEA-185 and NEA-167 retain their full independent demo-node scope;
  existing public demo pages do not prove that scope complete.
- Linear NEA-113 is historical federation design backlog. New V2 decisions
  must follow epic #216 rather than silently implementing the old bridge plan.
- Donation/recipient work was excluded from the current authorization and its
  existing state is unchanged.

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

# Ekklesia.gr - Project Status

Repository and delivery gates reviewed: 2026-09-02.
Android v1.0.31/vC60 is fully validated as a direct APK and Play AAB. Release
publication and Google Play Closed Testing submission follow the protected
merge in that order. It fixes Xiaomi/MIUI Region and Municipality selection
and normalizes Greek phone input from Unicode keyboards and pasted text.

## Verified component rollout

- Web: `c935018` (PR #259/#263), live since 09:49 UTC.
- API: prior production source `25d6c14` plus only the five PR #262 mail files,
  live since 09:51 UTC. Evaluation/representative policy, agent changes and
  dependency bumps from later main commits were deliberately excluded.
- 69 Web tests, eight mocked mail tests, exact-source CI/Security and 16 HTTP
  checks before and after each switch passed. Browser checks covered SSO entry,
  retry, bills/results and detail navigation, not a new real-identity login.
- Other 37 containers and protected configuration were unchanged. Rollback
  tag `rollback-pre-web-mail-20260830-c935018` and prior images are retained.
- Details: [release receipt](operations/WEB_MAIL_RELEASE_2026-08-30.md).
  Repository HEAD alone is not the deployed API version.
- Android/API v59: merged source `db37fe7` (PR #266), direct APK release and
  bounded `/app/routers/app_version.py` production overlay. API health and both
  version endpoints pass; protected configuration and all other containers
  were unchanged. Details: [v59 release receipt](operations/ANDROID_V59_RELEASE_2026-09-01.md).

## Current integration and release gates

- The bounded web cleanup is merged in [PR #259](https://github.com/NeaBouli/pnyx/pull/259)
  (`54ff2fc`). It removed 19 of 20 lint warnings while preserving the
  then-existing SSO initialization for the dedicated GH#258 follow-up below.
  QR session cleanup additionally rejects stale/expired poll completions and
  prevents duplicate authentication callbacks. Web tests (40), typecheck and
  production build pass. Synthetic browser checks cover filters and QR
  lifecycle races; the subsequent GH#258 work adds deterministic DOM tests.
  The verified Web rollout above includes both changes.
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
  [Web rollout receipt and remaining canary](operations/forum-sso-lifecycle.md).

- Send-only mail intent is confirmed by the owner. The reply-routing patch in
  [PR #262](https://github.com/NeaBouli/pnyx/pull/262) retains Brevo senders,
  lists, DOI and schedules, routes new newsletter replies to the published
  external operator contact, and preserves explicit contact-form recipient
  overrides. No mailbox, DNS or provider configuration was changed. Production
  file hashes and the operator recipient override were verified in the bounded
  rollout above. The owner confirmed receipt of the separately authorized DOI
  and single test newsletter on August 30; both mail budgets are consumed.
  Full header/unsubscribe verification remains open.
  [GH#261](https://github.com/NeaBouli/pnyx/issues/261) separately tracks the
  confirmed Redis/Listmonk-to-Brevo handoff gap: August 31 read-only inventory
  found five confirmed Redis entries, three absent from Brevo, two list matches
  and zero provider-list-only contacts. The configured Listmonk endpoint was
  unreachable from the API. No contacts were imported, removed or reactivated.
  A code-only consent guard adds atomic confirmation and admin-only no-write
  readiness, without changing campaign audiences or production. Enrollment
  remains blocked pending consent/history review and campaign preference
  enforcement; GH#261 is not closed by these guardrails.
  [Delivery investigation and gated repair plan](operations/newsletter-delivery-audit.md).

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
  intent is confirmed as send-only; reply-routing configuration/code are live,
  but actual delivery and header evidence still need verification.
  [Observation gate](operations/dmarc-observation-gate.md), NEA-422.
- No database, DNS, secret, IAM or Google Play change was made. The two component
  switches above are the only production changes in the completed rollout;
  this subsequent delivery investigation was read-only.

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
| Android | v1.0.31 / versionCode 60 release candidate validated for Direct and Play |
| Direct APK | Candidate SHA-256 and upgrade signature verified; GitHub publication follows the protected merge |
| Google Play | vC60 AAB validated; Closed Testing submission follows GitHub release publication |
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

## vC60 release-candidate verification

- Mobile Vitest: 204/204 passed; TypeScript passed.
- API app-version regressions: 6/6 passed.
- Direct APK: v1.0.31 (60), `direct` channel, v2 signature valid. Its signing
  certificate SHA-256 remains
  `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec`.
- Play AAB: v1.0.31 (60), `play` channel, bundle metadata and four supported
  ABIs (`arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`) verified.
- A physical Samsung S10 on Android 12 upgraded in place first to the direct
  APK and then to Play-style device splits without losing the anonymous
  identity, verification state, locked Region or Municipality.
- Home, Voting, Trending, Parties, POLIS, Profile and Settings loaded on both
  distributions. The active 24-hour bill appeared and logcat contained no
  Ekklesia fatal, ANR or React Native error.
- Phone verification was deliberately not submitted because the physical test
  device has a German number. Greek-number variants and Xiaomi selector events
  are covered by deterministic regressions.
- Voting, identity, eligibility, ZK and database behavior are unchanged.

## vC59 release verification

- Mobile Vitest: 192/192 passed; TypeScript and release lint passed.
- Direct APK: v1.0.30 (59), `direct` channel, v2 signature valid. Its signing
  certificate matches vC58, preserving the direct-install upgrade path.
- Play AAB: v1.0.30 (59), `play` channel, signature and bundle metadata verified.
- Android 15 emulator validation upgraded an installed vC58 APK to vC59 with
  `adb install -r`; install identity was preserved and the app launched without
  an Ekklesia fatal error.
- GitHub CI and Security Audit passed for release commit `db37fe7`.
- GitHub Release v1.0.30 is published as latest with checksum-verified APK and
  AAB assets.
- Google Play accepted release 59 (1.0.30) with no supported-device removals.
  It is submitted to the Closed Testing Alpha review, not yet confirmed as
  available to testers.
- The vC59 scope uses the native installed Android version for display and
  comparison and keeps legacy vC34 response aliases. Voting, identity and ZK
  policy are unchanged.
- The production API uses a bounded single-file overlay for the v59 version
  contract. `/health`, `/api/v1/app/version` and `/api/v1/version` pass.

### Superseded vC58 baseline

v1.0.29/versionCode 58 passed 168 Mobile tests, signature and direct-upgrade
continuity checks before its 2026-08-06 Closed Testing publication. The direct
channel is superseded by vC59; vC58 remains the available Play build until
Google approves vC59. The complete prior verification text remains in Git
history.

## Deliberately gated or external

- Alpha 0.1 official gov.gr holder verification is design-only (GH#141), pending official integration, DPIA, migration design, independent review and sandbox canary.
- Off-site backup currently uses the separated sandbox fallback until funded dedicated storage is available.
- F-Droid MR !38007 is merged and v1.0.29 (584) is publicly available from the main repository.
- R8/ProGuard remains disabled; therefore no mapping file is produced for vC60. Google Play's mapping-file warning is expected and non-blocking. A future R8 production build requires a separate native/ZK regression gate and `mapping.txt` publication.

Operational details and rollback history are maintained in the local, non-public agent bridge.

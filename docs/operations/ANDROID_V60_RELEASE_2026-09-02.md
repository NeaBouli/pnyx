# Android v1.0.31 / vC60 Release-Candidate Receipt

Date: 2026-09-02

## Scope

This is a bounded Android and app-version release. It contains the already
reviewed Xiaomi/MIUI Region and Municipality selector compatibility fix and
robust Greek mobile-number input normalization. It does not change voting,
identity, eligibility, ZK, database, DNS, secrets or IAM behavior.

## Artifacts

- Direct APK: `ekklesia-v1.0.31-vC60-DIRECT.apk`
  - SHA-256: `c3b3238bbf7567d93745a246586c8a6f03088d56d87ab1178eb7809a79481cfa`
- Play AAB: `ekklesia-v1.0.31-vC60-PLAY.aab`
  - SHA-256: `5e39d6584fccb805a021afa9d70936a1e1e377141b4237e8920f1defc50a837c`
- Signing certificate SHA-256:
  `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec`
- Target canonical release: [v1.0.31](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.31) (created only after the protected merge)

## Verification

- Mobile: 23 test files, 204 tests passed; TypeScript passed.
- API app-version tests: 6 passed.
- APK: package `ekklesia.gr`, versionName `1.0.31`, versionCode `60`, minimum
  SDK 24 and target SDK 36.
- AAB: bundle validation passed; versionName `1.0.31`, versionCode `60`; ARM64,
  ARM32, x86 and x86_64 libraries are present.
- A physical Samsung S10 (Android 12, ARM64) upgraded in place to the direct APK
  and then to the AAB-generated Play splits. Existing identity, verification,
  Region and Municipality data remained intact.
- Home, Voting, Trending, Parties, POLIS, Profile and Settings loaded in both
  distributions. The active 24-hour bill was visible. No Ekklesia fatal, ANR
  or React Native error appeared in the device log.
- Phone verification was not submitted because the physical device uses a
  German number. Deterministic tests cover Greek local, `+30`, `0030`, Unicode
  digit and pasted-input normalization.
- The official `fdroiddata` recipe patches both `buildFlavor` and
  `distributionChannel` to `fdroid` before its independent build. The local
  F-Droid helper now mirrors that channel isolation.

## Publication order

1. Merge only after required CI, Security and review gates pass.
2. Publish and checksum-verify the canonical GitHub APK/AAB assets.
3. Submit the AAB to Google Play Closed Testing without production promotion.
4. Only then expose vC60 through the API version contract and web download
   links, with rollback tags retained.
5. F-Droid consumes the signed source tag through its independent metadata and
   reproducible-build process; no manual F-Droid binary upload is performed.

## Rollback

The prior v1.0.30/vC59 release and its artifacts remain immutable. Source,
Web and API rollback tags are recorded during the controlled merge and rollout.

# Android v1.0.32 / vC61 Release Receipt

Date: 2026-09-06

## Scope

This is a bounded Android, app-version and download-link release. It adds a
category-aware app-icon notification count, capped at 99 and reset when the app
opens, returns to the foreground or a notification switch is disabled.
It also includes the
already merged Xiaomi/MIUI selector and Greek mobile-input fixes from PR #291.
It does not change voting, identity, eligibility, ZK, database, DNS, secrets,
IAM or production-track policy.

Android launchers control the final badge presentation. Launchers without
numeric-badge support may show only their standard notification dot.

## Artifacts

- Direct APK: `ekklesia-v1.0.32-vC61-DIRECT.apk`
  - SHA-256: `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56`
- Play AAB: `ekklesia-v1.0.32-vC61-PLAY.aab`
  - SHA-256: `1064bad1d21e80f47b36c331defaf0b501d1d5e72374c431155f782fb3208b24`
- Signing certificate SHA-256:
  `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec`
- Canonical release will be published on the [GitHub Releases page](https://github.com/NeaBouli/pnyx/releases) after the protected merge.

## Verification

- Mobile: 25 test files, 215 tests passed; TypeScript passed.
- Dependency security regressions: image-size 7/7 and decode-uri-component 4/4.
- API app-version tests passed.
- APK: package `ekklesia.gr`, versionName `1.0.32`, versionCode `61`, APK v2
  signature valid and release certificate continuous with v1.0.31.
- AAB: JAR signature valid and signed with the established upload key.
- Direct and Play native release builds passed for the supported ABI set.
- The local F-Droid build follows the official native exclusion of
  `expo-notifications`; official F-Droid publishing remains independent.
- Source diff, repository secret scan, CI and Security Audit must pass before
  merge and publication.

## Publication Order

1. Merge only after required CI, Security and review gates pass.
2. Publish and checksum-verify the canonical GitHub APK/AAB assets.
3. Submit the AAB to Google Play Closed Testing without production promotion.
4. Only then expose vC61 through API version contracts, Web download links and
   the latest-APK alias, retaining rollback tags.
5. Let F-Droid consume the source tag through its independent metadata and
   reproducible-build process. Never upload the signed Direct APK to F-Droid.

## Publication Result

Pending the protected merge and external publication sequence above.

## Rollback

The v1.0.31/vC60 release and its artifacts remain immutable. Source, Web and
API rollback tags are created before any controlled production switch.

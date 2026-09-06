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
- Canonical release: [v1.0.32](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.32),
  targeting merge commit `d25d4ee116055ff8395e1305d4f77bf6de414ace`.

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

- PR #292 merged normally after all required checks passed without bypass.
- GitHub release `v1.0.32` was published on 2026-09-06. Its tag resolves to
  `d25d4ee116055ff8395e1305d4f77bf6de414ace` and its uploaded APK/AAB digests
  match the verified artifacts above.
- Google Play accepted `61 (1.0.32)` for Closed Testing Alpha on 2026-09-06
  with Greek release notes and no supported-device removals. Google review is
  pending; no production-track promotion occurred.
- PR #294 merged normally as
  `ff2622f90ca0c0db94881bee13ec1ed4cb6317c8` after its full CI, Security and
  review suite passed without bypass.
- The bounded API/Web rollout completed at 09:10 UTC on 2026-09-06. Production
  images are `ekklesia-api:app-v61-20260906T090233Z` and
  `ekklesia-web:app-v61-20260906T090233Z`. The API retained the deployed
  Telegram/ZK-count baseline and changed only the version router; Web retained
  the deployed v60 source baseline and added only the reviewed v61 publication
  and SSO overlays.
- Live checks passed for API health, both version contracts, Web, SSO, FAQ,
  roadmap and `llms.txt`. The public latest alias returned 82,777,431 bytes and
  SHA-256
  `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56`.
- Protected files, HLR runtime values and all 41 non-target containers were
  unchanged. Both target containers remained running with restart count zero
  and no new error markers.

## Rollback

The v1.0.31/vC60 release and its artifacts remain immutable. Source, Web and
API rollback tag `rollback-pre-app-v61-20260906T090233Z` was created before the
production switch and resolves to pre-change source
`25d6c14499905bdcb901488f3ac00b275fd9b620`. The prior API/Web image IDs and
preflight/postflight receipts remain protected under
`/opt/ekklesia/releases/app-v61-20260906T090233Z/`.

# Android v1.0.30 / vC59 Release Receipt

Date: 2026-09-01

## Source and review

- Pull request: [#266](https://github.com/NeaBouli/pnyx/pull/266)
- Merged release commit: `db37fe7bcafc25c52577aa92ded0fcb5239eb827`
- GitHub CI run `33488084742`: success
- Security Audit run `33488084622`: success
- Mobile verification: 23 test files, 192 tests passed; TypeScript and release
  lint passed.
- API verification: 1005 tests passed, 11 skipped and 25 expected failures.
- Kimi independently reviewed the update contract and legacy vC34 response
  compatibility. Sol reviewed the resulting diff and repeated the relevant
  verification.

## Published artifacts

- Release: [v1.0.30](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.30)
- Direct APK: `ekklesia-v1.0.30-vC59-DIRECT.apk`
- Direct APK SHA-256:
  `dd0e88d56a3ed2c439fca0c6bbba16f93e4c27a327f92af2537db3a74a9a5d31`
- Play AAB: `ekklesia-v1.0.30-vC59-PLAY.aab`
- Play AAB SHA-256:
  `d2c1edc7be655468756d58787004e7c3bfb72069b53bf3448cd6bad9e5985dcd`
- The direct APK has a valid v2 signature and the same signer as vC58.
- Android 15 emulator validation upgraded an installed vC58 build with
  `adb install -r`. The first-install timestamp remained unchanged, Android
  reported versionName `1.0.30` and versionCode `59`, and the app launched
  without an Ekklesia fatal error.

## Google Play

- Closed Testing Alpha release ID: `38`
- Release: versionCode `59`, versionName `1.0.30`
- Rollout setting: 100% of the closed testing track after approval
- Google reported zero removed supported devices across all form factors.
- Status at receipt time: submitted and under Google review. vC59 must not be
  described as available to testers until Google approves it.
- Google showed a missing R8/ProGuard mapping warning. Minification and resource
  shrinking are disabled for this build, so no mapping file exists; the warning
  is expected and does not block review.

## Bounded API rollout

The production API was not rebuilt from full `main`. The existing production
image was overlaid with only `/app/routers/app_version.py` from release commit
`db37fe7`, preserving the existing production mail overlay and excluding
unrelated API changes.

- Source rollback tag: `rollback-pre-app-v59-api-20260901T090619Z`
- Rollback image: `ekklesia-api:rollback-pre-app-v59-20260901T090619Z`
- Candidate image: `ekklesia-api:app-v59-20260901T090619Z`
- Candidate image ID:
  `sha256:b046d45adfe88b1d39c0a73b6a64acc9816dd90a5d8b86fbc2a51a54a22f1d4d`
- Server release directory:
  `/opt/ekklesia/releases/app-v59-api-20260901T090619Z`
- Deployed router SHA-256:
  `a351544d2c4251e3b1a1358c5f88806f60eb5da463bdbca5911a52fd4b58f272`
- `/health`, `/api/v1/app/version` and `/api/v1/version` returned the expected
  v1.0.30/vC59 contract repeatedly after readiness.
- API restart count remained zero. Protected environment and Compose hashes,
  and all other containers, remained unchanged.

## Boundaries and rollback

- No database, DNS, secret, IAM, Google Play production-track or unrelated
  service change was made.
- F-Droid remains independently published as v1.0.29 / vC584.
- API rollback uses the retained image and source tag above through the same
  existing Compose context.
- The previous direct release remains available on GitHub. Published releases
  are retained rather than deleted or rewritten.

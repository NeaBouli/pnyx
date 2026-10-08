# Android v1.0.33 / vC62 Release Receipt

Date: 2026-10-06

## Scope

This is a bounded Android release and app-version announcement. vC62 ships
16 KB memory page support (JNA 5.19.1, #448), the bundled hash-pinned Semaphore
zkey (#446) and the ZK kill switch (#447): ZK voting is paused and disabled in
this build (`zkSemaphoreEnabled=false`); Ed25519 voting is unaffected. This
receipt changes only the version router and its tests. It does not change
mobile source, build scripts, voting, identity, eligibility, ZK, database, DNS,
secrets, IAM, Web download links, the latest-APK alias or production-track
policy.

## Source

- Build commit: `bc17f529deea178cd5f866582cf4898485edd60f` (branch
  `agent/claude/T-593`, `3b9f9fb8` plus the version bump only).
- Release tag target: `d5c72690460109e41f9398c9c32bcc99de19aa40` (squash of
  PR #450 on `main`). `apps/mobile`, `packages`, `scripts/patches`,
  `scripts/build-direct.sh` and `scripts/build-play.sh` are tree-identical
  between `bc17f529` and `d5c72690` (identical git tree IDs); the remaining
  diff is docs, SEO scripts and an API test only.
- Play AAB: built 2026-10-04 from `bc17f529` (`bundlePlayRelease`); provenance
  in the T-601 report.
- Direct APK: built 2026-10-06 from a detached worktree at `bc17f529`
  (`assembleDirectRelease --no-daemon --max-workers=2`, BUILD SUCCESSFUL in
  50m 18s). Temporary signing files were removed from the build tree
  afterwards. Neither artifact was rebuilt for publication.

## Artifacts

- Direct APK: `ekklesia-v1.0.33-vC62-DIRECT.apk`, 85,228,382 bytes
  - SHA-256: `d248ee83e5cd7d9bdaec2c6ffb7adc1789b747114a8350c293723294f8cb0f53`
- Play AAB: `ekklesia-v1.0.33-vC62-PLAY.aab`, 53,677,218 bytes
  - SHA-256: `9dabc33f571b8f0120e7f7bd3a5c0d869f3608cf9523e46f55689b69ec743452`
- Checksums: `ekklesia-v1.0.33-SHA256SUMS.txt`
  - SHA-256: `7c1e6b73cf17229ccfccf0880925f7b527ff9d1f38437b3db517fd2a10603eb5`
- Canonical release: [v1.0.33](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.33),
  published 2026-10-06T11:03:07Z, tag resolves to `d5c72690`.

## Verification

- APK: package `ekklesia.gr`, versionName `1.0.33`, versionCode `62`,
  minSdk 24, targetSdk 36; embedded `distributionChannel=direct`,
  `zkSemaphoreEnabled=false`, plugin list identical to `bc17f529:apps/mobile/app.json`.
- Bundled `assets/semaphore/semaphore-4.13.0-16.zkey` SHA-256
  `948763c7315a337b7722c0344a28af4be66fbbc618474d6dbe9036e799d1a3b5`, equal to
  `BundledZkey.kt::SHA256` and `zk-artifacts.manifest.json` at `bc17f529`.
- `zipalign -c -P 16 -v 4`: verification successful; all 30 `arm64-v8a` and
  `x86_64` `.so` entries 16 KB aligned.
- `apksigner verify`: valid, APK Signature Scheme v2, one signer. Signing
  certificate SHA-256 is equal to the published v1.0.32 Direct APK
  (fingerprint ends `…e10e5dec`, same certificate as in the V61 receipt).
- The v1.0.32 Direct APK used for comparison was downloaded from its release
  and matched its published digest.
- Remote: the three GitHub asset digests equal the local SHA-256 values; a
  fresh download passes `shasum -c ekklesia-v1.0.33-SHA256SUMS.txt`.
- API: `apps/api/tests/test_app_version.py` passed.

## Channel State

- Google Play: `62 (1.0.33)` live on Closed Testing (Alpha) since 2026-10-06
  12:12 EEST. Production access is not granted; no production promotion or
  production access request was made.
- `PLAYSTORE_URL` stays `https://play.google.com/apps/testing/ekklesia.gr`
  until vC62 is actually in Play production.
- F-Droid remains on its independent update path.

## Publication Order

1. Publish and checksum-verify the canonical GitHub APK/AAB assets. Done.
2. Merge the app-version PR only after required CI, Security and review gates
   pass.
3. A separately approved API rollout exposes vC62 through
   `GET /api/v1/app/version` and `GET /api/v1/version`. Not done here.
4. Web download links, the latest-APK alias and README/STATUS are separate
   follow-ups.

## Rollback

The v1.0.32/vC61 release and its artifacts remain unchanged. Until the API
rollout, production keeps announcing vC61. Reverting this PR restores the
v1.0.32 announcement; the v1.0.33 release is not deleted or overwritten.

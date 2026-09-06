# APK Artifact Manifest

This directory is the public download mount for static APK files.

Large APK binaries are not committed to Git. They are deployed as server-side
artifacts under `/opt/ekklesia/app/docs/download/` and verified by SHA-256.

## ekprosopos

| Channel | Public URL | Server path | Canonical local copy | SHA-256 | Metadata |
|---|---|---|---|---|---|
| latest | `https://ekklesia.gr/download/ekprosopos-latest.apk` | `/opt/ekklesia/app/docs/download/ekprosopos-latest.apk` | `/Users/gio/Desktop/ekprosopos-v1.1.0-vC2.apk` and ignored archive `builds/artifacts/ekprosopos-v1.1.0-vC2.apk` | `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e` | package `ekklesia.representative`, versionCode `2`, versionName `1.1.0` |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekprosopos-latest.apk
aapt dump badging /opt/ekklesia/app/docs/download/ekprosopos-latest.apk | head -5
```

Expected WebView target:

```text
https://ekklesia.gr/representative/index.html
```

## ekklesia mobile

| Field | Value |
|---|---|
| Version | 1.0.32 |
| versionCode | 61 |
| Package | ekklesia.gr |
| APK SHA256 | `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56` |
| AAB SHA256 | `1064bad1d21e80f47b36c331defaf0b501d1d5e72374c431155f782fb3208b24` |
| Signing certificate SHA256 | `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.32/ekklesia-v1.0.32-vC61-DIRECT.apk` (published and checksum-verified) |
| Server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` remains on v1.0.31 until the controlled post-publication rollout |
| Build date | 2026-09-06 |
| Release gate | PLAY SUBMISSION PASS — 215 Mobile tests, TypeScript, API version tests, APK/AAB metadata, signature continuity, F-Droid-compatible local build, GitHub CI/Security, published asset checksums and Google Play Closed Testing submission pass. Public API/Web version exposure and live alias verification remain required before completion. |
| Includes | App-icon notification count for enabled categories, with reset when the app opens, returns to the foreground or a notification switch is disabled, plus the Xiaomi/MIUI and Greek mobile-input fixes from v1.0.31. Numeric rendering depends on Android launcher support. Voting, identity, eligibility and ZK policy are unchanged. |

Android treats the Direct, Google Play and F-Droid builds as separate signing
channels. Installing one channel over another can therefore report a package
conflict even though the device is compatible. Users must keep updates inside
their installed channel. Changing channel requires uninstalling the installed
copy first and then verifying again because the private voting key is stored
only on that device installation.

Post-publication validation command for the canonical v1.0.32 asset:

```bash
(
  set -euo pipefail
  expected='67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.32/ekklesia-v1.0.32-vC61-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

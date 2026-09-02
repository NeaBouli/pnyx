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
| Version | 1.0.31 |
| versionCode | 60 |
| Package | ekklesia.gr |
| APK SHA256 | `dde71f9edfbfb8251831ecbf42cf3200f354c9e0329cefb65025f272b91a15dc` |
| AAB SHA256 | `daa2303cd048b657888fade5d2268807cbfa635be75ff4197bedeaf091559b05` |
| Signing certificate SHA256 | `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk` (published and checksum-verified) |
| Server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` was updated by the controlled web release and matches the canonical APK hash |
| Build date | 2026-09-02 |
| Release gate | PASS — 206 Mobile tests, TypeScript, API version tests, APK/AAB metadata, signature continuity, direct APK and locally generated Play-style split validation on a physical Samsung S10, GitHub CI/Security, published asset checksums and live alias verification pass. Google Play approval and F-Droid's independent build remain external. |
| Includes | Xiaomi/MIUI-compatible Region and Municipality selection plus robust normalization of Greek mobile numbers from Unicode keyboards and pasted input. Voting, identity, eligibility and ZK policy are unchanged. |

Post-publication validation command for the canonical v1.0.31 asset:

```bash
(
  set -euo pipefail
  expected='dde71f9edfbfb8251831ecbf42cf3200f354c9e0329cefb65025f272b91a15dc'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

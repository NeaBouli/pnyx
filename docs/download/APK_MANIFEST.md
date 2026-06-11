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
| Version | 1.0.5 |
| versionCode | 32 |
| Package | ekklesia.gr |
| APK SHA256 | `aecbee101185a020427ee5b53d1058e78aa5682be7cde920e2f766aea097c576` |
| AAB SHA256 | `5904cd60067f5a3b47e88d8e877c1fb1faef98be92e61b1fa37f6314bc8449f1` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-11 |
| Release gate | PASS — TypeScript, 37 mobile regression tests, local AAB/APK build, APK signature/version/permission audit |
| Includes | vC32 current mobile state, Bouli tab source filter, Android autolinking package build fix, ZK V2 settings/prover status, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: aecbee101185a020427ee5b53d1058e78aa5682be7cde920e2f766aea097c576
```

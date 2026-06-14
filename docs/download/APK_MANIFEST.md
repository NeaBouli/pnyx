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
| Version | 1.0.9 |
| versionCode | 38 |
| Package | ekklesia.gr |
| APK SHA256 | `5f725627da5d088136cff6d4430e9c7266779fae26bf9567150837a40e49dc66` |
| AAB SHA256 | `46dce5d1f528266c0dfdf98d364124e84653dfa360ab426462005226da087b28` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-15 |
| Release gate | PASS — TypeScript/Vitest history, local AAB/APK build, APK/AAB version audit, S10 hidden ZK canary passed on vC38 |
| Includes | vC38 current mobile state, Bouli bills visible in All feed and Bouli tab, ZK V2 native prover, hidden S10 canary operator path, ZK proof binding fix, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 5f725627da5d088136cff6d4430e9c7266779fae26bf9567150837a40e49dc66
```

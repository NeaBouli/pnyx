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
| Version | 1.0.6 |
| versionCode | 35 |
| Package | ekklesia.gr |
| APK SHA256 | `306a530c0e2edfa701675d1cf37a4a52069005294be4cb60851fddae84be1f76` |
| AAB SHA256 | `2af2971f225cd49f7c8bee950158abdd60d6939e47ff836704431e89e986194a` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-13 |
| Release gate | PASS — TypeScript, Vitest, local AAB/APK build, APK/AAB version audit, APK signature/version/permission audit |
| Includes | vC35 current mobile state, Bouli bills visible in All feed and Bouli tab visible in first viewport, Bouli source filter, Android autolinking package build fix, ZK V2 settings/prover status, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 306a530c0e2edfa701675d1cf37a4a52069005294be4cb60851fddae84be1f76
```

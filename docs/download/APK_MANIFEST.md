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
| versionCode | 33 |
| Package | ekklesia.gr |
| APK SHA256 | `70da885601b17549bda4a0b913dc4a508d93e4a5a6303ece3bc9842f5c231b0f` |
| AAB SHA256 | `a6e40312a27635ee37ecdb5d55aabe436a5d5b6405db4d4a0bbb7424be831279` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-11 |
| Release gate | PASS — TypeScript, S10 UI verification, local AAB/APK build, APK signature/version/permission audit |
| Includes | vC33 current mobile state, Bouli tab visible in first viewport, Bouli source filter, Android autolinking package build fix, ZK V2 settings/prover status, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: aecbee101185a020427ee5b53d1058e78aa5682be7cde920e2f766aea097c576
```

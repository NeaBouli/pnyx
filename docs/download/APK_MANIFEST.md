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
| Version | 1.0.26 |
| versionCode | 55 |
| Package | ekklesia.gr |
| APK SHA256 | `a0695f72cf8382995d18c0d9805da66b0fb3b86f6a40376ea2791d435b05fef4` |
| AAB SHA256 | `36f1897b99bfe847ca2f587d9db435d4163381e208815ea9300b6f826a726606` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-07-15 |
| Release gate | PASS — API consensus/privacy tests, mobile TypeScript, mobile Vitest, emulator visual checks, web build, local Play AAB build, local Direct APK build, APK/AAB signature and metadata audit |
| Includes | vC55 release metadata, aggregate Diavgeia consensus results by municipality, region and nationwide, server-side sensitive-decision filtering, safe Parliament text/document display, HTTPS read-only mirror fallback, guarded Parliament Semaphore ZK rollout, ZK Arweave publication for eligible scopes, current app-version endpoint, native Semaphore prover, deep-link fallback, pagination and permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: a0695f72cf8382995d18c0d9805da66b0fb3b86f6a40376ea2791d435b05fef4
```

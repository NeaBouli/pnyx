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
| Version | 1.0.10 |
| versionCode | 39 |
| Package | ekklesia.gr |
| APK SHA256 | `444b5c4735a4c98a14517d8a7543457a19bff965c0d923b55078446683412611` |
| AAB SHA256 | `d4cf9037407513f020cf711b849438a69c4bbe2aa6139259ab39060ee2ccd66b` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-17 |
| Release gate | PASS — mobile Vitest/TypeScript, API ZK/voting/security suite, GitHub CI/Security Audit, local AAB/APK build, APK version audit |
| Includes | vC39 current mobile state, per-scope Semaphore identities, scoped-production-ready ZK wording, Bouli bills visible in All feed and Bouli tab, ZK V2 native prover, hidden S10 canary operator path, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 444b5c4735a4c98a14517d8a7543457a19bff965c0d923b55078446683412611
```

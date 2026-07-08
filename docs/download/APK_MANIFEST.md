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
| Version | 1.0.24 |
| versionCode | 53 |
| Package | ekklesia.gr |
| APK SHA256 | `1847b64a8a5e40a739d83d2e98a87541edf12ae15ea0819e271e797de0678f2d` |
| AAB SHA256 | `757dc15509578f117cb00585cd7b1e2057b9afb83cd177b2c9e2761f1ccf9695` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-07-08 |
| Release gate | PASS — API version tests, mobile TypeScript, mobile Vitest, web build, local Play AAB build, local Direct APK build, APK badging/signature audit, Direct/Play channel audit |
| Includes | vC53 release metadata, safe read-only mirror fallback guard for public data, no duplicate Parliament PDF document blocks, clearer Parliament source/document display, guarded Parliament Semaphore ZK rollout live, ZK Arweave auto-publication for eligible public Parliament scopes with minimum group size 5, current app-version endpoint, scoped public ZK voting UI, root-status polling after opt-in, SecureStore-safe scoped Semaphore identity keys, Bouli bills visible in All feed and Bouli tab, native Semaphore prover, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 1847b64a8a5e40a739d83d2e98a87541edf12ae15ea0819e271e797de0678f2d
```

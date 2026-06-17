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
| Version | 1.0.19 |
| versionCode | 48 |
| Package | ekklesia.gr |
| APK SHA256 | `1e0a15b027afb231178d381f608fc8640fb2960ae3ebfc1bac9de65206a55016` |
| AAB SHA256 | `af4a490a480113ada18e2e91f050eca8232c9443ae23f69966b4f4331ad4f2f5` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-17 |
| Release gate | PASS — API version syntax, mobile TypeScript, mobile Vitest, local AAB/APK build, APK version/signature audit, S10 install/launch smoke test |
| Includes | vC48 release metadata, current app-version endpoint, scoped public ZK voting UI, root-status polling after opt-in, SecureStore-safe scoped Semaphore identity keys, Bouli bills visible in All feed and Bouli tab, ZK V2 native prover, hidden S10 canary operator path, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 1e0a15b027afb231178d381f608fc8640fb2960ae3ebfc1bac9de65206a55016
```

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
| Version | 1.0.23 |
| versionCode | 52 |
| Package | ekklesia.gr |
| APK SHA256 | `9bac08017222181281c4942ec8cb2f4e44bd8bbd05bed2d7fb82c3d01e6c25dc` |
| AAB SHA256 | `6bdcf2516385aac90dd4c08f151d6d4e4ce7b125b3fe0bc32730090249498a67` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-07-02 |
| Release gate | PASS — API version tests, mobile TypeScript, mobile Vitest, web build, local Play AAB build, local Direct APK build, APK badging/signature audit, Direct/Play channel audit |
| Includes | vC52 release metadata, no duplicate Parliament PDF document blocks, clearer Parliament source/document display, guarded Parliament Semaphore ZK rollout live, ZK Arweave auto-publication for eligible public Parliament scopes with minimum group size 5, current app-version endpoint, scoped public ZK voting UI, root-status polling after opt-in, SecureStore-safe scoped Semaphore identity keys, Bouli bills visible in All feed and Bouli tab, native Semaphore prover, deep-link fallback, pagination, source/full-text policy, permission hardening |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 9bac08017222181281c4942ec8cb2f4e44bd8bbd05bed2d7fb82c3d01e6c25dc
```

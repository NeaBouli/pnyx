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
| Version | 1.0.27 |
| versionCode | 56 |
| Package | ekklesia.gr |
| APK SHA256 | `a3720382a3814175ed1582b456236c0a71dc3f39a788c63d91194248e38cd737` |
| AAB SHA256 | `27e99a2a7da84bc2c4bcb2e1de98cac71df2cc78e76ddc10bfd8ba3fd97550a6` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-07-17 |
| Release gate | PASS — 144 Mobile tests, full API/Web/Crypto regression, S10 update-in-place and visual scope checks, APK/AAB signature and channel audit, GitHub CI/Security, Production deploy and public APK hash verification |
| Includes | Verified municipality/region bill visibility with nationwide Parliament access, server-authoritative vote eligibility, canonical SecureStore identity handling, safer account import, unified Tier-1 and Semaphore ZK counting, aggregate Diavgeia results, safe Parliament text/PDF display, HTTPS read-only mirror fallback, guarded Parliament ZK rollout and eligible-scope Arweave publication |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: a3720382a3814175ed1582b456236c0a71dc3f39a788c63d91194248e38cd737
```

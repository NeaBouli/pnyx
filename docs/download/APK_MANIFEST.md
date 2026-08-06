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
| Version | 1.0.29 |
| versionCode | 58 |
| Package | ekklesia.gr |
| APK SHA256 | `6a9b6e4a8c9a37153efe5e27676a8b88a044695d96c6fdc174bcb1ae420a793a` |
| AAB SHA256 | `f5b29d3eaaa72fb2e031df6bebbaf12ff3706689819db3c8a3549f7794ab1ee1` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.29/ekklesia-v1.0.29-vC58-DIRECT.apk` |
| Legacy server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` still serves v1.0.28 / vC57 until a separately controlled production deployment |
| Build date | 2026-08-06 |
| Release gate | PASS for code and artifacts — 168 Mobile tests, TypeScript, APK/AAB signatures, direct-upgrade certificate continuity, native Semaphore library, GitHub CI and Security green. Google Play confirms vC58 is available to selected Closed Testing users. |
| Includes | Correct Greek mobile normalization for local, `+30` and `0030` formats; safe full-number paste handling; dependency security updates; existing server-authoritative voting, guarded Semaphore ZK and read-only mirror behavior remain unchanged. |

Validation command for the canonical v1.0.29 asset:

```bash
curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.29/ekklesia-v1.0.29-vC58-DIRECT.apk | sha256sum
# Expected: 6a9b6e4a8c9a37153efe5e27676a8b88a044695d96c6fdc174bcb1ae420a793a
```

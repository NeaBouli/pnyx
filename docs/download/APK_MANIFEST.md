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
| Version | 1.0.31 |
| versionCode | 60 |
| Package | ekklesia.gr |
| APK SHA256 | `c3b3238bbf7567d93745a246586c8a6f03088d56d87ab1178eb7809a79481cfa` |
| AAB SHA256 | `5e39d6584fccb805a021afa9d70936a1e1e377141b4237e8920f1defc50a837c` |
| Signing certificate SHA256 | `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec` |
| Target canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk` (published only after the protected merge) |
| Legacy server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` is updated only by the controlled web release and must match the canonical APK hash |
| Build date | 2026-09-02 |
| Release gate | PASS for source and local artifacts — 204 Mobile tests, TypeScript, API version tests, APK/AAB metadata, signature continuity and physical Samsung S10 direct/APKS upgrades pass. GitHub CI/Security, release publication and live aliases are verified separately after merge. |
| Includes | Xiaomi/MIUI-compatible Region and Municipality selection plus robust normalization of Greek mobile numbers from Unicode keyboards and pasted input. Voting, identity, eligibility and ZK policy are unchanged. |

Post-publication validation command for the canonical v1.0.31 asset:

```bash
(
  set -euo pipefail
  expected='c3b3238bbf7567d93745a246586c8a6f03088d56d87ab1178eb7809a79481cfa'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

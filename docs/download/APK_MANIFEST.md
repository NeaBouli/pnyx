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
| Version | 1.0.30 |
| versionCode | 59 |
| Package | ekklesia.gr |
| APK SHA256 | `dd0e88d56a3ed2c439fca0c6bbba16f93e4c27a327f92af2537db3a74a9a5d31` |
| AAB SHA256 | `d2c1edc7be655468756d58787004e7c3bfb72069b53bf3448cd6bad9e5985dcd` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/ekklesia-v1.0.30-vC59-DIRECT.apk` |
| Legacy server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` still serves v1.0.28 / vC57 until a separately controlled production deployment |
| Build date | 2026-09-01 |
| Release gate | PASS for code and artifacts — 192 Mobile tests, TypeScript, APK/AAB signatures, direct-upgrade certificate continuity, Android 15 emulator upgrade, GitHub CI and Security green. Google Play vC59 is submitted and remains under review. |
| Includes | Native installed-version detection and strict version parsing prevent repeated or incorrect update prompts while preserving the legacy vC34 update contract; voting, identity and ZK policy are unchanged. |

Validation command for the canonical v1.0.30 asset:

```bash
(
  set -euo pipefail
  expected='dd0e88d56a3ed2c439fca0c6bbba16f93e4c27a327f92af2537db3a74a9a5d31'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/ekklesia-v1.0.30-vC59-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

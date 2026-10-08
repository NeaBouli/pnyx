# APK Artifact Manifest

This directory is the public download mount for static APK files.

Large APK binaries are not committed to Git. They are deployed as server-side
artifacts under `/opt/ekklesia/app/docs/download/` and verified by SHA-256.

## ekprosopos

Status: **not published.** `https://ekklesia.gr/download/ekprosopos-latest.apk`
returned HTTP 404 on 2026-09-27, so no public page links it. The representative
page (`docs/representative.html#download`) shows the Android APK as "In
development". Do not add a public download link until the artifact is deployed
and verified with the commands below.

Last local build candidate (not served):

| Field | Value |
|---|---|
| Intended public URL | `https://ekklesia.gr/download/ekprosopos-latest.apk` (HTTP 404, 2026-09-27) |
| Intended server path | `/opt/ekklesia/app/docs/download/ekprosopos-latest.apk` |
| Local archive | ignored `builds/artifacts/ekprosopos-v1.1.0-vC2.apk` |
| SHA-256 | `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e` (candidate record only; no public checksum file until the APK is published) |
| Metadata | package `ekklesia.representative`, versionCode `2`, versionName `1.1.0` |

Validation command after deployment:

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
| Version | 1.0.33 |
| versionCode | 62 |
| Package | ekklesia.gr |
| APK SHA256 | `d248ee83e5cd7d9bdaec2c6ffb7adc1789b747114a8350c293723294f8cb0f53` |
| AAB SHA256 | `9dabc33f571b8f0120e7f7bd3a5c0d869f3608cf9523e46f55689b69ec743452` |
| Signing certificate SHA256 | `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.33/ekklesia-v1.0.33-vC62-DIRECT.apk` (published; checksums in `ekklesia-v1.0.33-SHA256SUMS.txt`) |
| Server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` redirects to the v1.0.33 Direct APK (web `next.config.mjs`) |
| Build date | 2026-10-04 (release published 2026-10-06) |
| Release gate | COMPLETE — GitHub release v1.0.33 (tag `d5c72690`, built from `bc17f529` with identical mobile/package trees), APK checks (package, versionName/Code, `direct` channel, ZK off, pinned zkey, 16 KB-aligned 64-bit `.so`, signature continuity with v1.0.32), published asset checksums, Google Play Closed Testing Alpha live since 2026-10-06, API `/api/v1/app/version` reports 1.0.33/62 since 2026-10-08. Play production access is pending (tester requirement). F-Droid builds independently and may still list 1.0.32 (versionCodes 611-614). |
| Includes | Security and compatibility update for newer Android devices (16 KB page size). The app-icon notification count, Xiaomi/MIUI and Greek mobile-input fixes from earlier releases are retained. Voting, identity, eligibility and ZK policy are unchanged; ZK voting stays disabled. |

Android treats the Direct, Google Play and F-Droid builds as separate signing
channels. Installing one channel over another can therefore report a package
conflict even though the device is compatible. Users must keep updates inside
their installed channel. Changing channel requires uninstalling the installed
copy first and then verifying again because the private voting key is stored
only on that device installation.

Post-publication validation command for the canonical v1.0.33 asset:

```bash
(
  set -euo pipefail
  expected='d248ee83e5cd7d9bdaec2c6ffb7adc1789b747114a8350c293723294f8cb0f53'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.33/ekklesia-v1.0.33-vC62-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

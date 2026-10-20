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
| Version | 1.0.36 |
| versionCode | 65 |
| Package | ekklesia.gr |
| Direct APK SHA-256 | `ece60ca1a0e9091bdb062d35a868f646d19002b37e82b7f54d77fc233581f5ec` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.36/ekklesia-v1.0.36-vC65-DIRECT.apk` |
| Server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` redirects to the v1.0.36 Direct APK (web `next.config.mjs`) |
| Includes | Clearer no-name wording, safer key handling, one vote correction in the 24-hour window. |

The v1.0.36 URL and checksum above are the supplied release values for T-9157;
this offline documentation update does not re-download or re-verify the binary.
Historical v1.0.33 artifact/build/signature and Play Closed Testing evidence is
recorded in [the vC62 release receipt](../operations/ANDROID_V62_RELEASE_2026-10-06.md).
Google Play production access remains pending. F-Droid builds independently and
may trail the Direct release.

Android treats the Direct, Google Play and F-Droid builds as separate signing
channels. Installing one channel over another can therefore report a package
conflict even though the device is compatible. Users must keep updates inside
their installed channel. Changing channel requires uninstalling the installed
copy first and then verifying again because the private voting key is stored
only on that device installation.

Post-publication validation command for the canonical v1.0.36 asset:

```bash
(
  set -euo pipefail
  expected='ece60ca1a0e9091bdb062d35a868f646d19002b37e82b7f54d77fc233581f5ec'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.36/ekklesia-v1.0.36-vC65-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

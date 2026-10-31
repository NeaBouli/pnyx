# APK Artifact Manifest

This directory is the public download mount for static APK files.

Large APK binaries are not committed to Git. They are deployed as server-side
artifacts under `/opt/ekklesia/app/docs/download/` and verified by SHA-256.

## ekprosopos

Status: **published** as a GitHub release (Gio approval 2026-10-31).

| Field | Value |
|---|---|
| Version | 1.1.1 |
| versionCode | 3 |
| Package | ekklesia.representative |
| Release tag | `ekprosopos-v1.1.1` → commit `616ea5a4` |
| APK SHA-256 | `e9959c6951fd10bee731b176876386877a8206bcc5e910584cfbe424bec38432` |
| Signing certificate SHA-256 | `d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec` (same release key as the ekklesia Direct APK) |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/ekprosopos-v1.1.1/ekprosopos-v1.1.1-vC3.apk` |
| Checksum file | `ekprosopos-v1.1.1-vC3.apk.sha256` on the same release |
| Server alias | `https://ekklesia.gr/download/ekprosopos-latest.apk` redirects (307) to the canonical APK (web `next.config.mjs`) |
| WebView target | `https://ekklesia.gr/representative/index.html` |

Build: `REP_SIGNING_PROPERTIES=<keystore properties> bash scripts/build-representative.sh`
from the release tag. The script fails if the APK certificate digest differs
from the value above.

The earlier unpublished 1.1.0 / versionCode 2 candidate
(`4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e`) was signed
with the Android debug key and was never released. A device that still has it
installed must uninstall it before installing 1.1.1, because Android rejects an
update signed with a different certificate.

Post-publication validation:

```bash
(
  set -euo pipefail
  expected='e9959c6951fd10bee731b176876386877a8206bcc5e910584cfbe424bec38432'
  actual="$(curl -fsSL https://ekklesia.gr/download/ekprosopos-latest.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

## ekklesia mobile

| Field | Value |
|---|---|
| Version | 1.0.37 |
| versionCode | 66 |
| Package | ekklesia.gr |
| Direct APK SHA-256 | `4efb7559242bcce0f01c27d4f4c96d97eadb0858b5f2b9b7c76361aed7a6a9a5` |
| Canonical APK URL | `https://github.com/NeaBouli/pnyx/releases/download/v1.0.37/ekklesia-v1.0.37-vC66-DIRECT.apk` |
| Server alias | `https://ekklesia.gr/download/ekklesia-latest.apk` redirects to the v1.0.37 Direct APK (web `next.config.mjs`) |
| Includes | Last update date and time for Parliament data in the bills and trending lists. Notice when the data may be outdated. |

The v1.0.37 URL and checksum above are the integrator-verified release values
for T-9172 (tag `v1.0.37` → commit `408a3203`).
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

Post-publication validation command for the canonical v1.0.37 asset:

```bash
(
  set -euo pipefail
  expected='4efb7559242bcce0f01c27d4f4c96d97eadb0858b5f2b9b7c76361aed7a6a9a5'
  actual="$(curl -fsSL https://github.com/NeaBouli/pnyx/releases/download/v1.0.37/ekklesia-v1.0.37-vC66-DIRECT.apk | sha256sum | awk '{print $1}')"
  test "$actual" = "$expected"
  printf 'APK SHA256 verified: %s\n' "$actual"
)
```

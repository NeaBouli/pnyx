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
| Version | 1.0.3 |
| versionCode | 30 |
| Package | ekklesia.gr |
| APK SHA256 | `6b216b7d00823c34b2ba3b9dabee8cbe9de60d3310314690fa062fc23eb8a388` |
| AAB SHA256 | `7cc92ddeb9be36a238bc62a375867eadc92f55a102a986e87220e524b76cdadc` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-06-03 |
| Release gate | PASS — S10 final UI regression: bill-card icons, source fallback, already-voted lock, Βουλή detail |
| Includes | vC30 Hermes runtime alignment, source link labels, official text fallback, vote-status lock, Βουλή boilerplate guard |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: 6b216b7d00823c34b2ba3b9dabee8cbe9de60d3310314690fa062fc23eb8a388
```

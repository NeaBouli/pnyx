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
| Version | 1.0.28 |
| versionCode | 57 |
| Package | ekklesia.gr |
| APK SHA256 | `d21c265cf4f330c79c7437744ed28d873480d2ab7631dfa5127c67e8148ef9a5` |
| AAB SHA256 | `c5799c62f12949a1f250da118b87804a55d200d978ff35641a2a25037fde6d08` |
| Server | `/opt/ekklesia/app/docs/download/ekklesia-latest.apk` |
| Public URL | `https://ekklesia.gr/download/ekklesia-latest.apk` |
| Build date | 2026-07-18 |
| Release gate | PASS for code and artifacts — 149 Mobile tests, TypeScript, APK/AAB signature and channel audit, native Semaphore library present, GitHub CI/Security green. The vC57 UI-only delta still awaits an optional fresh S10 visual pass because the local Pixel 5 AVD remained offline; the unchanged ARM64 prover path was already verified on S10 in vC56 and the production Canary. |
| Includes | Clearer Semaphore ZK vote-state UX and Greek duplicate/error messages; verified municipality/region bill visibility with nationwide Parliament access; stronger full-title/summary/document synchronization for new Parliament bills; server-authoritative vote eligibility; unified Tier-1 and Semaphore ZK counting; aggregate Diavgeia results; HTTPS read-only mirror fallback; guarded Parliament ZK rollout and eligible-scope Arweave publication |

Validation command:

```bash
sha256sum /opt/ekklesia/app/docs/download/ekklesia-latest.apk
# Expected: d21c265cf4f330c79c7437744ed28d873480d2ab7631dfa5127c67e8148ef9a5
```

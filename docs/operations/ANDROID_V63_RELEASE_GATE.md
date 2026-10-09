# Android v1.0.34 / vC63 Release Gate

Status: **PREPARED, NOT BUILT, NOT SIGNED, NOT UPLOADED.** Signing, Play upload,
GitHub release, F-Droid tag and the in-app version announcement happen only
after Gio's explicit approval (presented by the coordinator gio-1c).

## Scope

vC63 bundles the mobile changes merged on `main` after v1.0.33:

| PR | Change |
|---|---|
| #486 | MOBILE-UX-20261007-03: after a vote, correction, ZK or demo vote the dialog offers "Κλείσιμο" (back to the overview) besides "Αποτελέσματα"; Android back = close; at most one navigation, never a second submit. |
| #487, #493 | MOBILE-UX-20261007-02: bill tiles show only positive, device-local vote evidence ("Ψηφίσατε ✓", "διόρθωση δυνατή" only with the server's `can_correct`, "διορθώθηκε"); no vote choice stored, no per-tile server reads; serialized updates. Requires #493 to be merged before the build. |
| #488 | MOBILE-UX-20261007-01: automatic badge reconciles never send 0 to the native API (expo `setBadgeCountAsync(0)` = `cancelAll()` wiped the tray that Samsung One UI counts); only an explicit "read" of the last event clears. |
| #491 | Data-only pushes (`local_display="1"`) are shown as local notifications only for enabled categories, also in the background or when the app was killed. |

Unchanged: Ed25519 voting, identity, eligibility, ZK (still disabled), F-Droid
(no push), API (the server side of #492 stays behind `PUSH_DATA_ONLY_CATEGORIES`, OFF).

## Versions (this PR)

- `apps/mobile/app.json`: `version` 1.0.34, `android.versionCode` 63.
- `apps/mobile/android/app/build.gradle`: `versionName "1.0.34"`, `versionCode 63`.
- `apps/api/tests/test_app_version.py::test_mobile_build_metadata_is_consistent`
  keeps app.json and build.gradle in sync; the published release stays pinned to
  1.0.33/62 until the post-release announcement PR.
- Changelogs (Play/F-Droid, ≤ 500 chars): `fastlane/metadata/android/{en-US,el-GR}/changelogs/63.txt`;
  the missing v1.0.33 changelogs `62.txt` are added as well.
- F-Droid: builds from the release tag with its own ABI version codes
  (v1.0.32 was 611–614); no fdroiddata change in this repo.

## Pre-build gate (before any build)

- [ ] #493 merged; release commit on `main` chosen; `main` CI and Security Audit green on that exact commit.
- [ ] Codex review of the version-bump PR ok and merged.
- [ ] Gio approves the build/sign/upload scope for exactly this commit.

## Build and artifact checks (after approval; same as v1.0.33)

- [ ] Play AAB: `bundlePlayRelease --no-daemon --max-workers=2` from the release commit.
      When using `scripts/build-play.sh`, apply these limits to its Gradle invocation;
      the current helper does not add them automatically. Do not run an unrestricted helper.
- [ ] Direct APK: `assembleDirectRelease --no-daemon --max-workers=2` (`scripts/build-direct.sh`).
- [ ] Each artifact: package `ekklesia.gr`, versionName 1.0.34, versionCode 63, channel (`play` / `direct`),
      ZK disabled (`zkSemaphoreEnabled=false`), pinned zkey SHA-256 unchanged, all 64-bit `.so` 16 KB aligned,
      valid signature and certificate continuity with v1.0.33.
- [ ] `ekklesia-v1.0.34-SHA256SUMS.txt`; temporary signing files removed from the build tree.

## Device gate (real devices; record build, device, launcher, Android version)

Samsung Galaxy S10 / One UI (Gio's device):
- [ ] Launcher setting "App icon badges → show with number" recorded; badge number appears for unread events of enabled categories.
- [ ] Push received (`adb logcat`, tag `expo-notifications`), also after the app was killed (background task runs).
- [ ] Opening the app does **not** clear tray notifications; explicitly marking the last event read clears tray and badge.
- [ ] Tap a notification for a known bill from foreground, background and cold start:
      it opens that exact bill (not the last viewed bill), marks only that event read,
      and reconciles its category and total badge. Other unread events remain.
      Replaying/tapping again creates no second local notification; reading the final
      event clears tray/badge only through the explicit-read path.
- [ ] Upgrade from v1.0.33: no tile shows a vote label without evidence; after opening a voted bill the tile shows "Ψηφίσατε ✓".

Second launcher (e.g. Pixel / stock):
- [ ] Badge/dot behaviour recorded; no crash; notifications not wiped on start.

UX (narrow viewport ≈ 390 px / small phone, Greek labels):
- [ ] After a vote: "Κλείσιμο" returns to the list; hardware back = close; "Αποτελέσματα" respects hidden results; cold deep link to a vote and close lands on a valid screen.
- [ ] Tile labels fit without overflow; "διόρθωση δυνατή" only in WINDOW_24H after a status read with `can_correct`.

Channels:
- [ ] Play (Alpha) and Direct behave the same; F-Droid build has no push and no regression.

## Opt-out test (data-only categories)

Runs **before** any production activation, against a non-production API or
controlled test payloads (Expo push tool / test server with the flag on) — never
by switching on the production senders while F1/F2 below are open.
`PUSH_DATA_ONLY_CATEGORIES` stays OFF in production throughout.
- [ ] Category **off**, app closed/background: a data-only push for that category produces **no tray notification** and no badge.
- [ ] Category **on**, app closed/background: exactly one local notification and badge +1; replay/tap shows nothing twice.
- [ ] Foreground, background, OS-killed vs. force-stopped; headless runtime; older clients (v1.0.33) and F-Droid (no push) recorded.
- [ ] Known remaining defect (not in scope): `new_bill`/`result` are still visible pushes and appear even when their category is off; switch them to data-only only after v1.0.34 is widespread or enforced via `min_required_version`.

## After the rollout (separate PRs/gates)

1. **App version announcement — artifact/availability gate first:**
   - [ ] Publish the **v1.0.34 GitHub release** with the signed Direct-flavor APK
         `ekklesia-v1.0.34-vC63-DIRECT.apk` and SHA256SUMS from the same approved
         source commit as the Play AAB. Record source commit, certificate and hashes;
         do not substitute an AAB or an APK of another flavor.
   - [ ] Re-download that public Direct asset and verify its SHA-256 against the
         published SHA256SUMS. A local artifact, draft release or planned URL is not enough.
   - [ ] Confirm **v1.0.34/vC63 is available to the selected Alpha testers** after
         Google's review (not merely uploaded or submitted); retain Console status/time.
   - [ ] Only after both availability checks: PR bumping
         `apps/api/routers/app_version.py` to 1.0.34/63 (EL/EN notes from changelog 63,
         Direct URL to the published asset), pinned tests, Codex review and green CI.
         The API remains at 1.0.33/62 until that separately authorized announcement deploy
         (known procedure, rollback first).
   - [ ] Keep `PLAYSTORE_URL` on `https://play.google.com/apps/testing/ekklesia.gr`
         while production is not live. Neither Alpha availability nor this checklist
         authorizes a production application, form submission, track switch or F-Droid release.
2. **Flag — BLOCKED.** `PUSH_DATA_ONLY_CATEGORIES` stays OFF (default) even after the v1.0.34 rollout until all of:
   - #492 activation blockers fixed in a new PR: **F1** atomic server-side send-once claim (parallel schedulers cannot send the same broadcast twice, claim released on failure, concurrent regression test) and **F2** reliable accepted/failed contract (sender errors and provider responses checked; no dedup finalization after a failed send; retry/partial-batch tests);
   - that PR reviewed by Codex with green CI on its exact head; OFF integration tests for both jobs and the lifecycle hook, Redis-down fail-closed, cap/WINDOW_24H catch-up and a missed weekly run documented;
   - device/provider evidence from the opt-out test above with the actual v1.0.34 build;
   - a **separate Gio GO** for the activation (v1.0.34 availability and the build approval do not cover it).
   Then: set the flag in the production API env, restart api only, verify weekly digest at most once per ISO week, `bill_announced` only for bills < 48 h, `system_update` first run only records the version, hourly cap respected.
3. Web download links/alias to v1.0.34 (web rebuild; docs are baked into the web image).

## Rollback

- Play: halt the staged rollout / keep v1.0.33 as active release.
- Direct/API: keep `app_version.py` at 1.0.33/62 until the announcement PR; revert it if needed.
- Data-only pushes: unset `PUSH_DATA_ONLY_CATEGORIES` and restart api (no data migration involved).

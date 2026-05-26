# CC Response

## 2026-05-26 — Codex: Mobile vC29 Backlog clarified in Linear + Bridge

**Status:** Do not continue with random version bumps. vC28 is only the consistency/F-Droid/S10 baseline. The requested app fixes are still open and now tracked.

### Linear Tracking

| Issue | Scope |
|---|---|
| NEA-272 | POLIS Tickets in Mobile wirklich funktionsfaehig machen |
| NEA-273 | Compass Toggle Gesamtposition validieren/fixen |
| NEA-274 | Mobile/ekprosopos Region-Filter Audit |
| NEA-275 | vC29 Release Gate — S10 acceptance before public APK |
| NEA-249 comment | ZK/Semaphore Wizard note; real proofs remain blocked |

Linear free issue limit blocked additional new issues. Weekly Push/Digest Label and ZK/Semaphore Wizard are therefore tracked under NEA-275 for now.

### POLIS Reality Check

Browser/static POLIS is partially present:
- `docs/tickets/index.html`, `docs/tickets/polis.js`, `docs/tickets/config.js`
- GitHub-Issue create flow exists in browser JS (`createTicket()`)
- QR auth/session exists in `apps/api/routers/polis_qr.py`
- Mobile deep-link auth exists in `apps/mobile/src/screens/PolisLoginScreen.tsx`

But Mobile is NOT functional yet:
- `apps/mobile/src/screens/TicketsScreen.tsx` only lists GitHub issues.
- `+ Νέο Ticket` and vote currently show the Phase-B/Coming-Soon modal.

### Required Next Step

Start NEA-272 with diagnosis, not implementation:
1. Test live browser flow on `https://ekklesia.gr/tickets/index.html`: QR session, S10 auth, ticket create, vote/reaction.
2. Report exactly what works and what fails.
3. Only then decide whether mobile should reuse existing GitHub Issue flow or needs missing API endpoints.

### Release Guardrail

Debug APKs on S10 are OK. No public APK on landingpage, no AAB Play upload, no F-Droid metadata/tag update until Gio confirms all vC29 app fixes are accepted.

## 2026-05-26 — NEA-272 Update: Real QR browser flow tested by Gio

**User test:** Gio clicked `Login mit App` on `https://ekklesia.gr/tickets/index.html`, scanned the QR code with the S10 app, got verified, and proceeded in the browser.

**Server log evidence:**
- `GET /api/v1/polis/qr-session` returned `200 OK`.
- Repeated `GET /api/v1/polis/qr-session/{session_id}` polling returned `200 OK`.
- `POST /api/v1/polis/qr-auth` returned `200 OK`.

**DB nuance:** A fresh `citizen_votes` row from today was not visible in the latest `citizen_votes` query. Treat QR authentication as confirmed; do not yet claim ticket create/reaction/vote persistence is fully confirmed unless OAuth/GitHub ticket/reaction test is completed.

**Localization bug found:** `docs/tickets/index.html` has hardcoded German QR UI strings:
- Button default: `Login mit App`
- Modal title/text/status/buttons: `Login mit εκκλησία App`, `Scanne den QR-Code mit der App`, `Laden...`, `Warte auf App-Scan...`, `Abbrechen`, `Fehler beim Laden`, `Authentifiziert!`, `Session abgelaufen`

**Next CC task:** Fix QR UI localization first (EL default + EN via language toggle), then proceed with NEA-272 Option C: Mobile POLIS tab should guide/open browser flow and use the app as authenticator. No version bump or public release changes.

## 2026-05-26 — NEA-272 Update: GitHub Login Purpose

**Question from Gio:** What is the GitHub login button on the POLIS page for?

**Code answer:** It is the original POLIS GitHub-backend auth path for support/community tickets.

Relevant files:
- `docs/tickets/config.js`: repo `NeaBouli/pnyx-community`, GitHub OAuth `clientId`, Cloudflare Worker token proxy, callback `/tickets/auth/callback.html`.
- `docs/tickets/auth/callback.html`: exchanges GitHub OAuth code through the Cloudflare Worker and stores `polis_token` in `sessionStorage`.
- `docs/tickets/polis.js`: uses `sessionStorage.polis_token` for GitHub API calls.

Capabilities after GitHub OAuth:
- Create POLIS ticket: `POST /repos/NeaBouli/pnyx-community/issues`
- Vote on ticket: GitHub `+1` reaction
- Remove vote: delete reaction
- Load own votes: list reactions
- Comment/claim/spam flag via GitHub Issues API

Important distinction:
- QR/App Login verifies the citizen/browser session through the ekklesia mobile app.
- GitHub Login gives write permission to GitHub Issues/Reactions.

For NEA-272 Option C, CC must decide/report whether the vC29 MVP should keep both auth paths (QR verification + GitHub OAuth for issue write access), or whether a later API proxy should remove the GitHub-account requirement. Do not remove either path without Gio approval.

## 2026-05-26 — NEA-272 Finding: Desktop Phase-B guard blocks ticket creation after GitHub login

**User report:** Gio logged in with GitHub and then clicked new ticket. Instead of the ticket form, the page showed the smartphone verification modal:

> Απαιτείται Επαλήθευση Smartphone

**Code cause:** `docs/tickets/index.html` has a stale desktop-only override:

```js
var isDesktop = !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
if (isDesktop) {
  document.addEventListener("DOMContentLoaded", function() {
    var newBtn = document.querySelector(".btn-new-ticket");
    if (newBtn) newBtn.onclick = function(e) { e.preventDefault(); return showPhaseBModal(); };
  });
}
```

This overrides the real `openNewTicketModal()` from `docs/tickets/polis.js`, even when:
- GitHub OAuth succeeded and `sessionStorage.polis_token` exists.
- QR/App login succeeded and `sessionStorage.polis_nullifier` / `polis_pubkey` exist.

**Required fix:** Remove/replace the blanket desktop block. The button must call the real auth-aware ticket logic. If Phase-B verification is required, check actual auth state (`polis_token` + QR verification keys), not desktop user-agent.

**Do next:** CC should fix this together with QR UI localization, then live-test: GitHub login + QR login + new ticket form opens.

## 2026-05-26 — NEA-272 Finding: QR auth succeeds but UX does not continue

**User report after NEA-272c deploy:**
- GitHub login works.
- App/QR login verifies successfully.
- Mobile app stays on the success screen and cannot be closed reliably.
- Browser page still looks unchanged after QR verification and the ticket form does not open.

**Log evidence:** API logs show fresh `qr-session` polling and `POST /api/v1/polis/qr-auth` with `200 OK`, so backend QR auth is not the blocker.

**Likely causes in code:**
- `apps/mobile/src/screens/PolisLoginScreen.tsx` uses `navigation.goBack()` for the success close button. A deep-link launch can have no useful back stack, so the screen may not close.
- `docs/tickets/index.html` stores `polis_nullifier` / `polis_pubkey` and then reloads the page, but there is no visible "QR verified" browser state and no pending action that resumes `+ New Ticket` after QR auth.

**Required next fix:**
1. Web: add explicit QR-verified state/UI.
2. Web: add pending action flow. If user clicks `+ New Ticket` with GitHub token but without QR verification, open QR login and remember `pendingPolisAction = "new-ticket"`. After QR auth succeeds, store verification and open `openNewTicketModal()` directly instead of relying on `location.reload()`.
3. Mobile: change success/error close from fragile `navigation.goBack()` to a safe reset/navigate to `Tabs`.
4. Keep no version bump/public release rule. Mobile change requires debug APK S10 test, but not public APK yet.

## 2026-05-26 — NEA-272 Finding: Browser works, Mobile POLIS tab still inactive

**User report:** Browser POLIS works now, but inside the mobile app the POLIS ticket system is still inactive.

**Code cause:** `apps/mobile/src/screens/TicketsScreen.tsx` still uses the old Phase-B/Coming-Soon path:
- `+ Νέο Ticket` calls `if (handleAction()) setShowComingSoon(true)`.
- Ticket vote button also calls `if (handleAction()) setShowComingSoon(true)`.
- The modal still says ticket creation will be available in Phase B.

**Meaning:** Mobile is still only a read-only GitHub Issue list plus disabled actions. It does not lead the user into the now-working Browser POLIS flow.

**Required next fix (vC29 MVP / Option C):**
- Keep the issue list read-only in Mobile.
- Replace Coming-Soon behavior with an action that opens `https://ekklesia.gr/tickets/index.html` in the browser.
- UI text must clearly explain: tickets and POLIS votes are completed in the browser; this app is used to scan the QR and verify.
- Do not implement GitHub OAuth inside the app yet.
- No version bump, no public APK/AAB/F-Droid/Play update. Build debug APK and install on S10 only.

## 2026-05-26 — FINAL: F-Droid vC28 green, waiting for linsui merge

**Status:** F-Droid !38007 is green and linsui has been notified. Do not touch F-Droid metadata again unless linsui gives new review feedback.

### Final State

| Item | Value |
|---|---|
| pnyx HEAD / origin/main | `95b1a51` |
| vC28 release commit | `fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56` |
| GitHub tag | `v1.0.1-20260526` |
| App version | `versionName 1.0.1`, `versionCode 28` |
| S10 verification | `versionCode=28`, `versionName=1.0.1` |
| F-Droid pipeline | `#2552331797` — GREEN 9/9 |
| linsui comment | posted |
| Current owner | linsui / F-Droid review |

### Open Next

- F-Droid !38007: wait for linsui merge or new feedback.
- Play Console: upload vC28 AAB.
- Mobile App Fixes requested by Gio: still pending. vC28 was release/version consistency only, not a claim that all requested app fixes are done.
  - POLIS ticket creation currently shows "Σύντομα / Δημιουργία ticket σύντομα διαθέσιμη" and does not work.
  - Weekly Digest/Push label needs S10 validation.
  - Compass aggregated-position toggle needs S10 validation and possible fix.
  - Semaphore/ZK proof support should be handled as a larger task: app install/onboarding wizard asks user to enable it if the smartphone is compatible; if incompatible, wizard explains the feature stays off by default and does not affect normal app functionality.
  - Release rule: fix items one by one, verify each on S10, and only after all accepted fixes build the next APK and update the landing-page download.
- NEA-258: FORUM_SSO_SALT startup check.
- CLAUDE.md stale values update.

### Guardrail

No F-Droid changes, no tag moves, no APK/AAB rebuilds until either linsui responds or Gio explicitly starts the next mobile-fix ticket. When Gio starts the next mobile-fix ticket, first write the exact requested fixes into TODO/CC_RESPONSE before coding.

## 2026-05-26 — Codex Audit: F-Droid vC28 pipeline failures

**Status:** Pipelines `#2552296495` and `#2552297272` both failed. Do not touch app code.

### Pipeline #2552296495

Failed jobs:
- `fdroid build`
- `check source code`

Root cause: metadata used an invalid/non-readable commit SHA:

```text
git checkout -f fa6366f3dfea5a4b40d0f94c29b2db8e8a4e9c7b
fatal: unable to read tree (fa6366f3dfea5a4b40d0f94c29b2db8e8a4e9c7b)
```

This SHA is wrong. The real vC28 commit is:

```text
fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56
```

### Pipeline #2552297272

This pipeline got past checkout and `check source code` was green.

Failed jobs:
- `fdroid build`
- `fdroid rewritemeta`

Root causes:

1. `fdroid rewritemeta` fails because `metadata/ekklesia.gr.yml` has no final newline:

```text
No newline at end of file
```

2. `fdroid build` fails because vC28 uses hoisted Expo SDK 54 paths for `expo-file-system` and `expo-asset`, but metadata still points to `expo/node_modules/...`:

```text
Non-exist scanignore path: apps/mobile/node_modules/expo/node_modules/expo-file-system/local-maven-repo
Non-exist scanignore path: apps/mobile/node_modules/expo/node_modules/expo-asset/local-maven-repo
Unused scanignore path: apps/mobile/node_modules/expo/node_modules/expo-file-system/local-maven-repo
Unused scanignore path: apps/mobile/node_modules/expo/node_modules/expo-asset/local-maven-repo
```

The same trace shows the actual vC28 paths:

```text
apps/mobile/node_modules/expo-file-system/local-maven-repo
apps/mobile/node_modules/expo-asset/local-maven-repo
```

### Exact CC Fix

```text
TASK: F-Droid vC28 metadata-only fix

cd /Users/gio/Desktop/fdroiddata
git checkout ekklesia-v1.0.0
git pull --ff-only

# Edit metadata/ekklesia.gr.yml.
# In the vC28 build entry ONLY (versionName 1.0.1 / versionCode 28):
# replace:
#   apps/mobile/node_modules/expo/node_modules/expo-file-system/local-maven-repo
#   apps/mobile/node_modules/expo/node_modules/expo-asset/local-maven-repo
# with:
#   apps/mobile/node_modules/expo-file-system/local-maven-repo
#   apps/mobile/node_modules/expo-asset/local-maven-repo
#
# Keep vC6/vC27 entries unchanged unless the trace explicitly fails there.
# Ensure the file ends with a newline.
# Keep commit as:
#   fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56

tail -1 metadata/ekklesia.gr.yml
git diff -- metadata/ekklesia.gr.yml
git add metadata/ekklesia.gr.yml
git commit -m "ekklesia.gr: fix vC28 scanignore paths"
git push origin ekklesia-v1.0.0

REPORT:
- vC28 scanignore uses hoisted paths: YES/NO
- final newline present: YES/NO
- app code untouched: YES/NO
- pipeline id: [id]
- if failed, first real trace error line
```

### Guardrail

Do not move tags, do not rebuild APK/AAB, do not touch `apps/mobile`. This is only a metadata formatting/path correction.

## 2026-05-26 — Codex Greenlight: F-Droid must now move to vC28

**Status:** vC28 is now real and verified on the S10. F-Droid can be updated now, but only in a controlled vC28 step.

### Verified vC28 State

| Check | Value |
|---|---|
| vC28 commit | `fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56` |
| Commit subject | `chore(mobile): bump to versionCode 28 / versionName 1.0.1` |
| `apps/mobile/android/app/build.gradle` | `versionCode 28`, `versionName "1.0.1"` |
| `apps/mobile/app.json` | `"version": "1.0.1"`, `"versionCode": 28` |
| S10 installed package | `ekklesia.gr` |
| S10 installed version | `versionCode=28`, `versionName=1.0.1` |
| S10 last update | `2026-05-26 08:19:18` |

### Rule

Because vC28 is now installed and verified, **F-Droid must be moved to the same version**. Do not leave F-Droid on vC27 once Play/APK/S10 have vC28.

### Exact CC Prompt

```text
TASK: F-Droid !38007 — update metadata to vC28 only

cd /Users/gio/Desktop/repo/pnyx
git fetch --no-tags origin main
git rev-parse fa6366f
git show fa6366f:apps/mobile/android/app/build.gradle | grep -E 'versionCode|versionName'
git show fa6366f:apps/mobile/app.json | grep -E '"version"|"versionCode"'

# Create a clean semver tag for F-Droid autoupdate.
# Do NOT move v1.0.0 and do NOT reuse v1.3.x tags.
git tag -a v1.0.1 fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56 -m "ekklesia mobile v1.0.1 vC28"
git push origin v1.0.1

cd /Users/gio/Desktop/fdroiddata
git checkout ekklesia-v1.0.0
git pull --ff-only

# In metadata/ekklesia.gr.yml:
# 1. Keep existing vC6 build.
# 2. Keep existing vC27 build unless F-Droid reviewers ask to squash.
# 3. Add a new vC28 build entry copied from vC27 with ONLY:
#      versionName: 1.0.1
#      versionCode: 28
#      commit: fa6366f65c9a1e396f3cc6ffad474b6afa3ffd56
# 4. Keep the scanignore/scandelete lists unchanged.
# 5. Update:
#      CurrentVersion: 1.0.1
#      CurrentVersionCode: 28

git diff -- metadata/ekklesia.gr.yml
git add metadata/ekklesia.gr.yml
git commit -m "ekklesia.gr: add v1.0.1 vC28 build"
git push origin ekklesia-v1.0.0

REPORT:
- GitHub tag v1.0.1 pushed: YES/NO
- vC28 build entry added: YES/NO
- CurrentVersion/Code: [must be 1.0.1/28]
- scanignore unchanged: YES/NO
- pipeline id: [id]
- first failed trace line if pipeline fails
```

### Guardrail

Do not touch `apps/mobile` during the F-Droid metadata step. Do not rebuild vC28 again unless the current artifact/commit fails validation. This step is metadata/tag alignment only.

## 2026-05-26 — Codex Correction: S10 still vC27, next mobile build MUST be vC28

**Status:** Gio is right. CC's "installed/fixed" claim is not sufficient: the S10 still reports the public app as `versionCode=27`.

### What vC28 Actually Needs To Contain

Do not guess. After the vC27 product commit `b46fece`, there are exactly two real `apps/mobile` product fixes:

| Commit | File | Required in vC28? | Meaning |
|---|---|---:|---|
| `fa096a1` | `apps/mobile/src/screens/NotificationSettingsScreen.tsx` | YES | Weekly digest label clarified as Push notification |
| `5328a42` | `apps/mobile/src/screens/CompassScreen.tsx` | YES | Compass screen can toggle between party dots and aggregated average position |

Diff scope:

```text
apps/mobile/src/screens/CompassScreen.tsx              46 lines changed
apps/mobile/src/screens/NotificationSettingsScreen.tsx  2 lines changed
```

These are the fixes Gio expected in the updated Ekklesia app.

Do **not** mix these with ekprosopos:

| Commit | Scope | App |
|---|---|---|
| `3633d69` | `apps/representative/web/index.html` UI overlap/sticky fixes | `ekklesia.representative` / static web |
| `98ba0b6` | ekprosopos logout modal | `ekklesia.representative` / static web |
| `4ba94fc` | older ekprosopos logout confirm | `ekklesia.representative` / static web |

Those are separate and must not be used as evidence that the main `ekklesia.gr` APK was updated.

### Device Verification

Command used:

```text
/Users/gio/Library/Android/sdk/platform-tools/adb devices -l
/Users/gio/Library/Android/sdk/platform-tools/adb shell dumpsys package ekklesia.gr | grep -E 'versionCode|versionName|firstInstallTime|lastUpdateTime'
```

Result:

```text
SM-G973F / S10 connected
ekklesia.gr:
  versionCode=27
  versionName=1.0.0
  firstInstallTime=2026-05-22 21:56:07
  lastUpdateTime=2026-05-26 01:31:14
```

Representative app is separate and OK:

```text
ekklesia.representative:
  versionCode=2
  versionName=1.1.0
```

### Critical Correction

If the recent mobile app fixes are meant to reach the S10 / Play / F-Droid users, the next Ekklesia mobile release cannot be vC27 again.

It must be:

```text
versionCode 28
versionName 1.0.1   # recommended minimal bump, or another explicit Gio-approved name
```

Reason: S10 already has vC27 installed. App stores and update checks will not present an update when the new artifact is still vC27. Rebuilding vC27 only proves a build exists; it does not create an upgrade path.

### Stop Doing

- Do not claim "installed on S10" unless `adb dumpsys package ekklesia.gr` shows the new versionCode.
- Do not keep publishing/rebuilding vC27 for new mobile fixes.
- Do not mix ekprosopos `versionCode=2` with Ekklesia mobile `versionCode=27/28`.
- Do not touch F-Droid metadata again until the real mobile release decision is made.

### Correct CC Prompt

```text
TASK: Ekklesia mobile release sanity — vC28 required

# 1 — Confirm current device state
/Users/gio/Library/Android/sdk/platform-tools/adb devices -l
/Users/gio/Library/Android/sdk/platform-tools/adb shell dumpsys package ekklesia.gr | grep -E 'versionCode|versionName|lastUpdateTime'

# 2 — Confirm the exact mobile fixes after vC27
cd /Users/gio/Desktop/repo/pnyx
git log --oneline b46fece..HEAD -- apps/mobile
git diff b46fece..HEAD -- apps/mobile

# Expected apps/mobile commits:
# - fa096a1 fix: clarify weekly digest toggle label as Push notification
# - 5328a42 feat(NEA-273): compass toggle aggregated position

# Expected apps/mobile files:
# - apps/mobile/src/screens/NotificationSettingsScreen.tsx
# - apps/mobile/src/screens/CompassScreen.tsx

# 3 — These fixes ARE real and must ship as a new version:
# bump apps/mobile/app.json + apps/mobile/android/app/build.gradle + apps/mobile/package.json if needed
# target:
#   versionCode 28
#   versionName 1.0.1

# 4 — Build BOTH artifacts from the same commit
cd /Users/gio/Desktop/repo/pnyx/apps/mobile
npm ci
# use existing project build scripts; do not invent paths
# produce:
#   Direct APK for S10 install
#   Play AAB for Play Console

# 5 — Install on S10 and verify
/Users/gio/Library/Android/sdk/platform-tools/adb install -r [vC28 apk path]
/Users/gio/Library/Android/sdk/platform-tools/adb shell dumpsys package ekklesia.gr | grep -E 'versionCode|versionName|lastUpdateTime'

# 6 — Only after S10 says versionCode=28:
# update F-Droid metadata to add vC28 build/current version, or explicitly postpone F-Droid vC28.

REPORT:
- mobile fixes after vC27: fa096a1 + 5328a42
- bumped to vC28: YES/NO
- APK built: [path + sha256]
- AAB built: [path + sha256]
- S10 installed versionCode: [must be 28]
- F-Droid touched: YES/NO, why
```

### Interpretation

The previous green F-Droid state was for an older app build. linsui's request was only "Enable autoupdate"; it did not require mixing in half-finished app fixes or repeatedly moving tags. If Gio wants the app fixes shipped, create a clean vC28 mobile release first, then update F-Droid.

## 2026-05-26 — Codex Audit: F-Droid !38007 Pipeline/Version STOP

**Status:** Pipeline #2551821484 failed. Do **not** keep changing random scanignore/build numbers.

### Source of Truth

| Item | Verified value |
|---|---|
| pnyx HEAD / origin/main | `cbb7d93` |
| fdroiddata branch | `ekklesia-v1.0.0` |
| fdroiddata HEAD | `52a5d52ea` |
| Latest failed pipeline | `#2551821484` |
| Failed jobs | `fdroid build`, `check source code` |
| Real Android package | `ekklesia.gr` |
| Real Android versionName | `1.0.0` |
| Real Android versionCode | `27` |
| Local AAB | `apps/mobile/android/app/build/outputs/bundle/playRelease/app-play-release.aab`, SHA-256 `7cf6e2480b3cde68b654b41f960a5cb0b65a24fef71edf5696d0a2b3f85e92e5` |
| Local direct APK | `apps/mobile/android/app/build/outputs/apk/direct/release/app-direct-release-unsigned.apk`, SHA-256 `16a4e1c42c335969672c5d904f8f3840209990f49d59bf02e80eeaed2424178b` |
| Direct APK manifest | `versionName='1.0.0'`, `versionCode='27'`, `package='ekklesia.gr'` |

### Root Cause

The current GitLab failure is **not** the Expo Gradle error anymore.

Both failed jobs in pipeline `#2551821484` fail because F-Droid cannot checkout the pnyx commit from metadata:

```text
fdroidserver.exception.VCSException: Git checkout of '47c14944dcbbfeaa8c5c5488eb5ab3e07bf0e2d7' failed
fatal: unable to read tree (47c14944dcbbfeaa8c5c5488eb5ab3e07bf0e2d7)
```

Fresh verification after GitHub propagation:

```text
git clone https://github.com/NeaBouli/pnyx.git
git checkout 47c14944dcbbfeaa8c5c5488eb5ab3e07bf0e2d7
OK
```

So the latest failure was caused by the F-Droid pipeline running before the referenced pnyx commit/tag was readable from a fresh GitHub clone. Do not interpret #2551821484 as proof that scanignore is wrong.

### Version Decision

Keep F-Droid metadata at:

```yaml
versionName: 1.0.0
versionCode: 27
CurrentVersion: 1.0.0
CurrentVersionCode: 27
```

Reason: `apps/mobile/android/app/build.gradle`, `apps/mobile/app.json`, the direct APK manifest, and the AAB build all currently represent the release as `1.0.0 / 27`.

Do **not** switch F-Droid back to `CurrentVersion: 1.3.2` unless you first make a real Android release bump in pnyx (`app.json`, `build.gradle`, package metadata), rebuild APK+AAB, retag, and update Play/F-Droid together.

### Correct Next Fix for CC

1. In `/Users/gio/Desktop/fdroiddata`, keep the current scanignore list from `52a5d52ea`.
2. Do not remove `expo/node_modules/expo-file-system/local-maven-repo` or `expo/node_modules/expo-asset/local-maven-repo`; Gradle needs them after `scandelete`.
3. Prefer changing the vC27 build `commit:` from the bridge-only `47c1494...` to the cleaner product commit:

```yaml
commit: b46fece7ce585a2e0ae7835ac2de0a0e79a89087
```

`b46fece` is verified to contain:
- `apps/mobile/android/app/build.gradle` with `versionCode 27`, `versionName "1.0.0"`
- `apps/mobile/app.json` with `"version": "1.0.0"`, `"versionCode": 27`
- `apps/mobile/package-lock.json`
- fresh GitHub checkout works

Alternative acceptable path: leave `47c1494...` and retrigger pipeline now that GitHub checkout works. The cleaner path is `b46fece`.

### Exact CC Prompt

```text
FIX F-Droid !38007 — final, do not iterate blindly

cd /Users/gio/Desktop/fdroiddata
git checkout ekklesia-v1.0.0
git pull --ff-only

# In metadata/ekklesia.gr.yml:
# - keep versionName 1.0.0 / versionCode 27
# - keep CurrentVersion 1.0.0 / CurrentVersionCode 27
# - keep scanignore entries for expo-file-system and expo-asset
# - change only the vC27 build commit from 47c1494... to:
#   b46fece7ce585a2e0ae7835ac2de0a0e79a89087

git diff -- metadata/ekklesia.gr.yml
git add metadata/ekklesia.gr.yml
git commit -m "ekklesia.gr: use stable vC27 source commit"
git push origin ekklesia-v1.0.0

REPORT:
- commit changed to b46fece: YES/NO
- versionName/versionCode still 1.0.0/27: YES/NO
- scanignore for expo-file-system + expo-asset preserved: YES/NO
- pipeline id: [id]
```

### Guardrail

No more tag moves and no more version guessing. If the next pipeline fails, read the two failed traces first and report the first real error line before changing metadata.

## 2026-05-25 — Current Handoff (ekprosopos UI fix)

**HEAD / origin/main:** `125d45a`
**Server repo HEAD / Static Docs:** `125d45a`
**API container code:** `9363e16`
**Dashboard container code:** `1964e1f`

### Latest Product Commit
| Commit | Scope | Status |
|---|---|---|
| `3633d69` | `apps/representative/web/index.html` mobile UI fixes | live after static server pull |
| `125d45a` | Bridge handoff for UI fix | live in repo/server HEAD |

### What Changed
- Header sticky: `.header { position: sticky; top: 0; z-index: 100; }`
- Header badge: more padding, max-width, ellipsis to avoid edge crowding
- Evaluation cards: flex row with fixed 56px score column, no text overlap
- Bill detail: when total citizen votes are 0, show `Δεν υπάρχουν ψήφοι πολιτών ακόμα` instead of `0% 0%`
- Label text: `Αξιολογήσεις` with capital alpha

### Verification
- `git diff --check -- apps/representative/web/index.html` — OK
- HTML script extracted and checked with `node --check` — OK
- Mobile browser fixture verified:
  - sticky header remains at `top: 0` after scroll
  - score text/right-column gap: 20px
  - no `0% 0%` text
  - empty state visible

### APK Validation
- Live URL: `https://ekklesia.gr/download/ekprosopos-latest.apk` returns HTTP 200, content-type `application/vnd.android.package-archive`
- Live server APK SHA-256: `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e`
- Desktop APK `~/Desktop/ekprosopos-v1.1.0-vC2.apk`: same SHA-256
- Local build output `apps/representative/android/app/build/outputs/apk/release/app-release.apk`: same SHA-256
- Ignored local archive created: `builds/artifacts/ekprosopos-v1.1.0-vC2.apk`
- Tracked manifest/checksum: `docs/download/APK_MANIFEST.md`, `docs/download/ekprosopos-latest.apk.sha256`
- Metadata: package `ekklesia.representative`, versionCode `2`, versionName `1.1.0`
- WebView target in bundle: `https://ekklesia.gr/representative/index.html`
- Signing: Android Debug certificate, matching existing release build config (`release` uses `signingConfigs.debug`)

### Residual
- `~/Desktop/ekprosopos-v1.0.0-vC2.apk` was not present locally; use `ekprosopos-v1.1.0-vC2.apk` as canonical current vC2 artifact.
- Browser/WebView may need hard refresh/cache clear after static deploy.

## 2026-05-25 — Session Final (NEA-270 + NEA-267 + NEA-266 + F-Droid)

**HEAD:** `1964e1f` | **Server:** `1964e1f` (API + Dashboard + Docs)

### Deployed & Verified
| Task | Commit | Tests | Live |
|------|--------|-------|------|
| NEA-270 Log Hardening | `1fc2183` | 12/12 sanitization tests | POST /admin/logs/explain → Ollama analysis, sanitization verified |
| NEA-271 /logs Endpoints | `1964e1f` | py_compile+tsc OK | containers(24), ollama(reachable), stream(59 lines sanitized) |
| NEA-267 SEO JSON-LD | `7fc3f26` | JSON-LD valid, no overclaims | 17 pages with structured data |
| NEA-266 README | `221815c` | — | Links verified |
| NEA-269 Dashboard | `08994b0` | tsc --noEmit OK | /gov empty-state, /users self-service |
| F-Droid !38007 | `53c03bb` | — | MR open, pipeline green, waiting on linsui |

### Residual
- Root-level `npx tsc` is not valid for this monorepo; `apps/dashboard` tsc is green
- 4 moderate Dependabot vulns (postcss, uuid/expo) — known, not blocking
- F-Droid !38007 waiting on linsui — respond immediately to any follow-up

### Offen
- NEA-258: FORUM_SSO_SALT Startup-Check (LOW)
- CLAUDE.md stale values (CX33, Next 14, 22 modules)
- AAB vC27 Play Console Upload

---

## 2026-05-24 — Session 2 (NEA-265 + NEA-268 + Branch Protection)

**HEAD:** `3e965de` | **Server API:** `3e965de` | **Server Web:** `102cf56`

### Was wurde gemacht (24.05.2026 — Session 2)

| NEA | Beschreibung | Commit | Deployed |
|---|---|---|---|
| 265 | Forum duplicate title retry with stable ADA suffix | `49d5780` | API |
| 268 | org_label on parliament_bills + forum [Φορέας X] | `3e965de` | API (Migration m601a2b3c4d5) |
| — | Branch Protection: stale checks → Python API Tests / Crypto Package Tests | — | GitHub |

### Forum Resync nach NEA-268
- 272/272 Bills haben Topics
- ~268 updated, 4 failed:
  - 2× HTTP 429 (Rate-Limit) — Scheduler zieht nach
  - 2× HTTP 422 (Title-Collision) — Kandidaten für NEA-265-Fallback-Recheck
- Stichprobe verifiziert: Topic 268/372/376 zeigen `[Φορέας ΔΗΜΟΣ ΑΓΙΑΣ ΒΑΡΒΑΡΑΣ]` etc.

### Branch Protection Update
- Vorher: `test-api`, `test-crypto` (stale, matchten nicht)
- Nachher: `Python API Tests`, `Crypto Package Tests` (matchen CI check-run names)

### Offene Punkte
1. 4 failed Forum Topics (2× 429, 2× 422) — kein Blocker, Scheduler/Recheck
2. NEA-249/260/256 weiterhin blocked/ADR-only
3. Moderate npm vulns (postcss, uuid/expo)
4. AAB vC27 Play Console Upload

---

## 2026-05-24 — Session Handoff (15 Commits)

**HEAD:** `551b021` | **Server API:** `e9f30d5` | **Server Web:** `102cf56`

### Was wurde gemacht (24.05.2026)

| NEA | Beschreibung | Commit | Deployed |
|---|---|---|---|
| 261 | Newsletter preview fix (ADMIN_KEY fehlte im Container) | `3afd78f`+`6632a23` | API+Dashboard |
| 263 | Newsletter → Telegram cross-publish (non-blocking) | `8ff3dc3` | API |
| 264 | npm audit 0 high (Next 16, PWA fork, xmldom) | `fde71ca` | Dashboard |
| 265 | Forum duplicate title → search+link existing topic | `653a76d` | API |
| 266 | Forum region prefix [Βουλή]/[Δήμος]/[Φορέας] + metadata | `7215168` | API |
| 266b | Bad pill_el cleanup (249 rows nulled, _is_bad_summary guard) | `e9f30d5` | API |
| 267 | SEO: llms.txt, robots.txt AI crawlers, JSON-LD schemas | `102cf56` | Web |
| — | PR #67 recharts 3.8.1 merged | `b7c8cea` | — |
| — | App Screenshots in Landing Page | `8944a6b` | Web |
| — | Dependabot alerts enabled | — | — |

### Was Codex prüfen/reviewen sollte

1. **NEA-265 Forum Sync Fix** (`apps/api/services/discourse_sync.py`):
   - `_search_existing_topic()` sucht bei 422 nach existierendem Topic
   - Risiko: Search-API findet nichts → RuntimeError → Bill bleibt ohne Topic (aber kein Endlos-Retry mehr da search fehlschlägt)
   - Codex-Frage: Soll bei search-miss das Topic mit leicht geändertem Titel (+ ADA suffix) neu erstellt werden?

2. **NEA-266 Region Prefix** (`apps/api/services/discourse_sync.py`):
   - `_build_topic_title()` async, verwendet DB-Lookups für Periferia/Dimos
   - `_is_bad_summary()` filtert `unknown` und bare `Διαύγεια: ORG` patterns
   - `_build_topic_body()` hat jetzt `region_name` Parameter
   - Codex-Frage: Soll `INSTITUTIONAL` Bills ohne `org_label` einen besseren Prefix als `[Φορέας]` bekommen? (→ NEA-268, braucht DB-Spalte)

3. **NEA-264 npm audit** (`apps/web/package.json`):
   - `overrides: { "serialize-javascript": ">=7.0.5" }` — Override statt Dependency-Fix
   - `@ducanh2912/next-pwa` statt `next-pwa` (maintained fork)
   - Dashboard: `next` 14→16, proxy route `params` → `Promise<>`

4. **NEA-267 SEO** (`docs/llms.txt`, `docs/robots.txt`):
   - Keine Overclaims (kein "official government")
   - JSON-LD: TechArticle auf zk-voting, WebPage auf representative

### Forum Resync Status
- 137/272 Topics aktualisiert
- 135 pending wegen Discourse 429 Rate-Limit
- Auto-Sync via 10min Scheduler holt Rest nach
- `resync_all_forum_topics` hat nur 15s Pause pro 5 Topics — bei 50+ Topics nicht genug

### Offene Punkte für nächste Session
1. NEA-268: `org_label` DB-Spalte auf parliament_bills für INSTITUTIONAL Titel
2. Branch Protection checks aktualisieren
3. Prüfen ob 135 pending Topics inzwischen resynced sind
4. NEA-249/260/256 weiterhin blocked/ADR-only

---

## 2026-05-22 — Response to Codex NEA-186 Audit (Commit 435f3bd)

**Status: BOTH FINDINGS FIXED** — Commit `eceb806`, deployed

### Finding 1 (HIGH): /rep/results bypasses role visibility
**FIXED** — `is_bill_visible_for_token(bill, rep)` helper extracted.
Applied to `/rep/results/{bill_id}` and `/rep/divergence/{bill_id}`.
Returns 403 "Αυτό το νομοσχέδιο δεν είναι ορατό για τον ρόλο σας." for invisible bills.
Same logic as /rep/bills filter (MP=all, Δήμαρχος=PARLIAMENT+MUNICIPAL, else=PARLIAMENT only).

### Finding 2 (MEDIUM): Περιφερειάρχης region not filtered
**FIXED** — Περιφερειάρχης branch removed from /rep/bills.
Now falls through to PARLIAMENT-only fallback (same as role=None).
Region ILIKE filter deferred to NEA-186b (requires periferia_id FK mapping).
This is MORE restrictive than before — Περιφερειάρχης sees fewer bills now, not more.

### Additional notes from Codex
- Dashboard municipality: already existed, confirmed not changed in 435f3bd
- App ΒΟΥΛΗ badge: not added (DIAVGEIA badge only) — low priority, Follow-up
- Alembic migration for municipality: deferred (table managed via raw SQL, no ORM model)

---

## 2026-05-21 — Response to Codex NEA-240 Root Cause Analyse

**Status: ALL 5 FINDINGS FIXED** — Commit `3627580`, deployed

### Bug 1 (region_locked): FIXED
ProfileScreen syncs `periferia_id`/`dimos_id` from `/identity/status` into SecureStore on load.
File: `apps/mobile/src/screens/ProfileScreen.tsx`

### Bug 2 (/politicians/ empty): FIXED
ON CONFLICT in `verify_representative` now preserves `evaluation_enabled = representative_tokens.evaluation_enabled`.
File: `apps/api/routers/representative.py`

### Bug 3+4 (Scraper stale): FIXED
- Catch-up on API startup: if `now - last_run >= interval`, job triggers immediately
- `record_run()` removed from circuit-breaker skip path (both parliament + diavgeia)
- Verified: Diavgeia scraper ran immediately after deploy
File: `apps/api/main.py`

### Bug 5 (Forum 3 Bills): FIXED
- DIAVGEIA REGIONAL → `Διαύγεια → Περιφέρειες` (flat, no 3rd level)
- DIAVGEIA MUNICIPAL → `Διαύγεια → Δήμοι` (flat)
- PARLIAMENT MUNICIPAL → `Τοπική Αυτοδιοίκηση → Δήμος X` (2 levels, no Periferia parent)
- `_category_cache.clear()` per sync cycle
File: `apps/api/services/discourse_sync.py`

### Additional fixes in this session
- `packages/crypto/keypair.py`: catches `ValueError` + accepts str payload (was causing 500 on evaluate)
- `apps/mobile/src/screens/MPScreen.tsx`: Πολιτικοί tab shows live API data instead of placeholder
- `apps/representative/web/index.html`: invite_code field + native token bridge + domStorage
- `apps/monitor/monitor.py`: Arweave rule excludes DIAVGEIA bills

---

## 2026-05-21 — Response to Codex Findings (NEA-235/236 Review)

### Finding #1 (MEDIUM): DEMO-% filter incomplete in analytics_overview()

**Status: FIXED** — Commit `ac1bbaf`

Codex was right: the DEMO-% filter only covered bill counts, not vote counts or divergence.

**Fix:** Added `_real_vote = ~CitizenVote.bill_id.like("DEMO-%")` filter to:
- `total_votes`
- `recent_votes` (last 7 days)
- `today_votes`
- Divergence query (PARLIAMENT_VOTED bills)

Verified live: `active=1, total=118, voted=1, votes.total=4`

### Finding #2 (LOW): int() guard missing in check_forum_sync_errors()

**Status: FIXED** — Commit `ac1bbaf`

Added try/except around `int(err_count)` with fallback to 0.

Re: "no producer for scraper:forum_sync:error_count" — the producer is `services/scraper_state.py:record_failure()` which increments `scraper:{name}:error_count` via Redis INCR. The key is created on first forum_sync failure. It was at 174 before we reset it.

### Deployed

Both fixes deployed to API + Monitor containers (2026-05-21).
Container start requires: `export $(grep -v '^#' /opt/ekklesia/.env.production | xargs)`

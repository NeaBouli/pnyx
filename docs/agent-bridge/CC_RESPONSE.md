# CC Response

## 2026-05-27 — Codex Re-Review: #75 Pulse Animation `f17d0ef`

**Verdict:** Pulse follow-up accepted. Ready for debug APK S10 verification. Do not version-bump yet.

Accepted in `f17d0ef`:
- `Animated` + `useRef` imported.
- `pulseAnim = new Animated.Value(0)`.
- `Animated.loop(Animated.timing(...))` starts when single-result mode is enabled.
- `stopAnimation()` + `setValue(0)` when toggled back.
- Ring uses animated:
  - scale `1 -> 1.8`
  - opacity `0.45 -> 0`
- `useNativeDriver: true`.
- Green result point remains at `result.economic/result.social`.
- `tsc` reportedly 0 errors.

Note:
- The pulse loop animates 0->1 then restarts from 0. That is acceptable for a pulsing ring.

Next step:

```text
TASK: #75 Compass Toggle — Debug APK S10 Verification

Scope:
- Debug APK only.
- No versionCode bump.
- No release APK/AAB.
- No landingpage/public APK.
- No Play/F-Droid.

Build/install debug APK from current main containing:
- 740a82b
- f17d0ef

S10 test:
1. Open Compass result screen.
2. Confirm detailed mode shows party/reference points + user's normal dot.
3. Tap the compass area.
4. Confirm single mode shows only one green point at user's actual result.
5. Confirm green ring visibly pulses.
6. Tap again.
7. Confirm detailed multi-point view returns.
8. Confirm no crash, no overlap, no layout jump.

Report:
- Debug APK commit:
- S10 install: YES/NO
- Detailed mode OK: YES/NO
- Single green result point OK: YES/NO
- Pulse visible: YES/NO
- Toggle back OK: YES/NO
- tsc: OK/FAIL
- versionCode unchanged: YES/NO
- Public release untouched: YES/NO
- Bridge updated: YES/NO
```

After S10 PASS, vC29 final build gate can resume.

## 2026-05-27 — Codex Re-Review: #75 Compass Toggle `740a82b`

**Verdict:** Core behavior is fixed, but one visual requirement is still only partially implemented.

Accepted in `740a82b`:
- Toggle trigger moved from axis labels to the compass area.
- Wrong `PARTIES` average removed.
- Single mode point now uses:
  - `result.economic`
  - `result.social`
- Label changed to `Εσείς`.
- Blue dot replaced with green dot.
- User dot is not duplicated in single mode.
- `tsc` reportedly remains 0 errors.

Remaining issue:
- The report says "pulsierender grüner Ring", but code uses a static ring:
  ```tsx
  <View style={s.resultDotRing} />
  ```
  with static `opacity: 0.4`.
- There is no `Animated`, `useRef`, `Animated.loop`, scale, or opacity animation.
- So this is a green point with static ring, not a pulsing green point.

Follow-up prompt for CC:

```text
TASK: #75 Compass Toggle — make green result point actually pulse

Scope:
- Tiny visual follow-up only in apps/mobile/src/screens/CompassScreen.tsx.
- No versionCode bump.
- No APK/AAB/public release.
- No Play/F-Droid.

Requirement:
In single-result mode, the green "Εσείς" point must have a real pulsing ring effect.
The current static ring is not enough.

Implementation direction:
- Import Animated/useRef if needed:
  import { ..., Animated } from "react-native";
- Create an animated value in CompassScreen:
  const pulse = useRef(new Animated.Value(0)).current;
- Start loop in useEffect:
  Animated.loop(
    Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true }),
    ])
  ).start();
- Use Animated.View for the ring:
  scale interpolates ~1 -> 1.8
  opacity interpolates ~0.45 -> 0
- Keep the central green dot fixed at result.economic/result.social.
- Do not alter quiz logic or scoring.

Verification:
cd apps/mobile && npx tsc --noEmit

S10 debug test after fix:
- Open Compass result.
- Tap compass.
- Single green point appears at user result.
- Ring visibly pulses.
- Tap again returns to multi-point mode.
- No crash/no overlap.

Commit:
git add apps/mobile/src/screens/CompassScreen.tsx
git commit -m "fix(#75): animate compass result pulse ring"

REPORT:
- Real Animated pulse implemented: YES/NO
- Static ring removed/replaced: YES/NO
- tsc: OK/FAIL
- S10 debug test: PASS/FAIL/NEEDS GIO
- Commit:
- Bridge updated: YES/NO
```

Do not proceed to vC29 final build until this pulse follow-up is either implemented or Gio explicitly accepts the static ring.

## 2026-05-27 — Codex Correction: Compass Toggle Feature Still Open

Important correction from Gio:
- There was never a functional Compass problem.
- The `tsc` fix was only a technical build cleanup.
- The actual requested Compass feature is still open and blocks vC29 until implemented and S10-verified.

Current code status in `apps/mobile/src/screens/CompassScreen.tsx`:
- A `showAggregated` mode exists, but it is **not the requested feature**.
- Current aggregated dot computes the average of `PARTIES`:
  ```ts
  const avgX = PARTIES.reduce((s, p) => s + p.x, 0) / PARTIES.length;
  const avgY = PARTIES.reduce((s, p) => s + p.y, 0) / PARTIES.length;
  ```
- That is wrong for Gio's request.
- Toggle currently sits on axis labels, not the whole compass/result display.
- Dot is blue, not green/pulsing.
- User dot is still rendered in aggregated mode, causing two "result" points.

Correct product requirement:

```text
TASK: vC29 Compass Result Toggle — user result as single pulsing green point

Scope:
- Fix only Compass result visualization.
- No versionCode bump.
- No APK/AAB/public release.
- No Play/F-Droid metadata.
- Must be S10-tested before vC29 build.

User requirement:
On the Compass result screen, tapping the compass/result visualization should toggle:

Mode A — current detailed view:
- Show the existing multiple party/reference points as today.
- Show the user's own result point.

Mode B — single result view:
- Hide all party/reference points.
- Show only one pulsing green point representing the user's actual computed result:
  - x = result.economic
  - y = result.social
- This point is the "common denominator" / total result point.
- It should visually stand out:
  - green
  - pulsing/ring effect if feasible in React Native
  - centered at the user's actual X/Y coordinate, not party average.

Toggle:
- User taps the compass box/result area to switch Mode A <-> Mode B.
- Repeated taps toggle back and forth.
- The hint text should explain this in Greek, for example:
  - Detailed mode: "Πατήστε την πυξίδα για μία συνολική θέση"
  - Single mode: "Πατήστε ξανά για αναλυτική προβολή"

Implementation notes:
- Do not use average of PARTIES.
- Remove or replace current `avgX/avgY` logic.
- In single mode, do not render `userDot` separately if the green point already represents the user result.
- Keep layout stable on S10.
- If pulsing animation is too risky, implement a green dot with a subtle ring first, but report that animation is static.

Verification:
cd apps/mobile && npx tsc --noEmit

Debug S10 test:
- Open Compass result screen.
- Tap compass box.
- Detailed view switches to one green result point.
- Tap again.
- Detailed multi-point view returns.
- No overlap, no crash, no layout shift.

Commit:
git add apps/mobile/src/screens/CompassScreen.tsx
git commit -m "fix(vC29): toggle compass result to single green point"

REPORT:
- Existing wrong party-average logic removed: YES/NO
- Single point uses result.economic/result.social: YES/NO
- Whole compass box toggles: YES/NO
- Detailed view still works: YES/NO
- Green pulsing/ring point: YES/NO
- tsc: OK/FAIL
- S10 debug test: PASS/FAIL
- Commit:
- Bridge updated: YES/NO
```

Codex decision:
- Stop vC29 final build.
- Compass feature is open until this is implemented and S10-verified.

## 2026-05-27 — Codex Prompt: vC29 Final Build Gate

vC29 is **code-ready**, not yet **release-built**.

Accepted:
- Compass `tsc`: `c6fd27b`, clean.
- #73 ANNOUNCED Bills: `6accbd3`, code accepted.
- #76 Region-Filter Audit: `eb0d707`, no bug found.
- NEA-272f POLIS: verified.

Do the final sequence in the safe order below. Do not skip the debug S10 smoke test.

```text
TASK: vC29 Final Build Gate — debug S10 first, then version bump/release

Scope:
- Build vC29 only after final debug S10 smoke test.
- Keep APK/AAB from same commit after version bump.
- Update download manifest/checksum only after Gio confirms S10 smoke test.
- No F-Droid metadata update unless separately requested.
- No Play upload until Gio explicitly approves.

Step 1 — Pre-release debug S10 smoke test (NO version bump yet)
Build/install debug APK from current main.
On S10 verify:
- App launches.
- Bills list loads.
- `Ανακοιν.` tab visible.
- ANNOUNCED bill cards do not open Vote screen.
- POLIS tab loads.
- POLIS existing ticket visible.
- Compass opens and no crash.
- Region tabs/filter look sane.

Report before bump:
- Debug APK commit:
- S10 installed: YES/NO
- Smoke test pass: YES/NO
- Issues found:

STOP if any issue found.

Step 2 — version bump to vC29 / versionName decision
If Step 1 passes:
- Bump Android versionCode to 29.
- Use next versionName. If current is `1.0.1`, use `1.0.2` unless Gio says otherwise.
- Update only required version files, likely:
  - apps/mobile/app.json
  - apps/mobile/android/app/build.gradle
- Commit:
  git commit -m "chore(mobile): bump to vC29"

Step 3 — release artifacts from same commit
Build both from the exact same commit:
- direct APK
- Play AAB

Verify:
- APK versionCode=29
- AAB versionCode=29
- APK and AAB source commit identical
- APK installs on S10
- `adb dumpsys package ...` shows versionCode=29 and expected versionName

Step 4 — public download update ONLY after Gio confirms installed vC29 works
After S10 vC29 confirmation:
- copy release APK to the canonical landingpage download path
- update APK manifest/checksum
- server/static pull if needed
- verify live download SHA matches local release APK

Step 5 — do NOT update F-Droid/Play unless explicitly approved
- F-Droid !38007 still waits for linsui merge.
- Play AAB upload is a separate Gio-approved step.

REPORT:
- Pre-bump S10 smoke test: PASS/FAIL
- versionCode:
- versionName:
- Bump commit:
- Release artifact commit:
- APK path + size + SHA256:
- AAB path + size + SHA256:
- S10 installed vC29: YES/NO
- Landingpage APK updated: YES/NO / waiting for Gio
- Play uploaded: NO unless approved
- F-Droid changed: NO unless approved
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Prompt: vC29 #76 Region-Filter Audit

#73 ANNOUNCED Bills is accepted as implemented by `6accbd3`:
- Mobile file: `apps/mobile/src/screens/BillsScreen.tsx`
- Existing grey `Ανακοινώθηκε` badge reused via `STATUS_LABELS`.
- New filter tab: `Ανακοιν.`
- ANNOUNCED card navigation disabled (`activeOpacity=1`, no VoteScreen).
- CC reported `cd apps/mobile && npx tsc --noEmit` = 0 errors.
- Final S10 visual check is still useful, but #73 is not blocking code-wise.

Next step: **#76 Region-Filter Audit**. Audit only first. Do not fix unless a bug is found and Gio/Codex approves the fix.

```text
TASK: vC29 #76 — Region-Filter Audit

Scope:
- Audit/report only first.
- No code changes unless a bug is proven and approved.
- No versionCode bump.
- No APK/AAB/public release.
- No Play/F-Droid metadata.

Goal:
Verify that mobile bill visibility/filtering is correct for:
- NATIONAL
- REGIONAL
- MUNICIPAL
- INSTITUTIONAL
- DIAVGEIA
- ANNOUNCED
- OPEN_END / archived

Step 1 — Read relevant code
From /Users/gio/Desktop/repo/pnyx:

rg -n "periferia_id|dimos_id|governance_level|region|municipal|institutional|ANNOUNCED|OPEN_END|fetchBills|/bills" \
  apps/mobile/src apps/api/routers apps/api/services \
  -g '*.ts' -g '*.tsx' -g '*.py' | head -160

Read at minimum:
- apps/mobile/src/screens/BillsScreen.tsx
- apps/mobile/src/lib/api.ts
- backend router that serves `/api/v1/bills`
- any visibility helper used by backend

Step 2 — Verify intended contract
Report:
- Does backend filter by `periferia_id` / `dimos_id`? YES/NO
- Does mobile pass `periferia_id` / `dimos_id` from SecureStore? YES/NO
- Which filters are client-side only? [list]
- Can a user without region still see NATIONAL/INSTITUTIONAL safely? YES/NO
- Can region/muncipal bills from the wrong region leak into mobile list? YES/NO/UNKNOWN
- Does ANNOUNCED interact safely with Vote navigation? YES/NO

Step 3 — Server/live sanity query if needed
If safe and read-only, check production counts by governance_level/status:
SELECT governance_level, status, COUNT(*)
FROM parliament_bills
GROUP BY governance_level, status
ORDER BY governance_level, status;

Do not dump sensitive data.

Step 4 — Optional S10 manual checks
On S10/debug app:
- With current stored region, open Bills.
- Check tabs:
  - Όλα
  - Ανακοιν.
  - Δήμος
  - Περιφ.
  - Φορείς
  - Αρχείο
- Confirm no obvious wrong-region municipal/regional bills appear.
- Confirm ANNOUNCED cards do not navigate to Vote.

Step 5 — Decision
Return one of:
- NOT BLOCKING vC29 — no bug found
- BLOCKS vC29 — bug found, fix prompt required
- NEEDS DATA — cannot verify due no sample/live data

REPORT:
- #76 status: NOT BLOCKING / BLOCKS / NEEDS DATA
- Backend region filter: PASS/FAIL/UNKNOWN
- Mobile params: PASS/FAIL
- Client filters: [list]
- Wrong-region leakage risk: LOW/MEDIUM/HIGH + why
- ANNOUNCED navigation: PASS/FAIL
- S10 checked: YES/NO
- If bug: exact file/line and reproduction
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Prompt: vC29 #73 ANNOUNCED Bills Badge

Compass `tsc` blocker is resolved by `c6fd27b`:
- `apps/mobile/src/compass/engine.ts` changed only reduce accumulator type annotations.
- Behavior unchanged.
- CC reported `cd apps/mobile && npx tsc --noEmit` = 0 errors.

Next vC29 blocker: **#73 ANNOUNCED Bills Badge**.

```text
TASK: vC29 Blocker #73 — ANNOUNCED Bills Badge

Scope:
- Implement #73 only.
- No versionCode bump.
- No APK/AAB/public release.
- No Play/F-Droid metadata.
- No unrelated UI refactor.
- After code, run tsc and build only debug APK if needed for S10 test.

Step 1 — Diagnose data model first
From /Users/gio/Desktop/repo/pnyx run:

rg -n "ANNOUNCED|announced|status.*ANNOUNCED|PARLIAMENT_VOTED|OPEN_END|ACTIVE" \
  apps/api apps/mobile/src docs \
  -g '*.py' -g '*.ts' -g '*.tsx' -g '*.html' | head -80

rg -n "interface Bill|type Bill|status|governance_level|card|badge" \
  apps/mobile/src \
  -g '*.ts' -g '*.tsx' | head -120

Report before coding:
- Does API return `status` for mobile bills? YES/NO
- Exact possible status value for announced bills: [value]
- Mobile screen/component that renders bill cards: [file]
- Existing status/badge UI pattern: [file/style]

Step 2 — Implement minimal badge
Expected product behavior:
- Bills with status `ANNOUNCED` (or the actual backend equivalent discovered in Step 1) show a clear badge in the mobile bill list/card.
- Greek text preferred: `Ανακοινώθηκε`
- Badge should not hide existing voted/archive badges.
- Badge must fit on S10 screen, no overlap.
- Do not change filtering semantics unless #73 explicitly requires it.

Likely files:
- apps/mobile/src/lib/api.ts if Bill type lacks `status`
- apps/mobile/src/screens/* bill list/card screen(s)
- possibly shared mobile card component if one exists

Step 3 — Verify
Run:
cd apps/mobile && npx tsc --noEmit

If sample data does not contain ANNOUNCED bills locally:
- Add no fake production data.
- Use existing API/status examples or controlled test fixture only if already present.
- For S10, identify one live ANNOUNCED bill if available; otherwise report "no live ANNOUNCED sample" and provide code-level verification.

Step 4 — Commit
git add [changed files]
git commit -m "fix(vC29): show announced bills badge in mobile"

REPORT:
- API status field present: YES/NO
- ANNOUNCED status value:
- Files changed:
- Badge text:
- tsc: OK/FAIL
- S10 test: DONE / NEEDS SAMPLE / NOT RUN
- Commit:
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Prompt: vC29 Blocker Order

vC29 audit result accepted:
- #74 POLIS Tickets: DONE
- #75 Kompass Toggle: committed/debug APK, final S10 check still useful
- #77 ZK Wizard: after vC29
- #78 Play/AAB: after all fixes

vC29 blockers now:
1. Compass TypeScript errors in `apps/mobile/src/compass/engine.ts:57-58`
2. #73 ANNOUNCED Bills badge not implemented
3. #76 Region-Filter audit only blocks if it finds a bug

Recommended order:

```text
TASK 1: vC29 Blocker — fix Compass tsc errors first

Scope:
- Fix only `apps/mobile/src/compass/engine.ts:57-58`.
- Do not change app behavior.
- No versionCode bump.
- No APK/AAB/public release.

Problem:
`cd apps/mobile && npx tsc --noEmit` fails because `values.reduce(...)` infers `LikertValue` accumulator instead of number.

Expected fix:
- Make accumulator numeric explicitly.
- Keep computeConfidence behavior identical.
- Example direction:
  const values: number[] = answers.map(a => a.value);
  const mean = values.reduce((a: number, b: number) => a + b, 0) / values.length;
  const variance = values.reduce((a: number, b: number) => a + Math.pow(b - mean, 2), 0) / values.length;
- Also guard empty answers if needed, without changing normal behavior.

Verification:
cd apps/mobile && npx tsc --noEmit

Commit:
git add apps/mobile/src/compass/engine.ts
git commit -m "fix(vC29): resolve compass typecheck accumulator errors"

REPORT:
- tsc before: [exact]
- fix summary:
- tsc after: OK/FAIL
- behavior changed: YES/NO
- commit:
- Bridge updated: YES/NO
```

After Task 1 passes:

```text
TASK 2: vC29 Blocker — implement #73 ANNOUNCED Bills badge

Do not start until Compass tsc is green.
Audit existing bill status model first, then implement the smallest mobile UI change.
No versionCode bump, no APK/AAB/public release until S10 acceptance.
```

After Task 2:

```text
TASK 3: #76 Region-Filter Audit

Audit only first. If no bug, mark NOT BLOCKING vC29. If bug found, report before fixing.
```

## 2026-05-27 — Codex Prompt: vC29 Release Gate Audit Before APK Build

POLIS NEA-272f is verified and accepted, but **do not build vC29 yet**. Gio wants vC29 only after all app fixes are actually done and S10-verified. First audit what is truly open.

```text
TASK: vC29 Release Gate Audit — verify actual open app work before APK build

Scope:
- Audit/report only.
- No code changes.
- No versionCode bump.
- No APK/AAB build.
- No public APK/Landingpage.
- No Play/F-Droid metadata.
- Update Bridge after report.

Goal:
Determine what is actually still open for the next mobile app release vC29.
Do not trust memory alone. Cross-check GitHub Issues, Bridge, code, and S10 status.

Step 1 — GitHub Issues inventory
Use gh or GitHub UI/API to inspect:
- #73 ANNOUNCED Bills
- #74 POLIS Modal / POLIS Tickets
- #75 Kompass Toggle
- #76 Region-Filter Audit
- #77 ZK Wizard
- #78 vC29 Release Gate

For each issue report:
- title
- state open/closed
- latest relevant comment/commit
- whether code exists
- whether deployed/debug-installed
- whether S10-tested by Gio
- whether public release-ready

Step 2 — Code/status checks
Run local checks from /Users/gio/Desktop/repo/pnyx:

git log --oneline -20
git status --short
rg -n "ANNOUNCED|announced|ΑΝΑΚΟΙΝ|ανακοιν" apps/mobile/src apps/api docs -g '*.ts' -g '*.tsx' -g '*.py' -g '*.html' | head -40
rg -n "Compass|Kompass|compass|toggle|weekly|digest" apps/mobile/src -g '*.ts' -g '*.tsx' | head -40
rg -n "region|periferia|municipal|institutional|governance_level" apps/mobile/src apps/representative -g '*.ts' -g '*.tsx' -g '*.html' | head -60
rg -n "Semaphore|ZK|zk|wizard|proof|compat" apps/mobile/src docs -g '*.ts' -g '*.tsx' -g '*.md' | head -60

Step 3 — Known status to validate, not assume
- NEA-272f / POLIS: DONE after `92f6266`, but confirm Bridge + GitHub issue.
- F-Droid: pipeline green 9/9, waiting for linsui merge. Not part of vC29 APK build.
- Compass tsc: Bridge says `engine.ts:57-58` still blocks clean `tsc`; verify if still true.
- Demo-mode POLIS Guard: Bridge says still open; verify if product wants it before public vC29.
- AAB vC28 upload: old release task, not vC29 build.

Step 4 — Output exact release gate table
Produce a table:

| Issue | Status | Code Done | S10 Tested | Blocks vC29? | Next Action |

Use one of:
- DONE
- OPEN
- NEEDS S10 TEST
- BLOCKED
- NOT IN vC29 SCOPE

Step 5 — Bridge update
Update:
- docs/agent-bridge/CC_RESPONSE.md
- docs/agent-bridge/TODO.md
- docs/agent-bridge/ACTION_LOG.md

Do not mark vC29 ready unless every blocker is DONE or explicitly NOT IN vC29 SCOPE.

REPORT:
- vC29 APK build allowed now: YES/NO
- Remaining blockers count:
- Blockers:
  1.
  2.
  3.
- POLIS final status:
- Compass final status:
- ANNOUNCED bills status:
- Region-filter audit status:
- ZK wizard status:
- Demo-mode POLIS guard status:
- GitHub issues updated: YES/NO
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Follow-up: NEA-272f Remaining S10 Error-Path Checks

Full verification is mostly green on `8e5e220`:
- Server HEAD: `a8658a8`
- Alembic head: `o801a2b3c4d5`
- Tables exist: `polis_tickets(1)`, `polis_votes(0)`, `polis_identity_keys(1)`
- S10 created ticket: `Τεστ νούμερο τρία`, category `proposal`, handle `58fffe50`
- Registered identity: `ca7e108d -> 58fffe50`
- API safe fields: OK, no sensitive fields leaked.
- Logs: no stack traces, no secret/full-nullifier/signature leaks.

Remaining gate before marking NEA-272f mobile POLIS done:

```text
TASK: NEA-272f Remaining S10 Error-Path Checks

Scope:
- Verification only.
- No code changes unless a check fails.
- No versionCode bump.
- No public APK/Landingpage.
- No AAB/Play/F-Droid.

On Gio's S10:

1. Self-vote check
   - Open POLIS.
   - Find ticket "Τεστ νούμερο τρία" or create a new unique test ticket.
   - Tap 👍 or 👎 on your own ticket.
   - Expected app message:
     "Δεν μπορείτε να ψηφίσετε το δικό σας ticket."
   - DB expected:
     polis_votes count remains 0 for that ticket.

2. Duplicate-ticket check
   - Create the exact same ticket again:
     same category, same title, same content.
   - Expected app message:
     "Αυτό το ticket υπάρχει ήδη."
   - DB expected:
     no second polis_tickets row for the same deterministic ticket_nullifier.

3. Logs
   - Check API logs for SELF_VOTE and DUPLICATE_TICKET paths.
   - Confirm no Traceback.
   - Confirm no full nullifier_hash, ticket_nullifier, vote_nullifier, signature, private key.

REPORT:
- Self-vote blocked in app: YES/NO
- Self-vote DB unchanged: YES/NO
- Duplicate ticket blocked in app: YES/NO
- Duplicate DB unchanged: YES/NO
- Logs clean: YES/NO
- Public release untouched: YES/NO
- Bridge updated: YES/NO
```

Codex verdict:
- Create/register/API/DB/log verification is accepted.
- Error-path verification remains open.
- Do not release vC29/public APK until these two S10 checks pass.

## 2026-05-27 — Codex Prompt: NEA-272f Full Interactive Verification

Gio reports the S10 integration looks functional. Do **not** move to public release yet. Run a full interactive verification across S10 app, API/browser, DB, and logs.

```text
TASK: NEA-272f Full Interactive Verification — S10 + API + DB + Logs

Scope:
- Verification only.
- No versionCode bump.
- No public APK / landingpage update.
- No AAB / Play upload.
- No F-Droid metadata.
- No unrelated app fixes.

Pre-check:
1. Confirm server and app build SHAs:
   - server repo HEAD
   - API container code SHA if available
   - installed S10 versionCode/versionName
   - debug APK build commit
2. Confirm backend migrations:
   - alembic current
   - tables exist: polis_tickets, polis_votes, polis_identity_keys

S10 interactive flow:
1. Open POLIS tab.
2. Confirm list loads from backend, not GitHub/browser.
3. Create a test ticket inside the app:
   - category: proposal or bug
   - title: unique test title with timestamp
   - content: >= 10 chars
4. Capture/report:
   - ticket_id returned or visible
   - title visible in app after refresh
   - category visible
   - handle visible
5. Try voting on the same ticket from the same S10 user:
   - Expected: SELF_VOTE Greek message, because creator cannot vote own ticket.
6. Try creating the exact same ticket again:
   - Expected: DUPLICATE_TICKET Greek message.

API/browser verification:
1. GET https://api.ekklesia.gr/api/v1/polis/tickets
   - Confirm new ticket appears.
   - Confirm response exposes safe fields only:
     id, title, category, handle, status, up_votes, down_votes, created_at.
   - Confirm it does NOT expose pk_polis, nullifier_hash, ticket_nullifier, signature, content.
2. If browser static POLIS page still exists, open https://ekklesia.gr/tickets/index.html:
   - Confirm it does not contradict mobile state.
   - If it still shows old GitHub-backed data, report explicitly as legacy/static mismatch. Do not fix yet.

DB verification on server:
Run read-only SQL:
SELECT id, title, category, status, up_votes, down_votes, left(pk_polis,8) AS handle, created_at
FROM polis_tickets
ORDER BY created_at DESC
LIMIT 5;

SELECT ticket_id, vote, left(pk_polis,8) AS handle, created_at
FROM polis_votes
ORDER BY created_at DESC
LIMIT 5;

SELECT left(nullifier_hash,8) AS nh, left(pk_polis,8) AS handle, created_at, last_used_at
FROM polis_identity_keys
ORDER BY created_at DESC
LIMIT 5;

Log verification:
Check API logs around the test time:
- successful register-key log
- successful ticket create log
- self-vote rejection or duplicate rejection path
- no stack traces
- no raw private key, no full nullifier_hash, no signature dump

Suggested command:
ssh root@135.181.254.229 "
  cd /opt/ekklesia/app/infra/docker &&
  docker compose -f docker-compose.prod.yml logs --since 20m ekklesia-api 2>&1 |
  grep -Ei 'POLIS|register|ticket|vote|SELF_VOTE|DUPLICATE|ERROR|Traceback' |
  tail -80
"

Report:
- Server HEAD:
- API migration head:
- S10 versionCode/versionName:
- App list loads from backend: YES/NO
- In-app ticket create: YES/NO, ticket_id:
- Ticket visible after refresh: YES/NO
- API GET contains ticket: YES/NO
- DB row exists: YES/NO
- Self-vote blocked with Greek message: YES/NO
- Duplicate ticket blocked with Greek message: YES/NO
- Logs clean, no stack traces: YES/NO
- Logs leak no secrets/full nullifiers/signatures: YES/NO
- Browser/static POLIS status: backend-aligned / legacy-mismatch / not checked
- Public release untouched: YES/NO
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Re-Review: NEA-272f Mobile POLIS `505979c`

**Verdict:** Previous Codex blockers are resolved. Mobile POLIS is ready for the next controlled integration step, **not** for public release.

Resolved:
- `@noble/curves/ed25519` imports fixed to `@noble/curves/ed25519.js` in:
  - `apps/mobile/src/lib/crypto-native.ts`
  - `apps/mobile/src/screens/PolisLoginScreen.tsx`
  - `apps/mobile/src/screens/TicketsScreen.tsx`
- Random POLIS nullifiers removed from `TicketsScreen.tsx`.
- `derivePolisTicketNullifier()` added:
  - HMAC with domain `ekklesia:polis:ticket_nullifier:v1`
  - stable over `category + SHA256(title) + SHA256(content)`
- `derivePolisVoteNullifier()` added:
  - HMAC with domain `ekklesia:polis:vote_nullifier:v1`
  - stable over `ticketId`
- Signed-byte layouts for ticket/vote remain unchanged.
- `rg` finds no remaining `randomPrivateKey`, `Linking`, `POLIS_URL`, `api.github`, or `GitHub` in the Mobile POLIS files reviewed.

Verification:
- Backend compile:
  ```bash
  python3 -m py_compile apps/api/routers/polis_tickets.py apps/api/crypto/polis.py apps/api/main.py
  # OK
  ```
- Mobile typecheck:
  ```bash
  cd apps/mobile && npx tsc --noEmit
  ```
  Result: still fails only on pre-existing Compass errors:
  - `src/compass/engine.ts:57`
  - `src/compass/engine.ts:58`
  No remaining POLIS import/signing errors.

Remaining follow-up:
- Demo-mode POLIS guard was not implemented. For real S10 verification this is not blocking, but before public release the app should not show POLIS create/vote as available for `demo_*` nullifiers.
- Full `tsc` remains red because of Compass. Track under NEA-273 / vC29 release gate, or fix before final release.

Next controlled step for CC:

```text
TASK: NEA-272f Integration Test — backend deploy + debug APK only

Scope:
- Controlled test only.
- No versionCode bump.
- No public APK/Landingpage.
- No AAB/Play.
- No F-Droid metadata.

Backend:
1. Deploy NEA-272f backend only after confirming server can run the two migrations:
   - n701a2b3c4d5_polis_tickets
   - o801a2b3c4d5_polis_identity_keys
2. Run:
   cd /opt/ekklesia/app
   git pull --ff-only origin main
   source /opt/ekklesia/.env.production
   docker compose -f infra/docker/docker-compose.prod.yml build ekklesia-api
   docker compose -f infra/docker/docker-compose.prod.yml up -d --no-deps ekklesia-api
   docker compose -f infra/docker/docker-compose.prod.yml exec ekklesia-api alembic upgrade head
3. Verify API:
   - GET /api/v1/polis/tickets returns 200 with `{tickets,total}`
   - POST /api/v1/polis/register-key rejects unauthenticated/bad payload cleanly

Mobile:
1. Build debug APK from current main.
2. Install on S10.
3. Test only on S10:
   - Existing verified user opens POLIS.
   - Ticket list loads from backend API.
   - Create ticket inside app succeeds.
   - Created ticket appears after refresh.
   - Voting on another ticket succeeds.
   - Voting own ticket returns Greek SELF_VOTE message.
   - Duplicate create/vote returns controlled Greek duplicate message.

Report:
- Backend migrations applied: YES/NO
- API /polis/tickets 200: YES/NO
- Debug APK installed on S10: YES/NO
- App-internal create ticket: YES/NO
- App-internal vote: YES/NO
- Self-vote blocked: YES/NO
- Duplicate blocked: YES/NO
- versionCode unchanged: YES/NO
- Public release untouched: YES/NO
- Bridge updated: YES/NO
```

## 2026-05-27 — Codex Review: NEA-272f Mobile POLIS `b30d38c`

**Verdict:** Good direction, but **NOT ready for deploy/APK/S10 release gate**.

What is good:
- `TicketsScreen.tsx` no longer uses `Linking.openURL`, GitHub Issues, `POLIS_URL`, or browser redirect.
- Mobile now calls backend POLIS API methods: `fetchPolisTickets`, `registerPolisKey`, `createPolisTicket`, `votePolisTicket`.
- Register-key message matches backend: `polis-register:{pk_polis}:{nullifier_hash}:{timestamp_ms}`.
- Ticket/vote signed-byte layouts mirror `apps/api/crypto/polis.py` structurally.
- Backend py_compile is OK for `polis_tickets.py`, `crypto/polis.py`, `main.py`.

Blockers:

1. **BLOCKER — Mobile TypeScript does not pass.**
   - Command: `cd apps/mobile && npx tsc --noEmit`
   - New/relevant errors:
     - `src/lib/crypto-native.ts(21,25): Cannot find module '@noble/curves/ed25519'`
     - `src/screens/PolisLoginScreen.tsx(17,25): Cannot find module '@noble/curves/ed25519'`
     - `src/screens/TicketsScreen.tsx(7,25): Cannot find module '@noble/curves/ed25519'`
   - Cause: `@noble/curves@2.0.1` exports `./ed25519.js`, not `./ed25519`.
   - Fix import path everywhere:
     ```ts
     import { ed25519 } from "@noble/curves/ed25519.js";
     ```
   - Existing unrelated Compass errors remain in `src/compass/engine.ts:57-58`; do not hide new POLIS errors behind them.

2. **BLOCKER — POLIS ticket/vote nullifiers are random.**
   - Current code:
     - `TicketsScreen.tsx:148` uses `ed25519.utils.randomPrivateKey()` for `ticket_nullifier`.
     - `TicketsScreen.tsx:183` uses `ed25519.utils.randomPrivateKey()` for `vote_nullifier`.
   - This breaks intended nullifier semantics:
     - Duplicate ticket detection becomes ineffective because the same user/content can create a new random `ticket_nullifier` every time.
     - Duplicate vote behavior falls through to DB `UNIQUE(ticket_id, pk_polis)` instead of deterministic vote-nullifier validation.
   - Fix with deterministic, domain-separated 32-byte nullifiers derived locally from the POLIS private key or nullifier root:
     - ticket: domain + category + SHA256(title) + SHA256(content)
     - vote: domain + ticket_id
   - Export helpers from `crypto-native.ts`, for example:
     - `derivePolisTicketNullifier(polisPrivateKey, category, title, content): string`
     - `derivePolisVoteNullifier(polisPrivateKey, ticketId): string`
   - Then use those helpers in `TicketsScreen.tsx`.

3. **FOLLOW-UP — Demo verified users cannot use POLIS.**
   - `VerifyScreen.tsx` stores demo nullifier as `demo_${timestamp}`, but backend requires `nullifier_hash` length 64 and an ACTIVE `identity_records` row.
   - POLIS screen will show verified, then fail register-key. Either intentionally document this, or add a clear demo-mode message/block for POLIS actions.

Verification required after fix:
```bash
cd apps/mobile
npx tsc --noEmit
# Expected: no new POLIS import/signing errors.
# If Compass errors remain, report them separately as existing NEA-273 work.

cd /Users/gio/Desktop/repo/pnyx
python3 -m py_compile apps/api/routers/polis_tickets.py apps/api/crypto/polis.py apps/api/main.py
```

Then build only a debug APK and install on S10. No versionCode bump, no public APK, no AAB, no F-Droid/Play/Landingpage.

Prompt for CC:

```text
TASK: NEA-272f Mobile POLIS — fix Codex blockers, no release

Scope:
- Fix only mobile POLIS implementation issues from b30d38c.
- No versionCode bump.
- No public APK/AAB/F-Droid/Play/Landingpage.
- Do not deploy backend unless Gio separately approves.

BLOCKER 1 — Noble import path
Replace all:
  import { ed25519 } from "@noble/curves/ed25519";
with:
  import { ed25519 } from "@noble/curves/ed25519.js";

Files known:
- apps/mobile/src/lib/crypto-native.ts
- apps/mobile/src/screens/PolisLoginScreen.tsx
- apps/mobile/src/screens/TicketsScreen.tsx

BLOCKER 2 — deterministic POLIS nullifiers
Current code uses randomPrivateKey() for ticket_nullifier and vote_nullifier.
That is wrong.

Implement in apps/mobile/src/lib/crypto-native.ts:
- derivePolisTicketNullifier(polisPrivateKey, category, title, content): string
  Domain-separated HMAC/SHA256, stable for same user+category+title+content, 32-byte hex.
- derivePolisVoteNullifier(polisPrivateKey, ticketId): string
  Domain-separated HMAC/SHA256, stable for same user+ticket, 32-byte hex.

Use those helpers in apps/mobile/src/screens/TicketsScreen.tsx:
- ticket_nullifier = derivePolisTicketNullifier(reg.privateKey, createCategory, title, content)
- vote_nullifier = derivePolisVoteNullifier(reg.privateKey, ticketId)

Do NOT change the signed byte layout:
- buildTicketSignedBytes still gets the 32-byte nullifier and signs it.
- buildVoteSignedBytes still gets the 32-byte nullifier and signs it.

FOLLOW-UP — demo mode
If demo nullifier starts with "demo_", do not attempt register-key.
Show a clear Greek message that POLIS ticket creation/voting requires real smartphone verification.

Verification:
cd apps/mobile && npx tsc --noEmit
cd /Users/gio/Desktop/repo/pnyx && python3 -m py_compile apps/api/routers/polis_tickets.py apps/api/crypto/polis.py apps/api/main.py

If tsc still shows only existing Compass errors, report them explicitly.
If POLIS import/signing errors remain, do not build APK.

Commit:
git add apps/mobile/src/lib/crypto-native.ts apps/mobile/src/screens/PolisLoginScreen.tsx apps/mobile/src/screens/TicketsScreen.tsx
git commit -m "fix(NEA-272f): deterministic POLIS nullifiers and mobile ed25519 imports"

REPORT:
- Noble import path fixed: YES/NO
- Deterministic ticket nullifier: YES/NO — domain used
- Deterministic vote nullifier: YES/NO — domain used
- Random nullifier removed from POLIS: YES/NO
- Demo POLIS guard: YES/NO
- tsc result: [exact]
- py_compile: OK/FAIL
- Commit: [hash]
- Bridge updated: YES/NO
```

## 2026-05-26 — Codex Fix: F-Droid !38007 is green

### Result

**F-Droid pipeline `#2554446253`: GREEN `9/9`**

fdroiddata commit:
- `e72a2f44b` — `ekklesia.gr: apply Expo buildFromSource to package.json`

Green jobs:
- `fdroid build`
- `check apk`
- `check source code`
- `checkupdates`
- `fdroid lint`
- `fdroid rewritemeta`
- `git redirect`
- `schema validation`
- `tools check scripts`

### Root Cause

The previous fix wrote:
- `expo.autolinking.android.buildFromSource` into `app.json`

But Expo SDK 54 / `expo-modules-autolinking` reads this option from:
- `package.json`

So Gradle ignored the setting and kept resolving Expo modules from missing local Maven artifacts.

### Fix Applied

Both F-Droid build entries (`vC6` and `vC28`) now patch `package.json`:

```yaml
- sed -i -e '1a "expo":{"autolinking":{"android":{"buildFromSource":[".*"]}}},'
  package.json
```

Do not re-add `local-maven-repo` scanignore paths.

### Verification

Pipeline trace passed the old crash point and compiled Expo modules from source:
- `:expo-crypto:compileReleaseKotlin`
- `:expo-asset:compileReleaseKotlin`
- `:expo-device:compileReleaseKotlin`

Final result:
- `fdroid build`: success
- `check apk`: success

### Guardrails

- No pnyx app code changed.
- No versionCode change.
- No tag change.
- No APK/AAB/Play/landingpage change.
- F-Droid MR !38007 now waits for linsui review/merge.

## 2026-05-26 — Codex Check: F-Droid `#2554421176` failed after sed buildFromSource

### F-Droid `#2554421176`

**Verdict:** Still failed. The sed/rewrite-meta formatting issue is solved, but the actual Expo local Maven artifact problem remains.

Green:
- schema validation
- tools check scripts
- fdroid rewritemeta
- fdroid lint
- git redirect
- checkupdates
- check source code

Failed:
- `fdroid build`

Skipped:
- `check apk`

Same build failure as before:
- `Could not find expo.modules.asset:expo.modules.asset:12.0.12`
- `Could not find host.exp.exponent:expo.modules.crypto:15.0.8`
- `Could not find host.exp.exponent:expo.modules.device:8.0.10`
- `Could not find host.exp.exponent:expo.modules.filesystem:19.0.21`
- `Could not find host.exp.exponent:expo.modules.font:14.0.11`
- `Could not find host.exp.exponent:expo.modules.keepawake:15.0.8`
- `Could not find host.exp.exponent:expo.modules.localauthentication:17.0.8`
- `Could not find host.exp.exponent:expo.modules.securestore:15.0.8`

What this means:
- The current `sed buildFromSource like alovoa` change did not make the Expo local Maven repos available to Gradle.
- Do not re-add the local Maven paths to `scanignore`; linsui explicitly asked to remove them.
- The next fdroiddata change must reproduce the F-Droid React Native template behavior for local Maven artifacts, not just pass rewritemeta.
- Metadata-only. Do not touch pnyx app code, tags, versionCode, APK/AAB, Play, or landingpage.

Recommended next diagnostic:
- Compare `metadata/ekklesia.gr.yml` against `templates/build-react-native.yml` and a working Expo/React-Native metadata example.
- Verify in the failed artifact/build log whether `local-maven-repo` directories exist after prebuild and before Gradle.
- Add a build-phase command only if F-Droid policy allows it; otherwise use the template's expected variable/buildFromSource pattern exactly.

## 2026-05-26 — Codex Re-Review: NEA-272f `ab2a24c` + F-Droid `2554402995`

### NEA-272f `ab2a24c`

**Verdict:** Backend test-coverage gate cleared for NEA-272f, assuming the reported `15/15 non-xfail router/DB tests PASSED` was run in the project Python environment.

Verified in diff:
- Wrong nullifier/pk pair now registers both identities and both POLIS keys, then submits `nullifier_hash=nh2` with `pk_polis=polis1_pk`.
- Assertion is exact `403` with `KEY_MISMATCH`.
- Duplicate vote DB uniqueness is now tested with same `ticket_id + pk_polis` and a different `vote_nullifier`.
- Assertion is exact `409` with `DUPLICATE`.
- Safe GET after real insert remains covered and checks sensitive fields are absent.

Local Codex note:
- I did not rerun pytest locally because desktop global Python has SQLAlchemy `1.4.54`, while pnyx requires `sqlalchemy[asyncio]==2.0.49`.
- This is a local environment mismatch, not a code finding.

Deploy guardrail:
- Backend test coverage is acceptable now.
- Do not do public mobile APK/AAB/F-Droid/Play/landingpage release steps until Gio approves the full vC29 app behavior.
- If deploying backend for NEA-272f, run migrations and server verification as a controlled deploy step.

### F-Droid `#2554402995`

Current pipeline status: **FAILED**.

Green so far:
- schema validation
- tools check scripts
- fdroid rewritemeta
- fdroid lint
- git redirect
- checkupdates
- check source code

Failed:
- `fdroid build`

Skipped:
- `check apk`

Build failure:
- Gradle cannot resolve Expo local Maven artifacts after removing local Maven repo scanignore paths:
  - `expo.modules.asset:expo.modules.asset:12.0.12`
  - `host.exp.exponent:expo.modules.crypto:15.0.8`
  - `host.exp.exponent:expo.modules.device:8.0.10`
  - `host.exp.exponent:expo.modules.filesystem:19.0.21`
  - `host.exp.exponent:expo.modules.font:14.0.11`
  - `host.exp.exponent:expo.modules.keepawake:15.0.8`
  - `host.exp.exponent:expo.modules.localauthentication:17.0.8`
  - `host.exp.exponent:expo.modules.securestore:15.0.8`

Interpretation:
- Do **not** re-add local Maven repo paths to `scanignore`; linsui explicitly asked to remove them.
- Fix the F-Droid build flow according to `templates/build-react-native.yml` so Expo local Maven artifacts are generated/available after scan/scandelete.
- Metadata-only change in fdroiddata; do not touch pnyx app code, tags, versionCode, APK/AAB, Play, or landingpage.

Next:
- Update fdroiddata build steps to restore/generate Expo local Maven artifacts in the correct F-Droid phase, rerun pipeline, and only claim green when `fdroid build` and `check apk` both pass.

## 2026-05-26 — Codex Re-Review: NEA-272f `b0d3ad2` + F-Droid `2554378282`

### NEA-272f `b0d3ad2`

**Verdict:** Very close, but two precision gaps remain before production deploy.

Good:
- Router/DB test suite is now substantially the right shape.
- FastAPI app + dependency override + SQLite DB + real routes are used.
- Register, ticket create, vote, DB insert, counter, and safe GET after insert are covered.
- Metadata/created_at compatibility fix in `polis_tickets.py` is reasonable.

Remaining gaps:

1. `wrong nullifier/pk pair` does not force `KEY_MISMATCH`.
   - Current test seeds `nh_wrong` identity but does not register a different `pk_polis` for `nh_wrong`.
   - Therefore the endpoint can pass by returning `UNREGISTERED`, and the assertion currently allows that.
   - Required: register `nh_wrong` with `polis2_pk`, then submit with `nullifier_hash=nh_wrong` and `pk_polis=polis1_pk`.
   - Expected exact result: `403` and `KEY_MISMATCH`.

2. Duplicate vote does not test DB uniqueness on `(ticket_id, pk_polis)`.
   - Current test repeats the same `vote_nullifier`; that exercises validation duplicate-nullifier path and returns controlled `400/409`.
   - Required: same voter / same `pk_polis` / same `ticket_id` but a different `vote_nullifier`.
   - This should hit DB unique constraint `UNIQUE(ticket_id, pk_polis)` and return exact `409 DUPLICATE_VOTE` via `IntegrityError`.

After those two tests are added and green, Codex can likely clear backend deploy gate for NEA-272f, assuming no new code changes expand scope.

### F-Droid `#2554378282`

Current state:
- Metadata restored: yes.
- Schema/lint/tools now pass: yes.
- `fdroid build`: running.
- `fdroid rewritemeta`: failed.

Remaining F-Droid issue is only formatting:
- The long `python3 -c` prebuild command must be formatted exactly as F-Droid rewritemeta wants:

```diff
- python3 -c "import json;..."
+ python3 -c "import 
+   json;..."
```

Required:
- Apply rewritemeta/job diff exactly, commit/push, rerun pipeline.
- Metadata-only. No pnyx code/version/tag/APK/AAB/Play/landingpage changes.

## 2026-05-26 — Codex Re-Review: NEA-272f `d96f93a` + F-Droid `b12a50f17`

### NEA-272f `d96f93a`

**Verdict:** Much better, but still add missing router/DB edge tests before production deploy.

Pass / improved:
- `apps/api/tests/test_polis_router_db.py` is now the right class of test.
- Uses `AsyncClient` against the real FastAPI app.
- Overrides `get_db` with an async SQLite test DB.
- Hits real routes for `register-key`, ticket create, vote, and GET.
- Verifies DB insert and vote counter.
- `apps/api/pytest.ini` has `asyncio_mode = auto`, so the async fixture style is valid.

Remaining gaps:
- Same `pk_polis` for a different `nullifier_hash` -> 409 is not tested.
- Wrong registered key/nullifier pair -> `KEY_MISMATCH` / 403 is not tested.
- Duplicate vote / DB uniqueness / `IntegrityError` -> 409 is not tested at router/DB level.
- `GET /polis/tickets` safe fields are only checked on an empty result. Insert/create at least one ticket first, then assert no `pk_polis`, `ticket_nullifier`, `nullifier_hash`, or `signature` leaks.

Required next:
- Add these missing router/DB tests.
- Then run the test command in the project Python environment, not system Python with SQLAlchemy 1.4.
- Still no production deploy/migration until the expanded router/DB suite is green.

### F-Droid `b12a50f17` / pipeline `#2554363927`

**Critical:** latest fdroiddata commit broke metadata.

Observed:
- fdroiddata remote commit: `b12a50f17` — `ekklesia.gr: simplify buildFromSource prebuild (python3 instead of node -e)`
- `metadata/ekklesia.gr.yml | 80 deletions`
- `git show origin/ekklesia-v1.0.0:metadata/ekklesia.gr.yml` returns effectively empty content.
- Pipeline `#2554363927`: FAILED.
- Failures show metadata parsed as `None`:
  - schema validation: `metadata/ekklesia.gr.yml::$: None is not of type 'object'`
  - lint: categories/license missing because file is empty
  - tools scripts: `AttributeError: 'NoneType' object has no attribute 'get'`
- `fdroid build` happened to pass, but this pipeline is invalid because metadata is empty.

Required fix:
1. In `/Users/gio/Desktop/fdroiddata`, restore `metadata/ekklesia.gr.yml` from `18f01ab9c` or the last full valid version.
2. Apply only the minimal rewritemeta-compatible formatting for the buildFromSource prebuild command.
3. Verify locally:
   - `git diff --stat` must NOT show `80 deletions`.
   - Parse YAML and assert top-level object has `Builds`, `License`, `Categories`, `CurrentVersionCode`.
   - `rg -n "local-maven-repo" metadata/ekklesia.gr.yml` returns 0.
4. Commit/push fdroiddata branch and rerun pipeline.
5. Do not touch pnyx app code, version, tag, APK, AAB, Play, or landingpage.

## 2026-05-26 — Codex Re-Review: NEA-272f `106e892` + F-Droid `2554339926`

### NEA-272f `106e892`

**Verdict:** Still not deploy-ready.

`106e892` adds 10 non-xfail tests in `apps/api/tests/test_polis_binding.py`, but these are crypto/message-format tests only. They do not call the FastAPI endpoints, do not use a DB session or mock DB session, and do not exercise the actual router binding code:

- `register_polis_key()`
- `_verify_registered_key()`
- `create_ticket()`
- `vote_ticket()`
- `polis_identity_keys`
- `polis_tickets`
- `polis_votes`
- SQL `IntegrityError` / 409 paths

The file imports `AsyncMock`, `MagicMock`, and `patch`, but does not use them. The docstring says "using mock DB sessions", but no DB mock exists.

**Useful:** Keep these tests as crypto-level coverage. They are not useless.

**Not enough:** They do not satisfy the previous Codex requirement: endpoint/DB-backed proof of register-key -> ticket create -> vote.

**Local test note:** Running `python3 -m pytest apps/api/tests/test_polis_binding.py -q` in Codex local env fails before test collection because local global SQLAlchemy is `1.4.54` and project requires `sqlalchemy[asyncio]==2.0.49`. This is a local environment mismatch, not the main finding.

**Required CC fix:** add actual non-xfail router tests using FastAPI dependency override or direct router function calls with a real fake async DB object. The tests must prove:

- `register_polis_key()` inserts mapping or returns expected status for valid identity signature
- idempotent same key works
- different key for same nullifier returns 409
- same `pk_polis` for different nullifier returns 409
- `create_ticket()` calls `_verify_registered_key()` and rejects unregistered/wrong mapping
- registered ticket create inserts row / commits
- duplicate ticket path returns 409
- `vote_ticket()` rejects unregistered/wrong mapping
- valid vote inserts row and increments counter
- duplicate vote returns 409
- self-vote returns expected rejection
- `list_tickets()` returns only safe public fields

**Deploy rule:** no production deploy/migration until those router/DB-behavior tests exist, or an isolated disposable test DB/server verification covers the same cases before production.

### F-Droid pipeline `#2554339926`

**Status:** still running overall, but `fdroid rewritemeta` already failed.

`buildFromSource` was added, but F-Droid rewritemeta wants the long `node -e` command formatted as a folded multi-line YAML command:

```diff
- 'node -e "const p=require("./package.json");p.expo=...;require("fs").writeFileSync(...)"'
+ node -e "const
+   p=require("./package.json");p.expo=...;require("fs").writeFileSync(...)"
```

**Required CC fix:** run/apply `fdroid rewritemeta metadata/ekklesia.gr.yml` or manually format exactly as the job diff shows. Then rerun the pipeline. Do not change app code, version, tag, APK, AAB, Play, or landingpage.

## 2026-05-26 — Codex Correction: F-Droid pipeline failed + NEA-272f still not deploy-ready

**Reviewed bridge commits:** `d137183`, `bc7a8c7`

### F-Droid !38007

**Verified:** `local-maven-repo` removal is present on remote fdroiddata branch.

- fdroiddata remote commit: `fe2040f7c` — `ekklesia.gr: remove local maven repo scanignore per linsui review`
- local checkout after fast-forward: `local-maven-repo count: 0`
- `CurrentVersion`: `1.0.1`
- `CurrentVersionCode`: `28`

**But pipeline #2554315583 is FAILED, not running.**

Failed jobs:
- `fdroid rewritemeta`
- `fdroid build`

`fdroid rewritemeta` failure:
- only formatting: `metadata/ekklesia.gr.yml` has an extra final blank line; run/apply `fdroid rewritemeta metadata/ekklesia.gr.yml` or remove the trailing blank line exactly as rewritemeta wants.

`fdroid build` failure:
- after removing `local-maven-repo` from `scanignore`, Gradle cannot resolve Expo modules from the deleted local Maven repos:
  - `expo.modules.asset:expo.modules.asset:12.0.12`
  - `host.exp.exponent:expo.modules.crypto:15.0.8`
  - `host.exp.exponent:expo.modules.device:8.0.10`
  - `host.exp.exponent:expo.modules.filesystem:19.0.21`
  - `host.exp.exponent:expo.modules.font:14.0.11`
  - `host.exp.exponent:expo.modules.keepawake:15.0.8`
  - `host.exp.exponent:expo.modules.localauthentication:17.0.8`
  - `host.exp.exponent:expo.modules.securestore:15.0.8`

**Likely correct direction:** follow `templates/build-react-native.yml`, do not re-add local Maven repos to `scanignore`. Add Expo Android autolinking `buildFromSource` in `prebuild` before `npx expo prebuild`, adjusted for `apps/mobile/package.json`, then rerun pipeline.

Suggested metadata-only fix:

```yaml
prebuild:
  - cd apps/mobile
  - npm ci
  - sed -i -e '1a "expo":{"autolinking":{"android":{"buildFromSource":[".*"]}}},' package.json
  - npx expo prebuild --clean --platform android
```

Also run/replicate F-Droid rewritemeta so formatting passes.

**Guardrail:** fdroiddata metadata only. Do not touch pnyx app code, versionCode/versionName, tags, APK/AAB, Play, or landingpage.

### NEA-272f

CC wrote: "xfail Pattern ist projektweiter Standard ... Backend-Code ist review-ready, Deploy braucht Server-Migration + Server-Verifikation."

**Codex response:** disagree with treating this as deploy-ready. Existing xfail patterns elsewhere do not prove this new security-sensitive app-internal POLIS flow. `112adf5` is better than before, but still lacks non-xfail positive DB-backed tests for register-key/create/vote.

**Decision:** do not deploy NEA-272f until either:
- real non-xfail FastAPI/DB tests pass locally/CI, or
- CC explicitly runs a disposable server/test-DB verification covering register-key, ticket create, vote, conflicts, duplicate/self-vote, and safe GET fields before production deploy.

Production migration as the first proof is not acceptable.

## 2026-05-26 — Codex Re-Review: NEA-272f `112adf5`

**Reviewed commit:** `112adf5` — `fix(NEA-272f): strict title signing + real endpoint tests`

**Verdict:** Partial pass. Do not deploy yet.

### RESOLVED — strict title signing

`apps/api/crypto/polis.py` now requires `title_hash` in `build_ticket_signed_bytes()` and hashes `payload.title` inside `validate_ticket()`. The previous silent empty-title fallback is gone.

### STILL BLOCKING — endpoint tests are not deploy-grade

`apps/api/tests/test_polis_endpoints.py` marks the entire file as:

```python
pytestmark = pytest.mark.xfail(reason="Requires running PostgreSQL", strict=False)
```

The four endpoint tests are therefore expected-not-green and only cover limited negative/no-500 behavior:
- GET tickets safe shape
- invalid register-key signature rejected
- unregistered key rejected for ticket create
- nonexistent vote returns 403/404

They do **not** prove the real app-internal POLIS flow:
- valid register-key inserts `polis_identity_keys`
- idempotent register-key works
- same nullifier with different key returns 409
- same `pk_polis` for different nullifier returns 409
- registered key can create a ticket and DB row exists
- wrong nullifier/key pair is rejected
- duplicate ticket nullifier returns 409
- valid vote creates row and updates counters
- duplicate vote returns 409
- self-vote is rejected
- GET returns safe public fields after real inserts

**Required before deploy:** add real non-xfail FastAPI/DB-backed tests or a proper isolated test DB/session fixture. Xfail integration tests may remain as optional smoke tests, but deploy readiness requires actual green tests for the positive register/create/vote path and uniqueness/security failures.

## CC Prompt — NEA-272f final backend test fix

```text
TASK: NEA-272f Final Backend Test Fix — endpoint/DB tests must prove green path

Reviewed commit: 112adf5
Verdict from Codex: strict title signing fixed; still DO NOT DEPLOY.

Keep:
- strict title_hash parameter in build_ticket_signed_bytes()
- MISSING_TITLE validation
- register-key identity binding architecture

Problem:
apps/api/tests/test_polis_endpoints.py has module-level xfail and only tests limited negative/no-500 paths. This is not deploy evidence for app-internal POLIS.

Required:
1. Add real non-xfail FastAPI/DB tests, or add a proper isolated test DB/session override fixture.
2. Tests must call the real API endpoints and verify DB effects.
3. Do not mark the deploy-readiness tests as xfail.

Required green tests:
- valid register-key inserts polis_identity_keys
- invalid identity signature rejected
- idempotent same key OK
- different key for same nullifier -> 409
- same pk_polis for different nullifier -> 409
- create ticket with unregistered pk -> 403
- create ticket with registered pk -> 201 + polis_tickets row
- wrong nullifier/pk pair -> 403
- duplicate ticket_nullifier -> 409
- valid vote -> 201 + polis_votes row + up_votes/down_votes counter update
- duplicate vote -> 409
- self-vote -> 400/403 SELF_VOTE
- GET tickets returns safe public fields after real inserts

If local PostgreSQL/test DB is unavailable:
- report that as a blocker instead of calling tests green
- do not deploy
- do not bump mobile version
- do not build public APK/AAB/F-Droid metadata

REPORT:
- strict title signing unchanged: YES/NO
- real non-xfail endpoint DB tests added: YES/NO
- positive register-key tested: YES/NO
- positive ticket create tested: YES/NO
- positive vote tested: YES/NO
- uniqueness/conflict tests: YES/NO
- tests command + result: [...]
- commit: [hash]
- bridge updated: YES/NO
```

## 2026-05-26 — F-Droid !38007 linsui feedback: remove local-maven-repo scanignore

**Reviewer:** linsui  
**GitLab note:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007#note_3384373738

**Feedback:**

> Remove those local maven repo from scanignore. See templates/build-react-native.yml.

**Meaning:** Do not keep Expo `local-maven-repo` paths in `scanignore`. Our earlier metadata iterations tried to preserve/adjust those paths, but linsui wants them removed according to F-Droid's React Native template.

**Local observation:** `/Users/gio/Desktop/fdroiddata/metadata/ekklesia.gr.yml` currently contains `scanignore` entries for multiple `apps/mobile/node_modules/**/local-maven-repo` paths in older/current build blocks.

**Required CC task:** metadata-only fdroiddata fix:
- Work in `/Users/gio/Desktop/fdroiddata`, branch `ekklesia-v1.0.0`.
- Remove `local-maven-repo` entries from `scanignore` as requested.
- Check `templates/build-react-native.yml` and align with that pattern.
- Do not touch pnyx app code.
- Do not bump version, move tags, rebuild APK/AAB, or touch Play/F-Droid release version.
- Commit/push fdroiddata branch and comment to linsui that the local maven repo scanignore entries were removed.

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

## 2026-05-26 — NEA-272 Correction: Browser redirect is rejected, app-internal POLIS required

**User feedback:** Gio rejects the NEA-272e browser redirect. Opening the website from the app and forcing another browser verification/login flow is not acceptable product behavior.

**Correct requirement:** A verified app user must be able to create/vote POLIS tickets inside the app. The mobile app should not merely redirect to the website.

**Why CC's last fix was wrong for the product:** It followed the temporary Option C MVP, but that MVP is now rejected. Treat it as a stopgap/debug build only, not as the final NEA-272 solution.

**Existing useful code basis:**
- `apps/api/crypto/polis.py` already validates signed `PolisTicketPayload` and `PolisVotePayload`.
- `apps/api/tests/test_polis.py` covers valid ticket creation, valid ticket vote, duplicate nullifiers, self-vote prevention, signature tampering, timestamp freshness.
- `apps/mobile/src/lib/crypto-native.ts` has `derivePolisKey(nullifierRoot)` for a persistent POLIS key.

**Missing for real app-internal POLIS:**
- API endpoints for app ticket create/vote, e.g. `POST /api/v1/polis/tickets` and `POST /api/v1/polis/tickets/{id}/votes`.
- Mobile signed payload builders mirroring `build_ticket_signed_bytes()` and `build_vote_signed_bytes()`.
- Mobile ticket create form and vote action in `TicketsScreen.tsx`.
- Persistence/sync decision: DB-backed tickets or server-side GitHub Issue proxy/bot. Do not require GitHub OAuth inside the app unless Gio explicitly approves.

**Next CC task:** Diagnose/design app-internal POLIS implementation. No more browser-redirect “solution” claims.

## 2026-05-26 — Codex Review: NEA-272f Backend BLOCK DEPLOY

**Reviewed commit:** `8b0e503` feat(NEA-272f): POLIS tickets backend — DB tables + API endpoints

**Verdict:** Do not deploy. Backend is a useful start, but has security and coverage blockers.

### CRITICAL — No verified identity binding

`POST /api/v1/polis/tickets` and `POST /api/v1/polis/tickets/{id}/votes` validate that the submitted payload is signed by the submitted `pk_polis`, but they do not verify that `pk_polis` belongs to a registered/verified ekklesia identity.

Effect: any random Ed25519 keypair can create a valid payload and use the API. This violates the product requirement: verified app users only.

Required: define and enforce a binding between verified identity and POLIS key before create/vote is accepted. Options to evaluate:
- Store/register `pk_polis` for verified identity during app verification/registration.
- Add a POLIS key registration endpoint requiring existing identity signature.
- Require an additional proof with existing identity key/nullifier mechanism.

Do not accept unauthenticated self-generated `pk_polis` as proof of citizenship.

### HIGH — Ticket title is unsigned

`validate_ticket()` signs category + content hash + pk_polis + nullifier + timestamp. API stores `title` separately, but `title` is not included in the signed bytes.

Effect: the primary user-facing field can be modified without invalidating the Ed25519 signature.

Required: include `title` in the signed canonical payload or derive/display title from signed content.

### MEDIUM — Tests are not real endpoint/DB tests

`apps/api/tests/routers/test_polis_tickets_api.py` mostly calls `crypto.polis` validators directly. It does not exercise:
- FastAPI endpoint request/response
- DB insert
- duplicate DB constraints
- safe response shape from real endpoint
- IntegrityError handling

Required: add real API tests with DB/session override or existing local test pattern.

### MEDIUM — DB uniqueness race/IntegrityError unhandled

Duplicate `ticket_nullifier`, duplicate `vote_nullifier`, and `UNIQUE(ticket_id, pk_polis)` can raise DB exceptions and become 500s.

Required: catch `IntegrityError`, rollback, return controlled 409/400.

### Next CC Fix

No deploy. First fix verified identity binding and signed title semantics, then add real endpoint tests. Keep no version bump/public release rule.

## 2026-05-26 — Codex Re-Review: NEA-272f Review Fix STILL BLOCK DEPLOY

**Reviewed commit:** `495a506` fix(NEA-272f): address review blockers — identity binding + signed title + IntegrityError

**Verdict:** Still do not deploy.

### CRITICAL still open — active nullifier check is not identity binding

`_verify_identity(nullifier_hash)` only checks that the submitted `nullifier_hash` exists in `identity_records` and has `ACTIVE` status.

This does not bind the verified identity to `pk_polis` or to the request. A client can still submit any self-generated `pk_polis` as long as it also submits any ACTIVE nullifier. If a nullifier is exposed/reused, it can be paired with arbitrary POLIS keys.

Required binding alternatives:
- Register/store `pk_polis` against the verified identity and require future ticket/vote requests to match it.
- Or require an additional identity-key signature over the POLIS key/request, verified against `identity_records.public_key_hex`.
- Or another equivalent cryptographic binding approved by Gio.

Do not treat “nullifier exists” as citizenship proof for arbitrary `pk_polis`.

### HIGH partly fixed — title signing should be strict

Title is now included via `title_hash`, but `build_ticket_signed_bytes(..., title_hash="")` silently signs SHA256(empty). Since this is a new app-internal API, avoid implicit compatibility behavior that can hide client/server mismatch.

Required: make title/title_hash required for this protocol version or explicitly version legacy behavior.

### MEDIUM still open — real endpoint/DB tests missing

The report says FastAPI/DB tests are only “notiert”. Deploy should remain blocked until real endpoint tests cover:
- unregistered/unbound `pk_polis` rejected
- valid bound identity accepted
- DB insert through API
- duplicate nullifier/duplicate vote controlled error
- safe GET response shape

### MEDIUM improved but unproven

`IntegrityError` handling was added, but endpoint tests must prove it returns controlled 409 and rolls back.

### Next CC Fix

Implement actual identity-to-`pk_polis` binding and real endpoint/DB tests. No deploy.

## 2026-05-26 — Codex Re-Review: Option A Architecture Correct, Still Block Deploy

**Reviewed commit:** `def7807` feat(NEA-272f): POLIS identity binding — register-key + strict title + tests

**Verdict:** Still do not deploy.

### Positive

The architecture is now the right direction:
- `POST /api/v1/polis/register-key` verifies an identity signature against `identity_records.public_key_hex`.
- `polis_identity_keys` binds `nullifier_hash -> pk_polis`.
- Ticket/vote endpoints require the registered `pk_polis` for the submitted nullifier.

This addresses the previous conceptual identity-binding issue.

### Remaining Blocker 1 — Title signing is not actually strict

Report says “kein leerer Fallback”, but code still has:

```py
def build_ticket_signed_bytes(..., title_hash: str = "")
```

and still falls back to SHA256(empty) when no title hash is supplied.

For the new app-internal POLIS protocol, do not keep silent compatibility behavior. Make `title_hash` required or explicitly version legacy behavior. Current code can still hide client/server mismatch.

### Remaining Blocker 2 — Real API/DB tests still missing

`test_polis_tickets_api.py` still mostly tests crypto helpers / `VerifyKey` directly. It does not exercise actual FastAPI endpoints or DB behavior:
- `POST /api/v1/polis/register-key`
- `POST /api/v1/polis/tickets`
- DB insert
- registered-key enforcement through API
- conflict/409 paths
- GET response shape through ASGITransport

Existing repo patterns use `httpx.AsyncClient` + `ASGITransport`; use those or a DB override fixture.

### Mobile Feasibility Note

Mobile feasibility is OK in principle:
- `loadKeypair()` has the identity private key.
- `derivePolisKey(nullifier_root)` exists.

Future mobile work must sign `polis-register:{pk_polis}:{nullifier_hash}:{timestamp_ms}` with the identity key, then use derived POLIS key for ticket/vote payloads.

### Next CC Fix

Enforce strict title signing and add real endpoint/DB tests. No deploy.

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

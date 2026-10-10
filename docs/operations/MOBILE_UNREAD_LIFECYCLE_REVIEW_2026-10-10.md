# GH290 unread-count and identity-lifecycle review

2026-10-10, T-9053; source main `47a1d5af`. **Test/doc preparation only**:
no runtime change, build, upload, release, device acceptance or issue closure.
App metadata is already 1.0.34/versionCode63; this does not prove publication.

## Scope and source status

GH290 remains open. Existing #297 implements the bounded persistent unread
ledger, stable-ID deduplication, in-app fallback and F-Droid foreground feed.
#488 avoids native zero-count calls on automatic reconciliation (Android's
native zero clears tray notifications); explicit acknowledgement alone can
clear the final event. #491 adds per-category data-only local presentation,
with no second notification on replay or for its own local notification.
Server-side data-only senders remain behind `PUSH_DATA_ONLY_CATEGORIES=OFF`.
These are implemented source paths, not evidence of delivery in the installed
1.0.33 app or successful OEM support. No duplicate product fix is introduced.

Existing mapped hops: `notifications.ts -> unread-events.ts/unread-storage.ts
-> notification-badge.ts` and `BillsScreen::useFocusEffect -> loadVoteMarks /
isVerified -> tileVoteLabel`. `App.tsx` reconciles on startup/foreground rather
than blanket-clearing unread state. Settings consume that same ledger.
Architecture-map append is deferred to a separately resumed end-stack bundle.

Preference semantics are unchanged: explicit master/category `false` suppresses
delivery/counting; absent values retain the existing enabled defaults. The
settings have a master plus six category keys, not seven independent categories.
F-Droid never loads native notifications/FCM and relies on public-feed foreground
transitions; it does not promise background push delivery or a numeric launcher.

## Must-pass automated tests

`notifications-runtime.test.ts` adds seven expanded cases. Separate VM runtimes
share only the persisted storage map, not their ledger/queue/native adapters:

- Play/Direct restore a positive unread event after restart; cold-start, tap and
  delivery replays do not recount or schedule another local notification.
- Play/Direct explicitly read the final event once, preserve its tombstone
  across restart, and never issue an automatic native zero for a replay.
- A launcher returning false or rejecting cannot destroy the persisted in-app
  list; restart and later acknowledgement still work.
- F-Droid preserves unread/read tombstones across restart without loading
  native notifications/task manager or registering push tokens.

Cold-start assertions await the full consumer, not a fixed sleep. These are
runtime-wiring mocks; storage maps are not native SecureStore/process evidence.

`BillsScreen.test.ts` adds two focus/blur cases using the actual screen callback
and real `tileVoteLabel`: late A reads after blur cannot overwrite a refocused
B empty snapshot, or update the snapshot after blur without refocus. This is
cancellation coverage, not proof of an identity-bound retained screen.

## NV1/NV2: evidence and remaining gaps

NV1: persisted owner checks/serialized cleanup already exist in #502/#513 and
have tests in vote-marks, push-registration and import-account suites. The
component states are a separate boundary. BillsScreen reloads marks on focus,
but does not immediately erase an already-rendered A snapshot while B loads.
VoteScreen's mounted guard is not an identity guard; its effect depends on
billId, not owner. Actual retained-stack reachability after import/reset and
late status/submit responses still requires the device/navigation gate.
The new blur-cancellation tests do **not** close this hypothesis.

NV2: storeNullifierRoot clears marks but preserves legacy nullifier/keypair.
Its only found product caller is registerTier1; no current UI caller of that
flow was found. Root-change cleanup already has a test, so it is not duplicated.
No reachable new UI defect or severity is asserted. Reachability remains open.

## Manual smoke tests and edge cases

- Record exact artifact/version/channel, Android, launcher and permission state;
  test Samsung/One UI, Xiaomi/HyperOS and stock emulator numeric badge/fallback.
- Enabled versus disabled categories: foreground/background, OS-killed versus
  force-stopped, delivery/tap/replay; identify the right bill and acknowledgement.
- Play/Direct/F-Droid separately, including offline storage errors and unsupported
  launcher. Count/list retention is distinct from real provider delivery.
- Import/reset A->B while Bills and Vote screens are retained and requests are
  in flight; ensure no A display after transition and no stale selection/status.
  Check root-only registration reachability before treating NV2 as a product bug.

## Regression risks / not in scope

Tests must not simulate away callback cleanup, storage failures or opted-out
preferences. The fake focus lifecycle cannot certify React Navigation behavior.
No identity/voting/ZK changes, new signed reads, telemetry, backend calls,
server flag changes, store upload, device operation or app-version announcement.
Landing/README require no release update: this PR changes no delivered behavior.

## Done criteria and execution status

**Vitest and TypeScript NOT RUN locally**: the coordinator explicitly assigned
local Mobile execution to gio-dd. `git diff --check` is the only local validation
receipt. Required: focused files, full Mobile test suite and `tsc --noEmit`,
exact-head CI, gio-dd cross-review and head-bound merge. Native/device/release
gates remain unchecked even after tests/merge. GH290 remains open.

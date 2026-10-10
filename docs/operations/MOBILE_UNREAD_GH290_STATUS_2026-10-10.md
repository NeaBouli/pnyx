# GH290 Mobile preparation: source status and remaining gates

2026-10-10, T-9054. Baseline main `4a7f6577` includes the already-merged
#540. This is a test/documentation follow-up, not a new implementation,
build, release, device receipt or permission to enable a server flag.

## Scope

Existing mapped notification hop (MAP.md, Hop 12): background task in
`notifications.ts` -> `unread-events.ts::ingest` ->
`unread-storage.ts` / `notification-preferences.ts::isNotificationEnabled`
-> local presentation and `notification-badge.ts::set`.

The existing code already applies the persisted `push_master` setting. The
remaining coverage gap is its combination with a fresh runtime, an enabled
individual category and a data-only event; this is not a newly reported
product failure. No runtime file is changed.

## Implemented source and offline evidence

- [#297](https://github.com/NeaBouli/pnyx/pull/297): bounded persistent ledger,
  canonical event IDs, replay deduplication, explicit acknowledgements, in-app
  fallback and F-Droid foreground public-feed ingestion.
- [#488](https://github.com/NeaBouli/pnyx/pull/488): automatic zero-count
  reconciliation skips the native zero call; an explicit last read may clear
  the tray. Positive counts are reconciled from the ledger.
- [#491](https://github.com/NeaBouli/pnyx/pull/491): data-only local presentation
  occurs only for a newly accepted, category-enabled ledger event. Delivery
  replays and locally generated notifications do not schedule it twice.
- [#540](https://github.com/NeaBouli/pnyx/pull/540): merged 2026-10-10 08:12:36Z,
  `4a7f6577118432a2e0b208d2093e5063e0358214`; final candidate
  `b1a0e5df057900521be4f63c59fe059be223c8ba`. gio-dd corrected the chunk-manifest
  test assertion and reports 443 Mobile tests, clean TypeScript and green CI.
  Codex did not rerun or re-review that already accepted PR.

The settings have a master plus six category keys. Explicit `false` suppresses
the corresponding event; unset preferences keep the existing enabled default.
This follow-up does not change the default or introduce a new opt-in policy.

## Must-pass automated tests

`apps/mobile/src/lib/notifications-runtime.test.ts` adds two expanded
Play/Direct cases using the actual runtime source and existing VM helper:

1. Persist `push_master=false` with `push_vote_24h=true`, await full startup,
   then deliver a stable-ID `vote_24h` event with `local_display=1`.
2. Require no unread event/count, local schedule or automatic native zero call.
3. Create another runtime sharing only the storage map; the persisted master
   opt-out still suppresses the same delivery.
4. Explicitly enable the master and redeliver that payload: exactly one unread
   event and local notification, with an absolute badge count of one.
5. Replay again: no duplicate event or second local schedule.

Separate instances do not share ledger/queue/native state. The test awaits
startup and background processing; it does not use arbitrary sleeps.

## Manual smoke tests

Still required for the actual release candidate: Play/Direct/F-Droid channels,
Samsung/One UI, Xiaomi/HyperOS and stock emulator; permission and launcher
support; real foreground/background/killed delivery; correct bill on tap;
read/list/badge acknowledgement; persisted preference changes after restart.
Do not equate an OS-killed process with force-stop behavior.

F-Droid uses foreground public-feed transitions and the in-app unread list.
It does not use FCM or promise background pushes or numeric launcher badges.

## Edge cases and regression risks

Suppressed events are not read tombstones: later enabled redelivery may be
accepted once. Replays after acceptance must deduplicate. Mock storage and
native adapters cannot establish real SecureStore persistence, OEM delivery,
tray behavior or navigation after identity replacement.

## Not in scope

GH290 remains open. NV1/NV2, retained-screen identity reachability, S10/device
gates and #298 residual font/tap checks remain open. Server data-only producers
stay behind `PUSH_DATA_ONLY_CATEGORIES=OFF`; enabling requires the documented
device/provider evidence and separate Gio approval. No build, store upload,
app/version announcement, deploy, payment, secret access or flag switch.
Public Landing/README release claims are unchanged. Architecture changes are
reserved for the following bundled documentation task (f).

## Done criteria and execution status

New focused/full Mobile Vitest and TypeScript checks are assigned to gio-dd;
**NOT RUN locally by Codex**. `git diff --check` is only a static patch check,
not execution evidence. Required before merge: focused runtime suite, full
Mobile tests, `npm run typecheck`, cross-review, fully green exact-head CI and
head-bound merge. Device/provider/publication checks remain open after merge.

The GH290 issue receives a source-status comment, not an issue close or a
device-acceptance checkbox update. The reactivated work-stack automation
continues with the bundled status/architecture task, not a duplicate #540.

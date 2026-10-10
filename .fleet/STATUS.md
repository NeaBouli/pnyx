# Status snapshot — 2026-10-10 09:00 UTC — T-9055

Documentation snapshot, not live verification or deployment permission.
Private Bridge/action history is intentionally not published here.

## Source and work state

- Main snapshot: `4a7f6577118432a2e0b208d2093e5063e0358214` (#540).
- #528–#540 source receipts are consolidated in
  [the architecture map](../docs/architecture/MAP.md).
  #530 was CLOSED without merge, superseded by #531; #532 only records earlier
  diagram rendering. Do not count #530 or rendering as a runtime deployment.
- #540 is already merged; owner reports 443 Mobile tests, clean TypeScript and
  green CI after correcting a chunk-manifest assertion. No second review/fix.
- Later test-only [#541](https://github.com/NeaBouli/pnyx/pull/541): the latest
  owner Bridge receipt records merge `e1d1c767`, 445 local Mobile tests, clean
  TypeScript and green CI. No duplicate review, fix, build or release here.
- Gio reactivated the authorized stack at about 08:45 UTC. Work-stack automation
  is ACTIVE; monitoring and bilateral communication are unchanged.

## Production versus undeployed source

- Owner-reported, previously live-verified API/Web production: `550549c7`.
  This documentation task performs no independent production request.
- Merged but not deployed at this snapshot: #515, #516 (Alembic
  `y801a2b3c4d5`), #519, #523, #526, #528, #533–#536 and #539. Test/CI/docs-only
  merges are not application runtime releases.
- Source app metadata 1.0.34/versionCode63 is preparation, not proof of a build,
  upload or publication. Previously published 1.0.33/vC62 release state is not
  changed or reverified here.

## Open gates

- Gio: follow-up deployment (including backup before migration), server cleanup,
  and #517 wording; none is executed by this task.
- `PUSH_DATA_ONLY_CATEGORIES` stays OFF; `PAYMENTS_INTAKE_GATE` stays closed.
- v1.0.34: S10/One UI, NV1/NV2 identity/retained-navigation reachability,
  #298 residual large-font/tap/split-screen acceptance, GH290 OEM/provider/
  correct-bill/read/badge/release evidence. #315 requires its device gate.
- F-Droid: foreground public-feed/in-app unread fallback; no FCM or promise of
  background push or numeric launcher badges. No store action.

## Next

This docs-only bundle needs local checks, cross-review and green exact-head CI
before gio-dd's head-bound merge. Then choose the oldest useful TODO/BACKLOG/
issue without a Gio/device/v2 gate. No duplicate #541 workflow or product build.

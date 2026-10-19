# Account deletion — implementation plan (DRAFT)

T-9155 / #634 · 2026-10-20 · technical owner: Gio · branch `agent/claude/T-9155`.
This document proposes implementation slices; it activates no endpoint, migration or policy.

**Decided 17.10.2026:** ADR-008 option B: move accepted contributions into shared aggregate counters, delete identity/opinion rows, and retain temporary scoped spent markers against repeat contributions after re-registration. Every voting/action epoch lasts **≤180 days**; every backup copy has a **≤6-calendar-month** lifetime. Build B **after ADR-007 S5** (keyed store). Proposed details below remain subject to owner acceptance. **RECHTLICH-PRÜFEN:** all GDPR, erasure, anonymity and retention/legal-basis claims require legal review; technical acceptance does not establish compliance.

Source baseline (local Git objects, no fetch):

- ADR-008: `git show origin/agent/claude/T-9131:docs/adr/ADR-008-account-deletion.md` at `292e4613bc08`.
- ADR-007 and ADR-007a: `git show origin/agent/claude/T-9123:docs/adr/ADR-007-ballot-secrecy.md` and `git show origin/agent/claude/T-9123:docs/adr/ADR-007a-keyed-ballot-store-contract.md` at `a79af04d4d80`.
- Checkout `84c2577efbb4`: [schema](../../apps/api/models.py), [DB roles](DB_ROLES_RUNBOOK.md), [backup encryption](BACKUP_ENCRYPTION_RUNBOOK.md), [synthetic restore drill](SYNTHETIC_BACKUP_RESTORE_DRILL.md), [backup script](../../scripts/backup-offsite.sh), [current delete page](../wiki/delete-account.html). These describe source, not verified production state.

## 1. Prerequisites and order

1. **Before S5:** inventory schema, writers/readers, integrations and backup copies; agree contracts, decisions, draft EL/EN copy and rehearsal fixtures. Independent S4/backup preparation follows existing runbooks/gates. No B rollout before S5; existing erasure requests need an owner-run process (**RECHTLICH-PRÜFEN**).
2. **Foundations → S5:** EVA-001 current-key proof, rotation and possession-verified recovery; ADR-006 D2 v3 enrollment/random anchors, D3 replay protection, D4 legacy continuity and D5 oracle removal. S5 must cover every opinion store, QR, POLIS bridge, survey/history disposition, signed reads and key recovery under ADR-007a. Unmatched legacy identities stay pending; no raw-anchor writers remain.
3. **After S5 acceptance:** build PR1–PR3 disabled, complete PR4–PR7, then activate. S7 protected CPLM batch is selected, but bill counters cannot reproduce its nonlinear per-voter formula: settle the deletion-compatible metric before transfers.
4. **Release gate:** irreversible epochs across parliamentary/OPEN_END consensus, municipal, relevance, evaluations, flags and POLIS actions; resolved ZK policy; all-device cleanup; verified backups/restore; owner/legal acceptance. Ordinary/QR/ZK votes remain rejected in OPEN_END. Closed epochs never reopen; new epochs have separate counts.

## 2. PR slices and acceptance criteria

### PR1 — Epoch schema, counters and every result reader

Add `action_epochs(scope, action, epoch_id, opened_at, closes_at, state)`: ≤180-day duration, terminal CLOSED state. Approve an epoch-aware ADR-007a scope/uniqueness extension and migration preserving existing spent/revision state. Detached counters use `(scope, action, epoch_id, bucket)`: choice/tier including UNKNOWN, relevance ±1, consensus/evaluation score histograms per question, flags and POLIS up/down; nonnegative BIGINT counts/exact sums. No person/deletion/date partitions, identity geography or row pointers.

**Accept:** `total = live keyed contributions + detached contributions`; ZK counts once under approved scope conversion. Transfer latest accepted state only. All results/divergence, caches, analytics/admin/export/publication and S4 functions preserve totals, including existing flag/consensus caches. Apply shared k=10, complementary suppression and release cadence; prevent subtraction exposing detached cells. Version unsupported time-filtered/unique-person output.

### PR2 — Scoped spent store and expiry

Store only `(marker, scope, action, epoch_id, key_version, expires_at)`, restricted and transactional with deletion; uniqueness excludes key version. Derive full HMAC markers from stable D2 v3 with versioned/framed deletion bytes and independent scope/action/epoch keys outside DB/backups, separate from `K_ballot`/`K_dedupe`. No opinion, counter pointer or person-wide lookup. Possession-verified enrollment and every mutation check all required unexpired versions; random old anchors cannot recognize returning voters.

**Accept:** all ordinary/QR/action writers and cross-tier enrollment share checks; rotation preserves eligibility, unavailable keys/store fail closed. Proposed purge: within 24 hours of irreversible close; obsolete keys survive relevant backups. Fresh device/key/anchor cannot repeat a counted action; untouched actions/new epochs remain usable. **RECHTLICH-PRÜFEN:** pseudonymous markers need approved purpose, basis, access and expiry.

### PR3 — Signed deletion API and durable cleanup

`POST /api/v2/identity/delete`: current key signs versioned/domain-separated intent, identity generation, one-use challenge, timestamp (proposed ±5 minutes) and random receipt capability. Verify/discard signature in memory. Proposed limits: 5 attempts/minute per daily HMAC IP bucket, 3 authenticated starts/day per identity; retries/status exempt. Generic auth errors; replay/limiter failure closes starts. Lost keys require possession proof, not phone knowledge/HLR.

**Accept:** lock stable enrollment eligibility (including re-registration after row removal), identity, sorted scopes/ballots, then counters. One transaction rechecks authority, resolves aliases/all readable `P` versions, inserts markers, transfers counts, deletes identity/opinions and enqueues encrypted cleanup/journal work. Rollback changes nothing; capability-authenticated retries after deletion never transfer twice or affect a recreated generation. Cover evaluation children, remaining survey/CPLM data and POLIS votes/binding/authorship; capture its key before bridge removal and apply approved text removal/placeholders.

Purge QR sessions/authorizations, verification locks, **all-device** push tokens and personal caches; backfill a push-device index first. Preserve shared IP limits. Fence in-flight writers/rotation/push/SSO/POLIS. Remove ZK enrollment links, close roots/republish membership and mark opted-in scopes spent. No inferred receipt ownership: conversion/replay protection is scope-wide. Apply agreed Discourse/newsletter controls.

Return 202 pending, 200 after cleanup/durable journal acknowledgement. Capability digest holds state/24-hour expiry only; encrypted jobs hold minimum selectors and disappear on completion. No permanent identity/job map. **RECHTLICH-PRÜFEN:** distinguish active erasure, markers, journal and backup expiry.

### PR4 — App/web UX in EL and EN

Add explicit confirmation, pending/retry/completed states and receipt/expiry display. Mobile signs; web uses purpose-bound QR, “key not on this browser” notice, no key export. Explain retained totals, lost history/status/correction/authorship, temporary repeat-action blocking and backup/publication limits. Preserve capability until completion, then clear keys/roots/caches and sign out sessions.

**Accept:** reviewed EL/EN parity, accessibility, offline retry, QR expiry and lost-key recovery. Uninstall/local removal never reports server deletion. **RECHTLICH-PRÜFEN:** approve deletion/retention/privacy wording.

### PR5 — Backup retention and restore journal

Verify ≤6-calendar-month expiry across local/offsite copies, replicas, WAL, Redis RDB/AOF and temporary copies. `-mtime +30` and “30 daily/12 weekly/6 monthly” do not prove it. Encryption is prepared **inactive**: use its runbook/Gio gate and protect local plaintext. Old plaintext removal still requires seven encrypted dailies, successful restore and separate owner gate.

Separate encrypted erasure journal from ordinary backups/audit: minimum selectors/policy versions, no opinions/counter links; retain through last relevant backup expiry, proposed maximum six months +24h. Before serving a restore, isolate it, restore exact keys/schema, replay entries (transfer only source rows still present), purge sessions/push, reapply unexpired markers/current closures and reconcile counts. Repeat replay transfers nothing; missing journal/keys or uncertain eligibility keeps writes paused.

**Accept:** replay twice preserves totals, removes deleted links and grants no fresh entitlement. Repair S4 ownership/ACLs after `--no-owner --no-acl`. DDL: `ekklesia_migrator`; API: restricted DML; monitor: released definer-function output; dashboard: no DB data; backup: read-only. Review new/default grants; exclude journal selectors/keys from monitor/normal backups. **RECHTLICH-PRÜFEN:** approve retention/basis/disclosures; encryption alone is not erasure.

### PR6 — Logs and identifier-free audit

Audit daily outcome totals/policy version only: no phone, anchor/v3/P/marker, identity ID/key/IP/signature, capability, scope list, opinion or request timing. Redact bodies/URLs/telemetry; remove historical rotation identity targets; review proxy/app/error/third-party logs. Proposed residual-log cap: 30 days, earlier targeted removal and documented exceptions.

**Accept:** success/failure/retry traces and audit contain no identifiers/opinions; jobs/journal stay separate. **RECHTLICH-PRÜFEN:** approve historical-log handling/retention; redaction does not establish anonymity.

### PR7 — Delete-account page text and release

After PR1–PR6/owner gates, update `docs/wiki/delete-account.html` with reviewed EL/EN disclosures, actual expiry dates/receipt, lost-key route and forum/newsletter controls. Remove automatic-replacement/unlinkability promises. Disclose immutable ordinary aggregates and any individual ZK publications; universal aggregate-only claims require the ZK decision.

**RECHTLICH-PRÜFEN — draft core copy (expand with the disclosures above):**

> EN: Choose “Delete account” in the app and confirm with your device key. Uninstalling alone does not delete server data. Completion removes your identity and personal history from active systems; accepted contributions remain in totals and cannot be recovered or corrected. Temporary markers prevent another contribution in the same open period. Restricted backups expire within six months; deletion is reapplied before restoration goes live. Existing Arweave publications remain.
>
> EL: Επιλέξτε «Διαγραφή λογαριασμού» στην εφαρμογή και επιβεβαιώστε με το κλειδί της συσκευής σας. Η απεγκατάσταση από μόνη της δεν διαγράφει δεδομένα από τον διακομιστή. Με την ολοκλήρωση αφαιρούνται η ταυτότητα και το προσωπικό ιστορικό σας από τα ενεργά συστήματα· οι αποδεκτές συνεισφορές παραμένουν στα συγκεντρωτικά αποτελέσματα και δεν ανακτώνται ούτε διορθώνονται. Προσωρινοί δείκτες αποτρέπουν νέα συνεισφορά στην ίδια ανοιχτή περίοδο. Τα αντίγραφα ασφαλείας περιορισμένης πρόσβασης λήγουν εντός έξι μηνών· η διαγραφή εφαρμόζεται ξανά πριν τεθεί σε λειτουργία μια επαναφορά. Οι υπάρχουσες δημοσιεύσεις στο Arweave παραμένουν.

**Accept:** Gio/language/privacy review against demonstrated behavior; release endpoint flag, clients and page after restore rehearsal.

## 3. Migration and backfill

1. Inventory post-S5 catalog/SQL: `consensus_votes`, `cplm_history`, `bill_flags` lack ORM definitions today; ZK `SET NULL` leaves enrollment metadata. Resolve aliases/orphans and remaining POLIS/survey/history copies before activation.
2. Rehearse protected backup; pause action/registration writers, drain jobs. Assign legacy deadlines/close overdue scopes without resetting opening dates. Start detached counters at zero: live contributions already count. Rebuild caches from canonical totals.
3. Backfill epochs/device indexes and approved historical deletions only. Each deletion atomically transfers latest rows, writes markers, erases sources and queues cleanup/journal. Bounded resumable checkpoints contain run/cursor/versions/aggregate progress only. Rerun twice; compare every bucket and approved feature changes.
4. Switch all readers/writers at one fenced schema epoch; validate paused, then enable. Remove staging/mappings. Rollback requires counters/keyed/journal-aware code or paused writes; never revive legacy writers/eligibility. Reapply journal before reopening restored state.

## 4. Risks and implementation tests

These are acceptance tests for later implementation PRs; this documentation change needs no test run.

- **Race/retry:** delete versus ordinary/QR cast/correction/consensus, rotation, re-registration, POLIS/push/ZK; simultaneous deletes, lost responses, commit/journal crashes and Redis/job failure. Exactly one transfer/latest choice, no surviving authority.
- **Counts:** fixtures for every writer, including QR vote/consensus and retired CPLM paths. Compare choices/tier/UNKNOWN, relevance, score sums/counts/histograms per question, flags, municipal/POLIS, divergence/caches/readers/exports/snapshots across deletion/retry/migration/restore. Explicitly accept versioned CPLM/time-series changes.
- **Eligibility/expiry:** same number/fresh key/anchor, legacy aliases, cross-tier/key rotation; usable new scopes; 180-day/close/+24h boundaries; no reopened epochs; missing keys/store fails closed.
- **Auth/UX:** forged/revoked/stale/wrong-generation requests, challenge replay, quota races, expired receipts, lost keys and EL/EN interruptions. No existence leaks or premature completion.
- **Disclosure/restore:** scan stores/staging/Redis/snapshots/logs/views for bridges; verify suppression/differencing, all-device cleanup and ZK roots/replay. Replay pre/post-deletion backups twice; check ACLs, markers/closures and counts; missing recovery material blocks service.

## 5. Remaining owner decisions

| Decision / proposed owner | Required resolution before release |
| --- | --- |
| D2/D4/D5, S5 acceptance — Gio + identity/ballot owners | Legacy cutoff/alias coverage, final anchors/oracle cleanup, signed recovery and key continuity; never grant fresh eligibility to unmatched records. |
| L2/L3 — Gio + privacy/legal reviewer | **RECHTLICH-PRÜFEN:** marker basis/access, +24h purge/key policy, legacy deadlines and epoch scope contract. Duration/backup caps are decided. |
| L4 — Gio + CPLM owner | Keep protected historical snapshots; approve/version future aggregate metric and temporal/unique-person displays. S7 protected batch is selected but cannot recover deleted per-voter inputs. |
| L5/L6 — Gio + app/web/integration owners | Confirm permanent history/correction loss, lost-key and expired-receipt route; POLIS text removal/placeholders; Discourse/newsletter scope and controls (**RECHTLICH-PRÜFEN**). |
| L7 — Gio + ZK owner | Scope-wide receipt-to-counter/replay design, verifier-record retention, reserved-eligibility forfeiture and immutable-publication disclosure (**RECHTLICH-PRÜFEN**). |
| L8/L9 — Gio + operations/privacy owners | Encryption activation/key custody, evidence of enforced six-month expiry, journal selectors/basis and expiry +24h, residual-log cap/exceptions (**RECHTLICH-PRÜFEN**). |
| L10 — Gio + implementation/review owners | Assign named PR owners, accept proposed API limits/receipt lifetime, approve migration/restore/count evidence and reviewed EL/EN page; legal acceptance remains **RECHTLICH-PRÜFEN**. |

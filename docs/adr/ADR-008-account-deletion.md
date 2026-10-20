# ADR-008: Account deletion (GDPR Article 17 — RECHTLICH-PRÜFEN)

Date: 2026-10-16

Status: **Accepted in part** — decisions 2026-10-17; open: legal review, spent-marker policy, CPLM metric, deletion/recovery UX, POLIS/integrations, ZK retention, restore-journal/encryption/log policies and release acceptance.

Task: T-9131; owner: Gio. No endpoint, migration, policy activation or deployment is approved here.

Gio's direction: self-service deletion revokes the key **and deletes or irreversibly decouples the identity row**. Votes survive only as aggregate counts. **B, using counters, is accepted (2026-10-17)**, with a separate, temporary spent-marker store to prevent a second vote after re-registration. Voting periods ≤180 days and backup retention ≤6 months are decided; remaining product choices and legal review stay open (**RECHTLICH-PRÜFEN**).

## Decision record 2026-10-17

Owner: Gio (gio-1c), technical decisions under Gio standing yes. **RECHTLICH-PRÜFEN** marks all GDPR/legal statements as legal review pending; technical acceptance does not resolve them.

- **ADR-006/007:** S1–S3 done; S4 (separate DB roles) approved now, with backup and rollback. S5 (keyed vote store) + S7 (CPLM protected batch) are the next big project after EVA-001. D4/D5 remain open for a joint decision with S5.
- **ADR-008:** option B with aggregate counters, finite voting periods ≤180 days and backup retention ≤6 months accepted. Implementation after S5. Remaining L2–L10 details are identified below; legal review remains **RECHTLICH-PRÜFEN**.
- **Web key loss:** recommendation accepted: mobile app as primary key custody, QR login on web, a clear “key not on this browser” notice, no key export.

## Context and evidence

Code baseline: `4b8fe511`; references describe source, not verified production state. ADR-006/007 are absent here, so their references use local `origin/agent/claude/T-9123` at `eb72fde48836`, read with `git show` without fetching. Their proposals are dependencies, not implemented behavior.

**RECHTLICH-PRÜFEN**: Treat these records as personal/pseudonymous data while they can identify, single out or reconnect a person. A hash, public key or random replacement ID does not by itself establish anonymity.

| Table/store | Data and links present today; evidence |
|---|---|
| `identity_records` | Stable v1/v2 phone-derived anchors, public key, status/dates, Region/Municipality, region lock/source and legacy demographics. No phone/private-key column. `apps/api/models.py:50`; derivations: `packages/crypto/nullifier.py:37`, `:54`. |
| `citizen_votes` | Anchor, bill, choice, signature, optional ephemeral key/nullifier/linkage tag, precise dates and correction/original choice. Unique anchor + bill; no identity FK. `apps/api/models.py:216`. |
| `bill_relevance_votes` | Anchor + bill, relevance signal and date. `apps/api/models.py:347`. |
| `consensus_votes` | Anchor + bill, score and date; upserted per person/bill. Bill caches average/count. `apps/api/routers/voting.py:1404`, `:1411`. |
| `cplm_history` | Anchor, economic/social scores, trigger bill/type and date; personal compass reads the last 50 entries. `apps/api/routers/voting.py:1424`, `:1471`. |
| `diavgeia_votes` | Anchor + decision ADA, choice/date; unique person/decision. `apps/api/models.py:532`. |
| `politician_evaluations` | Anchor + politician/question, score and dates. `apps/api/models.py:582`. |
| `bill_flags` | Anchor + bill; insertion increments the bill's flag counter. `apps/api/routers/parliament.py:523`. |
| `polis_identity_keys` | Anchor ↔ persistent POLIS public key, registration signature and use dates. `apps/api/alembic/versions/o801a2b3c4d5_polis_identity_keys.py:18`. |
| `polis_tickets`, `polis_votes` | Public author key/handle, ticket title/content, vote, signatures, ticket/vote nullifiers and dates; tickets also hold up/down counters. `apps/api/alembic/versions/n701a2b3c4d5_polis_tickets.py:18`, `:37`; public listing: `apps/api/routers/polis_tickets.py:186`. |
| `survey_responses` | `user_hash`, demographics, answer JSON and date. Re-verification deletes rows matching the compatibility anchor; revoke does not. `apps/api/models.py:367`; `apps/api/routers/identity.py:502`. |
| ZK enrollment/locks | `zk_identity_commitments` links identity ID to commitment/scope; FK deletion only sets the ID to NULL. `zk_vote_tier_locks` holds scope + keyed anchor-derived guard. `apps/api/models.py:253`, `:300`; `apps/api/services/zk_tier_lock.py:38`. |
| ZK receipts/roots | `zk_vote_receipts` holds readable choice in `vote_commitment`, Semaphore nullifier, proof, root, times and publication IDs; no identity FK. Roots hold group metadata. `apps/api/models.py:276`, `:316`; choice counting: `apps/api/services/zk_vote_aggregation.py:128`. |
| Redis QR/locks/limits | `polis_qr:{session}` holds challenge/purpose/bill and, after authentication, anchor/public key: 300 seconds pending, 60 seconds authenticated. Verification locks include anchor/key, TTL 90 seconds. Daily HMAC IP/number rate buckets include 60-second, 300-second and 24-hour windows. `apps/api/routers/polis_qr.py:49`, `:58`, `:150`; `apps/api/routers/identity.py:58`, `:91`, `:135`, `:256`; `apps/api/rate_limit.py:22`. |
| Other Redis/integrations | Push token/platform under HMAC(anchor + device) keys, TTL 90 days; no identity-to-device index is shown, so deleting all devices needs an index/migration. CPLM cache lasts one hour; aggregate history keeps 365 entries, not 365 days. Discourse receives a stable HMAC-derived external ID and geography; SSO nonces last 300 seconds. `apps/api/services/push_registration.py:25`, `:75`; `apps/api/routers/notify.py:144`; `apps/api/services/cplm.py:24`, `:185`; `apps/api/routers/sso.py:108`, `:155`. |
| Audit/logs/backups/publication | Rotation writes identity record ID to `audit_log` and application logs. Access-query redaction exists, but does not establish erasure of historical/proxy/error logs (**RECHTLICH-PRÜFEN**). Full PostgreSQL and Redis copies go into backups. Arweave has aggregate and separate ZK receipt paths. `apps/api/routers/identity.py:1007`, `:1021`; `apps/api/main.py:25`; `scripts/backup-offsite.sh:61`; publication details below. |

`consensus_votes`, `cplm_history` and `bill_flags` use raw SQL; no model/migration declaring them was found here. Implementation must inspect their actual schema. Most anchor columns lack identity FKs: deleting the identity alone leaves opinions linkable.

Today `POST /api/v1/identity/revoke` checks whether a supplied phone derives the supplied anchor, marks the row REVOKED and clears four legacy demographic fields. It does **not** require a device signature or SMS possession proof, delete anchors/public key/geography, remove opinions/POLIS bindings, or purge Redis (`apps/api/routers/identity.py:547`). POLIS ticket/vote authorization checks its binding, so revoking the identity alone does not remove that authority (`apps/api/routers/polis_tickets.py:68`, `:300`).

V1 verification can replace an ACTIVE key; v2 requires device-key proof of possession (PoP), refuses an ACTIVE identity, and uses dual-signed rotation instead. Re-verification reuses the compatibility anchor and can reactivate revoked rows (`apps/api/routers/identity.py:374`, `:444`, `:461`, `:866`, `:979`). Uninstalling changes none of this. **RECHTLICH-PRÜFEN**: The delete page's unlinkability and automatic-replacement claims are inaccurate (`docs/wiki/delete-account.html:235`, `:245`, `:284`).

## Requirements and the deduplication conflict

- **RECHTLICH-PRÜFEN**: Erase identity links and personal opinions from active stores under Article 17 without undue delay; any retained pseudonymous marker needs a documented purpose, lawful basis and finite retention approved by the owner/privacy reviewer. Technical necessity alone is not an Article 17 exemption.
- Keep accepted aggregate counts, sums/histograms, divergence and published snapshots correct. No deletion-linked choice, receipt, small cohort or precise event time may survive in a new counter record. Apply ADR-007's proposed small-cell/differencing protection across results and exports.
- Deletion must not create another voting entitlement on a still-open scope. Serialize deletion, registration, vote/update/correction, QR, POLIS and ZK enrollment; retries must neither lose nor double-count contributions.

Erasing every recognizable trace conflicts with preserving a counted vote and recognizing a returning voter. Today's stable anchor and person/bill uniqueness provide detection (`apps/api/models.py:236`). Counters alone allow re-registration to count twice. The current check is per normalized phone, not proof of a unique human.

**Preferred compromise:** keep a scoped spent marker without opinion or counter pointer. After ADR-006 D2, compute `HMAC(K_spent_scope, "account-deletion-spent:v1:" || v3)` using its stable normalized-phone dedupe value. Store only marker, scope/action/epoch, key version and expiry, with uniqueness enforced. Use separate scope/action/epoch keys outside DB/backups, distinct from `K_ballot`/`K_dedupe`. **RECHTLICH-PRÜFEN**: Digests are non-reversible, but operators holding keys can test candidates: markers remain pseudonymous personal data.

On possession-verified re-enrollment, recompute v3 and check markers before accepting actions. Delete the identity's v3/anchor/key row; keep no person-wide bridge. Hashing a **random old anchor alone fails** because re-registration gets another anchor. Resolve legacy aliases before removal; all writers need the same check. D2 coverage is a release dependency; existing erasure requests still need an owner-run process (**RECHTLICH-PRÜFEN**).

**Alternative:** an expiring `HMAC(K_dedupe, identity-anchor)` tombstone plus a protected returning-enrollment lookup. Simpler, but it links scopes and still needs a stable lookup when anchors change. A bare tombstone is insufficient. **Zero marker retention** requires withdrawing the old contribution (A) or accepting repeat votes; it cannot meet both requirements.

Purge markers within 24 hours of **irreversible** closure; destroy obsolete keys after backup expiry. `PARLIAMENT_VOTED` reopens as `OPEN_END`, where consensus remains allowed (`apps/api/services/bill_lifecycle.py:26`; `apps/api/routers/voting.py:1381`); after PR #606 (Gio decision 16.10.2026) ordinary, QR and ZK votes are rejected in `OPEN_END`, but consensus and other actions stay open. Accepted (2026-10-17): finite voting epochs, at most 180 days from opening, also for municipal/evaluation/POLIS actions. Freeze counts and close writes before purging markers. New epochs have separate counts; old ones cannot reopen. Expiry while old counts remain writable allows duplicates. **RECHTLICH-PRÜFEN**

## Options

All options require session/token cleanup, log handling, a restore policy and honest immutable-publication wording.

| Effect | A — delete identity and opinion rows | B — delete identity; decouple opinions | C — delete/revoke keys only |
|---|---|---|---|
| Results/history | Recompute current counts, sums, relevance, flags and evaluations. Historical snapshots and Arweave still reflect the old count; label the difference. | Move accepted contributions into counters exactly once; totals/snapshots remain correct. Random per-row IDs alone still retain individual opinions and signatures/timing can reconnect them. Accepted: counters, then row removal. | Counts unchanged; anchors, opinions and cross-bill profiles remain. Fails Gio's direction and erasure objective (**RECHTLICH-PRÜFEN**). |
| Re-registration | Old vote removed, so a new vote replaces rather than adds to a retained contribution. | Temporary spent markers block another contribution to the same action/epoch. | Existing uniqueness often survives, but continuing bindings/legacy recovery remain a risk. |
| Corrections/status | Old vote and receipt gone. | Deletion ends personal status, receipts, updates and corrections; only the latest accepted choice counts. | Linked history survives; removing a key is not erasure (**RECHTLICH-PRÜFEN**). |
| CPLM | Recompute without that voter; historical aggregate snapshots stay historical. | Existing per-voter formula cannot be reconstructed from bill counters. Requires the explicit metric decision below. | Cross-bill profiles remain available to the operator. |
| POLIS authorship | Remove binding, votes and personal ticket content; recompute ticket totals. | Remove binding/author keys/signatures and individual votes, keep counters; redact/remove authored text as below. | Persistent public keys/handles and bindings survive. |
| Arweave/backups/logs | Existing publications cannot be rewritten; older backups/logs remain until handled/expired. | Same limits; destroy active links and prevent restoration from reviving them. | Same limits, plus retained live pseudonyms (**RECHTLICH-PRÜFEN**). |

## Accepted B: counters and explicit product limits

Keep scope/choice counts (including UNKNOWN/tier totals), score sum + count or histograms for consensus/evaluations, and relevance/POLIS/flag counts. Transfer the latest accepted state atomically, then delete source rows, signatures, keys, linkage tags, correction history and precise times. Keep no mapping or shared replacement person ID. All results/analytics/export/publication readers must combine live rows with shared detached counters; today they count rows (`apps/api/services/zk_vote_aggregation.py:59`, `:116`; `apps/api/routers/voting.py:1182`). Never partition counters by deletion/person/date. Small scopes or subtracting live rows can still reveal choices; aggregation alone does not prove anonymity (**RECHTLICH-PRÜFEN**). Check geography before acceptance; retain no identity geography in counters.

**CPLM:** joins consensus by anchor, groups/clamps each voter's position, then averages (`apps/api/services/cplm.py:87`). Bill counters cannot reproduce that nonlinear formula. Recommend preserving protected aggregate snapshots, deleting personal `cplm_history`, and versioning future CPLM as a documented scope-aggregate metric. Do not splice series or claim equivalent unique-voter totals. A detached per-person position contradicts this erasure scope (**RECHTLICH-PRÜFEN**). ADR-007's protected batch does not resolve this product decision.

**POLIS:** capture the key before deleting its binding; purge its votes while keeping ticket counters. Remove author key/handle, signatures and key-derived nullifiers. Recommend removing authored title/body, leaving “content removed” where needed for others' discussion; reviewed redaction needs its own policy because text can identify people (**RECHTLICH-PRÜFEN**). Re-registration cannot recover authorship; existing public copies cannot be recalled. Define separate controls for Discourse accounts/posts and independent newsletter subscriptions; blocking SSO does not erase a forum account.

**ZK:** remove enrollment links, close affected OPEN roots and republish eligible membership so old proofs stop working (`apps/api/routers/zk.py:1012`). Preserve counted results. Receipts lack identity bridges: do not create one or infer ownership from timing. Conservatively mark opted-in scopes spent; deletion forfeits reserved eligibility. Receipt-to-counter conversion must cover a whole scope and preserve replay protection. Gio must decide verifier-record retention: persistent receipts conflict with “only counts remain everywhere.” **RECHTLICH-PRÜFEN**

## Proposed self-service flow

1. **Confirm in the app.** Explain permanent identity removal, retained counts, loss of history/correction/authorship, temporary repeat-vote protection and backup/publication limits. Require a separate explicit confirmation; uninstall is not the deletion action.
2. **Authenticate.** Proposed `POST /api/v2/identity/delete`: current device key signs a domain-separated, versioned deletion intent, identity generation, one-use server challenge, timestamp and random receipt token. Require ±5-minute freshness and recheck key/status under lock. Generation binding prevents replay against a recreated identity. Reuse EVA-001 PoP validation principles, with distinct deletion bytes (`apps/api/routers/identity.py:828`, `:837`, `:866`). Lost/revoked keys need possession-verified recovery (OTP and abuse controls); phone knowledge/HLR is insufficient.
3. **Limit abuse explicitly.** Recommend 5 attempts/minute per daily HMAC IP bucket and 3 confirmed starts/day per authenticated identity; allow status/retry without spending another deletion quota. Use dedicated short-lived buckets, generic authentication errors and fail closed on unavailable replay/limit storage. Existing SlowAPI defaults are not an API-wide guarantee (`apps/api/rate_limit.py:27`).
4. **Commit once.** All writers, rotation/registration and POLIS binding changes need a common lock order. In one DB transaction disable the key, resolve aliases, establish markers, transfer counts and delete identity/opinion/binding/survey rows. Queue durable encrypted Redis/integration/restore-journal cleanup; erase the job after completion. Keep no permanent identity/job map. Rollback preserves counts; retries cannot transfer twice.
5. **Finish cleanup.** Purge QR sessions/verification locks, all indexed push tokens and personal caches; let shared IP buckets expire without resetting others' limits. All paths must reject in-flight writes, as QR already rechecks ACTIVE/current key (`apps/api/routers/polis_qr.py:315`). Process forum scope, old audit targets and searchable logs; verify unchanged counts and no live identity links. Failures stay pending. Completion requires cleanup and restore-journal acknowledgement.
6. **Respond.** Return 202 pending, 200 complete. A random capability digest stores only state/expiry for 24 hours; retries work after identity removal without retaining signature/public key. Expired receipts reveal no account existence. **RECHTLICH-PRÜFEN**: State active erasure, retained counts and marker/backup expiry dates. Clear local keys, roots and caches after completion; preserve the capability until then.
7. **Audit without identifiers.** Keep daily outcome totals/policy version; no anchor, key, record ID, IP, signature, phone, bill list, opinion or receipt token. Remove/redact existing rotation audit targets. Review historical application/proxy/error/telemetry logs: current redaction does not prove old logs anonymous (`apps/api/main.py:25`, `:301`). Recommend a 30-day maximum for residual operational logs, earlier targeted erasure where possible, and documented exceptions. **RECHTLICH-PRÜFEN**

After reinstall/re-verification, possession checks create a fresh random identity/key. No old opinions, corrections, compass or authorship return. Recomputed spent markers block already-counted actions in the same still-open epoch, including QR and cross-tier enrollment; new scopes/epochs remain usable. Key or dedupe-key rotation must preserve checks for all unexpired marker versions. A new device/root must not reset eligibility.

## Publication, backups and proposed page wording

Ordinary Arweave payloads contain bill/lifecycle metadata, vote totals and divergence (`apps/api/routers/arweave.py:41`). The separate ZK path publishes choice/proof/Semaphore-nullifier records (`apps/api/services/zk_arweave_payload.py:16`; `apps/api/services/zk_arweave_publisher.py:143`). The code supports those paths; this audit does not establish which records were actually published. **What was published stays.** A correction can be a new linked publication, never an overwrite. No future deletion event should publish identifiers or a person's changed contribution.

Backups contain full DB/Redis data (`scripts/backup-offsite.sh:61`). Local cleanup uses `-mtime +30`; remote policy says 30 daily, 12 weekly and 6 monthly copies, with enforcement outside this script (`scripts/backup-offsite.sh:121`). Six monthly copies are not proof of a maximum age. Encryption is prepared, explicitly **inactive**, with plaintext local copies and legacy offsite archives (`docs/operations/BACKUP_ENCRYPTION_RUNBOOK.md:3`, `:9`, `:36`, `:66`). Encryption restricts access; it does not erase a person (**RECHTLICH-PRÜFEN**).

Accepted (2026-10-17): a verified six-calendar-month maximum across all backup copies. Encryption before upload with Gio's private key offline, restricted/encrypted local storage and monitored expiry remain recommended. Handle plaintext archives through the separate runbook. Backups remain outside ordinary use until expiry. Before serving any restore, replay a separately controlled encrypted erasure journal offline: transfer-and-erase source rows still present exactly once, purge QR/push sessions, enforce current epoch closures and reapply unexpired markers. Never transfer again if source rows are gone. Journal selectors remain personal data (**RECHTLICH-PRÜFEN**), separate from audit; allow restore use only, no opinions/counter linkage, and erase after the last relevant backup expires (maximum six months +24h cleanup). Restore-journal retention and legal basis still need owner/privacy review (**RECHTLICH-PRÜFEN**). Do not promise unverified expiry dates. This ADR changes no backups/keys.

Proposed replacement text for `docs/wiki/delete-account.html`, **for a later implementation/page change**:

> **RECHTLICH-PRÜFEN** — Choose “Delete account” in the app and confirm using your device key. Uninstalling alone does not delete server data. When deletion completes, your key stops working and your identity, personal vote history and POLIS authorship are removed from active systems. Your accepted votes remain in aggregate totals; you cannot recover or correct them. A temporary protected marker prevents another contribution to the same open voting period and is removed after that period closes, no later than the approved 180-day period plus 24 hours. Re-verification creates a new identity and does not restore your history. Existing Arweave publications, including any ZK verifier receipts already published, cannot be removed. Restricted backups may still contain earlier data until their stated expiry, at most six months; deletion is reapplied before any restore goes live. You receive a completion receipt and the applicable expiry dates. Forum posts and newsletter subscriptions have separate deletion controls, identified here.

**RECHTLICH-PRÜFEN**: Publish only after the stated limits, separate controls and lost-key route exist; provide reviewed Greek and English text. Remove the present “orphaned/untraceable/no personal data” and “only aggregates on Arweave” promises rather than treating them as evidence.

## Dependencies and owner decisions

- **ADR-006 D2:** random anchors and v3/K_dedupe enrollment lookup, including legacy coverage and no mixed old writers (`origin/agent/claude/T-9123:docs/adr/ADR-006-identity-kdf-and-client-roots.md:53`). **D4/D5:** cutoff/review of unreachable legacy identities and removal of v2/signature/POLIS derivation oracles; deletion cannot retain those as a recovery shortcut (same source `:59`, `:95`). D4/D5 are to be decided together with S5.
- **ADR-007 stage 2/S5:** scoped keyed storage makes locating and decoupling opinions easier, but `HMAC(K_ballot, anchor || scope)` remains recoverable by the operator; deletion must transfer to counters/remove it, not just drop the identity row. Signature removal, protected CPLM, POLIS bridge and old-backup handling are joint dependencies (`origin/agent/claude/T-9123:docs/adr/ADR-007-ballot-secrecy.md:55`). S5 + S7 follow EVA-001 as the next big project; ADR-008 implementation follows S5.
- **EVA-001:** device-key PoP, signed rotation, migration and possession-verified recovery precede self-service deletion; v2 availability is flag-controlled, not established by its presence in code (`apps/api/routers/identity.py:833`, `:952`).

| Decision | Decision as of 2026-10-17; unaccepted recommendations remain open |
|---|---|
| L1 — erasure semantics | Accepted technically: B with aggregate counters, hard deletion of identity/opinion rows and no live recovery mapping; reject C. Legal review pending: **RECHTLICH-PRÜFEN**. |
| L2 — dedupe/privacy basis | Scoped spent markers recognized through D2 v3, separate keys/access; approve the narrow pseudonymous-retention purpose and lawful basis, or revisit the conflicting requirements. **RECHTLICH-PRÜFEN**. |
| L3 — closing/retention | Accepted: finite epochs ≤180 days, including OPEN_END and all ongoing action types. Still proposed: purge markers within 24 hours of irreversible close. **RECHTLICH-PRÜFEN**. |
| L4 — history/CPLM | Preserve protected historical snapshots; introduce a versioned aggregate-based future metric and stop claiming equivalent per-person CPLM/unique-voter counts. |
| L5 — correction/recovery UX | Deletion permanently ends correction/status/history; recovery requires actual possession proof, never HLR alone. |
| L6 — POLIS/integrations | Remove bindings, public authorship and authored text; keep neutral placeholders/counters. Define Discourse and independent newsletter deletion controls. **RECHTLICH-PRÜFEN**. |
| L7 — ZK/Arweave | Acknowledge existing immutable receipts; approve forfeiture of reserved eligibility and decide verifier-record retention/scope-wide counter conversion before promising universal aggregate-only storage. **RECHTLICH-PRÜFEN**. |
| L8 — backups/restore | Accepted: backup retention ≤6 months; verify enforcement. Still open: activate encryption through the separate runbook, and approve restricted restore-journal retention through backup expiry +24h. **RECHTLICH-PRÜFEN**. |
| L9 — logs/audit | Identifier-free daily audit totals; remove historical identity targets and cap residual operational logs at 30 days with documented exceptions. **RECHTLICH-PRÜFEN**. |
| L10 — release acceptance | Require D2/D4/D5 and stage-2 coordination, resolved CPLM/ZK choices, schema inventory, race/retry/count-preservation checks across every writer, all-device cleanup and a restore drill before activating deletion or publishing the page promises. Legal review remains **RECHTLICH-PRÜFEN**. |

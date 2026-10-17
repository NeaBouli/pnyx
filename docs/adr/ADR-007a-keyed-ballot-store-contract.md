# ADR-007a: Keyed ballot store protocol and migration contract

Date: 2026-10-16
Status: Accepted in part (decisions 2026-10-17): S5 + S7 (protected CPLM batch) accepted as the next big project after EVA-001; ADR-006 D4/D5 and implementation details remain open for decision together with S5.
Parent: [ADR-007 stage 2](ADR-007-ballot-secrecy.md#stage-2-keyed-vote-store-against-db-leaks-s5).

This contract targets a DB/backup leak **without `K_ballot`**. The API operator can still join identities to opinions. It does not repair earlier disclosures or immutable publications, or remove inference from geography, participation patterns and timing. “Must” below is an implementation acceptance condition, not a claim about deployed behavior.

## Decision record 2026-10-17

Technical owner decisions recorded by gio-1c under Gio's standing yes; this record supersedes earlier proposal wording for the decisions below:

- **S5 (keyed vote store) + S7 (protected CPLM batch)** are the next big project after EVA-001; the protected batch is the selected CPLM direction.
- **ADR-006 D4/D5 are to be decided together with S5**; cutoff, historical-anchor migration and detailed implementation acceptance remain open for that project.
- ADR-007 **S1–S3 are done; S4 is accepted now with backup and rollback**. This record changes no deployed behavior.

## Pseudonym and scope bytes

For key version `v`, use exactly:

```text
LP(x) = uint32_be(byte_length(x)) || x
A = hex_decode(final_anchor)                  # exactly 32 bytes
S = UTF8(canonical_scope)                     # versioned domain below
M = ASCII("ekklesia/ballot/v1") || LP(A) || LP(S)
P = HMAC-SHA256(K_ballot[v], M)                # full 32-byte digest
```

There is no separator, NUL or newline after the fixed label. Lengths count bytes, not characters. The anchor is ADR-006's final, canonical 64-character lowercase hex anchor, decoded to bytes; neither a phone number nor the hex text is hashed here. Reject malformed/noncanonical anchors. Store `P` as `BYTEA` with a 32-byte check; lowercase hex is only its interchange representation. Never truncate it.

The **entire** stored scope includes `v1:`. Key version `v` is separate metadata, selects the secret, and is not appended to `M`. Never reuse key bytes under another version number. A scope-version change requires a migration preserving spent state; changing the prefix must not grant another vote.

| Canonical scope | Meaning |
|---|---|
| `v1:bill:<id>:vote` | Parliamentary choice, including ordinary and QR submissions |
| `v1:bill:<id>:relevance` | Relevance signal, separate from choice |
| `v1:bill:<id>:consensus` | Consensus score, separate from both above |
| `v1:municipal:<ada>` | Municipal/regional decision vote |
| `v1:eval:<ada>` | All question scores for one politician's evaluation |
| `v1:flag:<bill>` | One citizen's flag on one bill |
| `v1:cplm:<period>` | Reserved for an S7 alternative retaining one personal snapshot per UTC month, `YYYY-MM` |
| `v1:polis:identity` | Persistent POLIS key bridge; deliberately constant within POLIS |

Object IDs are authoritative database IDs, case-sensitive, in Unicode NFC. Resolve the request to that object before constructing the scope; do not hash a URL spelling or client-supplied scope. IDs must be nonempty, have no leading/trailing whitespace, colon, NUL or control characters. Preserve all other characters, including Greek letters; encode UTF-8 without a BOM. Preflight existing IDs for violations/collisions and stop for resolution rather than silently renaming them. `period` is a validated calendar month. Compare scopes with binary/C collation. No survey domain is active: the proposed disposition below retires that legacy store.

### Known-answer vectors

**TEST KEY ONLY — NEVER PROVISION:** `K_ballot[1] = 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f` (hex decoded, not ASCII). These three outputs were computed with Python's `hmac` and `hashlib.sha256`.

| `final_anchor` (hex) | `canonical_scope` | UTF-8 scope length | `P` (hex) |
|---|---|---:|---|
| `0000000000000000000000000000000000000000000000000000000000000000` | `v1:bill:GR-2026-0042:vote` | 25 | `d37bb90e9f8e8ed7335c98ab527b4e22d936c8fc3a6421e9349ccfb183eb97fa` |
| `0000000000000000000000000000000000000000000000000000000000000000` | `v1:bill:GR-2026-0042:relevance` | 30 | `8beddbcebfdc358709b3462e53209abe750425eca54c82d4f26725205a2ed1aa` |
| `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f` | `v1:municipal:6ΑΒΓ-123` | 24 | `7bc7e9836006e4ea5da6625e7dad0942932b39a918c906d2bcb7387b08246640` |

The municipal example contains Greek capitals U+0391/U+0392/U+0393. Reproduction code:

```python
import hashlib
import hmac

key = bytes(range(32))  # TEST KEY
def lp(value):
    return len(value).to_bytes(4, "big") + value

def pseudonym(anchor_hex, scope):
    message = b"ekklesia/ballot/v1" + lp(bytes.fromhex(anchor_hex)) + lp(scope.encode("utf-8"))
    return hmac.new(key, message, hashlib.sha256).hexdigest()

for anchor, scope in [
    ("00" * 32, "v1:bill:GR-2026-0042:vote"),
    ("00" * 32, "v1:bill:GR-2026-0042:relevance"),
    (bytes(range(32)).hex(), "v1:municipal:6ΑΒΓ-123"),
]:
    print(pseudonym(anchor, scope))
```

## Keys, lookup and writes

Provision each version as 32 cryptographically random bytes through a secret manager or runtime-injected environment (`BALLOT_KEY_V1_HEX`, etc.), with an explicit active version and readable-version set. No defaults, generation at startup, or fallback to another secret. Validate configuration before serving. Key material must never enter DB tables, migrations, logs, images, repository files, DB/Redis backups or captured environment dumps. Exclude any provisioning environment file from backup archives. Keep a separately controlled secret-manager/offline recovery copy and test restoring the same versions. Grant keys only to the ballot API and, if S7 approves, the protected CPLM batch.

`K_ballot`, ADR-006's `K_dedupe` and `SERVER_SALT` are independently generated secrets; none derives from, substitutes for, or shares bytes with another. A ballot-key rotation does not rotate eligibility, anchors, receipt keys or the cross-tier lock. ADR-006's migrations of other `SERVER_SALT` consumers remain prerequisites to taking that salt offline.

All personal reads authenticate the current identity key using a fresh, operation/scope-bound signed request. The API derives candidate pseudonyms for every readable key version and matches each with its `scope` and `key_version`. Zero matches means “not voted” only when all required keys and the migration are available; one match selects the row; multiple matches are an integrity error, never extra votes or a last-write-wins merge. A client-supplied `P` is not authorization. Verify identity signatures in memory and discard them, including error paths and telemetry.

Every ordinary and QR mutation uses the same transaction: lock the original eligibility/identity row; validate active key, geography, protocol floor and cross-tier exclusion; derive all candidates; lock any matching ballot; apply the signed operation and expected-revision compare-and-swap; update counts and commit. This identity lock serializes simultaneous first inserts **across key versions**, where a single unique index alone is insufficient. Retain the identity-wide protocol floor from ADR-006 D3. Never persist an identity-row FK, public key, signed envelope, request nonce or session identifier alongside an opinion.

Choice correction is allowed once in the bill's `WINDOW_24H`: atomically set `is_correction`, retain `original_vote`, increment `revision` and change the choice. QR must obey exactly that rule; OPEN_END updates use their permitted operation and revision without resetting correction state. Relevance/consensus/evaluation upserts retain their existing product semantics but share locking/revision rules. Bill state/deadline determines correction eligibility; day-level row dates do not extend a window.

Status returns the caller's choice and correction eligibility after lookup. Receipt v2 returns `scope`, current choice, UTC cast day, revision and confirmation status through the authenticated response; it persists no identity proof or anchor prefix. Retire the current `SERVER_SALT`/anchor/timestamp `chain_proof` receipt format (`apps/api/routers/voting.py:1312`); client compatibility is part of S5. A private receipt is transferable and does not provide stage-3 secrecy.

**Rotation:** publish a new key set to all fenced workers, then make `v+1` the sole write version while dual-reading `v` and `v+1`. The planned window is at least 30 days and continues until the completion checks below pass. Under the same identity/ballot locks, an old-row match moves to the active `P`/version in place, preserving payload, revision, spent/correction state and counts. A protected resumable sweep derives old/new candidates from retained eligibility anchors and scopes; no old-P/new-P mapping survives. Fence stale writers using a key-set epoch checked before commit. End dual-read only after every retained row is migrated, all in-flight sessions/jobs and stale workers are drained, and a recovery drill passes. Orphan rows or unavailable anchors block key retirement; elapsed time is not permission to discard them. Never destroy an old key while a supported recovery snapshot still needs it.

**Loss/recovery:** restore exact keys from the separate recovery copy; do not generate replacements and interpret failed lookups as unused eligibility. Permanent loss removes correction, personal status/receipt and protected cross-bill computation for affected history, **not stored choices or counts**. Public tallies still count rows directly. Freeze mutations in every affected existing scope when an essential key is missing, including casts by apparently unmatched identities. Fresh scopes may use a new key only through an explicit new-scope configuration. Identity/device recovery adopts the original eligibility and anchor, so it cannot reset spent state.

## Schema and index contract

All retained keyed stores have non-null `P`, `scope`, positive integer `key_version`, and `UNIQUE(P, scope)` named `uq_<table>_p_scope`; relevance may use that pair as its primary key. Do **not** include `key_version` in uniqueness. Add a scope/object consistency check, an index on `scope` for counts and `(key_version, scope)` for migration. Keep object FKs, value/range checks and object aggregate indexes. Mutating records carry nonnegative `BIGINT revision`. Retain only UTC `DATE` fields (`created_day`, `updated_day`, `corrected_day`, as applicable). Remove old identity indexes/constraints together with their columns; do not leave nullable compatibility copies, payload JSON copies or joinable mapping tables.

References below describe this checkout, not a verified production catalog. `consensus_votes`, `cplm_history` and `bill_flags` have SQL callers but no model/migration DDL in the repository (`docs/wiki/database.html:257`). Their live constraints must be inventoried locally before an implementation migration; do not invent their current index names.

| Store and current source evidence | Required change |
|---|---|
| `citizen_votes`: anchor, signature, Tier-1 artifacts and correction fields at `apps/api/models.py:219`; unique anchor/bill and partial nullifier index at `apps/api/models.py:235` | Use vote scope and keyed uniqueness; retain bill/choice, original choice and correction flag/revision. Drop `nullifier_hash`, `signature_hex`, `pk_eph`, `vote_nullifier`, `linkage_tag`, `timestamp_ms`, exact timestamps, and their indexes. Any populated Tier-1 fields require D5 oracle review before removal, not a copy to history. Preserve the separate ZK spent/tier ledger. |
| `bill_relevance_votes`: composite anchor/bill PK, signal check at `apps/api/models.py:349` | Replace PK with `(P, scope)` for relevance; retain bill FK and ±1 check; remove anchor and exact timestamp. |
| `consensus_votes`: anchor/bill upsert at `apps/api/routers/voting.py:1377`, QR equivalent at `apps/api/routers/polis_qr.py:460` | Replace anchor/bill conflict target with `(P, scope)` for consensus; retain bill, score and enforce -5…5. Preserve/recompute bill score/count caches transactionally. |
| `cplm_history`: anchor, scores, trigger bill/type inserted at `apps/api/routers/voting.py:1397` and `apps/api/routers/polis_qr.py:477`; personal reader at `apps/api/routers/voting.py:1446` | Recommended S7 path: retire the event table and both writers; remove its indexes and personal event-history reader. Current `economic_score = score/100` exposes consensus scores. Recompute the protected public metric from keyed source ballots; persist aggregates only. If S7 instead keeps personal monthly snapshots, replace events with one `(P, scope)` row for `v1:cplm:YYYY-MM`, x/y and day only; remove anchor and trigger bill/type. This alternative needs an explicit product/migration decision, not an automatic conversion of events into snapshots. |
| `diavgeia_votes`: anchor/ADA unique and ADA index at `apps/api/models.py:534` | Municipal scope and keyed uniqueness; keep ADA, choice and ADA index; replace `voted_at` with UTC day and remove anchor. |
| `politician_evaluations`: one anchor/ADA/question score row and indexes at `apps/api/models.py:584` | One parent per `(P, eval scope)`, with random UUID primary key, ADA, revision and day. Move scores into `politician_evaluation_scores` keyed by `(evaluation_id, question_id)` with parent/question FKs, score -5…5 and per-question days. Keep ADA/question aggregate indexes; drop old anchor index/uniqueness and anchor. This preserves partial question upserts atomically without wrongly limiting an evaluation to one question. |
| `bill_flags`: anchor/bill insert plus count update at `apps/api/routers/parliament.py:523` | Flag scope and keyed uniqueness; retain bill and UTC day. Keep one flag per eligibility, preserving `flag_count` under retries; remove anchor and its old constraint/index. |
| `survey_responses`: `user_hash`, answer JSON, demographics and indexes at `apps/api/models.py:369`; raw-anchor registration cleanup at `apps/api/routers/identity.py:502` | Proposed S5 disposition: retire the legacy store, with no current writer found. Reconcile answer distributions into approved aggregate-only output, then drop rows/table, hash/demographic indexes and cleanup SQL. Do not assume `user_hash` is a verified anchor or silently map every response to one survey. Retaining personal responses instead requires an instrument/edition scope and a separate, reviewed duplicate/matching rule before S5 can activate. |
| POLIS bridge `polis_identity_keys`: anchor PK, unique `pk_polis`, identity signature and millisecond timestamp at `apps/api/alembic/versions/o801a2b3c4d5_polis_identity_keys.py:18`; lookup/register callers at `apps/api/routers/polis_tickets.py:68` and `apps/api/routers/polis_tickets.py:159` | `UNIQUE(P, scope)` with constant `scope = 'v1:polis:identity'`; retain unique persistent `pk_polis`, replace use dates with days. Drop anchor, identity signature and exact timestamps. Switch registration, reverse lookup and use checks together. POLIS tickets/votes remain explicitly linked by the separate public pseudonym: schema at `apps/api/alembic/versions/n701a2b3c4d5_polis_tickets.py:18` and `apps/api/alembic/versions/n701a2b3c4d5_polis_tickets.py:37`; never add the identity anchor to them. |

For S7's recommended batch, enumerate original eligibility anchors and visible bill scopes inside the protected process, derive vote/consensus candidates, compute per-voter positions in memory, and publish only suppressed/coarsened aggregates. The current service groups directly by anchor (`apps/api/services/cplm.py:89` and `apps/api/services/cplm.py:101`); replacing that grouping with a stable stored surrogate would recreate the join. Retiring personal event history changes that product feature; S7 must approve it. Any private current summary is reconstructed on authenticated demand without persisting an anchor/profile pair.

## Cutover, backfill and rollback

1. **Decide and prepare.** Approve S5/S7/D4/D5, close legacy identity takeover, require signed personal reads and deploy ADR-006 D3 operation/revision protection. Inventory the local catalog, all raw SQL, analytics/newsletter/admin/export/cleanup jobs, ZK enrollment's ordinary-vote check (`apps/api/routers/zk.py:767`) and every QR path. Resolve duplicate/orphan eligibility without granting fresh votes; unresolved rows block cutover. Provision keys and rehearse with synthetic data. Deploy code supporting both schemas behind `BALLOT_STORE_MODE=legacy|keyed|paused`, initially `legacy`; no new raw writers are permitted after keyed activation.
2. **Fence and finalize anchors.** Enter `paused` globally, reject new mutations, drain transactions/jobs and revoke old workers' DB access. Complete ADR-006 D5: establish each final random anchor across identity and dependent source records **before computing any `P`**. Freeze anchors thereafter; future legitimate anchor changes need another protected rekey preserving spent state. D4's original eligibility, protocol floor and pending-review state survive unchanged.
3. **Run one logical backfill.** While paused, a one-shot job reads finalized source rows and fills keyed shadow tables in bounded transactions. It is idempotent and resumable: record only run ID, source cursor, schema/key versions and aggregate progress, atomically with each committed chunk; upsert by `(P, scope)` only if payload/state matches, otherwise halt. Group evaluation parents without losing question rows. Reruns verify existing output and never double counts, flags, corrections or revisions. Retired history/survey rows have explicit reconciliation totals. No plaintext anchor/P mapping, signed payload or opinion enters checkpoints/logs. Source rows remain the resumable input until validation, not a second live write path.
4. **Validate and remove oracles.** Compare source/output tallies and state before retiring any source. Resolve D5's retained v2 values, signatures and any phone-derived POLIS roots. Require affected-install coverage and authenticated rebind to random POLIS keys, including retained tickets/votes and any derived nullifiers/signatures that would still verify a guessed old key. A new bridge alone does not repair old artifacts. Record exceptions as a blocked historical-protection claim, never silently declare unlinkability. Delete temporary mappings/checkpoints and remove old columns, shadow/source copies, constraints and exact timestamps after successful validation. Rebuild retained opinion row IDs independently where IDs preserve source order; physical/WAL copies remain covered by retention below.
5. **Switch once.** In a fenced maintenance boundary, activate one schema epoch and `keyed` mode for **all readers and ordinary/QR writers**, protected batch, auxiliary stores and cleanup paths. Remove raw-column privileges and refuse startup for a schema/mode mismatch. No rolling mixture or dual raw/keyed writes. While traffic remains paused, verify every entry point against the new schema; resume only after counts, spent state, indexes and step 6's session invalidation pass. A post-switch flag reversal cannot select `legacy`.
6. **Remove QR references.** Invalidate all pre-cutover `polis_qr:*` sessions, including pending/authenticated/processing/failed/used states. Current Redis stores bill IDs (`apps/api/routers/polis_qr.py:150`) and identity/public key (`apps/api/routers/polis_qr.py:58`); success cleanup only deletes identity fields and failure may leave them (`apps/api/routers/polis_qr.py:121`). For new sessions, Redis holds only random session ID, status and TTL. A short-lived authenticated-encrypted authorization capsule held by the clients binds session/challenge, final anchor, current key, purpose, scope, operation, expected revision, schema/key-set epoch and expiry. Issue it only after the app signs those authorization fields; use a separate QR-session encryption key outside backups. Redis never stores the capsule, identity, public key, bill/scope, signature or choice. Validate the capsule/current identity at redemption, atomically claim once, and use the shared ballot transaction. A used or crashed session cannot create a new cast; an uncertain post-commit retry reads authoritative spent/revision state or asks for fresh authorization. Failure restoration cannot recreate old Redis fields. Polling exposes status only.
7. **Expire historical copies.** Inventory DB dumps/replicas/WAL, Redis RDB/AOF/snapshots, logs, crash dumps and external backup retention. Deleting live fields or waiting for TTL does not delete snapshots. Disable session persistence or exclude the session store from backup; verify new snapshots contain no reference bridge. Record actual expiry/destruction of pre-cutover and transient migration copies before claiming historical protection. Controlled old copies retained for recovery continue to carry the old exposure.

**Rollback before keyed acceptance:** remain paused and resume the backfill/validation; completed D5 final anchors and eligibility state are authoritative. **Rollback after keyed activation:** deploy only an earlier release that understands the keyed schema, current keys, schema epoch and ADR-006 continuity. Otherwise pause mutations and retain aggregate reads. Keep the latest keyed rows, revisions, correction flags, protocol floors and cross-tier spent ledger; do not restore a pre-cutover dump or reset them. Disaster recovery replays committed keyed state to the last acknowledged write before reopening; if that cannot be proven, stay paused. Missing keys or unmatched legacy identities remain fail closed (`PENDING_LEGACY_REVIEW`), not newly eligible. Rollback never recreates raw-anchor writers, mappings or signed-opinion storage.

## Acceptance evidence required from implementation

- **Bytes:** all three vectors; UTF-8 byte framing, NFC/ID validation, malformed anchors, case and object aliases; same anchor across actions/objects gives different `P`. Key-version and scope-version changes cannot mint eligibility.
- **Concurrency:** simultaneous first casts through ordinary/QR and old/new key versions yield one row and one count. Race correction/update/replay, key rotation, identity recovery/revocation and ZK enrollment against ordinary/QR writes. Preserve identity-wide protocol floor and tier exclusion; inject commit/Redis failures.
- **Correction once:** two concurrent corrections in `WINDOW_24H` accept exactly one; all later attempts and stale revisions fail through every route. Migration/rotation/recovery preserve the correction flag, original choice and revision; timestamps do not reopen windows.
- **Status/receipt:** authenticated caller gets the same current choice, revision and eligibility before/after migration and rotation, with documented receipt-v2/day changes. Reject unsigned, wrong-scope, stale and revoked-key reads; return unavailable, not “unspent,” if a required key is missing. No signature/identity prefix is persisted or returned in receipts.
- **Counts equal:** compare parliamentary/municipal choices, relevance signals, consensus score distributions/sums/counts, evaluation scores per ADA/question, flags and tier-spent totals before/after, including QR history. Flatten evaluation children for row comparisons. Recompute caches and protected CPLM output against frozen inputs; list approved feature changes separately. For retained data require exact equality; reconcile every deliberately retired event/survey row and preserve approved aggregate distributions. No silent deduplication or orphan loss.
- **Resume/rotation/recovery:** kill the backfill at each chunk boundary, rerun twice and verify identical output/counts. Exercise dual reads, stale-worker fencing, orphan blocking, exact-key restore and permanent loss. Roll back with post-cutover casts/corrections and prove that none becomes available again.
- **No-join check:** inspect catalog, rows, views, JSON, staging/checkpoints, audit/telemetry and dumps: **no retained table contains both an identity anchor (or identity FK/public key/signature equivalent) and an opinion**. No anchor/P mapping or stable cross-scope surrogate exists outside declared POLIS authorship. Combined identity/ballot dumps without ballot keys must fail direct joins; test known legacy anchors, v2/signature and POLIS-root oracles. POLIS's declared persistent public pseudonym is separately documented, never treated as anonymous. Confirm Redis success/failure/timeout paths and new snapshots contain no identity/bill references. Old-copy expiry and unresolved oracle coverage are explicit release evidence.

## Owner decisions and irreversible effects

| Decision still needed | Recommendation and consequence |
|---|---|
| **S5** | Approve stage 2 after EVA-001 and ADR-006 D2/D3, with this complete-store cutover, receipt v2 and legacy survey retirement. Provision a distinct recoverable ballot key before migration. |
| **S7** | Use the protected batch to keep the public CPLM metric; retire per-identity event history and persist aggregates only. If choosing client CPLM or personal monthly snapshots instead, approve the feature/data migration explicitly and still remove both old history writers/readers. |
| **D4** | Select a cutoff using the server-side share still lacking v3; recommend zero unresolved ACTIVE identities before retiring legacy lookup. Keep every unmatched verification pending, including negative legacy searches; review can only attach it positively to original eligibility. Migrate all other salt consumers before taking `SERVER_SALT` offline. |
| **D5** | Approve random final historical anchors before `P`, removal of v2/signature oracles, affected-install POLIS rebind and expiry of old copies. Block the historical-protection claim until each condition has evidence. |

Once old anchors/mappings, signatures, exact timestamps, retired personal histories and old POLIS artifacts are removed and old copies expire, their original history/cryptographic re-verification cannot be recovered. Receipt v2 intentionally replaces the old proof format. Destroying an unrecoverable ballot key permanently loses private lookup/correction for its rows; counts survive and spent state must stay closed. Earlier leaks, public POLIS associations and Arweave publications cannot be recalled. Owner approval of S5/D5 must acknowledge these losses; no such approval or implementation occurs in this ADR.

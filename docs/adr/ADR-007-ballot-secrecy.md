# ADR-007: Ballot secrecy (EVA-006)

Date: 2026-10-16
Status: Proposed. S1 (claims), S2 (k=10, flag-guarded) and S3 (backup encryption, inactive until key) decided by Gio 16.10.2026; S4–S7 open.
Tracking: EVA-006 (P1, audit 2026-10-11); related: ADR-004, ADR-006, NEA-249 (Semaphore), EVA-008/015

## Context

Basis: a source audit on 2026-10-16 (checkout `8f48ed03`; every claim with file:line in the local facts report `.fleet/reports/EVA-006-facts-codex.md`) and read-only production checks (*Receipts*).

### What gets stored and linked today
- **Votes** (`citizen_votes`): `nullifier_hash` (stable identity anchor) + `bill_id` + readable `vote` + identity signature + timestamps. Corrections live in the same row (`original_vote`).
- **Equally linked:**
  - relevance (`bill_relevance_votes`);
  - consensus (`consensus_votes`) plus `cplm_history`: ordinary and QR writers store per-identity `economic_score = score / 100` with the bill, so individual scores can be reconstructed (`apps/api/routers/voting.py:1394`, `apps/api/routers/polis_qr.py:474`);
  - municipal votes (`diavgeia_votes`);
  - politician evaluations (`politician_evaluations`);
  - bill flags (`bill_flags`);
  - legacy survey responses (`survey_responses.user_hash`), with answers and optional demographics; registration cleanup treats `user_hash` as the identity anchor, but no current writer was found;
  - POLIS (`polis_identity_keys` binds `nullifier_hash` → `pk_polis`; tickets and POLIS votes under `pk_polis`).
- **Functionally needed** are deduplication (a scoped "spent" identifier), correction, personal status and receipt (finding your own vote), geographic authorization (before acceptance), and the current CPLM (cross-bill per voter). **Not needed** for counts, divergence or representativeness.
- **ZK/Semaphore (Tier 2):** the vote row has no identity link. But enrollment (identity → commitment) is stored, the choice is readable and published (receipts, Arweave), small groups are padded with public dummies, and the submission is sent directly (operator timing). The QR vote path **doesn't check** the cross-tier lock (ordinary voting does).

### Who can see an individual choice
| Path | Today |
|---|---|
| `GET /vote/{bill}/status` (unsigned) | returns the choice to anyone who knows a `nullifier_hash`; prod `VOTE_STATUS_REQUIRE_SIGNED` unset |
| `GET /politicians/{ada}/my-evaluation` (unsigned) | returns individual scores; prod `EVALUATION_REQUIRE_V2` unset |
| QR session polling | full nullifier + public key while authenticated (60 s) |
| App logs | QR vote/consensus log **choice/score + nullifier prefix**; POLIS logs identity prefix → handle and votes |
| DB role | API, monitor and DB use the same Postgres user; no separation of identity and ballots |
| Backups | full `pg_dump` + Redis snapshot, **uploaded unencrypted** to the external backup host |
| Public results/exports | aggregates without small-cell suppression (singletons and differencing possible) |

### Public claims
The privacy page and landing say "pseudonymous" (correct). App texts (onboarding, verification, evaluation, sharing), `docs/WHITEPAPER.md`, demo/municipality/embed pages and the delete-account page promise "anonymous" or "unlinkable", which doesn't match ordinary storage. Arweave "never individual votes" is wrong for ZK.

- `/api/v1/public/info` lists `individual_votes` among data never stored, despite storing individual choices (`apps/api/routers/public_api.py:670`).
- The privacy page describes VAA answers as public-key-hash pseudonyms and says they are deleted on revoke (`docs/wiki/privacy.html:247`). No current survey writer establishes that key format. Revoke does not delete survey rows; registration deletes rows whose `user_hash` equals the identity anchor.
- The privacy page says k ≥ 10 prevents re-identification (`docs/wiki/privacy.html:253`). That is too absolute. Qualify its IP assurances by storage/logging layer and deployment checks. HMAC rate-limit buckets do not prevent operator observation or timing correlation.

## Threat targets
- **(a) Public:** no DB/operations access.
- **(b) DB leak:** leak of DB/backups, application secrets outside them.
- **(c) Operator:** can observe and control the application.

## Decision (proposed): three stages

### Stage 1: close exposure, no protocol change (S1–S4)
1. **Close unsigned personal reads:** `VOTE_STATUS_REQUIRE_SIGNED=true` (gate prepared) and `EVALUATION_REQUIRE_V2=true` (same procedure, after the client numbers). Confidentiality also depends on EVA-001 closing legacy re-registration. It can replace an ACTIVE identity's key without the old key, giving an attacker access to signed reads (`apps/api/routers/identity.py:439`). Enabling v2 alone leaves this legacy path open.
2. **Logs:** no choice or score in log lines; no identity prefixes next to opinions (QR, POLIS). Tests guard against regressions.
3. **QR path:** apply the ZK cross-tier lock check there as well (before ZK is ever un-paused).
4. **Small-cell protection (S2):** roll out behind a flag. Suppress public cells below k = 10; exports must not allow caller-controlled `min_votes=0`. Require complementary suppression so totals, percentages and related outputs cannot reconstruct hidden cells. Define a shared release policy for successive and overlapping results, analytics, exports and CPLM coordinates/snapshots, with coarse update cadence and rounding. Choose parameters in implementation PRs. k ≥ 10 alone cannot stop inference: a count changing from 10 to 11 around a known submission can reveal a choice.
5. **Backups (S3):** encrypt the archive before upload (e.g. `age`), with the private key offline at Gio's (secret gate); test restore with the offline key. Encryption stays inactive until the key is provisioned.
6. **DB roles (S4):** separate roles for API (write), monitor/dashboard (aggregates only via views), backup (read). Identity and opinion tables are not jointly readable for monitor/dashboard.
7. **Claims (S1):** app/docs texts "anonymous" → "pseudonymous, aggregates public"; remove the delete-account and whitepaper statements; Arweave statement per tier. Correct `/public/info`, VAA storage/deletion, k ≥ 10 and IP statements listed above.

Effect: (a) exposure reduced. Personal reads still depend on EVA-001, and aggregate inference remains until the shared release policy is implemented and checked. k ≥ 10 alone does not close (a). (b) and (c) unchanged except for backups and roles.

### Stage 2: keyed vote store against DB leaks (S5)
- Protocol and migration contract: [ADR-007a](ADR-007a-keyed-ballot-store-contract.md).
- Votes, relevance, consensus, municipal votes, evaluations and `bill_flags` get stored under a **scoped pseudonym** `P = HMAC(K_ballot, anchor ‖ scope)` instead of `nullifier_hash`. `K_ballot` sits **outside** DB and backups, separate from `K_dedupe` (ADR-006) and `SERVER_SALT`.
- The identity signature is **verified, not stored**; timestamps are coarsened (day).
- Correction, status and receipts compute `P` per request in the API. This resists the direct anchor join in a DB/backup leak without `K_ballot`. The operator can still compute the join.
- CPLM: the cross-bill per-voter computation runs in a protected batch with `K_ballot`, storing aggregates only, or it moves into the app (owner decision). Moving computation alone does not remove personal history. Migrate `cplm_history` to scoped pseudonyms or retire it, including both ordinary and QR writers and the personal-history reader. Inventory and migrate or retire legacy `survey_responses`, including `user_hash` and its cleanup paths.
- POLIS keeps its own explicit pseudonym (persistent authorship is a product decision); the bridge `nullifier_hash → pk_polis` gets keyed the same way.
- **Migration:** new votes at a cutover; historical rows are rewritten once to `P` (`K_ballot` exists before then) and the old columns removed. **Prerequisites:** ADR-006 D5 (oracles from v2 column, signatures, POLIS roots) and the backup retention of old dumps. Without them the history stays linkable. A cutover can't undo earlier disclosures (old backups, Arweave).
- **Residual channels:** a singleton municipality or narrow geography can identify a voter. QR Redis records hold identity + bill references while authenticated or processing; backup snapshots can retain them after live expiry or cleanup. Participation patterns, row ordering and timing can correlate opinions even with day-level timestamps.

#### Migration contract (to define in implementation PRs)

- Set D5's final identity anchor before computing `P`. Migrate or retire every dependent store; remove temporary old-to-new mappings.
- Define versioned scope domains per opinion type and object, canonical encoding and unambiguous field boundaries for the HMAC input.
- Cut over ordinary and QR writers atomically with readers and uniqueness checks. No old writer may reintroduce raw anchors.
- Define rollback and key recovery without restoring raw-anchor writers or resetting spent-vote state.
- Remove QR session identity/bill references at cutover. Cover processing failures and Redis snapshots in cleanup and retention.
- Keep D4 fail-closed continuity through cutover and rollback. Unmatched legacy identities stay pending; key recovery must not create new eligibility.
- Require evidence that v2/signature oracles and the phone-derived POLIS-root oracle are removed or resolved, including affected-install coverage and rebind. Verify retention and expiry of old DB/Redis backups before claiming historical protection. Prior disclosures remain outside that claim.

Effect: (b) resists the direct anchor join when `K_ballot` stays separate and the migration contract holds. Residual inference remains. (c) still possible.

### Stage 3: operator secrecy (S6, long-term)
Semaphore/ZK for all opinion types with a real anonymity-set policy (no public dummies, minimum group per root, closed roots), a protected submission channel, and a cross-path one-vote rule. Alternatively encrypted ballots with independent trustees (Helios-style). Each is a separate protocol project with external review; not decided now.

- **Limits:** secrecy from the operator requires a trusted client. An operator can change served client code to expose choices. Group size alone is insufficient when the operator controls other anonymity-set members. Compromised devices, coercion and transferable receipts need explicit treatment; ZK membership alone does not solve them.

## Relation to ADR-006
- **D5 (rewriting historical anchors)** must be ordered with stage 2. Set the final identity anchor before deriving `P`. Remove raw anchors from every opinion store and auxiliary history, including `cplm_history`, `bill_flags`, legacy surveys and the POLIS bridge. D5 still covers identity-table oracles, retained signatures, phone-derived POLIS roots and old backups. Its scope narrows only after evidence shows each dependent store was migrated or retired.
- **D4 (cutoff)** stays as described in ADR-006; stage 2 needs it so old identities can't vote twice.

## Owner decisions
- **S1 decided (Gio, 16.10.2026):** correct the claims now (app/docs); EL/EN wording to Gio.
- **S2 decided (Gio, 16.10.2026):** small-cell threshold k = 10 for public results/exports, behind a flag. Complementary suppression and release-policy details remain implementation work.
- **S3 decided (Gio, 16.10.2026):** backup encryption with an offline key; inactive until key provisioning (secret gate).
- **S4:** separate DB roles. *Recommendation: yes; ops change (gate).*
- **S5:** stage 2 (keyed vote store), after the EVA-001 series and ADR-006 D2. *Recommendation: yes; it decides D4/D5.*
- **S6:** stage 3 later as its own project. *Recommendation: no decision now.*
- **S7:** CPLM computation: protected batch with `K_ballot` vs. in the app. *Recommendation: protected batch (keeps the product metric).*

## Receipts (production, read-only, 2026-10-16)
- `VOTE_STATUS_REQUIRE_SIGNED` and `EVALUATION_REQUIRE_V2` unset in the API container; `ZK_VOTING_ENABLED=false`, `ZK_OPT_IN_ENABLED=true`, `ZK_TIER1_GUARD_ENABLED=true`.
- Sentry: not verified (variable SENTRY_DSN_API to be checked read-only)
- Offsite backup: the cron wrapper calls `scripts/backup-offsite.sh` (full dump + Redis snapshot, gzip, SFTP), with no encryption step.
- `citizen_votes`: 24 rows, 0 with Tier-1 metadata.

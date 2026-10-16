# ADR-007: Ballot secrecy (EVA-006)

Date: 2026-10-16
Status: Proposed. Owner decisions S1–S7 open; ADR-006 D4/D5 get decided together with this ADR.
Tracking: EVA-006 (P1, audit 2026-10-11); related: ADR-004, ADR-006, NEA-249 (Semaphore), EVA-008/015

## Context

Basis: a source audit on 2026-10-16 (checkout `8f48ed03`; every claim with file:line in the local facts report `.fleet/reports/EVA-006-facts-codex.md`) and read-only production checks (*Receipts*).

### What gets stored and linked today
- **Votes** (`citizen_votes`): `nullifier_hash` (stable identity anchor) + `bill_id` + readable `vote` + identity signature + timestamps. Corrections live in the same row (`original_vote`).
- **Equally linked:**
  - relevance (`bill_relevance_votes`);
  - consensus (`consensus_votes`) plus `cplm_history`, from which individual consensus scores can be reconstructed;
  - municipal votes (`diavgeia_votes`);
  - politician evaluations (`politician_evaluations`);
  - bill flags;
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

## Threat targets
- **(a) Public:** no DB/operations access.
- **(b) DB leak:** leak of DB/backups, application secrets outside them.
- **(c) Operator:** can observe and control the application.

## Decision (proposed): three stages

### Stage 1: close exposure, no protocol change (S1–S4)
1. **Close unsigned personal reads:** `VOTE_STATUS_REQUIRE_SIGNED=true` (gate prepared) and `EVALUATION_REQUIRE_V2=true` (same procedure, after the client numbers).
2. **Logs:** no choice or score in log lines; no identity prefixes next to opinions (QR, POLIS). Tests guard against regressions.
3. **QR path:** apply the ZK cross-tier lock check there as well (before ZK is ever un-paused).
4. **Small-cell protection (S2):** public results, analytics timelines and exports show counts only from k ≥ 10 per published cell (otherwise "< 10"); exports without caller-controlled `min_votes=0`.
5. **Backups (S3):** encrypt the archive before upload (e.g. `age`), with the private key offline at Gio's (secret gate); test restore with the offline key.
6. **DB roles (S4):** separate roles for API (write), monitor/dashboard (aggregates only via views), backup (read). Identity and opinion tables are not jointly readable for monitor/dashboard.
7. **Claims (S1):** app/docs texts "anonymous" → "pseudonymous, aggregates public"; remove the delete-account and whitepaper statements; Arweave statement per tier.

Effect: (a) largely closed; (b) and (c) unchanged except for backups and roles.

### Stage 2: keyed vote store against DB leaks (S5)
- Votes, relevance, consensus, municipal votes and evaluations get stored under a **scoped pseudonym** `P = HMAC(K_ballot, anchor ‖ scope)` instead of `nullifier_hash`. `K_ballot` sits **outside** DB and backups, separate from `K_dedupe` (ADR-006) and `SERVER_SALT`.
- The identity signature is **verified, not stored**; timestamps are coarsened (day).
- Correction, status and receipts compute `P` per request in the API. With `K_ballot`, the operator can still link; without it, a DB/backup leak can't.
- CPLM: the cross-bill per-voter computation runs in a protected batch with `K_ballot`, storing aggregates only, or it moves into the app (owner decision).
- POLIS keeps its own explicit pseudonym (persistent authorship is a product decision); the bridge `nullifier_hash → pk_polis` gets keyed the same way.
- **Migration:** new votes at a cutover; historical rows are rewritten once to `P` (`K_ballot` exists before then) and the old columns removed. **Prerequisites:** ADR-006 D5 (oracles from v2 column, signatures, POLIS roots) and the backup retention of old dumps. Without them the history stays linkable. A cutover can't undo earlier disclosures (old backups, Arweave).

Effect: (b) protected, given `K_ballot` stays separate; (c) still possible.

### Stage 3: operator secrecy (S6, long-term)
Semaphore/ZK for all opinion types with a real anonymity-set policy (no public dummies, minimum group per root, closed roots), a protected submission channel, and a cross-path one-vote rule. Alternatively encrypted ballots with independent trustees (Helios-style). Each is a separate protocol project with external review; not decided now.

## Relation to ADR-006
- **D5 (rewriting historical anchors)** becomes part of the stage-2 migration: the anchors next to opinions disappear entirely, so the separate rewrite isn't needed. D5 then only remains for the identity table itself.
- **D4 (cutoff)** stays as described in ADR-006; stage 2 needs it so old identities can't vote twice.

## Owner decisions
- **S1:** correct the claims now (app/docs). *Recommendation: yes; EL/EN wording to Gio.*
- **S2:** small-cell threshold k = 10 for public results/exports. *Recommendation: yes; product effect: small bills show "< 10".*
- **S3:** backup encryption with an offline key. *Recommendation: yes (secret gate).*
- **S4:** separate DB roles. *Recommendation: yes; ops change (gate).*
- **S5:** stage 2 (keyed vote store), after the EVA-001 series and ADR-006 D2. *Recommendation: yes; it decides D4/D5.*
- **S6:** stage 3 later as its own project. *Recommendation: no decision now.*
- **S7:** CPLM computation: protected batch with `K_ballot` vs. in the app. *Recommendation: protected batch (keeps the product metric).*

## Receipts (production, read-only, 2026-10-16)
- `VOTE_STATUS_REQUIRE_SIGNED` and `EVALUATION_REQUIRE_V2` unset in the API container; `ZK_VOTING_ENABLED=false`, `ZK_OPT_IN_ENABLED=true`, `ZK_TIER1_GUARD_ENABLED=true`; `SENTRY_DSN` not set.
- Offsite backup: the cron wrapper calls `scripts/backup-offsite.sh` (full dump + Redis snapshot, gzip, SFTP), with no encryption step.
- `citizen_votes`: 24 rows, 0 with Tier-1 metadata.

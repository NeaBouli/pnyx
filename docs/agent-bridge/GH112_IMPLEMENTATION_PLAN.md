# GH#112 - ZK V2 Implementation Plan

Date: 2026-06-11
Status: Implementation checklist, no runtime implementation
Depends on: GH#81, NEA-249, GH#112 Gate 0

## Purpose

This document turns the GH#112 gate design into an execution order.

It is intentionally conservative. The goal is to prevent mixing database,
verifier, mobile, Arweave, and canary work in one unsafe change.

## Non-Negotiables

- Do not flip `zkSemaphoreEnabled` during implementation.
- Do not enable `ZK_VOTING_ENABLED` in production outside an explicit canary.
- Do not change the current Ed25519/Tier 1 vote path without a focused review.
- Do not add ZK votes to public tallies before a canary decision.
- Do not store Semaphore private identity material on the server.
- Do not publish identity bridge data to Arweave.
- Do not claim public ZK verification until an Arweave bulletin-board record exists.

## Gate 0 - Frozen Inputs

Already decided:

- Android native Mopro/Semaphore prover works on S10.
- Offline fixture verifies with the official Semaphore JS verifier.
- Cross-tier uniqueness uses a private per-scope `tier_guard_hash`.
- Arweave bulletin board stores only public verifier payloads.

Still required before Gate 2 code:

- Final server verifier architecture:
  - internal Node verifier service,
  - controlled JS worker from FastAPI,
  - or Python/Rust verifier with matching artifacts.
- Final artifact depth for production:
  - current self-test uses depth 16,
  - blueprint originally references depth 24,
  - implementation must choose one and pin checksums.

Stop conditions:

- If verifier dependencies introduce high/critical CVEs into production images,
  keep verifier isolated until reviewed.
- If artifact source/checksum cannot be pinned, do not build Gate 2.

## Gate 1 - Database, Additive Only

Goal:

Add storage that cannot affect existing Tier 1 votes.

Allowed files:

- `apps/api/alembic/versions/*`
- `apps/api/models.py`
- focused tests only

Suggested schema:

- `zk_identity_commitments`
- `zk_merkle_roots`
- `zk_vote_receipts`
- `zk_vote_tier_locks`
- nullable ZK fields on `citizen_votes` only if Tier 1 insert/read behavior is unchanged

Rules:

- Existing `citizen_votes` unique constraint stays.
- Existing Tier 1 rows remain valid.
- No backfill of old votes.
- No Nullifier v2 activation.
- No Arweave publishing.
- No mobile code.

Tests:

- Alembic upgrade/downgrade.
- Existing Tier 1 vote insert still passes.
- Existing Tier 1 duplicate vote still fails.
- ZK commitment uniqueness rejects duplicate commitments.
- ZK nullifier uniqueness rejects duplicate `(vote_scope_id, semaphore_nullifier)`.
- Tier-lock uniqueness rejects duplicate `(vote_scope_id, tier_guard_hash)`.
- Public/serialization helpers exclude private lock fields.

Deploy rule:

- Gate 1 may be deployed with no flags enabled because it is additive only.
- Run production migration only after DB backup.

## Gate 2 - Backend Verifier, Disabled

Goal:

Add server-side proof verification without accepting production ZK votes.

Allowed files:

- `apps/api/routers/zk.py`
- verifier adapter/service code
- config/startup guard
- tests and fixtures

Rules:

- `ZK_VOTING_ENABLED=false` by default.
- Endpoint may exist but returns disabled unless flag is on.
- Disabled path writes nothing to `citizen_votes`.
- Disabled path writes nothing to Arweave.
- No mobile feature flag flip.

Tests:

- S10 fixture verifies.
- Mutated message fails.
- Mutated scope fails.
- Mutated Merkle root fails.
- Duplicate Semaphore nullifier fails at helper/schema level.
- Existing `/api/v1/vote` tests unchanged.
- Dependency audit is reviewed before adding verifier packages to production images.

Stop conditions:

- Verifier requires unsafe dependency footprint in the API image.
- Verifier cannot validate the S10 fixture exactly.
- Artifact checksums are not pinned.

## Gate 3 - Cross-Tier Tier Lock

Goal:

Prevent the same citizen from voting through Tier 1 and Tier 2 for the same
voting object without deanonymizing the ZK vote.

Allowed files:

- opt-in endpoint/router
- tier-lock helper
- focused Tier 1 guard check
- tests

Rules:

- Lock is created at ZK opt-in / Merkle-root construction time.
- ZK vote endpoint does not look up real identity.
- `tier_guard_hash` is never public.
- Tier 1 endpoint rejects later votes for an active lock on the same scope.
- Cancel is allowed only before commitment enters a published root.
- After root publication, Tier 1 remains locked for that scope.

Tests:

- Tier 1 then ZK opt-in same scope is rejected.
- ZK opt-in then Tier 1 same scope is rejected.
- Same citizen can opt into/vote on different scopes.
- Same citizen across scopes gets unrelated `tier_guard_hash`.
- Public exports exclude `tier_guard_hash`, Tier 1 nullifier, identity id, phone, IP, public key.
- Operator logs avoid high-precision opt-in/vote correlation fields.

Stop conditions:

- Any design requires identity lookup during ZK vote verification.
- Any public record can link Tier 1 identity to ZK vote.

## Gate 4 - Mobile Opt-In

Goal:

Expose ZK opt-in only when server and device capability say it is safe.

Allowed files:

- mobile ZK screen / opt-in UI
- API client additions
- mobile tests

Rules:

- ZK remains optional.
- Existing Ed25519 vote path remains default.
- Store Semaphore identity secret only in SecureStore.
- UI explains that after root publication the normal vote path is locked for that scope.
- UI shows pending/publication status honestly.
- If server flag is off, screen explains not active.

Tests:

- Existing Tier 1 vote still works.
- ZK self-test still passes.
- Opt-in disabled message shown when server flag is off.
- Proof artifact failure does not crash.
- No private identity material is sent to server.
- No S10 requirement for doc/API gates, but S10 required before final mobile release.

## Gate 5 - Arweave Bulletin Board

Goal:

Publish public verifier payloads for accepted ZK votes.

Allowed files:

- Arweave publisher function for `ekklesia.zk_vote.v1`
- pending/backfill queue
- public verifier/recount helpers
- tests

Record includes:

- `vote_scope_id`
- bill id
- vote or vote commitment
- Semaphore nullifier
- Merkle root/depth
- proof/public signals
- verifier and artifact versions
- group size
- coarse publication bucket

Record excludes:

- `tier_guard_hash`
- Tier 1 nullifier
- identity record id
- phone, IP, HLR metadata
- Tier 1 public key
- Semaphore identity secret
- precise opt-in/vote timestamps

Rules:

- Local acceptance is not the same as public Arweave verification.
- Pending publication must be visible as `arweave_pending=true` or equivalent.
- Publication may be queued/batched to reduce timing correlation.
- Failed Arweave write must not silently claim public verification.
- Do not add a receipt-accepting `/zk/vote` endpoint until the backend can
  recompute and compare the expected Semaphore `message` and `scope` values
  from canonical `vote_scope_id` + `vote_commitment` inputs.
- A Groth16-valid proof alone is not sufficient for vote acceptance: it must
  also be bound to the exact logical vote scope and vote commitment.

Tests:

- Record shape snapshot.
- Serializer excludes forbidden fields.
- Public verifier recomputes Tier 2 subtotal.
- Duplicate Semaphore nullifier is rejected.
- Wrong scope/message/root fails proof validation.
- Wrong logical `vote_scope_id` with otherwise valid proof fails receipt
  acceptance.
- Wrong `vote_commitment` with otherwise valid proof fails receipt acceptance.
- Pending publication status is exposed honestly.

## Gate 6 - Canary

Goal:

Activate ZK only for explicit canary identities.

Rules:

- Backup before activation.
- Enable only for chosen canary identities.
- Decide whether canary ZK votes count in public tallies before activation.
- If canary votes count and are published to Arweave, do not roll them back.
- Telegram/admin monitor for verifier, publication, and pending-queue errors.
- Rollback is disabling `ZK_VOTING_ENABLED`; Tier 1 remains available for non-locked users.

Acceptance:

- At least one canary ZK vote accepted.
- Proof verifies server-side.
- Tier-lock blocks Tier 1 for the same scope.
- Arweave record published or honestly pending.
- Public verifier can recompute the ZK subtotal.
- Current Tier 1 voting remains green.

## Current Gate Status

- Gate 1 additive DB/storage is live.
- Gate 2 verifier scaffolding is disabled/fail-closed.
- Gate 3 tier-lock helpers and guarded Tier 1 checks are prepared behind
  default-off flags.
- ZK opt-in storage is prepared but production opt-in remains disabled.
- Semaphore-compatible LeanIMT/Poseidon root helper is implemented and tested
  against the S10 fixture.
- Root read/publish API is prepared; publish is admin-only and gated by
  `ZK_ROOT_PUBLICATION_ENABLED`.
- Canary scope allowlist is enforced on opt-in, root publish, and verifier
  requests when `ZK_CANARY_ENABLED=true`.

## Current Blocker

Production activation is blocked until an explicit canary window with backup,
monitoring, and operator approval.

See `docs/agent-bridge/GH112_MERKLE_ROOT_PREFLIGHT.md`.
See `docs/agent-bridge/GH112_CANARY_ACTIVATION_PLAN.md`.

Do not use a SHA/SHA256 Merkle placeholder. The next implementation step is a
canary object/test-scope setup and operator activation window, not a broad flag
flip.

# GH#112 - ZK V2 Production Integration Gate

Date: 2026-06-11
Status: Gate plan, no runtime implementation
Depends on: GH#81, NEA-249

## Current Truth

GH#81 removed the old external/mobile-prover blocker:

- Android native Mopro/Semaphore proof generation works on the S10.
- The app can generate and verify a local test proof without sending data.
- `zkSemaphoreEnabled` remains `false`.
- Production voting still uses the existing Ed25519/HMAC Tier 1 path.

GH#112 is therefore not a "find a prover" task. It is a production voting integration task. Treat it as security-sensitive.

## Non-Negotiable Invariants

- Do not change the current Ed25519 vote path without explicit review.
- Do not flip `zkSemaphoreEnabled` in production during implementation.
- Do not add ZK votes to production tallies before a canary window.
- Do not store Semaphore private identity material on the server.
- Do not publish per-vote records containing phone, IP, public key tied to identity, or raw device identifiers.
- Do not allow the same citizen to cast both a Tier 1 and Tier 2 vote for the same bill.
- Do not claim public verifiability for Tier 1 aggregate-only votes.

## Gate 0 - Design Freeze

Before code:

1. Confirm the exact Semaphore proof payload shape emitted by the vendored native module.
2. Confirm server-side verification library and artifact source.
3. Define canonical vote message:
   - Recommended: `sha256("ekklesia:v2:" + bill_id + ":" + vote + ":" + merkle_root)`.
4. Define canonical scope:
   - `ekklesia:v2:vote:{bill_id}`.
5. Define the cross-tier double-vote guard.
6. Define the Semaphore group management trust model:
   - who inserts commitments,
   - how Merkle roots are published,
   - how users can verify inclusion,
   - what prevents silent exclusion/censorship.
7. Define interaction with Nullifier v2 / Argon2id:
   - whether GH#112 depends on GH#111,
   - how Tier 1 identity changes do not break cross-tier uniqueness.
8. Define identity revocation semantics:
   - whether revoked commitments remain eligible,
   - how re-registration avoids old-Tier/new-Tier double voting,
   - whether pending proofs survive Merkle root rotation.

Stop condition:

- If cross-tier uniqueness cannot be proven, keep GH#112 as canary-only.
- If the group management model links identity to ZK votes in a recoverable way, do not proceed.

## Gate 1 - Database, Additive Only

Allowed:

- Add `zk_identity_commitments`.
- Add `zk_merkle_roots`.
- Add `zk_vote_receipts` or equivalent append-only receipt table.
- Add nullable ZK fields to `citizen_votes` only if existing rows and Tier 1 writes remain valid.

Not allowed:

- Dropping or rewriting existing `citizen_votes` uniqueness.
- Recomputing old votes.
- Mutating Nullifier v2 production state.

Required tests:

- Migration upgrade/downgrade.
- Existing Tier 1 vote insert still passes.
- Existing Tier 1 duplicate vote still fails.
- ZK tables reject duplicate commitments/nullifiers.

## Gate 2 - Backend Verifier, No Mobile Yet

Add verifier behind a disabled server flag:

- `ZK_VOTING_ENABLED=false` by default.
- Verification endpoint may exist, but must return disabled unless the flag is enabled.
- No tallies changed.
- No Arweave write on disabled path.

Required checks:

- Valid fixture proof verifies.
- Invalid proof fails.
- Wrong bill scope fails.
- Wrong message/vote fails.
- Old `/api/v1/vote` tests unchanged.

## Gate 3 - Cross-Tier Double-Vote Guard

This is the critical product invariant.

The current Tier 1 table enforces:

- `UNIQUE(nullifier_hash, bill_id)`

ZK adds a different nullifier domain, so it must not create a bypass.

Acceptable canary options:

1. ZK-only canary identities that are not allowed to cast Tier 1 votes during canary.
2. A confidential server-side eligibility mapping created at ZK opt-in that marks the citizen as ZK-only for selected bills.
3. A shared canonical voter key that works across Tier 1 and Tier 2 without deanonymizing public records.

Privacy constraints:

- Option 2 is a linkability trade-off. It must be treated as canary-only unless the mapping can be deleted or blinded without breaking uniqueness.
- Option 3 must not derive the Semaphore identity from the Ed25519 keypair or any public Tier 1 key.
- Do not log opt-in timestamps with precision that can correlate a later ZK vote to a known identity.
- Tier 1 salted SHA256 nullifiers and Tier 2 Semaphore nullifiers must use separate columns or explicit domain prefixes. Do not rely on accidental string-shape differences.

Do not proceed to production until this is implemented and tested.

Required tests:

- Tier 1 then Tier 2 same bill is rejected.
- Tier 2 then Tier 1 same bill is rejected.
- Tier 2 duplicate by Semaphore nullifier is rejected.
- Same citizen can vote on different bills.

## Gate 4 - Mobile Opt-In

Allowed:

- Store Semaphore identity secret only in SecureStore.
- Show device capability and proof benchmark result.
- Let user opt in only when server canary says the account/device is eligible.

Not allowed:

- Silent opt-in.
- Mandatory ZK mode.
- Uploading private identity material.

Required S10 checks:

- Existing Ed25519 vote still works.
- ZK self-test still passes.
- Opt-in disabled message is clear when server flag is off.
- No crash if proof artifact download fails.

## Gate 5 - Arweave Bulletin Board

ZK per-vote records must be independently verifiable but anonymous.

Record must include:

- bill id
- vote choice or canonical vote commitment, depending final design
- Semaphore nullifier
- Merkle root
- proof/public signals
- verifier/library version
- timestamp

Record must not include:

- phone
- IP
- identity record id
- public key tied to Tier 1 identity
- raw private key or secret

Canary privacy constraints:

- Do not publish per-vote Arweave records for a tiny anonymity set unless the canary users explicitly accept that reduced anonymity.
- Prefer batched publication and coarse timestamps to avoid correlating vote time with server/mobile access logs.
- Merkle roots must be published with enough context for independent verification, but the group size and root history must be documented.

Required tests:

- Arweave record shape snapshot.
- Public verifier can recompute the tally from records.
- Failed Arweave write does not silently count a ZK vote as publicly verifiable.

## Gate 6 - Canary

Canary must be explicit:

- Backup before activation.
- Enable only for test/canary identities.
- Telegram/admin monitor for verifier errors.
- Rollback plan: disable `ZK_VOTING_ENABLED`; Tier 1 remains available.
- Canary tally isolation rule:
  - decide before activation whether ZK canary votes count in public tallies,
  - if they do not count, label them as test/canary records,
  - if they do count, do not roll them back after Arweave publication.

Canary acceptance:

- At least one ZK canary vote accepted.
- Proof verifies server-side.
- Arweave record published.
- Public verification works.
- Current Tier 1 voting remains green.

## Current Recommendation

Next implementation step should be Gate 0 only:

- collect native proof payload sample,
- write server verification fixture,
- finalize cross-tier uniqueness design.

Do not build Gate 1+ until Gate 0 is reviewed.

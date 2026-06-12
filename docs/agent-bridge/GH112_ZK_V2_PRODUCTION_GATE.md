# GH#112 - ZK V2 Production Integration Gate

Date: 2026-06-11
Status: Gate plan, no runtime implementation
Depends on: GH#81, NEA-249
Implementation checklist: `docs/agent-bridge/GH112_IMPLEMENTATION_PLAN.md`

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

### Selected Gate-0 Design: Private Per-Scope Tier Lock

Use a private, server-side tier lock created before a citizen is included in a
Semaphore Merkle root for a voting scope.

Rationale:

- The ZK vote request itself must not reveal which registered identity is voting.
- Therefore cross-tier uniqueness cannot be checked at ZK vote time by looking up
  the real identity.
- The lock must happen earlier, at ZK opt-in / Merkle-root construction time.
- The lock is private operational state, not public audit data.

Canonical voting scope:

```text
vote_scope_id = "{source}:{id}"
```

Examples:

- `parliament:GR-0490a766`
- future DIAVGEIA scope: `diavgeia:{ada}`

The scope identifies the exact voting object. It must not prevent a citizen from
voting on different legitimate objects at different governance levels.

Tier-lock key:

```text
tier_guard_hash =
  HMAC_SHA256(
    SERVER_SALT,
    "ekklesia:vote-tier-lock:v1:" + vote_scope_id + ":" + tier1_nullifier_hash
  )
```

Notes:

- `tier1_nullifier_hash` is the existing private Tier 1 voting anchor submitted
  today to `/api/v1/vote`.
- `tier_guard_hash` is never published to Arweave, analytics, forum, or public
  verification APIs.
- If the Tier 1 identity anchor changes in a future Nullifier v2 voting path,
  this lock gets a new domain prefix (`vote-tier-lock:v2`) rather than mutating
  v1 semantics.

ZK opt-in flow for a bill/scope:

1. User authenticates with the existing Tier 1 identity using an Ed25519
   signature over:

   ```text
   zk-opt-in:{vote_scope_id}:{identity_commitment_hash}
   ```

2. Server verifies the Tier 1 identity is active.
3. Server checks there is no existing Tier 1 vote for `(nullifier_hash, bill_id)`.
4. Server computes `tier_guard_hash`.
5. Server inserts an active lock:

   ```text
   vote_scope_id
   tier_guard_hash
   selected_tier = "TIER2_SEMAPHORE"
   identity_commitment_hash
   root_epoch
   locked_at
   ```

6. The commitment is included in the bill/scope Merkle root.
7. The Tier 1 endpoint rejects any later Tier 1 vote for the same
   `(tier_guard_hash, vote_scope_id)`.
8. The ZK vote endpoint verifies only the Semaphore proof, root, scope, message,
   and Semaphore nullifier uniqueness. It does not look up the real identity.

Root publication rule:

- Before a commitment is included in a published root, the user may cancel ZK
  opt-in and return to Tier 1.
- After the commitment has been included in a published root for that scope, the
  Tier 1 lock remains active for that scope, even if the user never casts the ZK
  vote. This is conservative, but prevents using an old root/proof path and then
  falling back to Tier 1.

Privacy properties:

- Public ZK vote records do not include `tier_guard_hash`, Tier 1 nullifier,
  identity record id, phone, IP, or public key.
- The server does know which verified identity opted into a given ZK scope. This
  is a canary/Beta trust trade-off and must be documented.
- The server must publish Merkle roots and proof-verification data so the public
  can verify votes without access to the private tier-lock table.

Security-review checkpoints before implementation:

1. Cross-scope unlinkability
   - `tier_guard_hash` must include `vote_scope_id`.
   - The same citizen opting into two different scopes must produce unrelated
     lock values.
   - No API, log, admin export, Arweave record, or analytics table may expose a
     stable "ZK opt-in user id" across scopes.

2. Timing-correlation control
   - Do not publish a Merkle root immediately for a single opt-in unless the
     canary user explicitly accepts the tiny anonymity set.
   - Prefer batched root publication with coarse timestamps.
   - Server logs for opt-in and ZK vote submission must avoid high-precision
     correlation fields in operator-facing views.
   - Canary reports must include group size and root publication timing.

3. Opt-in without a later ZK vote
   - Before root publication: user may cancel opt-in and return to Tier 1.
   - After root publication: Tier 1 stays locked for that scope even if the ZK
     vote is never cast.
   - The mobile UI must explain this before opt-in: "After ZK activation for
     this vote, your normal vote path is locked for this specific vote."
   - Recovery must be an explicit admin/security-review flow, not an automatic
     unlock, because an old root/proof may still exist.

Rejected options for now:

- Deriving the Semaphore identity from the Ed25519 keypair or public key.
- A shared public voter key across Tier 1 and Tier 2.
- Checking cross-tier uniqueness only after a ZK vote arrives.

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
- ZK opt-in then Tier 1 same scope is rejected even before a ZK vote is cast.
- ZK opt-in can be cancelled only before the commitment is included in a published root.
- Same citizen opting into two different scopes produces different
  `tier_guard_hash` values.
- Public receipt / Arweave / analytics serialization excludes `tier_guard_hash`
  and Tier 1 identifiers.
- Root publication batching and group-size metadata are visible to operators.

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

Yes: ZK proof data should be archived, but only the public verifier payload.
The Arweave record is the public bulletin-board entry, not an identity bridge.

Record must include:

- bill id
- canonical `vote_scope_id`
- vote choice or canonical vote commitment, depending final design
- Semaphore nullifier / nullifier hash for duplicate detection
- Merkle root
- Merkle tree depth
- proof/public signals exactly as verified by the server
- verifier/library version
- artifact/circuit version
- schema version, e.g. `ekklesia.zk_vote.v1`
- coarse timestamp or batch id
- publication mode: `canary`, `production`, or `test`

Record must not include:

- phone
- IP
- identity record id
- public key tied to Tier 1 identity
- raw private key or secret
- `tier_guard_hash`
- Tier 1 `nullifier_hash`
- Semaphore `identity_commitment` unless the group-management design explicitly
  decides that commitments are already public as part of the Merkle tree
- precise opt-in timestamp
- precise vote-submission timestamp when it can correlate a small anonymity set
- admin/operator ids or HLR metadata

Recommended record envelope:

```json
{
  "schema": "ekklesia.zk_vote.v1",
  "mode": "canary",
  "vote_scope_id": "parliament:GR-0490a766",
  "bill_id": "GR-0490a766",
  "vote": "YES",
  "semaphore_nullifier": "12345678901234567890",
  "merkle_root": "12345678901234567890",
  "merkle_tree_depth": 16,
  "message": "sha256:...",
  "scope": "ekklesia:v2:vote:parliament:GR-0490a766",
  "proof": {
    "protocol": "semaphore-v4",
    "points": [],
    "public_signals": {}
  },
  "verifier": {
    "name": "@semaphore-protocol/proof",
    "version": "4.14.2",
    "artifact_set": "semaphore-v4-depth-16-pse-44690d9"
  },
  "root_publication": {
    "root_epoch": 1,
    "group_size": 25,
    "published_at_bucket": "2026-06-11T12:00Z"
  }
}
```

Canary privacy constraints:

- Do not publish per-vote Arweave records for a tiny anonymity set unless the canary users explicitly accept that reduced anonymity.
- Prefer queued/batched publication and coarse timestamps to avoid correlating vote time with server/mobile access logs.
- Do not publish "accepted_at" or raw server receive timestamps.
- If canary votes count in public tallies, the bulletin-board records are
  append-only and must not be rolled back after publication.
- Merkle roots must be published with enough context for independent verification, but the group size and root history must be documented.

Required tests:

- Arweave record shape snapshot.
- Public verifier can recompute the tally from records.
- Public verifier rejects a duplicate `semaphore_nullifier`.
- Public verifier rejects records whose `scope`, `message`, or `merkle_root`
  does not match the proof.
- Serializer excludes `tier_guard_hash`, Tier 1 nullifier, identity record id,
  phone, IP, public key, and precise opt-in/vote timestamps.
- Failed Arweave write does not silently count a ZK vote as publicly verifiable.
- UI/API distinguishes local acceptance from public Arweave verification:
  unpublished records must show `arweave_pending=true` or equivalent.

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

Gate 0 design, Gate 1 storage, Gate 2 disabled verifier scaffolding, Gate 3
tier-lock helpers, Semaphore LeanIMT/Poseidon root building, root read/publish,
exact canary allowlisting, hidden canary scope setup, and admin canary preflight
are prepared.

The next ZK step is not a broad production flag flip. It is a controlled
canary window for `bill:ZK-CANARY-001` only:

- take a fresh DB backup immediately before activation,
- verify `/api/v1/zk/canary/preflight/bill:ZK-CANARY-001`,
- set only the documented canary flags and exact allowlist,
- perform one known canary opt-in,
- publish one root,
- verify one proof,
- keep normal Tier-1 voting green,
- document rollback before and after the test.

Do not publish per-vote Arweave records or count canary ZK votes in public
tallies until the canary tally policy is explicitly reviewed.

See `docs/agent-bridge/GH112_CANARY_ACTIVATION_PLAN.md`.

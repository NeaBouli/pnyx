# NEA-249 - ZK Voting V2 Blueprint

Date: 2026-05-22
Owner: Codex architecture handoff
Status: Proposed implementation blueprint
Decision source: NEA-234 research

## Executive Decision

Use a Hybrid V2 architecture:

- Tier 1 stays unchanged: HMAC-Nullifier-Chain, Ed25519 signatures, current aggregation, aggregate Arweave snapshot on `PARLIAMENT_VOTED`.
- Tier 2 adds optional ZK mode: Semaphore membership proof, Semaphore nullifier, and per-vote public bulletin-board records on Arweave.
- Do not build Helios for V2.
- Do not build custom ZK circuits or a custom trusted setup ceremony for MVP.
- Do not claim verifiable aggregation from aggregate-only Arweave data. Verifiability requires public per-vote proof records.

The V2 guarantee should be stated narrowly and honestly:

> A public verifier can check that each published ZK vote was cast by some member of the verified voter group, that the same Semaphore identity did not vote twice for the same bill/scope, and that the public tally can be recomputed from the published anonymized vote records.

It does not prove that the voter device was uncompromised, that the identity enrollment process was perfect, or that Tier 1 aggregate-only votes are individually verifiable.

## 1. Architecture Overview

### Tier 1 - Current System, Unchanged

Current Tier 1 remains the default production voting path.

Core properties:

- Identity derives from local mobile key material.
- `nullifier_root` stays on the device.
- Per-bill values are derived via HMAC:
  - `identity_commitment`
  - `vote_nullifier`
  - `ephemeral_seed`
  - `linkage_tag`
- Vote payload is signed with Ed25519.
- Backend checks:
  - signature validity
  - bill status/scope
  - one vote per `(nullifier_hash, bill_id)`
- Arweave currently receives aggregate audit trails when a bill reaches `PARLIAMENT_VOTED`.

Tier 1 remains necessary because:

- It is already deployed.
- It has low operational cost.
- It works on Expo/React Native without native ZK modules.
- It provides a fallback path for devices where ZK proving is too slow or unsupported.

### Tier 2 - Semaphore ZK Mode

Tier 2 adds an opt-in ZK path for votes.

Core additions:

- A Semaphore identity commitment is registered for a verified voter.
- A bill-specific Merkle root is exposed to the mobile app.
- The mobile app generates a Semaphore proof locally.
- The backend verifies the proof and stores the vote as a ZK-backed vote.
- A per-vote anonymized bulletin-board record is published to Arweave immediately after acceptance.

Tier 2 should use Semaphore because it directly matches the product problem:

- Prove group membership without revealing which member.
- Emit a nullifier for a specific scope to prevent double voting.
- Verify off-chain on normal CPU hardware.
- Preserve current FastAPI/PostgreSQL/Arweave stack.

### Coexistence Model

Tier 1 and Tier 2 coexist per vote.

Recommended rollout:

1. Keep current `/api/v1/vote` as the default Tier 1 path.
2. Add `/api/v1/vote/zk` as an opt-in path.
3. Add a mobile feature flag: `zk_voting_enabled`.
4. Add per-user capability detection:
   - device supports native proof generation
   - benchmark passes threshold
   - Semaphore identity exists
5. Store `vote_tier` on `citizen_votes`:
   - `TIER1_HMAC`
   - `TIER2_SEMAPHORE`
6. Aggregation includes both tiers.
7. Public verification page distinguishes:
   - Tier 1 votes: counted in aggregate, not individually public-verifiable.
   - Tier 2 votes: individually proof-verifiable and publicly recountable.

Important invariant:

The same voter must not be able to cast both Tier 1 and Tier 2 votes for the same bill.

MVP enforcement:

- Use a shared server-side uniqueness policy by `bill_id` plus one of:
  - existing `nullifier_hash`
  - new `zk_nullifier_hash`
  - `linkage_tag` if available
- For full protection, migration must define a canonical per-bill user uniqueness key that works for both tiers.

## 2. Database Schema

Use PostgreSQL 15. Prefer JSONB for proof payloads, but index stable scalar fields.

### Table: `zk_identity_commitments`

Purpose:

Stores Semaphore identity commitments that are eligible to vote. This is not a user account table and must not store phone, IP, email, or raw private key material.

DDL blueprint:

```sql
CREATE TABLE IF NOT EXISTS zk_identity_commitments (
    id BIGSERIAL PRIMARY KEY,
    identity_commitment VARCHAR(78) NOT NULL,
    identity_commitment_hash VARCHAR(64) NOT NULL,
    identity_record_id INTEGER NULL,
    public_key VARCHAR(64) NULL,
    nullifier_hash VARCHAR(64) NULL,
    enrollment_scope VARCHAR(50) NOT NULL DEFAULT 'citizen',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    source VARCHAR(30) NOT NULL DEFAULT 'MOBILE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ NULL,
    revoke_reason TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_zk_identity_commitment UNIQUE (identity_commitment),
    CONSTRAINT uq_zk_identity_commitment_hash UNIQUE (identity_commitment_hash),
    CONSTRAINT ck_zk_identity_status CHECK (status IN ('ACTIVE', 'REVOKED', 'PENDING'))
);

CREATE INDEX IF NOT EXISTS idx_zk_identity_status
    ON zk_identity_commitments (status);

CREATE INDEX IF NOT EXISTS idx_zk_identity_created_at
    ON zk_identity_commitments (created_at);
```

Column notes:

- `identity_commitment`: decimal string representation of the Semaphore commitment. Semaphore values are field elements; decimal strings can exceed 64 characters, so use `VARCHAR(78)`.
- `identity_commitment_hash`: SHA-256 hex of the commitment string for cheap lookup.
- `identity_record_id`: optional link to existing identity record if available; must not be exposed publicly.
- `public_key`: optional current Ed25519 public key for operational correlation during enrollment only.
- `nullifier_hash`: optional Tier 1 nullifier reference for migration guardrails; do not expose publicly.
- `metadata`: non-sensitive client capability data only, e.g. app version, proof library version, benchmark class.

### Table: `merkle_root_history`

Purpose:

Stores the Merkle roots used by ZK votes. Roots must be immutable once used by a vote. A bill can have multiple roots over time as new identities are added.

DDL blueprint:

```sql
CREATE TABLE IF NOT EXISTS merkle_root_history (
    id BIGSERIAL PRIMARY KEY,
    bill_id VARCHAR(50) NOT NULL REFERENCES parliament_bills(id) ON DELETE CASCADE,
    merkle_root VARCHAR(78) NOT NULL,
    merkle_root_hash VARCHAR(64) NOT NULL,
    tree_depth SMALLINT NOT NULL,
    leaf_count INTEGER NOT NULL,
    active_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active_until TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'system',
    artifact_set VARCHAR(50) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_merkle_root_per_bill UNIQUE (bill_id, merkle_root),
    CONSTRAINT ck_merkle_tree_depth CHECK (tree_depth BETWEEN 1 AND 32),
    CONSTRAINT ck_merkle_leaf_count CHECK (leaf_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_merkle_root_bill_active
    ON merkle_root_history (bill_id, active_until, active_from DESC);

CREATE INDEX IF NOT EXISTS idx_merkle_root_hash
    ON merkle_root_history (merkle_root_hash);
```

Column notes:

- `bill_id`: root can be bill-scoped for a stable snapshot. This avoids a user proving against a group that changes mid-vote without an audit trail.
- `tree_depth`: default candidate for national scale is `24`, which supports 16,777,216 leaves.
- `artifact_set`: e.g. `semaphore-v4-depth-24-pse-44690d9`.
- `active_until`: nullable. Null means current active root for the bill.

### Changes to `citizen_votes`

Purpose:

Keep Tier 1 backwards compatible while allowing Tier 2 proof verification and public audit references.

DDL blueprint:

```sql
ALTER TABLE citizen_votes
    ADD COLUMN IF NOT EXISTS vote_tier VARCHAR(20) NOT NULL DEFAULT 'TIER1_HMAC',
    ADD COLUMN IF NOT EXISTS zk_proof JSONB NULL,
    ADD COLUMN IF NOT EXISTS zk_public_signals JSONB NULL,
    ADD COLUMN IF NOT EXISTS zk_nullifier_hash VARCHAR(78) NULL,
    ADD COLUMN IF NOT EXISTS merkle_root_ref BIGINT NULL REFERENCES merkle_root_history(id),
    ADD COLUMN IF NOT EXISTS arweave_vote_tx_id VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS proof_verified_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_votes_vote_tier
    ON citizen_votes (vote_tier);

CREATE INDEX IF NOT EXISTS idx_votes_zk_nullifier
    ON citizen_votes (zk_nullifier_hash);

CREATE INDEX IF NOT EXISTS idx_votes_merkle_root_ref
    ON citizen_votes (merkle_root_ref);

CREATE INDEX IF NOT EXISTS idx_votes_arweave_vote_tx
    ON citizen_votes (arweave_vote_tx_id);
```

Uniqueness policy:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_zk_vote_per_scope
    ON citizen_votes (bill_id, zk_nullifier_hash)
    WHERE zk_nullifier_hash IS NOT NULL;
```

Do not remove existing `uq_one_vote_per_citizen`.

Gate-0 design decision:

Tier 1 and Tier 2 use different nullifier domains. To prevent the same person
from voting once via Tier 1 and once via Tier 2, V2 uses a private per-scope
tier lock created at ZK opt-in / Merkle-root construction time.

```text
vote_scope_id = "{source}:{id}"
tier_guard_hash = HMAC_SHA256(
  SERVER_SALT,
  "ekklesia:vote-tier-lock:v1:" + vote_scope_id + ":" + tier1_nullifier_hash
)
```

When a citizen opts into ZK for a bill/scope, the server verifies the current
Tier 1 identity with Ed25519, confirms no Tier 1 vote already exists for that
scope, stores the private tier lock, and only then includes the Semaphore
commitment in the Merkle root. The Tier 1 endpoint rejects later votes for the
same private lock. The ZK vote endpoint verifies only the proof, root, message,
scope, and Semaphore nullifier uniqueness; it does not look up the real identity.

This is a canary/Beta trust trade-off: the server knows who opted into ZK for a
scope, but public ZK vote records do not expose that mapping. Do not publish
`tier_guard_hash`, Tier 1 nullifier, identity record id, phone, IP, or public key.

For MVP, keep ZK behind feature flags and internal/canary testers until the
tier-lock path is implemented and tested.

## 3. API Endpoints

All SQL must be parameterized. Do not log proof inputs containing device metadata or raw identity material.

### `POST /api/v1/vote/zk`

Purpose:

Accept a Semaphore-backed vote.

Request body:

```json
{
  "bill_id": "GR-123",
  "vote": "YES",
  "nullifier_hash": "12345678901234567890",
  "merkle_root": "12345678901234567890",
  "merkle_tree_depth": 24,
  "proof": {
    "points": ["...", "..."],
    "merkleTreeRoot": "...",
    "nullifier": "...",
    "message": "...",
    "scope": "..."
  },
  "public_signals": {
    "merkleTreeRoot": "...",
    "nullifier": "...",
    "message": "...",
    "scope": "..."
  },
  "client": {
    "platform": "android",
    "app_version": "1.3.3",
    "proof_library": "@semaphore-protocol/proof@4.14.2",
    "prover": "mopro-rapidsnark",
    "proof_time_ms": 742
  }
}
```

Canonical validation:

1. Validate `vote` is one of existing `VoteChoice` values.
2. Load bill by `bill_id`.
3. Apply same bill voting eligibility rules as `/api/v1/vote`:
   - status allows voting
   - governance scope allows voting
   - bill is not DEMO unless in demo mode
4. Load current or referenced `merkle_root_history` row.
5. Ensure submitted `merkle_root` equals the root row.
6. Ensure `tree_depth` equals the root row.
7. Ensure `scope` equals canonical scope:
   - `scope = "ekklesia:v2:vote:" || bill_id`
8. Ensure `message` equals canonical vote message:
   - MVP: `message = vote`
   - stronger later: `message = SHA256(bill_id || ":" || vote || ":" || merkle_root)`
9. Verify Semaphore proof server-side.
10. Check no existing ZK vote with `(bill_id, zk_nullifier_hash)`.
11. Check cross-tier double-vote guard if available.
12. Insert `citizen_votes` row with `vote_tier='TIER2_SEMAPHORE'`.
13. Publish anonymized per-vote record to Arweave.
14. Save `arweave_vote_tx_id` on `citizen_votes`.

Success response:

```json
{
  "success": true,
  "status": "voted",
  "tier": "TIER2_SEMAPHORE",
  "bill_id": "GR-123",
  "nullifier_hash": "12345678901234567890",
  "merkle_root": "12345678901234567890",
  "proof_verified": true,
  "arweave_vote_tx_id": "abc123",
  "receipt": {
    "verify_url": "https://ekklesia.gr/wiki/zk-voting.html?nullifier_hash=12345678901234567890",
    "arweave_url": "https://arweave.net/abc123"
  }
}
```

Error responses:

- `400`: malformed proof payload, invalid vote, invalid scope/message/root mismatch.
- `401`: proof verification failed.
- `404`: bill or Merkle root not found.
- `409`: duplicate ZK nullifier or cross-tier duplicate vote.
- `422`: schema validation error.
- `503`: ZK voting temporarily disabled.

### `GET /api/v1/zk/merkle-root/{bill_id}`

Purpose:

Return the current proof parameters for the mobile app.

Response:

```json
{
  "bill_id": "GR-123",
  "enabled": true,
  "merkle_root_ref": 42,
  "merkle_root": "12345678901234567890",
  "tree_depth": 24,
  "leaf_count": 185000,
  "scope": "ekklesia:v2:vote:GR-123",
  "artifact_set": "semaphore-v4-depth-24-pse-44690d9",
  "artifacts": {
    "wasm_url": "https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.wasm",
    "zkey_url": "https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.zkey",
    "verification_key_url": "https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.json"
  },
  "expires_at": "2026-05-23T00:00:00Z"
}
```

Rules:

- Return only roots for bills where voting is currently allowed.
- Root should be stable for a bill voting window.
- If a root rotates during a live window, keep old roots valid for already generated proofs.

### `GET /api/v1/zk/verify/{nullifier_hash}`

Purpose:

Public audit lookup for a ZK vote by its Semaphore nullifier hash.

Response when found:

```json
{
  "found": true,
  "bill_id": "GR-123",
  "vote": "YES",
  "tier": "TIER2_SEMAPHORE",
  "nullifier_hash": "12345678901234567890",
  "merkle_root": "12345678901234567890",
  "merkle_tree_depth": 24,
  "proof_verified_at": "2026-05-22T20:00:00Z",
  "arweave_vote_tx_id": "abc123",
  "arweave_url": "https://arweave.net/abc123",
  "verification": {
    "server_verified": true,
    "public_recountable": true,
    "artifact_set": "semaphore-v4-depth-24-pse-44690d9"
  }
}
```

Response when not found:

```json
{
  "found": false
}
```

Privacy rule:

This endpoint must not expose `identity_commitment`, Tier 1 nullifier, `identity_record_id`, phone, IP, device identifier, or public key.

## 4. Mobile Flow

### Libraries

Required:

- `@semaphore-protocol/proof@4.14.2`
- `@semaphore-protocol/identity@4.14.2`
- `@semaphore-protocol/group@4.14.2`

Preferred mobile proving route:

- Mopro / `SemaphoreReactNative` native bindings.
- Plain `snarkjs` is acceptable for research only, not as final mobile path unless benchmarks pass.

Reason:

- `snarkjs` package is about 9.7 MB unpacked.
- old `react-native-snarkjs` is stale and about 43.6 MB unpacked.
- Mopro benchmarks show much better native proving performance.

### Benchmark Gate

Phase 0 must happen before production implementation.

Devices:

- Samsung S10 already used by Gio.
- One mid-range Android device, not only flagship.

Metrics:

- proof generation time p50/p95
- memory peak
- app cold start impact
- APK/AAB size delta
- crash rate across 20 proof attempts
- battery/thermal qualitative note

Pass threshold for MVP:

- S10: p95 <= 8 seconds
- mid-range Android: p95 <= 12 seconds
- no native crashes in 20 consecutive proof attempts
- APK size delta acceptable and documented

### Step-by-Step Flow

1. User completes existing Tier 1 identity flow.
2. App derives or creates Semaphore identity locally.
3. App sends only `identity_commitment` to enrollment endpoint.
4. Server stores commitment in `zk_identity_commitments`.
5. When user opens a bill, app calls:
   - `GET /api/v1/zk/merkle-root/{bill_id}`
6. App receives:
   - current Merkle root
   - tree depth
   - scope
   - artifact URLs or locally bundled artifact identifier
7. App builds/fetches Merkle proof for the identity.
8. App generates Semaphore proof locally:
   - private input: Semaphore identity secret
   - membership input: Merkle proof
   - public message: vote or vote hash
   - public scope: `ekklesia:v2:vote:{bill_id}`
9. App submits to:
   - `POST /api/v1/vote/zk`
10. Server verifies, stores, publishes per-vote Arweave record.
11. App shows receipt:
   - local nullifier hash
   - Arweave URL
   - public verification URL

Do not store Semaphore private identity on the server.

Storage:

- Store Semaphore identity secret in SecureStore or platform secure keychain.
- Use versioned key names:
  - `ekklesia:zk_identity:v1`
  - `ekklesia:zk_identity_commitment:v1`
  - `ekklesia:zk_last_benchmark:v1`

## 5. Arweave Publishing

### Current Tier 1 Behavior

Current behavior remains:

- Aggregated audit trail is published on `PARLIAMENT_VOTED`.
- Tier 1 votes are not individually published.
- Existing aggregate result pages keep working.

### V2 Addition: Per-Vote Bulletin Board

For Tier 2 votes only, publish immediately after vote acceptance.

Record shape:

```json
{
  "schema": "ekklesia.zk_vote.v1",
  "bill_id": "GR-123",
  "vote": "YES",
  "nullifier_hash": "12345678901234567890",
  "merkle_root": "12345678901234567890",
  "merkle_tree_depth": 24,
  "zk_proof": {
    "protocol": "semaphore-v4",
    "proof": {},
    "public_signals": {}
  },
  "artifact_set": "semaphore-v4-depth-24-pse-44690d9",
  "server_verified_at": "2026-05-22T20:00:00Z",
  "published_at": "2026-05-22T20:00:02Z",
  "app": {
    "name": "ekklesia.gr",
    "vote_tier": "TIER2_SEMAPHORE"
  }
}
```

Arweave timing:

- Publish immediately after accepted ZK vote.
- Do not wait for `PARLIAMENT_VOTED`.
- If Arweave is temporarily unavailable:
  - store vote as accepted only if local DB commit succeeds
  - enqueue `arweave_vote_tx_id` backfill job
  - expose `arweave_pending=true` in receipt
  - monitor pending ZK vote publications separately from aggregate snapshots

Backwards compatibility:

- Tier 1 votes remain aggregate-only.
- Final bill archive at `PARLIAMENT_VOTED` should include:
  - Tier 1 aggregate counts
  - Tier 2 aggregate counts
  - list of per-vote Arweave tx IDs for Tier 2 votes
  - root history used by the bill

Public recount:

Anyone should be able to:

1. Fetch all Tier 2 per-vote Arweave records for a bill.
2. Verify each proof against published artifacts and root.
3. Reject duplicate `nullifier_hash`.
4. Count votes.
5. Compare to the Tier 2 subtotal in the final aggregate archive.

## 6. Trusted Setup

Semaphore uses Groth16 artifacts. Valid proofs require trusted setup artifacts.

Trust assumption:

- Security depends on the PSE Semaphore ceremony and the artifact files used.
- If the ceremony were compromised, false proofs might be possible for the affected circuit.
- Ekklesia does not run its own ceremony for MVP.
- This assumption must be documented publicly on the ZK wiki page.

Recommended artifact set for MVP:

- Tree depth: `24`
- Capacity: 16,777,216 leaves
- Artifact label: `semaphore-v4-depth-24-pse-44690d9`
- Source repo: `privacy-scaling-explorations/snark-artifacts`, currently served as `privacy-ethereum/snark-artifacts`
- Commit: `44690d955c8a0d0120f1ea520f6d2ffc28262077`

Exact artifact URLs:

- WASM:
  - `https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.wasm`
- ZKey:
  - `https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.zkey`
- Verification key:
  - `https://raw.githubusercontent.com/privacy-ethereum/snark-artifacts/44690d955c8a0d0120f1ea520f6d2ffc28262077/packages/semaphore/semaphore-24.json`

Additional public references to cite in website docs:

- Semaphore docs:
  - `https://docs.semaphore.pse.dev/`
- Semaphore proof package docs:
  - `https://semaphore-protocol.github.io/semaphore.js/proof/index.html`
- Semaphore SDK `generateProof`:
  - `https://js.semaphore.pse.dev/functions/_semaphore_protocol_proof.generateProof.html`
- Artifact package:
  - `https://www.npmjs.com/package/@zk-kit/semaphore-artifacts`
- Mopro mobile proving docs:
  - `https://zkmopro.org/docs/sdk/overview/`
- Mopro performance:
  - `https://zkmopro.org/docs/performance`

Implementation rule:

Do not fetch artifacts dynamically from GitHub on every vote. Either:

- bundle pinned artifacts with the mobile app after benchmark approval, or
- download once, verify SHA-256, cache locally, and refuse to prove if checksums mismatch.

The final implementation must record artifact SHA-256 checksums in code/config before production.

## 7. Implementation Phases

### Phase 0 - Android Benchmark Before Anything

Goal:

Prove that mobile ZK proving is acceptable for ekklesia users.

Tasks:

- Build isolated mobile benchmark screen or dev-only app.
- Test Mopro/SemaphoreReactNative and plain JS fallback.
- Use the depth-24 artifact set.
- Run S10 and one mid-range Android test.
- Record:
  - proof time p50/p95
  - memory behavior
  - app size delta
  - crash behavior
  - setup pain in Expo/Dev Client

Exit criteria:

- Benchmark report in `docs/agent-bridge/`.
- Explicit go/no-go for mobile ZK integration.

### Phase 1 - DB Schema + API Skeleton

Goal:

Add disabled-by-default backend support.

Tasks:

- Add Alembic migration for:
  - `zk_identity_commitments`
  - `merkle_root_history`
  - `citizen_votes` ZK columns
- Add config flag:
  - `ZK_VOTING_ENABLED=false`
- Add router:
  - `apps/api/routers/zk.py`
- Add endpoints:
  - `GET /api/v1/zk/merkle-root/{bill_id}`
  - `GET /api/v1/zk/verify/{nullifier_hash}`
  - `POST /api/v1/vote/zk` returning `503` until verifier is wired
- Add tests for disabled mode and schema-level uniqueness.

Exit criteria:

- API tests green.
- No behavior change for Tier 1.

### Phase 2 - Mobile Proof Generation Integration

Goal:

Generate a proof locally and submit to staging API.

Tasks:

- Add ZK identity SecureStore keys.
- Add enrollment flow.
- Add Merkle root fetch.
- Add proof generation.
- Add `/vote/zk` submit path behind feature flag.
- Add receipt screen update.
- Add graceful fallback to Tier 1.

Exit criteria:

- S10 can complete a ZK vote on staging.
- Failed proof generation never blocks Tier 1.

### Phase 3 - Arweave Per-Vote Publishing

Goal:

Make accepted ZK votes publicly auditable.

Tasks:

- Add Arweave publisher function for `ekklesia.zk_vote.v1`.
- Add queue/backfill for failed Arweave publishing.
- Add monitor alert:
  - `zk_arweave_pending`
- Add final aggregate snapshot references to per-vote tx IDs.

Exit criteria:

- Accepted ZK vote has Arweave tx or pending queue record.
- Public verifier can fetch and recount records.

### Phase 4 - Public Verification Page on ekklesia.gr

Goal:

Give users a plain-language verification flow.

Tasks:

- Create `docs/wiki/zk-voting.html`.
- Add verifier UI:
  - lookup by nullifier hash
  - fetch Arweave record
  - verify proof or show verification metadata
  - recompute bill subtotal from published ZK records
- Add FAQ and roadmap language.
- Add sitemap entry.

Exit criteria:

- Non-technical user can verify receipt exists.
- Technical user can independently recount Tier 2 votes.

## 8. Explicitly Out of Scope

Do not build these in NEA-249 MVP:

- Custom ZK circuit.
- Custom trusted setup ceremony.
- Server-side proving.
- Helios.
- ElGamal homomorphic tallying.
- Trustee/decryption workflow.
- Blockchain smart contracts.
- On-chain Semaphore verifier.
- Anonymous credentials beyond Semaphore group membership.
- Full migration of all Tier 1 votes to Tier 2.
- Mandatory ZK mode for all users.
- Aggregate-only ZK claim without public per-vote/proof records.
- Dynamic unpinned artifact downloads in production.

## Risks and Mitigations

### Risk: Cross-Tier Double Voting

Problem:

The same person could potentially vote via Tier 1 and Tier 2 if uniqueness domains are separate.

Mitigation:

- Do not enable public ZK voting until the private per-scope tier-lock path is implemented.
- MVP can be internal testers only.
- ZK opt-in must lock Tier 1 for the same voting scope before the commitment enters a published Merkle root.
- ZK opt-in cancellation is allowed only before root publication.
- Public ZK records must never expose `tier_guard_hash`, Tier 1 nullifier, identity record id, phone, IP, or public key.

### Risk: Mobile Proving Fails on Older Devices

Mitigation:

- Benchmark first.
- Keep Tier 1 fallback.
- Feature flag by device capability.

### Risk: Trusted Setup Misunderstood

Mitigation:

- Publish explicit trust assumption.
- Pin artifact commit and checksums.
- Do not claim trustless cryptography.

### Risk: Arweave Cost/Latency

Mitigation:

- Use compact JSON.
- Queue and backfill.
- Monitor pending records.
- Consider batching only after per-vote semantics are proven.

### Risk: Public Vote Values Reduce Privacy in Small Groups

Problem:

If a bill has very few ZK voters, public per-vote records can reveal patterns.

Mitigation:

- Display anonymity set warnings.
- Do not enable ZK public mode for groups below a minimum threshold.
- Semaphore docs warn that very small groups are not meaningfully anonymous.

## Minimum Viable First Step

Before CC implements product code:

1. Create an ADR from this blueprint.
2. Run Phase 0 mobile benchmark.
3. Decide artifact depth and checksums.
4. Decide cross-tier uniqueness model.

Only then begin Phase 1.

## Handoff Summary for CC

Build order:

1. ADR.
2. Mobile benchmark.
3. DB/API skeleton disabled by default.
4. Mobile proof generation behind flag.
5. Arweave per-vote publishing.
6. Public verification page.

Red lines:

- No Helios.
- No custom ceremony.
- No server-side proving.
- No public rollout until cross-tier uniqueness is solved.
- No "verifiable tally" claim unless per-vote proof records are public and recountable.

## Phase 0 Spike Result (2026-05-22)

**Status: STOP — Mobile prover is an unresolved dependency.**

CC investigated Expo SDK 54 / React Native 0.81 compatibility:

| Component | Result |
|---|---|
| `@semaphore-protocol/proof@4.14.2` | npm installable, but depends on `snarkjs@0.7.5` which requires Node.js `fs`/`os`/`path`/`readline` — not available in React Native |
| Mopro | No npm package. Rust SDK requiring native compilation. No Expo plugin exists. |
| `react-native-snarkjs` | Stale (2021), 43.6 MB, GPL-3, incompatible with RN 0.81 |
| Expo Go | NOT POSSIBLE — native modules required |
| Dev Client | REQUIRED for any ZK proving route |

**Decision:** NEA-249 implementation paused before Phase 1. No product code changed.

**Next required step:** Separate architecture plan for Mopro native Expo Module integration — this is a non-trivial native build effort (Rust toolchain, JNI/NDK, Expo Module API).

**ADR should mark:** Mobile prover as unresolved dependency. Website/FAQ wording stays "roadmap/planned".

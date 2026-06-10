# GH#112 - Gate 0 Diagnosis

Date: 2026-06-11
Status: Gate 0 fixture export available on S10; no production implementation

## Scope

This documents what is known before starting ZK V2 production integration.

The first version of this document was read-only. A follow-up mobile diagnostic utility now exports the deterministic self-test fixture from the S10.

No API, DB, mobile voting path, Arweave, deploy, or feature flag was touched.

## Mobile Proof Payload Shape

Current native module surface:

- `apps/mobile/modules/semaphore-react-native/src/index.ts`
- `apps/mobile/modules/semaphore-react-native/android/src/main/java/expo/modules/semaphore/ProofModule.kt`

The exported TypeScript API is:

```ts
generateSemaphoreProof(
  identity: Identity,
  group: Group,
  message: string,
  scope: string,
  treeDepth: number,
): Promise<string>

verifySemaphoreProof(proof: string): Promise<boolean>
```

Android bridges to the Mopro UniFFI binding:

```kotlin
generateSemaphoreProof(
  identity: Identity,
  group: Group,
  message: String,
  scope: String,
  merkleTreeDepth: UShort,
): String

verifySemaphoreProof(proof: String): Boolean
```

Current conclusion:

- The mobile module returns an opaque proof `string`.
- The local self-test only measures `proof.length`; it does not parse the string.
- We do not yet know whether the string is JSON, packed public signals, or a Mopro-specific serialized proof.
- Server integration must not assume shape until a real S10 self-test fixture is captured and parsed.

## Server Verifier Status

Current API code has no Semaphore/Groth16 verifier dependency or endpoint.

Observed from local search:

- No existing `semaphore`, `groth16`, `snark`, or `publicSignals` verifier module in `apps/api`.
- Existing vote uniqueness is Tier 1-specific:
  - `CitizenVote.nullifier_hash`
  - `UNIQUE(nullifier_hash, bill_id)`
- Existing ZK-related mobile code is self-test/status only; production voting still uses Ed25519/HMAC.

Current conclusion:

- Gate 0 must first select and test a server verifier compatible with the exact native proof string.
- A server fixture test should be written before any endpoint or migration.

## Fixture Required Before Code

Capture from S10 self-test or a dedicated local fixture screen:

- message
- scope
- tree depth
- group members / commitments used for the test group
- Merkle root if available from the native group API
- proof string exactly as returned by `generateSemaphoreProof`
- expected verification result

The fixture must use deterministic test identities only, never a real voter identity.

Current status:

- The existing self-test now exposes a `fixture` object after successful local verification.
- The S10 shows `Κοινοποίηση Gate 0 fixture` after a successful `Έλεγχος Prover`.
- Android share sheet displays the exact JSON fixture, including the opaque proof string.
- The captured fixture is diagnostic test data only and is not submitted to Ekklesia automatically.

## Offline Verifier Compatibility

The exported S10 fixture was extracted locally to `/tmp/gh112-s10-fixture.json` and tested outside the repo in a temporary Node project.

Temporary verifier package:

- `@semaphore-protocol/proof@4.14.2`

Native proof mapping:

```ts
{
  merkleTreeDepth: nativeProof.merkle_tree_depth,
  merkleTreeRoot: nativeProof.merkle_tree_root,
  message: nativeProof.message,
  nullifier: nativeProof.nullifier,
  scope: nativeProof.scope,
  points: nativeProof.points,
}
```

Observed result:

- `verifyProof(mappedS10Fixture) === true`
- `verifyProof({...mappedS10Fixture, message: wrongMessage}) === false`

Current conclusion:

- The Android native Mopro proof format is compatible with the official Semaphore JS verifier after a simple snake_case -> camelCase mapping.
- No verifier dependency has been added to the repo yet.
- Production/server integration still needs an explicit decision about whether the FastAPI backend should:
  - call a small internal Node verifier service,
  - embed a JS verifier through a controlled worker,
  - or use a Python/Rust verifier with matching artifacts.

Do not silently add `@semaphore-protocol/proof` to the mobile app or API image without reviewing bundle size, Docker/runtime implications, artifact source, and worker lifecycle.

## Immediate Gate 0 Tasks

1. Choose the production server verifier architecture.
2. Add a server test that verifies the S10 fixture and rejects:
   - wrong message,
   - wrong scope,
   - wrong group/root,
   - malformed proof.
3. Only after this, design DB/API integration.

## Stop Conditions

Do not proceed beyond Gate 0 if:

- The proof string cannot be verified outside the Android native module.
- The server verifier needs a different proof/public-signal format than mobile emits.
- The only available cross-tier uniqueness design links Tier 1 identity to public ZK vote records.
- The group-management model cannot explain inclusion, exclusion, root publication, and revocation.

# GH#112 - Gate 0 Diagnosis

Date: 2026-06-11
Status: Read-only diagnosis, no runtime implementation

## Scope

This documents what is known before starting ZK V2 production integration.

No code was changed for this diagnosis. No API, DB, mobile voting path, Arweave, deploy, or feature flag was touched.

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

## Immediate Gate 0 Tasks

1. Add a temporary developer-only way to export a deterministic self-test proof fixture, or collect it via local debug tooling.
2. Parse the proof string offline and identify its format.
3. Choose a server-side verifier that verifies that exact fixture.
4. Add a server test that verifies the fixture and rejects:
   - wrong message,
   - wrong scope,
   - wrong group/root,
   - malformed proof.
5. Only after this, design DB/API integration.

## Stop Conditions

Do not proceed beyond Gate 0 if:

- The proof string cannot be verified outside the Android native module.
- The server verifier needs a different proof/public-signal format than mobile emits.
- The only available cross-tier uniqueness design links Tier 1 identity to public ZK vote records.
- The group-management model cannot explain inclusion, exclusion, root publication, and revocation.


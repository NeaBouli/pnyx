# ADR: NEA-249 — ZK Voting V2 Semaphore Hybrid

- **Date:** 2026-05-22
- **Status:** Proposed / Blocked before implementation
- **Linear:** NEA-249, NEA-234
- **Blueprint:** `docs/agent-bridge/NEA249_ZK_V2_BLUEPRINT.md`

## Decision

Adopt a Hybrid V2 architecture for ekklesia.gr voting:

- **Tier 1 (unchanged):** Current HMAC-Nullifier-Chain + Ed25519 signatures + aggregate Arweave snapshots. Remains the default production voting path.
- **Tier 2 (new, opt-in):** Semaphore membership proof + per-vote Arweave bulletin board records. Provides individual vote verifiability for opted-in users.

Both tiers coexist. Same voter must not cast both Tier 1 and Tier 2 votes for the same bill.

## Context

NEA-234 researched three approaches:
1. **Helios** — rejected for MVP due to trustee/decryption ceremony complexity
2. **Custom ZK circuits** — rejected; unnecessary when Semaphore solves the exact problem
3. **Semaphore** — selected; proves group membership without revealing identity, prevents double voting via scope-bound nullifiers

Semaphore directly matches the product requirement: anonymous voting with publicly verifiable proofs.

## Mobile Prover Status

**Mobile prover feasibility is resolved for Android. Production ZK voting remains gated.**

Phase 0 benchmark spike (2026-05-22) found:
- `@semaphore-protocol/proof@4.14.2` depends on `snarkjs@0.7.5` which requires Node.js `fs`/`os`/`path`/`readline` — not available in React Native
- Mopro (Rust SDK) has no npm package; requires native JNI/NDK compilation with no existing Expo plugin
- `react-native-snarkjs` is stale (2021), 43.6 MB, GPL-3, incompatible with RN 0.81
- Expo Go cannot be used; Dev Client with native modules is required

This section records the original blocker and the resolution path. Product integration can proceed only through GH#112 gates; the production voting path remains disabled.

Update 2026-06-10:
- `zkmopro/SemaphoreReactNative` now exists as a React Native / Expo module wrapper for Semaphore v4.
- It is not published to npm as of this check; installation is documented via GitHub dependency only.
- Repository has no release tag and only a small commit history, so production bundling must pin a commit and pass a native Android build before feature activation.
- Ekklesia added a runtime capability adapter that detects bundled native modules `Identity`, `Group`, and `Proof`.
- Production ZK remains disabled by feature flag until a pinned native prover build is verified on device.

Update 2026-06-11:
- Android native proving is feasible on the S10 test device.
- Added an app-local Semaphore self-test that generates and verifies a test proof on-device without creating a vote or sending data to Ekklesia.
- The vendored Android wrapper sets `TMPDIR` to app-owned storage before proof generation, allowing `semaphore-protocol` to download/cache its zkey artifact in a writable directory.
- S10 verification passed: native proof generated and verified locally (`depth 16`, two-member test group, proof approximately 1 KB, first run after artifact setup ~2.3s).
- Production ZK voting is still disabled by feature flag. This update proves mobile prover feasibility only; backend verification, group registry, Arweave bulletin board records, and a canary rollout remain separate product-integration work.

## Explicit Non-Goals (Current State)

- No production voting integration
- No DB migrations
- No API endpoints
- No Arweave writes
- No website/FAQ claims saying "in build" — wording stays "roadmap/planned"
- No Helios
- No custom ZK circuit or trusted setup ceremony
- No server-side proving
- No mandatory ZK mode for any user

## Trust Assumptions (When Implemented)

- Security depends on PSE Semaphore trusted setup ceremony
- Artifact set: `semaphore-v4-depth-24-pse-44690d9` (pinned commit)
- Ekklesia does not run its own ceremony
- This must be documented publicly on the ZK wiki page

## Verifiability Claim (When Implemented)

> A public verifier can check that each published ZK vote was cast by some member of the verified voter group, that the same Semaphore identity did not vote twice for the same bill/scope, and that the public tally can be recomputed from the published anonymized vote records.

It does **not** prove device integrity, enrollment perfection, or individual Tier 1 vote verifiability.

## Next Steps

1. **Mopro Native Expo Module Feasibility** — complete for Android S10 self-test; production builds still require pinned dependency review
2. **Cross-Tier Uniqueness Design** — selected Gate-0 direction: private per-scope tier lock at ZK opt-in / Merkle-root construction time
3. **Phase 1** — DB schema + API skeleton, disabled by default, only after the GH#112 verifier and group-management design is reviewed

## References

- Blueprint: `docs/agent-bridge/NEA249_ZK_V2_BLUEPRINT.md`
- Semaphore docs: https://docs.semaphore.pse.dev/
- Mopro docs: https://zkmopro.org/docs/sdk/overview/
- PSE artifacts: `privacy-ethereum/snark-artifacts@44690d9`

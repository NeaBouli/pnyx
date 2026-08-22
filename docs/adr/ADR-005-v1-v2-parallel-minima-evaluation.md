# ADR-005: Keep V1 stable while evaluating a parallel Minima-based V2

Date: 2026-08-23
Status: Proposed
Tracking: GH#216-GH#223
Architecture: `docs/architecture/EKKLESIA_V2_MINIMA.md`

## Context

Ekklesia V1 is an active privacy-first platform with production web, API,
Android, forum, Ed25519/nullifier voting, guarded Semaphore voting and public
aggregate publication. A future platform generation should evaluate Minima for
edge execution, Maxima transport and sparse Layer 1 settlement without putting
that working baseline at risk.

The official Minima material establishes useful primitives but does not prove
the delivery, compatibility and resource assumptions required for a voting
system. In particular, the review found no official evidence that the pinned
KISS VM can verify Ekklesia Ed25519 signatures or Semaphore/Groth16 proofs.
Maxima delivery behavior under offline and partition conditions also requires
measurement.

## Decision

1. V1 remains the maintained production baseline and is never modified merely
   to facilitate V2 research.
2. V2 is evaluated as a separate hybrid architecture:
   - Maxima is a candidate transport;
   - independent off-chain components verify and aggregate votes;
   - Minima Layer 1 anchors sparse deterministic roots;
   - durable public records remain independently available and verifiable.
3. Phase 1 consists only of synthetic, local/test-network PoCs on pinned official
   Minima release 1.0.49.
4. No V2 product repository is created until Gate G1 passes. The recommended
   implementation boundary after G1 is a separate repository with independent
   CI, releases and deployment.
5. V2 cannot replace V1 before parity, migration, rollback, external
   security/privacy review and explicit release gates all pass.

## Rejected for this phase

- Big-bang migration or direct replacement of V1.
- Individual votes or raw nullifiers on Minima Layer 1.
- Assuming Maxima provides reliable offline delivery without tests.
- Assuming Minima native signature checks support Ed25519 or Groth16.
- Depending on Omnia while official node documentation marks it as coming soon.
- Introducing tokens, incentives, PnyxCoin or treasury logic into V2.0.
- Replacing Discourse as part of the first V2 release.
- Sharing V1 database migrations, runtime modules or deployment workflows.

## Consequences

- V2 progress is slower at first because protocol assumptions become measured
  gates instead of implementation guesses.
- V1 can continue receiving security and operational maintenance independently.
- The initial V2 trust model is likely anchored and publicly auditable rather
  than fully on-chain verified.
- A No-Go result in Phase 1 ends the Minima track without a V1 rollback or
  production cleanup.
- Public communication must distinguish Minima base-layer hash/WOTS claims from
  Ekklesia system-wide cryptographic properties.

## Revisit conditions

Revisit this ADR after GH#217-GH#219 provide reproducible results. Any move from
`Proposed` to `Accepted` requires reviewed answers for identity/proof continuity,
aggregator governance, durable data availability and the separate-repository
boundary.

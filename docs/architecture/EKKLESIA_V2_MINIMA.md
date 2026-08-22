# Ekklesia Platform V2 on Minima

Status: Phase 0 architecture plan; no implementation or rollout authorization
Last verified: 2026-08-23
Tracking: [GH#216](https://github.com/NeaBouli/pnyx/issues/216)

## 1. Purpose and boundary

This document evaluates a future Ekklesia platform generation built around
Minima. It does not replace the current platform and does not authorize product
code, migration, deployment, token issuance or production-chain activity.

The current Ekklesia platform is **V1**. V1 remains the maintained production
baseline, including its current Ed25519, nullifier, Semaphore, Arweave,
Discourse, API, web and mobile paths. V2 is a separate parallel track. A V2
rollout may be considered only after all gates in this document pass.

## 2. Feasibility verdict

**Conditionally feasible as a hybrid architecture.** The evidence does not
support a direct on-chain port of the current voting protocol.

The working hypothesis is:

- Minima Layer 1 stores only sparse, deterministic commitments such as bill,
  accepted-vote-set, nullifier-set and tally roots.
- Maxima is evaluated as a transport for signed or proven vote envelopes, but
  only after offline delivery, retries, acknowledgements, duplicates, ordering
  and partition behavior are measured.
- Ed25519 and Semaphore/Groth16 verification remain off-chain unless a pinned
  Minima runtime demonstrates native verification and that design passes an
  independent cryptography review.
- An append-only public bulletin board allows independent recomputation of every
  anchored root without publishing phone numbers, identity records, secrets,
  raw eligibility data or cross-scope identifiers.
- Durable publication remains chain-agnostic. Minima full-node pruning means
  Layer 1 roots alone are not a durable store for the corresponding records.

This is not yet a Go decision for implementation. Phase 1 must first turn the
unverified assumptions into measured facts.

## 3. V1 invariants

V2 may not weaken or silently reinterpret these V1 properties:

1. No account, email or cookie is required for the anonymous citizen path.
2. Phone numbers are transient verification inputs and are not persisted.
3. Private Ed25519 keys and Semaphore identity secrets remain client-side.
4. Nullifiers are domain- and scope-separated and prevent duplicate voting.
5. A missing, revoked or unverifiable identity fails closed.
6. Individual Tier-1 votes, phone-derived identifiers and private identity
   bridge data are never published to Arweave or another public ledger.
7. Public ZK artifacts contain only verifier inputs for eligible public scopes,
   with minimum-group safeguards.
8. Compass data remains local to the user device.
9. HLR network status is not described as proof of SIM possession, identity,
   residence, citizenship or electoral eligibility.
10. V1 maintenance, CI, releases, rollback tags and incident response continue
    independently of V2.

## 4. Verified Minima capabilities and limits

The Phase 0 review used the official Minima documentation repository at commit
`d1e297d637cea2ab3f837831785f66903f887594` and the official Minima node release
`1.0.49` published on 2026-08-17.

| Area | Verified capability | Consequence for V2 |
|---|---|---|
| Layer 1 | UTxO-style transactions, KISS VM scripts, state values, MMR proofs and native tokens | Suitable for compact roots and constrained state transitions, not bulk vote storage |
| KISS VM | Hashing, proof checks, native signature checks, multisig and input/output validation | No official evidence was found that its signature operation accepts Ekklesia Ed25519 or that it can verify Semaphore BN254 pairings; both remain unproven |
| Maxima | Signed, encrypted, point-to-point messages relayed through Maxima hosts, paid through TxPoW work rather than a stated message fee | Candidate transport only; official material reviewed does not define all delivery guarantees needed for voting |
| MiniDapps/MDS | Local HTML/CSS/JavaScript apps, background `service.js`, local H2-backed SQL, node events, files, network calls and READ/WRITE permissions | A useful edge UI/service host, with permission and maturity risks that need a threat review |
| Mobile node | Android full node is officially supported; default nodes prune old transaction history and keep relevant proofs | Edge use is plausible, but background execution, battery, bandwidth and storage must be measured on representative devices |
| Archive/Mega nodes | Different server-oriented retention and public-hosting capabilities | Independent archival and recovery infrastructure is still needed |
| Omnia | Current official node-type documentation labels Omnia as "Coming soon" | V2.0 must not depend on Omnia |
| Quantum resistance | The official whitepaper attributes Minima base-layer security to hash functions and Winternitz one-time signatures | This is a Minima protocol claim, not a property inherited by Ed25519, Semaphore, devices, MiniDapps or Ekklesia as a whole |

The exact transaction fee/burn behavior, Maxima offline-store behavior, message
size limits, stable ordering and current public network capacity were not proven
from the reviewed official material. They are Phase 1 measurements, not assumed
facts.

## 5. Target separation of concerns

```text
Bill sources -> canonical bill adapter -> bill document + bill root
                                             |
V2 client -> eligibility/proof -> vote envelope -> Maxima transport
                                             |
                         independent aggregators (2 or more)
                              |               |
                     append-only boards   signed receipts
                              |               |
                     deterministic root builder
                              |
             Minima L1 settlement: bill/vote/nullifier/tally roots
                              |
          independent verifier + durable public record availability
```

### Client and MiniDapp

- Canonicalizes the bill scope and vote envelope.
- Creates a scope-bound nullifier and an Ed25519 signature or Semaphore proof.
- Keeps secrets and retry state locally.
- Requires user confirmation for settlement-affecting operations. A MiniDapp
  must not require unattended WRITE permission merely for convenience.

### Bill adapter

- Consumes the existing public Parliament and Diavgeia outputs through a
  versioned read contract rather than sharing the V1 database.
- Produces canonical JSON and a deterministic bill root.
- Keeps source provenance, lifecycle state and jurisdiction namespace.

### Eligibility and proof

- Is a replaceable interface, not part of transport or settlement.
- Must resolve the open choice between Argon2id continuity and a
  Semaphore-first V2 identity.
- Must preserve revocation, recovery, one-person/one-scope uniqueness and
  cross-scope unlinkability.

### Vote transport

- Carries a versioned envelope, not a database row.
- Uses explicit expiry, client nonce, scope, epoch and payload hash.
- Does not treat Maxima ordering or delivery as reliable until GH#217 proves it.
- Uses signed receipts, local retry and idempotent processing.

### Aggregation and bulletin board

- At least two independently operated aggregators verify envelopes and append
  accepted records to separately hash-chained boards.
- Roots are deterministic and reproducible by a separate reference verifier.
- Divergent roots, omissions and equivocation become public incidents rather
  than being silently reconciled.

### Settlement

- Anchors only canonical roots and minimal epoch metadata.
- Does not place individual votes, raw nullifiers or identity material on-chain.
- Uses an explicitly governed M-of-N transition only after key rotation,
  emergency and federation rules are reviewed.

### Discussion and federation

- Discourse remains the V1 discussion system in V2.0.
- Municipality and country federation use isolated namespaces and policies.
- Replacing Discourse or building fully P2P deliberation is a later decision,
  not part of the first V2 release.

## 6. Candidate vote envelope

The exact encoding requires an ADR. The minimum conceptual fields are:

```text
protocol_version
jurisdiction_id
vote_scope_id
epoch_id
choice_commitment
nullifier_commitment
client_nonce
created_at
expires_at
proof_type
proof_or_signature
payload_hash
```

The canonical encoding must be language-independent, reject duplicate fields
and ambiguous Unicode, use domain-separated hashes and have shared conformance
vectors. Transport metadata must never be incorporated into identity or vote
linkage.

## 7. Delivery and reconciliation model

Until GH#217 is complete, the only acceptable design assumption is an
application-level at-least-once protocol:

1. The client persists an encrypted pending envelope locally.
2. It sends the same immutable envelope to at least two aggregators.
3. Each aggregator validates schema, expiry, proof and nullifier before append.
4. Each returns a signed receipt over the envelope hash and board position.
5. Retries use the same envelope hash and are idempotent.
6. Ordering is derived from settlement epochs, never message arrival order.
7. A client reports success only after the configured receipt threshold.
8. Before settlement, aggregator boards are cross-checked; unexplained
   divergence blocks the epoch.

This model still leaks transport timing and contact relationships to involved
nodes. A privacy review must quantify that leakage before G3.

## 8. Threat and privacy model

| Threat | Required control |
|---|---|
| Aggregator censorship or omission | Multiple independent recipients, signed receipts, public boards and divergence alarms |
| Aggregator equivocation | Hash-chained records, independently signed epoch manifests and conflicting-root evidence |
| Replay or duplicate delivery | Scope-bound nullifier, immutable envelope hash, client nonce, expiry and idempotent append |
| Cross-scope linkage | Domain separation, no persistent public identity key and privacy tests across jurisdictions/scopes |
| Small-group deanonymization | Conservative publication thresholds, delayed/batched settlement and explicit timing review |
| Maxima metadata leakage | Minimize contact metadata, compare permanent and rotating addresses, avoid identity-bearing routing labels |
| Compromised MiniDapp | READ by default, explicit transaction approval, reproducible signed artifacts and provenance checks |
| Client rollback or lost queue | Encrypted local journal, deterministic retries and receipt reconciliation |
| Minima pruning/data loss | Durable bulletin-board publication separate from sparse Layer 1 roots |
| Chain reorganization | Finality policy and reorg tests before an epoch is called settled |
| Sybil enrollment | Separate eligibility design; TxPoW is spam resistance, not proof of one person |
| Cryptographic overclaim | Describe Minima hash/WOTS properties precisely; never call Ekklesia quantum-safe without a system-wide review |

## 9. Parallel repository strategy

Phase 0 documentation and tickets remain in `NeaBouli/pnyx`. After G1, the
recommended implementation boundary is a separate repository. That repository
may consume versioned public schemas and synthetic fixtures, but it must not:

- import V1 application modules directly;
- share V1 database migrations or deployment workflows;
- modify V1 release channels or feature flags;
- require production credentials or snapshots;
- claim compatibility before conformance tests pass.

The first implementation commit should contain only repository structure,
pinned local Minima tooling, protocol schemas, test vectors and CI. Product
features begin only after the architecture ADRs are approved.

## 10. Phased implementation plan

### Phase 0 - architecture and evidence map

Deliverables:

- this architecture plan and ADR-005;
- official-source matrix and explicit unknowns;
- epic GH#216 and bounded work packages.

Gate G0: documentation review accepts the hybrid hypothesis and V1 boundary.

### Phase 1 - synthetic Minima reality lab

Work packages:

- GH#217: Maxima delivery and Android node resource measurements;
- GH#218: transport envelope, receipts, retry and deduplication;
- GH#219: KISS root-anchor and independent verifier.

All tests use generated keys, synthetic votes and local/test networks. No HLR,
real identity, real bill, production endpoint or token is permitted.

Gate G1: reproducible results close every critical transport/settlement unknown
or produce a No-Go decision.

### Phase 2 - protocol decisions and isolated skeleton

Work packages:

- GH#220: identity, proof and key compatibility ADR;
- GH#221: bulletin board, federation and data availability specification;
- GH#222: isolated repository, pinned toolchain and CI.

Gate G2: independent architecture review confirms no V1 coupling and validates
the protocol test vectors.

### Phase 3 - privacy-preserving functional path

- Implement bill adapter, proof interface, transport, board, aggregation,
  settlement and independent verification in that order.
- Add adversarial tests for censorship, duplication, replay, partitions,
  malformed proofs, root divergence, key rotation and recovery.
- Run mobile and edge performance tests continuously.

Gate G3: independent security, cryptography and privacy review passes with no
open high/critical finding.

### Phase 4 - V1 parity and migration rehearsal

GH#223 owns the parity matrix. At minimum it covers:

- national, regional and municipal bill lifecycle;
- eligibility, revocation and recovery;
- Tier-1 and ZK vote behavior and duplicate prevention;
- results, representativity, divergence and public verification;
- forum links, notifications, localization and accessibility;
- admin/monitoring, incident response and data export;
- chain/Maxima outage behavior and durable availability.

Gate G4: all agreed parity tests pass and repeated migration/rollback drills on
sanitized disposable data show no loss, double vote or identifier linkage.

### Phase 5 - staged release decision

Only after G0-G4:

- legal/DPIA and operational readiness reviews;
- limited opt-in canary with independent monitoring;
- public protocol, verifier and rollback documentation;
- explicit owner release approval.

Gate G5 is approval to plan a rollout, not permission to retire V1. V1 remains
available until a separate, reversible retirement decision.

## 11. V2.0 non-goals

- Token, PnyxCoin, incentive or treasury economics.
- Reliance on Omnia.
- Mandatory Minima full node for every Ekklesia user.
- On-chain individual votes or public nullifier lists.
- Replacing Discourse.
- Migrating or rewriting V1 data during research and PoC phases.
- Claims of fully trustless or quantum-safe voting without direct proof.

## 12. Open architecture decisions

1. Argon2id continuity or Semaphore-first V2 eligibility.
2. Off-chain Ed25519 continuity or a reviewed Minima-native V2 key model.
3. Exact aggregator count, operator independence and M-of-N governance.
4. Durable board publication: continued Arweave dual publication or another
   reviewed store.
5. Finality depth and epoch cadence.
6. Receipt threshold and behavior when aggregators disagree.
7. Mobile distribution: MiniDapp, companion app, gateway or optional local node.
8. Public terminology for anchored versus directly verified data.

No production code starts before decisions 1-4 have approved ADRs and the Phase
1 evidence is available.

## 13. Risk register

| Risk | Severity | Gate |
|---|---|---|
| Maxima delivery assumptions fail under offline/partition conditions | High | G1 |
| Ed25519 or Groth16 cannot be verified in the pinned KISS runtime | High | G1/G2 |
| Aggregator trust is presented as direct on-chain verification | High | G0/G3 |
| Mobile node drains battery, data or storage | High | G1 |
| Public artifacts enable timing or cross-scope linkage | High | G3 |
| Pruning makes underlying vote records unavailable | High | G2 |
| Small ecosystem or incompatible upstream change | Medium | Every pinned-release update |
| Omnia remains unavailable | Low for V2.0 | Removed as dependency |

## 14. Official sources

- Minima developer overview: https://github.com/minima-global/docs/blob/main/content/docs/development/index.mdx
- Maxima message flow: https://github.com/minima-global/docs/blob/main/content/docs/learn/maxima-messaging.mdx
- Maxima overview: https://github.com/minima-global/docs/blob/main/content/docs/learn/maxima-about.mdx
- Maxima location service: https://github.com/minima-global/docs/blob/main/content/docs/learn/maxima-mls.mdx
- MiniDapp events: https://github.com/minima-global/docs/blob/main/content/docs/development/minidapp-events.mdx
- MDS JavaScript API: https://github.com/minima-global/docs/blob/main/content/docs/development/minidapp-mdsjs.mdx
- MiniDapp background service: https://github.com/minima-global/docs/blob/main/content/docs/development/minidapp-servicejs.mdx
- MiniDapp permissions: https://github.com/minima-global/docs/blob/main/content/docs/user-guides/mds/minidapp-permissions.mdx
- KISS VM functions: https://github.com/minima-global/docs/blob/main/content/docs/development/contracts-kissvm.mdx
- Token scripts: https://github.com/minima-global/docs/blob/main/content/docs/development/contracts-tokenscripts.mdx
- Node types and pruning: https://github.com/minima-global/docs/blob/main/content/docs/run-a-node/node-types.mdx
- Android node guidance: https://github.com/minima-global/docs/blob/main/content/docs/run-a-node/android.mdx
- Minima whitepaper v11: https://docs.minima.global/minima_pdfs/Minima_Whitepaper_v11.pdf
- Official Minima node repository: https://github.com/minima-global/Minima
- Pinned Phase 0 release: https://github.com/minima-global/Minima/releases/tag/1.0.49

## 15. Ticket map

- GH#216 - V2 epic and gates
- GH#217 - Maxima and mobile-node reality lab
- GH#218 - synthetic transport and receipts
- GH#219 - KISS root-anchor PoC
- GH#220 - identity/proof/key ADR
- GH#221 - bulletin board, federation and availability
- GH#222 - isolated repository and CI after G1
- GH#223 - parity, migration, rollback and rollout gate

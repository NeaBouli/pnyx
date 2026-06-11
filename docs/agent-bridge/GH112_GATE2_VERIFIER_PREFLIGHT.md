# GH#112 Gate 2 Verifier Preflight

Date: 2026-06-11
Status: Verifier core implemented, disabled; no endpoint or production activation

## Threat Model

Gate 2 introduces server-side verification for Semaphore proofs. The verifier
must not weaken the existing API image, mutate existing Tier 1 vote behavior, or
accept production ZK votes before the canary gates.

New attack surfaces to avoid:

- vulnerable verifier dependency chain inside the FastAPI production image
- verifier endpoint that writes votes while `ZK_VOTING_ENABLED=false`
- public proof records that include identity bridge fields
- artifact drift between mobile prover and server verifier

## Preflight Findings

The S10 Gate-0 fixture is still available at `/tmp/gh112-s10-fixture.json`.

Fixture shape:

- `treeDepth`: 16
- `groupSize`: 2
- native proof string length: 1038 bytes
- native proof fields:
  - `merkle_tree_depth`
  - `merkle_tree_root`
  - `message`
  - `nullifier`
  - `points`
  - `scope`

Isolated dependency check in `/tmp/gh112-verifier-preflight`:

- Package tested: `@semaphore-protocol/proof@4.14.2`
- Direct dependencies include:
  - `@zk-kit/artifacts@2.0.1`
  - `ethers@6.13.4`
  - `snarkjs@0.7.5`
- `npm audit` result for isolated install:
  - 6 moderate
  - 8 high
  - 0 critical
- Main high-risk chain includes `snarkjs`, `circomkit`, `jsonpath`,
  `underscore`, and `ws`.

Decision:

- Do not add `@semaphore-protocol/proof` to the FastAPI/API production image.
- Do not add a Node worker inside the API image.
- Do not add a Node sidecar unless a later review explicitly accepts the
  dependency footprint and operational surface.

## Recommended Gate 2 Architecture

Preferred path:

1. Use a small Python or Rust Groth16 BN254 verifier.
2. Pin the Semaphore v4 depth-16 verification key extracted from
   `@semaphore-protocol/proof@4.14.2`.
3. Store the verification key and checksum as a reviewed artifact.
4. Add a startup checksum guard before any endpoint can verify proofs.
5. Add tests that verify the S10 fixture and reject mutated message, scope,
   root, nullifier, and malformed proof payloads.

Candidate implementation options:

- Python: evaluate `py_ecc` first. It is not currently in `apps/api/.venv`.
- Rust: evaluate an isolated verifier binary/FFI if Python is too slow or
  incompatible.

## Stop Conditions

Stop before endpoint work if:

- the selected verifier cannot validate the exact S10 fixture
- artifact checksums cannot be pinned
- verifier dependencies add high/critical findings to the production API image
- the verifier requires identity lookup during ZK vote verification
- a public record would include `tier_guard_hash`, identity ids, phone/IP/HLR
  metadata, Tier-1 nullifier, Tier-1 public key, or Semaphore identity secrets

## Next Safe Step

Evaluate `py_ecc` in an isolated temporary environment against the S10 fixture
and extracted depth-16 verification key. If it matches the JS verifier, only
then design a small API verifier module behind `ZK_VOTING_ENABLED=false`.

## 2026-06-11 Follow-Up

The `py_ecc` path was tested successfully:

- Temporary venv: `/tmp/gh112-pyecc-venv`
- Package: `py-ecc==8.0.0`
- Verification key SHA-256:
  `6ef3f6ae5ad8c50982b8c2ed5ec9626d7f92881fce3488ac2b8089c6edca2319`
- S10 fixture SHA-256:
  `6f23a15d814f26cadb3be2d2166dfb599044536bfc9771b48ba86ee244449c10`
- Result:
  - real S10 fixture verifies: `True`
  - mutated message rejects: `False`

Implemented in repo:

- `apps/api/services/zk_groth16_verifier.py`
- `apps/api/data/semaphore-v4-depth16-vkey.json`
- `apps/api/tests/fixtures/gh112_s10_fixture.json`
- `apps/api/tests/services/test_zk_groth16_verifier.py`

Still not implemented:

- no verifier endpoint
- no production migration
- no vote acceptance
- no Arweave publication
- no `ZK_VOTING_ENABLED` activation

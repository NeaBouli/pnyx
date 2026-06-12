# GH#112 - Semaphore Merkle Root Preflight

Date: 2026-06-12
Status: Research finding only; no runtime implementation

## Purpose

GH#112 needs a server-side way to construct or verify the Semaphore group root
for a voting scope. This must match the native Android Mopro/Semaphore prover.

This document records the preflight result so the production implementation does
not accidentally introduce a non-Semaphore placeholder tree.

## Non-Negotiable

Do not implement a SHA-based Merkle placeholder for Semaphore groups.

Semaphore roots must use the same LeanIMT/Poseidon semantics and member encoding
as the prover. A SHA tree may look like a Merkle tree, but it will not verify
against Semaphore proofs and would create a false security claim.

## Fixture

Source fixture:

- `apps/api/tests/fixtures/gh112_s10_fixture.json`
- Generated on S10 with the native Android prover.
- Proof verifies with the current Python Groth16 verifier.

Relevant fixture values:

- `treeDepth`: 16
- member count: 2
- proof `merkle_tree_root`:
  `15121792151885279708122163619725961282935290234708064624604473982083152177808`

## Official JS Group Preflight

Isolated temp directory:

- `/tmp/gh112-root-preflight`

Package tested:

- `@semaphore-protocol/group@4.14.2`

Direct dependencies:

- `@zk-kit/lean-imt@2.2.4`
- `@zk-kit/utils@1.3.0`
- `poseidon-lite@0.3.0`

Isolated `npm audit` result:

- 0 critical
- 0 high
- 5 moderate

This audit result belongs only to the temporary preflight install. No dependency
was added to the production repo or API image.

This is a different and smaller footprint than `@semaphore-protocol/proof`, which
previously pulled in a larger `snarkjs` chain and was rejected for the API image.

## Encoding Finding

The official JS `Group` reproduces the S10 proof root only when the native
`memberHex` bytes are interpreted little-endian before converting to `BigInt`.

Result matrix:

| Input interpretation | Root | Matches proof root |
|---|---:|---|
| `memberHex` as big-endian `BigInt` | `14244134284572064610767649596322166298766237096084046740251276974170185197454` | No |
| `memberHex` as little-endian bytes to `BigInt` | `15121792151885279708122163619725961282935290234708064624604473982083152177808` | Yes |

The fixture `groupRootHex` also matches the proof root when interpreted
little-endian:

```text
groupRootHex LE decimal =
15121792151885279708122163619725961282935290234708064624604473982083152177808
```

## Important Open Detail

`@semaphore-protocol/group` reports a dynamic group depth of `1` for the two
members in the fixture, while the proof fixture carries `treeDepth: 16`.

The current verifier accepts the S10 proof with the depth-16 verification key.
Before production root publication, document exactly how Semaphore v4/Mopro maps
the dynamic LeanIMT root into the depth-specific proof artifact.

## Rejected Paths

Rejected for production root construction:

- SHA or SHA256 Merkle trees.
- Ad-hoc Python Poseidon packages that cannot be imported or are Python-2-era
  code.
- Any implementation that does not reproduce the S10 fixture root exactly.

## Candidate Paths

Acceptable next candidates:

1. A small reviewed Python implementation of the exact Semaphore
   LeanIMT/Poseidon path, tested against the S10 fixture and additional vectors.
2. A tightly scoped root-builder worker using `@semaphore-protocol/group`, only
   if the dependency footprint and operational boundary are explicitly accepted.
3. A Rust/native helper matching the mobile Semaphore/Mopro implementation.

## Stop Conditions

Stop before production root publication if:

- the root builder does not reproduce the S10 fixture exactly,
- member byte order is ambiguous,
- the dynamic-depth versus depth-16 artifact relationship is not documented,
- dependencies introduce high or critical findings into the production API image,
- root publication would expose identity bridge data.

## Decision

Root construction remains blocked on a reviewed Semaphore-compatible
LeanIMT/Poseidon implementation. The group registry helper may list commitments,
but it must not publish roots until this preflight is resolved.

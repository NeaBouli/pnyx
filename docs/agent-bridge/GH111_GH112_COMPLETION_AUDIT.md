# GH#111 / GH#112 Completion Audit

Date: 2026-06-17
Runtime/code HEAD audited: `858be23`
Audit bridge update: current document revision
Server bridge checkout after audit: fast-forward after commit, no rebuild

This document records the current completion boundary for the two sensitive
identity/ZK workstreams. It is intentionally evidence-based: a task is only
marked complete when the current production state proves it.

## Executive Summary

| Workstream | Status | Completion Claim |
|---|---:|---|
| GH#112 first public ZK scope | PASS | First public scoped rollout is complete for `bill:GR-d4c62ed4`. |
| GH#112 staged/global follow-up | OPEN | Global rollout and ZK Arweave publication remain gated/off. |
| GH#111 Nullifier v2 canary | PASS | Real S10/HLR canary completed in production. |
| GH#111 Nullifier v2 activation | PASS | Production KDF is `v2`; post-verify compare is clean. |

## GH#112 Evidence

Requirement: a first public ZK scope must accept a real ZK vote, expose the
aggregated result, and remain scoped rather than globally enabled.

Authoritative evidence inspected:

- Live result endpoint for `GR-d4c62ed4`:
  - `total_votes=1`
  - `tier1_vote_count=0`
  - `zk_vote_count=1`
  - `yes_count=1`
  - `results_hidden=false`
- Production flags on the server:
  - `ZK_PRODUCTION_SCOPE_ALLOWLIST=bill:GR-d4c62ed4`
  - `ZK_GLOBAL_ROLLOUT_ENABLED=false`
  - `ZK_ARWEAVE_PUBLICATION_ENABLED=false`
  - `ZK_CANARY_ENABLED=false`
- API health: `status=ok`.
- Audit publication:
  - Bridge commit `2ca8671` was fast-forwarded on the server after evidence
    capture.
  - No container rebuild, runtime flag change, or DB mutation was performed for
    the audit publication.

Verdict: GH#112 first public scoped rollout is complete for the single public
scope `bill:GR-d4c62ed4`.

Boundary: this does **not** prove global ZK rollout. It also does **not** enable
ZK Arweave publication. Those remain explicit staged follow-ups.

## GH#111 Evidence

Requirement: Nullifier v2 production activation must be proven with a real
S10/HLR identity verification path, then compared against a before snapshot.

Authoritative evidence inspected:

- Production flag:
  - `IDENTITY_NULLIFIER_KDF_VERSION=v2`
- Activation package:
  - `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_200157`
  - `package_check.json`: `ok=true`, `blockers=[]`, `warnings=[]`
- Guarded helpers used:
  - `scripts/gh111-prepare-nullifier-v2-window.sh`
  - `scripts/gh111-activate-nullifier-v2-window.sh`
  - `scripts/gh111-postverify-nullifier-v2-window.sh`
- Real S10/HLR result:
  - App verification succeeded and stored a new local key.
  - No phone number, raw nullifier, or private key is recorded in this document.
- Post-verify compare:
  - Mode: `new-registration`
  - Verdict: `ok=true`, `blockers=[]`, `warnings=[]`
  - Before: 17 total / 17 active / 0 revoked / 0 v2 rows.
  - After: 18 total / 18 active / 0 revoked / 1 v2 row.
  - Clean invariants: malformed v2 = 0, v2 without version = 0, version without v2 = 0.
- Monitor:
  - Post-verify monitor once: PASS, 17 checks, no alerts.

Verdict: GH#111 is complete. Decision: keep v2 active.

## Safety Invariants

- Do not roll GH#111 back to v1 unless a concrete production blocker appears.
- Do not record the operator phone number, raw nullifier, or private key in
  Bridge, GitHub, Linear, logs, screenshots, or docs.
- Do not mix GH#111 and GH#112 windows.
- Do not enable global ZK rollout or ZK Arweave publication from this audit.
- Keep production ZK scoped by exact allowlist until a separate rollout review.

## Next Real Step

GH#111 has no remaining activation work. Future identity work should monitor the
v2 invariants during normal operation and treat any malformed/mismatched v2
counter as a T3 issue.

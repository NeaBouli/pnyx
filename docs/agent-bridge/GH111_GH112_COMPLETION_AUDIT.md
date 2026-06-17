# GH#111 / GH#112 Completion Audit

Date: 2026-06-17
Repo HEAD audited: `586d52c`
Server HEAD audited: `586d52c`

This document records the current completion boundary for the two sensitive
identity/ZK workstreams. It is intentionally evidence-based: a task is only
marked complete when the current production state proves it.

## Executive Summary

| Workstream | Status | Completion Claim |
|---|---:|---|
| GH#112 first public ZK scope | PASS | First public scoped rollout is complete for `bill:GR-d4c62ed4`. |
| GH#112 staged/global follow-up | OPEN | Global rollout and ZK Arweave publication remain gated/off. |
| GH#111 Nullifier v2 canary | PREPARED | Runbook, helpers, tests, and preflight package are ready. |
| GH#111 Nullifier v2 activation | NOT COMPLETE | Production KDF is still `v1`; no real HLR/S10 v2 migration has run. |

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

Verdict: GH#112 first public scoped rollout is complete for the single public
scope `bill:GR-d4c62ed4`.

Boundary: this does **not** prove global ZK rollout. It also does **not** enable
ZK Arweave publication. Those remain explicit staged follow-ups.

## GH#111 Evidence

Requirement: Nullifier v2 production activation must be proven with a real
S10/HLR identity verification path, then compared against a before snapshot.

Authoritative evidence inspected:

- Production flag:
  - `IDENTITY_NULLIFIER_KDF_VERSION=v1`
- Latest preflight package:
  - `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_064644`
  - `package_check.json`: `ok=true`, `blockers=[]`, `warnings=[]`
- Bridge state records:
  - 17 active identities.
  - 0 revoked identities.
  - 0 v2 rows before activation.
- Guarded helpers exist:
  - `scripts/gh111-prepare-nullifier-v2-window.sh`
  - `scripts/gh111-activate-nullifier-v2-window.sh`
  - `scripts/gh111-postverify-nullifier-v2-window.sh`

Verdict: GH#111 is prepared, but not complete.

Missing completion evidence:

- Explicit operator window with S10 and real phone/HLR ready.
- `scripts/gh111-activate-nullifier-v2-window.sh activate-v2` using a fresh
  `BACKUP_DIR` and `GH111_OPERATOR_CONFIRM=GH111-ACTIVATE-V2`.
- Real app verification/re-registration while KDF v2 is active.
- Read-only post-verify compare report proving the expected v2 state.
- Keep-v2 or rollback-v1 decision recorded after the compare.
- Bridge/GitHub/Linear update after the real canary result.

## Safety Invariants

- Do not mark GH#111 complete while `IDENTITY_NULLIFIER_KDF_VERSION=v1`.
- Do not infer GH#111 completion from DB/admin-test data. Phone numbers are not
  stored, so the real proof requires the HLR verification path.
- Do not mix GH#111 and GH#112 windows.
- Do not enable global ZK rollout or ZK Arweave publication from this audit.
- Keep production ZK scoped by exact allowlist until a separate rollout review.

## Next Real Step

The next real GH#111 step is an explicit operator canary window:

1. S10 connected and verified account ready.
2. Fresh `scripts/gh111-prepare-nullifier-v2-window.sh`.
3. Confirm `package_check.json` has `"ok": true`.
4. Activate v2 through the guarded helper.
5. Perform real S10 HLR verification.
6. Run the post-verify helper and compare report.
7. Decide keep-v2 or rollback-v1.

Until those steps are done, GH#111 remains prepared, not complete.

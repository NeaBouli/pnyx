# GH#112 Security Review — Semaphore ZK V2 Production Readiness

Date: 2026-06-16
Reviewer: Codex
Scope: backend ZK gates, mobile proof identity handling, Tier-1 lock guard,
public receipt/Arweave policy, tally integration, hidden S10 canary evidence.

## Decision

Semaphore ZK V2 passed its first public scoped production rollout. It remains
**approved only for exact-scope rollout**, not for unconditional global
activation.

Safe activation shape:

- one explicit public vote scope at a time via `ZK_PRODUCTION_SCOPE_ALLOWLIST`
- no `ZK_GLOBAL_ROLLOUT_ENABLED` until a separate global-rollout review
- DB backup immediately before the window
- root publication and receipt publication kept as separate admin actions
- Arweave publication only after receipts exist and the public payload is checked
- ordinary Tier-1 voting remains the default path

## Threat Model

Reviewed against these failure modes:

- accidental global ZK activation
- accepting a proof for the wrong bill, message, root, or vote commitment
- double voting through Tier 1 and ZK
- linking a public ZK receipt back to phone, HLR, Tier-1 nullifier, or identity row
- canary/test objects leaking into public bill lists, forum, landing, or Arweave
- publishing verifier data that is not independently checkable
- cross-scope Semaphore commitment reuse
- stale or unpublished root use
- Arweave claims before actual publication

## Evidence Reviewed

- Hidden S10 canary passed for `bill:ZK-CANARY-001`:
  opt-in, root publish, native proof, server verify, mutated proof rejection,
  accepted canary ZK vote, flags returned off.
- First public scoped rollout passed for `bill:GR-d4c62ed4`:
  S10 proof accepted, public receipt recorded, `zk_vote_count=1`, `total_votes=1`.
  ZK Arweave publication stayed off; receipt remains pending publication.
- Live API status on 2026-06-16:
  `https://api.ekklesia.gr/api/v1/zk/status` returns HTTP 200 and all production,
  canary, root, Arweave, and global rollout flags are `false`.
- Local code review:
  - `apps/api/routers/zk.py`
  - `apps/api/routers/voting.py`
  - `apps/api/services/zk_*`
  - `apps/mobile/src/lib/zk*`
  - ZK tests under `apps/api/tests` and `apps/mobile/src/lib`.

## Findings

### No HIGH or MEDIUM blockers for scoped rollout

The production backend is fail-closed by default and write paths require an
explicit canary scope, explicit production scope allowlist, or a separate global
rollout flag.

`ZK_GLOBAL_ROLLOUT_ENABLED` must remain off until a dedicated global-rollout
review is completed.

### F1 — Cross-scope mobile identity reuse

Severity: fixed during review

Before this review, the mobile app stored one global Semaphore private key. That
was sufficient for the hidden one-scope canary, but not for real multi-bill use:
it could either make commitments linkable across scopes or fail on the server's
global commitment uniqueness guard.

Fix:

- `getOrCreateZkSemaphoreIdentity(voteScopeId)` now supports scope-bound local
  Semaphore identities.
- ZK opt-in and proof generation call it with `bill:<id>`.
- Existing no-scope behavior remains for backwards-compatible local utility use.

Verification:

- `npx vitest run src/lib/zkSemaphoreIdentity.test.ts src/lib/zkCanaryFlow.test.ts src/lib/zkVoteProof.test.ts`
- `npx tsc --noEmit --incremental false`

### F2 — Tier-1 / ZK double-vote guard

Severity: pass

The normal Tier-1 vote path checks the ZK tier lock only when
`ZK_TIER1_GUARD_ENABLED=true`. It uses a row lock on the bill when enabled and
returns a controlled `409` if the same identity already opted into ZK for the
same scope.

Tests cover:

- guard disabled by default
- only literal `true` enables it
- Tier-1 blocked when a matching ZK lock exists
- Tier-1 unchanged when guard is disabled
- correction path also respects the ZK lock

### F3 — Scope gates

Severity: pass

ZK write paths are gated:

- `/zk/opt-in`
- `/zk/roots/{scope}/publish`
- `/zk/vote`
- `/zk/receipts/{scope}/publish-pending`

Canary mode requires `ZK_CANARY_SCOPE_ALLOWLIST`; production mode requires
`ZK_PRODUCTION_SCOPE_ALLOWLIST` unless the explicit global flag is enabled.

Recommendation: continue using exact scope allowlists. Do not use the global
flag until a dedicated global-rollout review covers multi-scope privacy,
monitoring, UI wording, and Arweave publication policy.

### F4 — Proof binding

Severity: pass

`/zk/vote` recomputes canonical Semaphore message/scope binding from
`vote_scope_id` and `vote_commitment`. It rejects proofs bound to another
message, scope, root, or depth.

Accepted commitments are limited to `YES`, `NO`, `ABSTAIN`, and `UNKNOWN`.

### F5 — Root and group construction

Severity: pass

The Python Poseidon2/LeanIMT root builder reproduces the S10/native Semaphore
root and pins Poseidon constants by SHA-256. Sparse groups use deterministic
public dummy padding to avoid singleton canary failures without introducing
identity data.

Root publication is admin-only and additionally gated by
`ZK_ROOT_PUBLICATION_ENABLED`.

### F6 — Public receipt and Arweave payload

Severity: pass for scoped rollout; publish still admin-gated

Public receipt builders exclude:

- `tier_guard_hash`
- Tier-1 nullifier
- `identity_record_id`
- phone
- IP
- HLR metadata
- Tier-1 public key
- Semaphore secret

Arweave publishing is disabled unless `ZK_ARWEAVE_PUBLICATION_ENABLED=true`,
is refused in canary mode, and now also requires a dedicated exact
`ZK_ARWEAVE_SCOPE_ALLOWLIST`. This publisher allowlist is intentionally separate
from `ZK_PRODUCTION_SCOPE_ALLOWLIST` and `ZK_GLOBAL_ROLLOUT_ENABLED`, so global
ZK voting cannot automatically publish all pending ZK receipts to Arweave.

The publisher also enforces `ZK_ARWEAVE_MIN_GROUP_SIZE` (default: 5) before a
receipt can be archived. Receipts remain `arweave_pending=true` until a real
publication transaction exists.

### F7 — Tally integration

Severity: pass

Public result aggregation combines Tier-1 citizen votes with valid ZK receipts.
Hidden canary data remains excluded from public surfaces because the canary bill
is `admin_hidden=true` and not public.

## Release Boundary

For the next APK/AAB, it is correct to ship:

- native Semaphore prover support
- local prover self-test
- hidden operator canary path
- scoped Semaphore identity storage
- public wording that ZK canary passed but production is staged/gated

It is not correct to claim:

- global ZK voting is live
- every vote currently supports ZK
- Arweave verifier records exist for ZK votes before publication

## First Public Scoped Rollout Checklist

When a real public scope is selected:

1. Select exactly one eligible public bill scope, e.g. `bill:<id>`.
2. Create fresh DB backup.
3. Verify API status starts with all ZK flags off.
4. Set:
   - `ZK_PRODUCTION_SCOPE_ALLOWLIST=bill:<id>`
   - `ZK_VOTING_ENABLED=true`
   - `ZK_OPT_IN_ENABLED=true`
   - `ZK_TIER1_GUARD_ENABLED=true`
   - `ZK_ROOT_PUBLICATION_ENABLED=true`
5. Keep off:
   - `ZK_CANARY_ENABLED`
   - `ZK_GLOBAL_ROLLOUT_ENABLED`
   - `ZK_ARWEAVE_PUBLICATION_ENABLED` until receipt publication is explicitly run.
6. Monitor Tier-1 rejections, ZK verify failures, root freshness, and pending receipts.
7. Publish the root after opt-in collection.
8. Accept ZK votes only against the published root.
9. Publish pending ZK receipts to Arweave only after checking public payload shape
   and setting `ZK_ARWEAVE_SCOPE_ALLOWLIST=bill:<id>` plus an anonymity threshold
   via `ZK_ARWEAVE_MIN_GROUP_SIZE`.
10. Turn flags off after the scoped window unless intentionally keeping that one
    scope open.

## Current Status

Review result: **PASS for exact-scope production rollout.**

Remaining boundary: no global rollout. Global production ZK still requires a
follow-up review. ZK Arweave publication is safer now because it has a separate
scope allowlist and anonymity threshold, but it remains gated until the public
payload policy and the chosen scope are explicitly approved.

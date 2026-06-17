# GH#112 — Public Scoped ZK Rollout Runbook

Date: 2026-06-17
Status: first public scoped rollout complete for `bill:GR-d4c62ed4`; use this
runbook for any next exact-scope rollout.

## Boundary

The hidden S10 canary proved the Semaphore ZK path end to end. The first public
one-bill rollout then passed for `bill:GR-d4c62ed4`. Further production ZK use
must still remain exact-scope gated and must not enable global rollout.

## Current Meaning Of "ZK Is Rolled Out"

- Rolled out technically: Android native prover, backend verifier, Merkle root
  builder, receipt storage, public verifier payload policy, hidden S10 canary,
  and the first public one-bill scope have all passed.
- Not rolled out globally: live production flags remain off and
  `ZK_GLOBAL_ROLLOUT_ENABLED` must stay off.
- Public rollout shape: one explicit scope in `ZK_PRODUCTION_SCOPE_ALLOWLIST`,
  then backup, monitoring, root publication, one controlled vote flow, and
  flags off again unless the scope is intentionally kept open.

## Scope Eligibility

Run the read-only preflight before choosing a scope:

```bash
cd apps/api
python -m scripts.preflight_zk_public_scope --list-candidates
python -m scripts.preflight_zk_public_scope --bill-id GR-5294
```

Each public scoped rollout is conservative:

- allowed source: `PARLIAMENT`
- allowed statuses: `ACTIVE`, `WINDOW_24H`, `OPEN_END`
- blocked: `ANNOUNCED`, `DEMO-*`, `ZK_CANARY`, `admin_hidden=true`
- recommended governance levels: `NATIONAL`, `INSTITUTIONAL`

Do not activate a newly announced Bouli bill while it is still `ANNOUNCED`.
That would bypass the normal voting lifecycle.

## Flag Shape

Set only for the selected bill scope:

```text
ZK_PRODUCTION_SCOPE_ALLOWLIST=bill:<bill_id>
ZK_VOTING_ENABLED=true
ZK_OPT_IN_ENABLED=true
ZK_TIER1_GUARD_ENABLED=true
ZK_ROOT_PUBLICATION_ENABLED=true
```

Keep off for scoped rollout unless separately reviewed:

```text
ZK_CANARY_ENABLED=false
ZK_GLOBAL_ROLLOUT_ENABLED=false
ZK_ARWEAVE_PUBLICATION_ENABLED=false
```

ZK Arweave publication is a separate admin step after receipt payload review.
It is not controlled by the production/global rollout gates alone. Before any
ZK receipt is published to Arweave, configure the dedicated publication guards:

```text
ZK_ARWEAVE_PUBLICATION_ENABLED=true
ZK_ARWEAVE_SCOPE_ALLOWLIST=bill:<bill_id>
ZK_ARWEAVE_MIN_GROUP_SIZE=5
```

Do not use wildcards. Do not rely on `ZK_GLOBAL_ROLLOUT_ENABLED` to authorize
Arweave publication. Keep the minimum group size at 5 or higher unless a
separate privacy review explicitly accepts a smaller anonymity set.

## Operator Steps

1. Pick one eligible scope from the preflight output.
2. Create a fresh DB backup.
3. Verify live `/api/v1/zk/status` starts with all production flags false.
4. Set the scoped flags above.
5. Restart API and recheck `/api/v1/zk/status`.
6. Use the vC39+ app path to opt in and generate a real device proof.
7. Publish the scope root after opt-in collection.
8. Submit one ZK vote against the published root.
9. Confirm mutated proof/message/root tests still reject.
10. Confirm Tier-1 remains available outside the selected scope.
11. Keep Arweave publication off until the public verifier payload is inspected.
    If publishing, set the dedicated Arweave scope allowlist and verify the
    group size meets the minimum anonymity threshold.
12. Turn flags off after the window unless Gio explicitly keeps the scope open.

## Stop Conditions

Stop and roll back flags if:

- preflight reports blockers
- any non-allowlisted scope is accepted
- public receipts include private identity bridge fields
- mutated proof verifies
- Tier-1 voting is blocked outside the selected scope
- root mismatch or verifier errors appear
- monitor emits unexpected T3 alerts

## Current Candidate Reality

As of 2026-06-17, the first public scoped rollout completed for
`bill:GR-d4c62ed4`. Newest real Bouli bills that are still `ANNOUNCED` are not
eligible. Future exact-scope rollouts should use this runbook and a fresh
preflight for the selected bill.

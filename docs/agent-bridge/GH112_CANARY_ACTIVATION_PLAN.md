# GH#112 - ZK V2 Canary Activation Plan

Date: 2026-06-12
Status: Activation runbook; no activation performed

## Purpose

This document defines the first safe production canary for Semaphore ZK voting.

The goal is to prove the full chain on one controlled scope without enabling ZK
system-wide:

1. ZK opt-in creates a private Tier-1 lock.
2. Active scoped commitments produce a Semaphore-compatible Merkle root.
3. The server publishes the root snapshot.
4. A canary proof verifies against that root.
5. Public receipt data remains anonymous and auditable.

## Non-Negotiables

- No real Parliament bill as the first canary scope.
- No broad `ZK_VOTING_ENABLED=true` without a scope allowlist.
- No production activation without a DB backup immediately before the window.
- No Arweave claim unless a record is actually published or marked pending.
- No public record may contain `tier_guard_hash`, Tier-1 nullifier, identity id,
  phone, IP, HLR metadata, Tier-1 public key, or Semaphore identity secret.
- No rollback of already-published real Arweave records. Canary records must be
  labelled before publication.

## Canary Scope

Use a dedicated non-production scope:

```text
bill:ZK-CANARY-001
```

Requirements:

- The scope must map to a non-public/test bill or an admin-only canary object.
- It must not appear as an ordinary active citizen vote in public bill lists.
- It must be clearly labelled as canary/test in operator notes and any later
  bulletin-board payload.

Do not use `GR-*` Parliament bills for the first activation.

## Required Flags

Existing flags:

- `ZK_VOTING_ENABLED`
- `ZK_OPT_IN_ENABLED`
- `ZK_TIER1_GUARD_ENABLED`
- `ZK_CANARY_ENABLED`
- `ZK_ROOT_PUBLICATION_ENABLED`

Required new narrow flag before activation:

```text
ZK_CANARY_SCOPE_ALLOWLIST=bill:ZK-CANARY-001
```

The verifier, opt-in, root publication, and any later vote-acceptance path must
reject every scope not present in this allowlist while canary mode is active.

## Pre-Activation Checks

Run from the local repo:

```bash
git status --short
git rev-parse --short HEAD
cd apps/api
.venv/bin/python -m pytest tests/routers/test_zk_verify_api.py tests/services/test_zk_merkle_root.py tests/services/test_zk_group_registry.py tests/services/test_zk_tier_lock.py tests/test_voting.py -q
```

Run on production before any flag change:

```bash
ssh <prod-server> "
  cd /opt/ekklesia
  set -a
  . ./.env.production
  set +a
  cd /opt/ekklesia/app
  docker compose -f infra/docker/docker-compose.prod.yml exec -T api alembic current
  docker compose -f infra/docker/docker-compose.prod.yml exec -T db \
    pg_dump -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -Fc \
    > /opt/ekklesia/backups/pre_zk_canary_\$(date +%Y%m%d_%H%M%S).dump
"
```

Pre-check SQL:

```sql
select count(*) from zk_identity_commitments where vote_scope_id = 'bill:ZK-CANARY-001';
select count(*) from zk_merkle_roots where vote_scope_id = 'bill:ZK-CANARY-001';
select count(*) from zk_vote_receipts where vote_scope_id = 'bill:ZK-CANARY-001';
select count(*) from zk_vote_tier_locks where vote_scope_id = 'bill:ZK-CANARY-001';
```

Expected before first canary:

- commitments may be 0 or the planned canary count,
- roots may be 0 before publish,
- receipts must be 0,
- tier locks must match canary opt-ins only.

## Activation Sequence

Do not skip steps.

1. Create rollback tag:

   ```bash
   git tag rollback-pre-zk-canary-$(date +%Y%m%d-%H%M)
   git push origin --tags
   ```

2. Deploy only already-reviewed code if the production server is behind HEAD.
   Source `/opt/ekklesia/.env.production` before docker compose operations.

3. Set canary environment flags only in production config:

   ```text
   ZK_VOTING_ENABLED=true
   ZK_OPT_IN_ENABLED=true
   ZK_TIER1_GUARD_ENABLED=true
   ZK_CANARY_ENABLED=true
   ZK_ROOT_PUBLICATION_ENABLED=true
   ZK_CANARY_SCOPE_ALLOWLIST=bill:ZK-CANARY-001
   ```

4. Restart only API after config change.

5. Verify status:

   ```bash
   curl -s https://api.ekklesia.gr/api/v1/zk/status
   ```

6. Perform one canary opt-in from a known test identity.

7. Publish root for canary scope:

   ```bash
   curl -X POST https://api.ekklesia.gr/api/v1/zk/roots/bill:ZK-CANARY-001/publish \
     -H "Authorization: Bearer $ADMIN_KEY"
   ```

8. Fetch root:

   ```bash
   curl -s https://api.ekklesia.gr/api/v1/zk/roots/bill:ZK-CANARY-001
   ```

9. Verify one canary proof against the published root.

10. Do not publish to Arweave until the canary receipt path is explicitly
    reviewed and labelled as `mode=canary`.

## Monitoring During Window

Watch:

- API logs for `/api/v1/zk/*` 4xx/5xx spikes.
- Any Tier-1 rejection caused by ZK lock.
- `zk_vote_receipts.arweave_pending`.
- `zk_merkle_roots` root count for the canary scope.
- Telegram/admin monitor for lifecycle or verifier errors.

Rollback triggers:

- a non-canary scope accepts opt-in/root publish/verify,
- a Tier-1 vote outside canary scope is rejected by ZK lock,
- proof verifier accepts a mutated proof,
- public response includes private fields,
- root mismatch against the server builder or S10 fixture,
- unexpected 5xx during canary operations.

## Rollback

Primary rollback:

```text
ZK_VOTING_ENABLED=false
ZK_OPT_IN_ENABLED=false
ZK_TIER1_GUARD_ENABLED=false
ZK_CANARY_ENABLED=false
ZK_ROOT_PUBLICATION_ENABLED=false
ZK_CANARY_SCOPE_ALLOWLIST=
```

Restart API after changing flags.

Data rollback rules:

- If no ZK vote receipt exists, canary commitments/roots/locks may be archived or
  left inert.
- If a canary receipt exists but no Arweave record was published, mark it as
  canary/test in operator notes before any future cleanup.
- If an Arweave record was published, do not delete or pretend it never existed;
  publish a corrective canary note if needed.

## Acceptance Criteria

Canary is considered successful only when all are true:

- Only `bill:ZK-CANARY-001` accepts canary operations.
- Non-allowlisted scopes stay fail-closed.
- At least one canary opt-in succeeds.
- Root publish returns `created=true` once and `created=false` on repeat.
- Published root matches `build_active_group_root_for_scope()`.
- Server verifier accepts the real proof and rejects mutated proof/message/scope/root.
- Tier-1 is blocked only for the canary identity/scope after opt-in.
- Public root/receipt responses expose no private identity bridge fields.
- Existing Tier-1 voting tests remain green.
- Rollback flags restore fail-closed behavior.

## Implementation Work Before Activation

Before any real canary window, code must add:

- `ZK_CANARY_SCOPE_ALLOWLIST` enforcement in opt-in, root publish, verify, and
  later vote-acceptance paths.
- Tests proving non-allowlisted scopes return 403/503.
- A clear canary/test bill or canary object for `bill:ZK-CANARY-001`.
- Operator checklist for DB backup path and rollback tag.
- Optional monitor alert for ZK verifier/root-publish errors.

## Current Decision

Proceed with canary preparation code only. Do not activate flags until backup,
review, and explicit operator window are ready.

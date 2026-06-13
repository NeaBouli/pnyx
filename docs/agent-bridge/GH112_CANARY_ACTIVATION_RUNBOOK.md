# GH#112 - ZK Canary Activation Runbook

Date: 2026-06-13
Status: Operator runbook; no activation performed
Related:
- `docs/agent-bridge/GH112_CANARY_ACTIVATION_PLAN.md`
- `docs/agent-bridge/GH112_IMPLEMENTATION_PLAN.md`
- `docs/agent-bridge/GH112_ZK_V2_PRODUCTION_GATE.md`

## Purpose

This runbook defines the exact operator procedure for the first ZK voting canary.
It intentionally does not enable any flag by itself.

The canary may only use:

```text
vote_scope_id=bill:ZK-CANARY-001
bill_id=ZK-CANARY-001
source=ZK_CANARY
```

The goal is to prove the end-to-end ZK path on one hidden test scope while all
ordinary citizen-facing voting remains protected by the existing Tier 1 path.

## Hard Stop Rules

Stop immediately if any of these is true:

- `git status --short` is not clean before the window.
- Production DB backup fails or cannot be located.
- `ZK-CANARY-001` is visible in public bill lists, forum checks, votes-in-progress,
  Arweave eligibility, newsletter context, or forum sync.
- `ZK_CANARY_SCOPE_ALLOWLIST` contains anything except `bill:ZK-CANARY-001`.
- Any ZK endpoint accepts a non-allowlisted scope.
- A Tier 1 vote outside `bill:ZK-CANARY-001` is blocked by the ZK guard.
- Any public ZK response contains `tier_guard_hash`, Tier 1 nullifier,
  identity id, phone, IP, HLR metadata, Tier 1 public key, or Semaphore secret.
- The published root does not match the server-side Poseidon/LeanIMT builder.
- Mutated proof, message, scope, root, or depth verifies as valid.
- Arweave publication is attempted before the canary receipt policy is reviewed.

## Required Human Decision Before Window

Before activating flags, Gio must explicitly decide:

- Canary ZK votes are test-only and do not count in public tallies.
- No Arweave publication for the first canary unless separately approved.
- If a user opts in after root publication and never votes, Tier 1 remains locked
  for that canary scope. The UI/operator notes must explain this before opt-in.

## Pre-Window Checklist

Run locally:

```bash
git status --short
git rev-parse --short HEAD
cd apps/api
/tmp/pnyx-api-test-venv/bin/python -m pytest \
  tests/routers/test_zk_verify_api.py \
  tests/services/test_zk_merkle_root.py \
  tests/services/test_zk_group_registry.py \
  tests/services/test_zk_tier_lock.py \
  tests/test_voting.py \
  tests/test_monitor_hidden_bills.py \
  tests/test_monitor_zk_canary_health.py \
  -q
```

Run on production, read-only first:

```bash
ssh root@135.181.254.229 '
  set -e
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml exec -T api alembic current
  docker compose -f docker-compose.prod.yml exec -T api python - <<PY
import os
for key in [
    "ZK_VOTING_ENABLED",
    "ZK_OPT_IN_ENABLED",
    "ZK_TIER1_GUARD_ENABLED",
    "ZK_CANARY_ENABLED",
    "ZK_ROOT_PUBLICATION_ENABLED",
    "ZK_CANARY_SCOPE_ALLOWLIST",
]:
    print(f"{key}={os.getenv(key, "")}")
PY
'
```

Expected before flag window:

```text
ZK_VOTING_ENABLED=false or empty
ZK_OPT_IN_ENABLED=false or empty
ZK_TIER1_GUARD_ENABLED=false or empty
ZK_CANARY_ENABLED=false or empty
ZK_ROOT_PUBLICATION_ENABLED=false or empty
ZK_CANARY_SCOPE_ALLOWLIST empty
```

Check hidden canary isolation:

```bash
ssh root@135.181.254.229 '
  set -e
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml exec -T db psql \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
      select id, source, status, admin_hidden, forum_topic_id, arweave_tx_id
      from parliament_bills
      where id = '\''ZK-CANARY-001'\'';
    "
'
```

Expected:

```text
source=ZK_CANARY
admin_hidden=true
forum_topic_id is null
arweave_tx_id is null
```

Check canary tables through the production DB container:

```bash
ssh root@135.181.254.229 '
  set -e
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml exec -T db psql \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'"'"'SQL'"'"'
select count(*) as commitments
from zk_identity_commitments
where vote_scope_id = '"'"'bill:ZK-CANARY-001'"'"';
select count(*) as roots
from zk_merkle_roots
where vote_scope_id = '"'"'bill:ZK-CANARY-001'"'"';
select count(*) as receipts
from zk_vote_receipts
where vote_scope_id = '"'"'bill:ZK-CANARY-001'"'"';
select count(*) as locks
from zk_vote_tier_locks
where vote_scope_id = '"'"'bill:ZK-CANARY-001'"'"';
SQL
'
```

Expected for first window:

- receipts: `0`
- roots: `0` before first publish, unless deliberately reusing a previous
  inert canary root
- commitments/locks: `0` or the exact planned canary count

## Backup

Create a DB backup immediately before any flag change:

```bash
ssh root@135.181.254.229 '
  set -e
  TS=$(date +%Y%m%d_%H%M%S)
  mkdir -p /opt/ekklesia/backups
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml exec -T db pg_dump \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
    > "/opt/ekklesia/backups/pre_zk_canary_${TS}.dump"
  ls -lh "/opt/ekklesia/backups/pre_zk_canary_${TS}.dump"
'
```

Do not continue unless the backup file exists and is non-empty.

## Flag Window

Only these values are allowed for the first canary:

```text
ZK_VOTING_ENABLED=true
ZK_OPT_IN_ENABLED=true
ZK_TIER1_GUARD_ENABLED=true
ZK_CANARY_ENABLED=true
ZK_ROOT_PUBLICATION_ENABLED=true
ZK_CANARY_SCOPE_ALLOWLIST=bill:ZK-CANARY-001
```

Restart only the API after applying flags:

```bash
ssh root@135.181.254.229 '
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml up -d --no-deps api
'
```

Immediately verify:

```bash
curl -fsSL https://api.ekklesia.gr/api/v1/zk/status
```

Expected:

- production enabled: true
- opt-in enabled: true
- tier guard enabled: true
- canary enabled: true
- root publication enabled: true
- allowlist contains exactly `bill:ZK-CANARY-001`

## Canary Steps

1. Run monitor before operations:

   ```bash
   ssh root@135.181.254.229 'docker exec ekklesia-monitor python /app/monitor.py --once'
   ```

2. Perform one canary opt-in from the known test identity.

3. Confirm one active canary commitment and one active tier lock:

   ```sql
   select count(*) from zk_identity_commitments
   where vote_scope_id = 'bill:ZK-CANARY-001' and status = 'ACTIVE';

   select count(*) from zk_vote_tier_locks
   where vote_scope_id = 'bill:ZK-CANARY-001' and status = 'ACTIVE';
   ```

4. Publish the root:

   ```bash
   curl -fsS -X POST \
     'https://api.ekklesia.gr/api/v1/zk/roots/bill:ZK-CANARY-001/publish' \
     -H "Authorization: Bearer $ADMIN_KEY"
   ```

5. Repeat the root publish once.

   Expected:

   - first publish: `created=true`
   - repeat publish: `created=false`

6. Fetch root:

   ```bash
   curl -fsSL 'https://api.ekklesia.gr/api/v1/zk/roots/bill:ZK-CANARY-001'
   ```

7. Verify proof without accepting a vote:

   - real canary proof must verify
   - mutated message must fail
   - mutated scope must fail
   - mutated root must fail
   - mutated depth must fail

8. Accept exactly one canary ZK vote only after Step 7 passes:

   ```bash
   curl -fsS -X POST \
     'https://api.ekklesia.gr/api/v1/zk/vote' \
     -H 'Content-Type: application/json' \
     --data @/path/to/reviewed-canary-zk-vote-payload.json
   ```

   Requirements:

   - Payload must be reviewed before the window.
   - `vote_scope_id` must be exactly `bill:ZK-CANARY-001`.
   - The vote is test-only and must not be interpreted as a production citizen
     tally unless a separate production decision explicitly changes that.
   - The receipt must remain canary-labelled and must not be published to
     Arweave in the first canary window.

   Confirm the stored receipt state immediately after acceptance:

   ```bash
   ssh root@135.181.254.229 '
     set -e
     cd /opt/ekklesia/app/infra/docker
     set -a
     . /opt/ekklesia/.env.production
     set +a
     docker compose -f docker-compose.prod.yml exec -T db psql \
       -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'"'"'SQL'"'"'
   select
     count(*) as receipts,
     count(*) filter (where arweave_tx_id is not null) as arweave_published,
     count(*) filter (where arweave_pending is true) as arweave_pending
   from zk_vote_receipts
   where vote_scope_id = '"'"'bill:ZK-CANARY-001'"'"';
   SQL
   '
   ```

   Expected for the first canary window:

   - `receipts = 1`
   - `arweave_published = 0`
   - `arweave_pending = 1`

9. Confirm Tier 1 guard scope:

   - Tier 1 must be blocked only for the opted-in canary identity and
     `bill:ZK-CANARY-001`.
   - Tier 1 must remain available for every non-canary bill/scope.
   - Run the normal Tier 1 vote regression immediately after the window:

     ```bash
     cd apps/api
     /tmp/pnyx-api-test-venv/bin/python -m pytest tests/test_voting.py -q
     ```

10. Run monitor again:

   ```bash
   ssh root@135.181.254.229 'docker exec ekklesia-monitor python /app/monitor.py --once'
   ```

## Monitoring During Window

Watch:

```bash
ssh root@135.181.254.229 '
  docker logs --since 10m ekklesia-api 2>&1 |
  grep -E "zk|ZK|ERROR|Traceback|tier|verify|root" |
  tail -120
'
```

Watch DB counters through the production DB container:

```bash
ssh root@135.181.254.229 '
  set -e
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml exec -T db psql \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'"'"'SQL'"'"'
select status, count(*) from zk_identity_commitments group by status order by status;
select status, count(*) from zk_merkle_roots group by status order by status;
select arweave_pending, count(*) from zk_vote_receipts group by arweave_pending;
select status, count(*) from zk_vote_tier_locks group by status order by status;
SQL
'
```

No public canary leakage:

```bash
curl -fsSL 'https://api.ekklesia.gr/api/v1/bills?limit=50' | grep -q ZK-CANARY-001 && echo FAIL || echo PASS
curl -fsSL 'https://ekklesia.gr/' | grep -q ZK-CANARY-001 && echo FAIL || echo PASS
```

## Rollback

Primary rollback is flags off:

```text
ZK_VOTING_ENABLED=false
ZK_OPT_IN_ENABLED=false
ZK_TIER1_GUARD_ENABLED=false
ZK_CANARY_ENABLED=false
ZK_ROOT_PUBLICATION_ENABLED=false
ZK_CANARY_SCOPE_ALLOWLIST=
```

Restart only API:

```bash
ssh root@135.181.254.229 '
  cd /opt/ekklesia/app/infra/docker
  set -a
  . /opt/ekklesia/.env.production
  set +a
  docker compose -f docker-compose.prod.yml up -d --no-deps api
'
```

Post-rollback verification:

```bash
curl -fsSL https://api.ekklesia.gr/api/v1/zk/status
ssh root@135.181.254.229 'docker exec ekklesia-monitor python /app/monitor.py --once'
```

Data rollback policy:

- If no canary receipt exists, canary commitments/roots/locks may be left inert
  or archived in a later maintenance task.
- If a canary receipt exists but no Arweave record exists, do not delete it
  casually; keep it labelled as canary/test.
- If any Arweave canary record was published, do not delete or rewrite history.
  Publish a corrective canary note if needed.

## Success Criteria

The canary passes only if all are true:

- Only `bill:ZK-CANARY-001` accepts ZK canary operations.
- Non-allowlisted scopes fail closed.
- Opt-in creates one active commitment and one private Tier 1 lock.
- Root publish is idempotent.
- Published root matches the server Poseidon/LeanIMT builder.
- Real proof verifies; mutated proof/message/scope/root/depth fails.
- Exactly one reviewed canary ZK vote can be accepted through `/api/v1/zk/vote`.
- Tier 1 is blocked only for the canary identity/scope.
- Public responses expose no private identity bridge fields.
- Public bill/forum/Arweave/newsletter surfaces do not show `ZK-CANARY-001`.
- Monitor remains green or reports only expected canary-labelled warnings.
- Existing Tier 1 voting tests remain green after the window.

## Exit States

Use exactly one:

- `CANARY_NOT_STARTED`: pre-check failed or operator cancelled before flags.
- `CANARY_ABORTED`: flags were enabled but rollback was required.
- `CANARY_PASSED`: all success criteria passed, flags returned to OFF.
- `PRODUCTION_READY_REVIEW`: canary passed and a separate production review is
  requested. This is not automatic production activation.

## Current Decision

This runbook is preparation only. Do not start the flag window without explicit
operator approval, fresh DB backup, and a named canary test identity.

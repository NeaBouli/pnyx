# GH#112 - ZK Canary Operator Checklist

Date: 2026-06-13
Status: Short operator checklist for the first ZK canary window
Full runbook: `docs/agent-bridge/GH112_CANARY_ACTIVATION_RUNBOOK.md`

## What This Is

The ZK canary is a controlled live test of the Semaphore/ZK voting path on one
hidden test scope only:

```text
bill:ZK-CANARY-001
```

It is not production ZK voting. It must not affect normal public bills.

## What Gio Must Prepare

Before saying "start canary", Gio must have:

1. S10 available, charged, and unlocked.
2. The ekklesia app installed and opened once.
3. The verified S10 test account available.
4. 20-30 minutes where the app is not used for unrelated testing.
5. Explicit agreement that the canary vote is test-only and does not count in
   public tallies.

## What Gio Says To Start

Use this exact handoff phrase:

```text
Start GH#112 ZK Canary now. S10 is ready. Use my verified S10 test account.
```

Do not start the canary from vague phrasing like "weiter" or "ok".

## What Codex/CC Will Do

1. Confirm `git status` is clean.
2. Run the local ZK and voting regression tests listed in the full runbook.
3. Check production flags are OFF.
4. Check `ZK-CANARY-001` is hidden from public lists/forum/Arweave.
5. Create a fresh production DB backup.
6. Enable only the exact canary flags for `bill:ZK-CANARY-001`.
7. Publish/verify the canary Merkle root.
8. Run one reviewed canary ZK vote payload.
9. Confirm:
   - receipt exists
   - `arweave_published = 0`
   - `arweave_pending = 1`
   - no private fields leak publicly
   - normal non-canary bills are not blocked
10. Turn flags back OFF.
11. Run monitor and Tier 1 regression check.
12. Document result in the bridge.

## Gio During The Window

Gio should:

1. Keep the S10 connected/unlocked if possible.
2. Do not browse unrelated bills during the canary unless asked.
3. Follow only the specific prompts Codex gives.
4. Report immediately if the app shows:
   - `ZK-CANARY-001` in normal bill lists
   - a crash
   - a normal public bill refusing a normal vote
   - anything that looks like a real public ZK activation

## Immediate Stop Conditions

Stop and rollback if any of these happens:

- Backup fails.
- `ZK-CANARY-001` appears publicly.
- Any non-canary scope is accepted by a ZK endpoint.
- Any normal bill is blocked by the ZK Tier 1 guard.
- Any public response contains identity bridge fields.
- Mutated proof/message/scope/root/depth verifies as valid.
- Any Arweave publication is attempted during the first canary.

## Expected End State

Successful canary end state:

- ZK test vote accepted for `bill:ZK-CANARY-001` only.
- No public bill affected.
- No Arweave publication.
- ZK flags OFF again.
- Monitor clean.
- Bridge updated.

Failed/aborted canary end state:

- ZK flags OFF again.
- Backup path recorded.
- Failure reason documented.
- No retry until the cause is fixed.


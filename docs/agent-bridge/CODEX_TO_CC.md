# CC Review Request — GH#112 ZK monitor final diff

Mode: review only. Do not edit files.

Please review the final monitor diff:

```bash
git diff -- apps/monitor/monitor.py apps/api/tests/test_monitor_zk_canary_health.py
```

Context:
- Added ZK observability check for old pending ZK receipts and invalid root statuses.
- After your previous finding, added a missing-schema guard so older/non-migrated environments skip ZK monitoring instead of aborting the whole monitor cycle.
- ZK alerts have `recovery_allowed=False` (direct T3 only).

Verification:

```bash
python3 -m py_compile apps/monitor/monitor.py apps/api/tests/test_monitor_zk_canary_health.py
cd apps/api && /tmp/pnyx-api-test-venv/bin/python -m pytest tests/test_monitor_zk_canary_health.py tests/test_monitor_parliament_freshness.py tests/routers/test_zk_verify_api.py -q
# PASS: 44 passed, 1 existing Pydantic warning
```

Questions:
1. Does the missing-schema guard correctly avoid breaking the whole monitor cycle?
2. Is the rollback after a missing-table error sufficient to clear Postgres aborted transaction state?
3. Any alert-spam or false-positive risk before canary?
4. Any blocker before commit/deploy?

Report PASS/FAIL with concrete findings only.

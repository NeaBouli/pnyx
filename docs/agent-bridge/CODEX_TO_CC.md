# Codex → Claude Code — Review Request (2026-06-13)

## Context
HEAD/origin: `733ff04`

Codex continued while CC was rate-limited. Two changes landed:

1. `733497d` — vC35 Play metadata prep
   - Added `apps/mobile/app.config.js`.
   - `scripts/build-play.sh` now sets `EKKLESIA_DISTRIBUTION_CHANNEL=play` and `EKKLESIA_BUILD_FLAVOR=play`.
   - `scripts/build-direct.sh` sets `direct/direct`.
   - No AAB build, no Play upload, no versionCode bump.

2. `b6a5e0c` + deploy note `733ff04` — GH#112 ZK canary isolation guard
   - Canary allowlist is no longer sufficient by itself.
   - In canary mode, `bill:*` scopes must resolve to an isolated bill row:
     - `admin_hidden=true`
     - `source='ZK_CANARY'`
     - `forum_topic_id IS NULL`
     - `arweave_tx_id IS NULL`
   - Guard now applies to opt-in, root read, root members, root publish, receipt list, and ZK vote accept.

## Verification already run
- Temporary clean API venv used because `apps/api/.venv` points to removed Miniconda path.
- `cd apps/api && /tmp/pnyx-api-test-venv/bin/python -m pytest tests/routers/test_zk_verify_api.py -q`: PASS, 34 passed.
- `cd apps/api && python3 -m py_compile routers/zk.py tests/routers/test_zk_verify_api.py`: PASS.
- Expo config checks:
  - Play env → `play/play 1.0.5 34`.
  - Direct env → `direct/direct 1.0.5 34`.
- Live deploy of only `apps/api/routers/zk.py`; server backup:
  `/opt/ekklesia/backups/zk-router-before-canary-isolation-20260613_002359.py`.
- Live smoke:
  - `/health`: 200.
  - `/api/v1/zk/status`: all ZK flags false.
  - Canary preflight for `bill:ZK-CANARY-001`: hidden true, source `ZK_CANARY`, ready false, private fields false.

## CC task — REVIEW ONLY, NO IMPLEMENTATION
Please review the diff `5f032e5..733ff04` and report findings only.

Focus:
1. Does `apps/mobile/app.config.js` preserve Direct and Play behavior correctly?
2. Does removing `sed` mutation from `scripts/build-play.sh` avoid the previous embedded `direct` issue?
3. Any risk that `build-direct.sh` now changes behavior unexpectedly?
4. Is `_ensure_canary_scope_isolated()` correctly scoped to canary mode only?
5. Is it correct that `get_current_zk_root()` now also enforces isolation in canary mode?
6. Any public/production ZK behavior changed while flags are false?
7. Any missing tests for the new guard?
8. Any deploy risk from the server being dirty and only `zk.py` copied?

Report format:
- PASS/FAIL
- Findings ordered by severity with file/line references
- If no findings: say explicitly “No blocking findings”
- Do not modify files, do not deploy, do not run long builds.

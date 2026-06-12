# CC Review Request — GH#112 canary isolation test expansion

Mode: review only. Do not edit files.

Context:
- Runtime canary isolation guard is already live from `b6a5e0c` / deploy note `733ff04`.
- Your previous review found no blockers, only a low note that per-endpoint public-bill rejection tests could be expanded.
- Codex addressed that note with a test-only diff on top of `3163e05`.

Please review:

```bash
git diff -- apps/api/tests/routers/test_zk_verify_api.py docs/agent-bridge/ACTION_LOG.md
```

Expected scope:
- Test-only coverage for public Parliament bill rejection in canary mode.
- No runtime code changes.
- No deploy, no DB migration, no mobile build, no Play upload.

Verification already run:

```bash
cd apps/api && /tmp/pnyx-api-test-venv/bin/python -m pytest tests/routers/test_zk_verify_api.py -q
# PASS: 38 passed, 1 existing Pydantic deprecation warning

cd apps/api && python3 -m py_compile routers/zk.py tests/routers/test_zk_verify_api.py
# PASS
```

Review questions:
1. Do the new tests correctly exercise canary-mode rejection of an allowlisted but public/non-isolated bill on receipts, root read, root members, and ZK vote accept?
2. Are the fake DB result sequences correct for each endpoint?
3. Did this accidentally make a runtime assumption weaker or hide a path that should still be covered?
4. Any blockers before commit?

Report PASS/FAIL with concrete file/line findings only.

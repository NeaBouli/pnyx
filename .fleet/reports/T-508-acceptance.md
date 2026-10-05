id: T-508-acceptance
status: ok
worker: codex
branch: agent/codex/T-508-integration
summary: Lead acceptance of Claude T-508 after exact diff review. One results-lifecycle wording contradiction was corrected in df46ae07 and pinned by the focused test. Final candidate adds four narrow EL/EN canonical topics before RAG/models and changes no underlying identity, ZK, representative or results behavior.
files: apps/api/routers/agent.py; apps/api/tests/test_agent_eka63_canonicals.py; inherited architecture map; worker report
tests: EKA-63 focused -> 97 passed; existing agent/prompt/EKA-62/Claude-router -> 159 passed, 4 skipped; py_compile -> pass; git diff --check -> pass. Worker broader API evidence -> 1553 passed, 43 skipped, 25 xfailed, 3 Redis-environment failures reproduced on base.
risks: Heuristic phrase matching can miss unseen phrasings; Greek copy lacks native-editor review. Answers must be updated if any mapped domain contract changes. Copied `.fleet/tasks/` is untracked metadata only; no uncommitted product work.
security: none; no provider, production, secret, Sentry, data, KDF or EKA-65 access/change. JEV before dispatch: low, reversible, narrow, needs_human false.
next: Keep local. If Gio later authorizes publication capacity, push/open as a Draft after #404 in the serial queue without requesting CodeRabbit until every earlier gate completes. No merge/deploy/live.

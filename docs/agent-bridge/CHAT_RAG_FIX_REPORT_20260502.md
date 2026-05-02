# Chat RAG Fix Report - 2026-05-02

## Summary

Codex fixed the highest-risk landing-chat/RAG issues found in `LANDING_CHAT_TEST_REPORT_20260502.md`.

No `.env` files, secret files, keys, wallet files, deployment actions, commits, or pushes were performed.

## Changed Files

- `apps/api/routers/agent.py`
- `apps/api/scripts/seed_knowledge_base.py`
- `apps/api/tests/test_agent_guardrails.py`
- `apps/api/tests/test_agent_training_regression.py`
- Bridge report files under `docs/agent-bridge/`

## Fixes

### 1. Safety Pre-Filter

Implemented deterministic blocking before any Ollama/Claude call for:

- fake votes
- create votes
- vote manipulation
- admin key requests
- verification bypass
- related Greek-language variants

Unsafe requests now return:

- `model: safety-filter`
- no external model call
- `sources: []`
- clear safe-testing guidance

### 2. Canonical Knowledge Answers

Added deterministic `model: knowledge-base` answers for topics that must not drift:

- private key loss
- nullifier hash
- CPLM
- gov.gr OAuth deferred/gated status
- municipal/Diavgeia scope
- Android download channels
- vote correction / duplicate voting

This directly addresses the live-test failures:

- `EN-011` fake-votes unsafe answer
- `EN-006` private-key recovery hallucination
- `EN-005-R1` nullifier/Ed25519 imprecision
- `EL-009` CPLM missing answer
- `EL-012` gov.gr missing deferred/gated answer
- `EN-008` municipal scope contradiction
- `EL-007` vote-correction contradiction

### 3. Source Retrieval

Changed bill retrieval behavior:

- Generic platform/privacy/legal/crypto questions no longer attach unrelated current bills.
- Bill sources are attached only when the question explicitly asks about bills/laws/legislation or a `GR-...` bill id.

### 4. Knowledge-Base Seed Sync

Updated `apps/api/scripts/seed_knowledge_base.py`:

- corrected Ed25519/nullifier/private-key wording
- added CPLM, nullifier, private-key, Android download, vote correction, municipal/Diavgeia entries
- changed seed behavior from "skip if any KB rows exist" to insert/update by `(category, title_en)`

## Verification

Commands run locally:

```bash
cd /Users/gio/Desktop/repo/pnyx/apps/api
./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py
```

Results:

- `11 passed, 1 warning in 0.94s`
- `py_compile` passed

Note:

- Running plain `pytest` with system Python failed because system SQLAlchemy was too old and lacked `async_sessionmaker`.
- Running via repo API venv succeeded.

## Remaining Risks

- Live server not tested after fix because no deployment was performed.
- Production KB must be synced after deploy by running the seed script or equivalent migration/admin task.
- `greek_topics_scraper.py` remains untracked and outside this fix.
- Admin-key/query-auth hardening is still a separate security task.

## Deploy Notes For Claude Code

Recommended deployment flow:

1. Review changed files.
2. Run API tests in the repo venv.
3. Commit changes.
4. Deploy API only.
5. Sync/update production knowledge base with `apps/api/scripts/seed_knowledge_base.py` or an equivalent safe server-side command.
6. Re-run the 25 landing-chat regression questions against live `/api/v1/agent/ask`.
7. Confirm:
   - fake-vote/admin/bypass questions return `model: safety-filter`
   - private-key/nullifier/CPLM/gov.gr/municipal/download/vote-correction questions return correct canonical answers
   - generic platform questions no longer include unrelated bill sources


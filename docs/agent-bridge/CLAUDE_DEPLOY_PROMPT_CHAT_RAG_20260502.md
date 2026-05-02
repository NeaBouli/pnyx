# Prompt For Claude Code - Deploy Chat/RAG Fix

Du arbeitest im lokalen Repository:

`/Users/gio/Desktop/repo/pnyx`

Ziel:

Reviewe, committe und deploye den von Codex vorbereiteten Chat/RAG-Agent-Fix.

Wichtig:

- Keine `.env`-Dateien lesen oder ausgeben.
- Keine Secret-Dateien lesen oder ausgeben.
- Keine Secrets in Logs oder Bridge schreiben.
- `apps/api/services/greek_topics_scraper.py` bleibt untracked und fachlich gesperrt.
- Deploy nur API/KB-relevante Aenderungen.

Von Codex geaenderte Produktdateien:

1. `apps/api/routers/agent.py`
2. `apps/api/scripts/seed_knowledge_base.py`
3. `apps/api/tests/test_agent_guardrails.py`
4. `apps/api/tests/test_agent_training_regression.py`

Bridge-Artefakte:

1. `docs/agent-bridge/CHAT_RAG_FIX_REPORT_20260502.md`
2. `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
3. `docs/agent-bridge/LANDING_CHAT_FULL_TRANSCRIPT_20260502.md`
4. `docs/agent-bridge/LANDING_CHAT_TEST_REPORT_20260502.md`

Codex-Verifikation:

```bash
cd /Users/gio/Desktop/repo/pnyx/apps/api
./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py
```

Ergebnis:

- `11 passed, 1 warning`
- `py_compile` passed

Bitte ausfuehren:

1. Review der Diffs.
2. Tests erneut ausfuehren.
3. Commit erstellen.
4. API deployen.
5. Production Knowledge Base sicher aktualisieren:
   - bevorzugt mit `apps/api/scripts/seed_knowledge_base.py`
   - keine Secrets ausgeben
6. Live Regression gegen `/api/v1/agent/ask` mit den 25 Fragen aus:
   - `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
7. Bridge aktualisieren:
   - `ACTION_LOG.md`
   - `PROJECT_STATE.md`
   - `CODEX_TO_CLAUDE.md` oder neuer Claude-Report

Erwartete Live-Ergebnisse:

- Fake-vote/admin-key/bypass/manipulation Fragen werden blockiert:
  - `model: safety-filter`
  - `sources: []`
- Private-Key-Verlust erfindet keinen Recovery-Prozess.
- Nullifier Hash trennt Nullifier und Ed25519 korrekt.
- CPLM, gov.gr deferred/gated, municipal/Diavgeia, Android Download und Vote Correction haben korrekte Antworten.
- Allgemeine Plattformfragen haengen keine unrelated Bill-Sources an.


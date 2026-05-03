# Ollama System Audit 2026-05-03

- **Agent:** Codex
- **Datum/Zeit:** 2026-05-03 00:46 EEST
- **Scope:** Lokaler Code-Audit und Mock-basierte Regressionstests fuer Ollama-Anbindungen
- **Keine Secrets gelesen:** ja
- **Kein Commit/Push/Deployment/SSH:** ja
- **Keine externen Netzwerkaufrufe:** ja

## Gepruefte Ollama-Anwendungsfaelle

1. Landing Chat / RAG Agent: `apps/api/routers/agent.py` und `apps/api/services/ollama_service.py`
2. Bill-Summary Endpoint: `apps/api/routers/parliament.py` mit `summarize_bill`
3. MOD-10 Scraper-Summary: `apps/api/routers/scraper.py`
4. Scraper Provider-Status: `GET /api/v1/scraper/status` und `/test`
5. Admin Log-Erklaerung: `POST /api/v1/admin/logs/explain`
6. Scraper Auto-Healing: `apps/api/services/scraper_healer.py`
7. Compass Question Generator: `apps/api/services/compass_generator.py`
8. Dashboard-nutzbare Admin-Ollama-Flaechen wurden nur indirekt ueber API-Callsites geprueft; vorhandene Dashboard-Aenderungen wurden nicht angefasst.

## Findings

### HIGH: Ollama-Konfigurationsdrift im MOD-10 Scraper

- `apps/api/routers/scraper.py` nutzte eigene Defaults: `http://localhost:11434` und `llama3.2`.
- Der zentrale Service nutzt `http://ollama:11434` und `llama3.2:3b`.
- Risiko: Im Docker/API-Container zeigt `localhost` auf den API-Container, nicht auf den Ollama-Container. Dadurch kann der Scraper Ollama als offline sehen, obwohl `ekklesia-ollama` laeuft.

### MEDIUM: Bill-Summary war hart von Ollama-Verfuegbarkeit abhaengig

- `GET /api/v1/bills/{bill_id}/summary` gab 503 zurueck, bevor `summarize_bill()` seinen deterministischen Template-Fallback nutzen konnte.
- Risiko: Bei Ollama-Ausfall faellt eine eigentlich fallback-faehige Nutzerfunktion komplett aus.

### MEDIUM: JSON-Parsing war mehrfach ad hoc implementiert

- Scraper und Compass Generator parsten Ollama-JSON jeweils selbst.
- Risiko: Markdown-Fences, kurze Prefaces oder leicht variierende JSON-Antworten fuehren zu unnoetigen Fallbacks.

### LOW/MEDIUM: Scraper-Healing akzeptierte zu breite Selector-Ausgaben

- Auto-Healing pruefte nur Laenge und einen einfachen `I `-Prefix.
- Risiko: Prosa oder mehrzeilige Antworten konnten bis zum Selector-Test durchgereicht werden.

### LOW: Admin Log-Erklaerung gab leere Analyse durch

- Wenn Ollama erreichbar ist, aber keine Antwort erzeugt, konnte eine leere Analyse zurueckgegeben werden.
- Risiko: Dashboard zeigt scheinbar erfolgreichen, aber inhaltslosen AI-Check.

## Umgesetzte Justierungen

- `ollama_service.py`
  - Zentrale Modell-Matching-Logik fuer exakte Tags und Base-Names (`llama3.2` vs. `llama3.2:3b`).
  - Zentrale `ollama_json_generate()` mit `format: json`, niedriger Temperatur und robustem JSON-Parser.
  - Niedrigere Temperatur fuer normale Generierung zur stabileren Ausgabe.

- `routers/scraper.py`
  - Nutzt jetzt zentrale Ollama-Konfiguration und zentrale Verfuegbarkeitspruefung.
  - Nutzt `ollama_json_generate()` statt direkter HTTP-/JSON-Logik.
  - Validiert Pflichtfelder der Scraper-Zusammenfassung.

- `routers/parliament.py`
  - Entfernt den harten `ollama_available()` Gate vor `summarize_bill()`.
  - Der Endpoint kann nun deterministische Fallback-Summaries liefern, wenn Ollama offline ist.

- `services/compass_generator.py`
  - Nutzt zentrale JSON-Erzeugung statt eigenem Regex-/JSON-Parsing.
  - Fragen bleiben weiterhin `is_active=False` und muessen reviewed werden.

- `services/scraper_healer.py`
  - Selector-Ausgaben werden strenger validiert.

- `routers/admin.py`
  - Leere Ollama-Analyse wird als 503 behandelt.

## Tests

Ausgefuehrt lokal in `apps/api`:

```bash
./.venv/bin/python -m pytest tests/test_ollama_system.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile services/ollama_service.py routers/scraper.py routers/parliament.py services/compass_generator.py services/scraper_healer.py routers/admin.py tests/test_ollama_system.py
```

Ergebnis:

- `19 passed, 1 warning`
- `py_compile` erfolgreich
- Warnung: bestehende Pydantic-v2-Deprecation aus Dependency-Konfiguration.

## Geaenderte Dateien

- `apps/api/services/ollama_service.py`
- `apps/api/routers/scraper.py`
- `apps/api/routers/parliament.py`
- `apps/api/services/compass_generator.py`
- `apps/api/services/scraper_healer.py`
- `apps/api/routers/admin.py`
- `apps/api/tests/test_ollama_system.py`
- `docs/agent-bridge/OLLAMA_SYSTEM_AUDIT_20260503.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/PROJECT_STATE.md`

## Nicht angefasst

- `.env`, `.env.*`, Keys, Wallets, Secret-Dateien
- `apps/api/services/greek_topics_scraper.py`
- Dashboard-Dateien mit vorhandenen uncommitted Aenderungen
- Deployment, Commit, Push, SSH

## Empfehlungen fuer Claude Code

1. Vor Deployment Diff pruefen und sicherstellen, dass Ollama-Container in Production `OLLAMA_URL=http://ollama:11434` nutzt.
2. Nach Deployment `/api/v1/scraper/status`, `/api/v1/scraper/test`, `/api/v1/bills/{id}/summary`, `/api/v1/admin/logs/explain` und Landing Chat smoke-testen.
3. Compass-Generator nur im Admin-Review-Flow betreiben; keine generierten Statements automatisch aktivieren.
4. Wenn Live-Ollama weiter instabil antwortet, Prompt-Katalog fuer die einzelnen Aufgaben trennen: Chat, Bill-Summary, JSON-Scraper, Compass, Admin-Logs.
5. `greek_topics_scraper.py` weiterhin deaktiviert lassen, bis Review-/Draft-Flow und rechtliche Bewertung abgeschlossen sind.

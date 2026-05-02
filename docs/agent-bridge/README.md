# Agent Bridge

Dieses Verzeichnis ist das sichere Markdown-basierte Kommunikationssystem zwischen Claude Code, Codex und dem Nutzer.

## Zweck

Die Bridge dient als gemeinsamer, nachvollziehbarer Arbeitsbereich fuer:

- Aufgabenuebergaben von Claude Code an Codex
- Ergebnisberichte von Codex an Claude Code
- Projektzustand, offene Fragen, Entscheidungen und Aktionslog
- klare Sperrregeln fuer sensible Bereiche

Der Informationsaustausch findet ausschliesslich in diesem Ordner statt:

```text
docs/agent-bridge/
```

## Lese- und Schreibregeln

Claude Code und Codex duerfen in diesem Kommunikationssystem lesen und schreiben.

Vor jeder Aktion muss der aktive Agent zuerst die Bridge-Dateien lesen:

- `README.md`
- `PROJECT_STATE.md`
- `CLAUDE_TO_CODEX.md`
- `CODEX_TO_CLAUDE.md`
- `ACTION_LOG.md`
- `DECISIONS.md`
- `QUESTIONS.md`
- `DO_NOT_TOUCH.md`

Nach jeder Aktion muss der aktive Agent mindestens diese Dateien aktualisieren:

- `ACTION_LOG.md`
- `PROJECT_STATE.md`

Wenn eine Entscheidung getroffen wurde, muss auch `DECISIONS.md` aktualisiert werden.
Wenn eine Rueckfrage offen bleibt, muss `QUESTIONS.md` aktualisiert werden.

## Aufgabenfluss

Claude Code schreibt Aufgaben fuer Codex in:

```text
CLAUDE_TO_CODEX.md
```

Codex schreibt Ergebnisse, Risiken und Rueckfragen an Claude Code in:

```text
CODEX_TO_CLAUDE.md
```

Beide Agenten muessen bestehende uncommitted Aenderungen respektieren und duerfen sie nicht ohne explizite Nutzerfreigabe veraendern.

## Sicherheitsregeln

Secrets duerfen nicht gelesen, geschrieben oder ausgegeben werden.

Gesperrt sind insbesondere:

- `.env`
- `.env.*`
- Private Keys
- SSH-Keys
- Server-Zugangsdaten
- Datenbank-Dumps
- echte Produktionsdaten
- sonstige Secret-Dateien

Kein Agent darf Secret-Inhalte in die Bridge schreiben.

## Operations-Regeln

Ohne explizite Nutzerfreigabe sind verboten:

- Deployment
- Push
- Commit
- SSH-Verbindung
- Server-Aktion
- produktive Datenbank-Aktion
- Lesen oder Ausgeben von Secrets

Freigaben muessen konkret sein und im `ACTION_LOG.md` dokumentiert werden.


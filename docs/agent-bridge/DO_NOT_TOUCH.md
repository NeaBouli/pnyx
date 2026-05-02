# Do Not Touch

Diese Bereiche sind gesperrt, solange der Nutzer keine explizite Freigabe gibt.

## Secrets und Zugangsdaten

- `.env`
- `.env.*`
- `*.pem`
- `*.key`
- SSH-Keys
- Server-Zugangsdaten
- API-Keys
- Wallet-Dateien
- Datenbank-Dumps
- echte Produktionsdaten

## Operations

- Deployment-Skripte nur nach Freigabe
- Deployment nur nach Freigabe
- Push nur nach Freigabe
- Commit nur nach Freigabe
- SSH nur nach Freigabe
- Server-Aktionen nur nach Freigabe

## Codebereiche

- Produktcode nicht ohne expliziten Task aendern
- Auth-Code nur nach explizitem Task
- Voting-Code nur nach explizitem Task
- Security-Code nur nach explizitem Task
- Dateien unter `apps/`, `packages/`, `server/`, `src/` oder aehnlichen Code-Verzeichnissen nicht fuer Bridge-Aufgaben aendern

## Bestehende uncommitted Aenderungen

Nicht ohne Freigabe aendern:

- `apps/api/services/discourse_sync.py`
- `apps/api/services/greek_topics_scraper.py`


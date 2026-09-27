id: T-410
verdict: ok

Review von `agent/claude/T-406 @ a8dd8bd` (Basis `6104c6b`), Fokus CodeRabbit-Fix `a8dd8bd`:
- `a8dd8bd` schliesst die Luecke korrekt: `_ensure_same_tier` lehnt Tier-1-Korrektur gegen historische Zeilen mit `timestamp_ms IS NULL` jetzt fail-closed ab. Regressionstest prueft 400/STALE_PAYLOAD, 0 Commits und unveraenderte Zeile.
- Migration `x701a2b3c4d5`: read-only Preflight zaehlt nur Gruppen, keine Werte geloggt; fail-closed; `CREATE UNIQUE INDEX CONCURRENTLY` mit Invalid-Index-Cleanup; Downgrade entfernt nur den neuen Index. Case-insensitiv, partiell auf NOT NULL, Legacy-NULL frei.
- Router: Precheck bleibt Fast Path, Index ist Invariante; nur 23505 der zwei erwarteten Constraints wird 409, fremde IntegrityErrors nach Rollback erneut geworfen; Vote und Tier-1-Felder atomar in einer Transaktion; kein stiller Tier-Wechsel; Lowercase-Hex.
- Kimi verifizierte lokal mit danach entferntem PostgreSQL-16.14-Container: 27 PG-Migrations-/Race-Tests passed, `test_tier1_vote_enforcement.py` 39 passed, breite Gruppe `-k "vote or voting or tier1 or nullifier or municipal"` 320 passed und 5 xfailed.
- Type Hints vorhanden; EKA-65/KDF unberuehrt; keine Secrets; Commit-Trennung Migration/Router korrekt.
- Hinweis ohne Blocker: `.fleet/T-410_DESIGN.md` ist lokales Lead-Artefakt und nicht Teil des Produktbranches; Review erfolgte gegen die verbindlichen Constraints des Briefs.
security: none

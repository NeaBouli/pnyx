id: T-410
verdict: ok
worker: kimi (cross-review of branch agent/claude/T-410 @ 8a3a9cd)
review:
- Scope sauber: T-410-Aenderungen nur in 8660fb0 (Migration/Modell/PG-Fixtures) und c373177 (Router/Tests); keypair/nullifier-Diffs stammen ausschliesslich aus den uebernommenen, bereits reviewten PR-#371-Produktcommits.
- Migration x701a2b3c4d5: read-only Preflight zaehlt nur Gruppen, keine Werte und kein Rewrite; CREATE/DROP INDEX CONCURRENTLY in autocommit; INVALID-Index nach Fehlbau best-effort entfernt, Originalfehler erneut geworfen; Downgrade entfernt nur den neuen Index; down_revision v501a2b3c4d5 korrekt.
- Router: striktes 64-Hex-fullmatch vor Lookup, canonical lowercase-Storage, with_for_update in submit+correct, kein Tier-Wechsel, Replay-Schutz ueber strikt steigenden Timestamp, alle Vote-/Tier-1-Felder in einer Transaktion.
- 409-Mapping eng: nur PostgreSQL 23505 fuer den neuen Index bzw. uq_one_vote_per_citizen; fremde Unique/FK/Check- und Nicht-Integrity-Fehler werden nach Rollback unmaskiert erneut geworfen.
- Tests decken alle Acceptance-Punkte: echte PostgreSQL-Race 200+409, Case-Varianten, Legacy-NULL, Upgrade/Downgrade/Upgrade, YES->NO mit frischem Payload, Voll-Rollback und fremde Fehler.
- Type Hints vorhanden, keine Secrets oder Scope-Verstoesse; EKA-65/KDF unangetastet.
minor: SQLite mappt unbekannte IntegrityErrors nun nicht pauschal auf 409; akzeptabel, da PostgreSQL die vorgeschriebene Invariante ist. Der STALE-Check greift bei einer hypothetischen Tier-1-Zeile mit timestamp_ms NULL nicht; ein solcher gueltiger Zustand wird vom derzeit inaktiven Pfad nicht erzeugt.
security: none

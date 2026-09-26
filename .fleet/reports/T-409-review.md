id: T-409
verdict: ok

- Correctness: the pre-check/INSERT race is handled around commit; rollback precedes every rethrow, and only SQLSTATE 23505 on `uq_diavgeia_vote` maps to 409.
- The constraint name matches both the model and Alembic migration `g001a2b3c4d5`.
- Independently reproduced: SQLite 5 passed; PostgreSQL 16 with asyncpg 11 passed, 1 skipped. The barrier test proves one 200, one 409, one stored row, and reusable sessions.
- Other integrity and database errors remain fail-closed and are not masked.
- No new data, logs, schema, migration, configuration, or anonymity change.
- The task container and review container were removed; unrelated containers and the original T-407 worktree were untouched.
- Non-blocking risk: detection depends on the stable constraint name; a future rename would fail closed with 500 instead of 409, never double-count.

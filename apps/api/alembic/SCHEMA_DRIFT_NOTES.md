# Schema Drift Notes — decisions.id Type Mismatch

## Issue Summary

Migration `b501c2d3e4f5_mod16_municipal.py` defines the `decisions` table with:
```python
sa.Column('id', sa.String(60), primary_key=True)
```

However, the **live production DB** (Hetzner `ekklesia_prod`) has:
```
id | integer | not null | nextval('decisions_id_seq'::regclass)
```

And the **SQLAlchemy model** (`models.py:291`) defines:
```python
id = Column(Integer, primary_key=True)
```

**Model and live DB agree (Integer). Migration disagrees (String(60)).**

## Root Cause

The migration file `b501c2d3e4f5` was created on 2026-03-30.
The production database was likely initialized using `Base.metadata.create_all()`
(which follows the SQLAlchemy model = Integer), and then alembic was stamped to
the current head. The migration file was never actually executed against production
in its current form, or was manually corrected post-apply.

## Current Impact

### NOT affected by this drift:
- **Diavgeia Integration (d701)**: The FK `decisions.diavgeia_ada` references
  `diavgeia_decisions.ada` (String→String). The `decisions.id` type is irrelevant.
- **Existing API operations**: All queries go through SQLAlchemy ORM (Integer),
  which matches production.

### At-risk scenarios:
1. **Fresh DB rebuild from migration history** → `decisions.id` would be `varchar(60)`
   instead of `integer`, breaking auto-increment and any code expecting numeric IDs.
2. **`alembic stamp` on new replica** → history/schema mismatch if replica was
   created from production backup (integer) but alembic thinks it ran b501 (varchar).
3. **Local test DB via `alembic upgrade head`** → produces wrong schema silently.
   (Confirmed: local docker test DB gets `varchar(60)` while prod has `integer`.)

## Decision Record (PR feat/diavgeia-integration)

- This PR does **NOT** fix the drift.
- This PR works around it: Diavgeia FK is String→String on `ada`, independent of `id` type.
- Follow-up required: separate ADR + migration to realign history and production.

## Mitigation Options (for future ADR)

### Option 1: Corrective migration
Write a new migration that ALTERs `decisions.id` from String(60) to Integer
with sequence. Risky if any data exists with non-numeric IDs.

### Option 2: Reset alembic baseline (RECOMMENDED)
- Dump current production schema as the new "initial" migration.
- `alembic stamp head` on production.
- All subsequent migrations start from the true production state.
- Requires a coordinated deploy window (low traffic).
- Best done during next major version bump.

### Option 3: Edit b501 in-place
Change `sa.String(60)` to `sa.Integer()` in b501 and re-stamp.
Invalidates migration history integrity — not recommended for auditable systems.

---

*Documented: 2026-04-25 | PR: feat/diavgeia-integration*

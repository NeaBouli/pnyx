# ADR: NEA-256 — Alembic Schema Baseline

- **Date:** 2026-05-23
- **Status:** Proposed
- **Linear:** NEA-256
- **Alembic HEAD (production):** `l501a2b3c4d5`

## Problem

A fresh database created via `alembic upgrade head` does not match the production schema. Multiple tables and columns were added via manual server SQL and are not represented in migration history. Additionally, migration `b501c2d3e4f5` defines `decisions.id` as `String(60)` while production and ORM use `Integer`.

**Fresh install from migrations is broken.**

## Schema Drift Inventory

| Table/Column | Production | Migration | ORM Model | Status |
|---|---|---|---|---|
| `decisions.id` | Integer (autoincrement) | String(60) | Integer | **MISMATCH** |
| `audit_log` | Exists (UUID PK, JSONB) | Missing | AuditLog model | **MISSING** |
| `identity_records.source` | VARCHAR(20) DEFAULT 'SMS' | Missing | Column present | **MISSING** |
| `representative_tokens.periferia_id` | INTEGER FK | Missing | No ORM | **MISSING** |
| `representative_tokens.dimos_id` | INTEGER FK | Missing | No ORM | **MISSING** |
| `representative_tokens.municipality` | VARCHAR(255) | Missing | No ORM | **MISSING** |
| `representative_tokens.evaluation_enabled` | BOOLEAN | In l501 migration | No ORM | OK |
| `rep_invitations.periferia_id` | INTEGER FK | Missing | No ORM | **MISSING** |
| `rep_invitations.dimos_id` | INTEGER FK | Missing | No ORM | **MISSING** |
| `evaluation_questions` | Exists (8 rows) | In l501 migration | EvaluationQuestion | OK |
| `politician_evaluations` | Exists | In l501 migration | PoliticianEvaluation | OK |

**Total: 8 drifted items, 1 type mismatch.**

## Explicit Non-Goals

- No production DB mutation in this task
- No blind autogenerate migration
- No `alembic upgrade` or `alembic downgrade` on production
- No ORM or product code changes

## Recommended Plan

### Phase 1: Schema Snapshot
- Dump current production schema as SQL reference
- `pg_dump --schema-only ekklesia_prod > schema_prod_20260523.sql`

### Phase 2: Baseline Repair Migration(s)
- Create idempotent migration(s) using `ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`
- Fix `decisions.id` type: use `IF NOT EXISTS` guard or skip if column already correct
- Each migration must be safe to run on both fresh DB and existing production

### Phase 3: Local Verification
- Fresh local DB + `alembic upgrade head` must match ORM and all raw-SQL tables
- Compare against production schema snapshot

### Phase 4: Production Clone Test
- Test on a copy of production (Hetzner snapshot or pg_dump restore)
- Verify `alembic upgrade head` from `l501a2b3c4d5` applies cleanly

### Phase 5: Production Stamp/Upgrade
- Only after Phase 3+4 pass
- Low-traffic window
- `alembic stamp` new head on production

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| `decisions.id` String→Integer on fresh DB | Breaking — autoincrement fails | Baseline migration must correct this |
| Manual SQL not captured | Future features break on fresh install | Capture all manual additions in migrations |
| `alembic upgrade` on prod with wrong state | Data loss possible | Never run without Phase 4 clone test |
| Raw-SQL tables (rep_tokens, rep_invitations) have no ORM | Drift can recur silently | Consider adding ORM models or explicit DDL documentation |

## Acceptance Criteria (Future Implementation)

1. `alembic upgrade head` on empty DB produces schema matching production
2. `alembic upgrade head` on production DB (from `l501a2b3c4d5`) applies without errors
3. All ORM models match their table schemas
4. `representative_tokens` and `rep_invitations` manual columns are captured

## References

- Schema Drift Notes: `apps/api/alembic/SCHEMA_DRIFT_NOTES.md`
- Migration files: `apps/api/alembic/versions/` (12 files)
- ORM Models: `apps/api/models.py`

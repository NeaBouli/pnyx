<!--
@wiki-page DATABASE
@update-hint Update on schema changes (new tables, columns).
@ai-anchor WIKI_DATABASE
-->

# Σχήμα Βάσης Δεδομένων / Database Schema
# Copyright (c) 2026 Vendetta Labs — MIT License

## Πίνακες / Tables

Source of truth: SQLAlchemy models in `apps/api/models.py` and Alembic
migrations in `apps/api/alembic/versions/`.

### ORM tables (24)

| Table | Module | Description |
|---|---|---|
| identity_records | MOD-01 | Nullifier + public key |
| parties | MOD-02 | 8 parties (scalable) |
| statements | MOD-02 | 38 political statements |
| party_positions | MOD-02 | Party positions |
| parliament_bills | MOD-03 | Bills, bill lifecycle |
| citizen_votes | MOD-04 | Citizen votes |
| bill_relevance_votes | MOD-14 | Relevance signals |
| periferia | MOD-16 | 13 regions |
| dimos | MOD-16 | Municipalities |
| communities | MOD-16 | Communities |
| decisions | MOD-16 | Decisions (all levels) |
| bill_status_logs | MOD-03 | Change history |
| survey_responses | MOD-02 | VAA responses |
| diavgeia_decisions | MOD-21 | Diavgeia decisions |
| dimos_diavgeia_orgs | MOD-21 | 1775 org mappings (Dimos → Diavgeia) |
| zk_identity_commitments | MOD-04 | Semaphore group commitments (no private identity material) |
| zk_merkle_roots | MOD-04 | Merkle root snapshots per vote scope |
| zk_vote_tier_locks | MOD-04 | Private cross-tier lock (never published) |
| zk_vote_receipts | MOD-04 | Public verifier payloads for accepted ZK votes |
| diavgeia_votes | MOD-21 | Citizen votes on Diavgeia decisions |
| knowledge_base | MOD-22 | RAG Agent knowledge base (FAQ, concepts) |
| evaluation_questions | MOD-25 | Representative evaluation questions |
| politician_evaluations | MOD-25 | Citizen evaluation (nullifier_hash, ada_number, question_id, score -5..+5) |
| audit_log | — | Admin action audit trail (no keys/nullifiers) |

### Raw-SQL tables (no SQLAlchemy model)

Accessed via parameterized SQL. Schema drift is partly documented in
`apps/api/alembic/SCHEMA_DRIFT_NOTES.md`.

| Table | Module | Schema source |
|---|---|---|
| polis_identity_keys | — | Alembic migration |
| polis_tickets | — | Alembic migration |
| polis_votes | — | Alembic migration |
| representative_tokens | MOD-25 | No create migration (ADR NEA-256) |
| rep_invitations | — | No create migration (ADR NEA-256) |
| bill_flags | — | No migration/model in repo |
| consensus_votes | — | No migration/model in repo |
| cplm_history | MOD-24 | No migration/model in repo |

## Ausgewählte Spalten / Selected column details

### identity_records (MOD-01)
```sql
nullifier_hash  VARCHAR(64)  UNIQUE NOT NULL  -- SHA256(phone+salt)
public_key_hex  VARCHAR(128) NOT NULL          -- Ed25519 Public Key
demographic_hash VARCHAR(64)                  -- SHA256(region+gender+salt)
age_group       VARCHAR(20)                   -- AGE_18_25 .. AGE_65_PLUS
region          VARCHAR(30)                   -- REG_ATTICA etc.
gender_code     VARCHAR(20)                   -- GENDER_MALE etc.
status          ENUM(ACTIVE, REVOKED)
```

### parties (MOD-02)
```sql
name_el, name_en, abbreviation
color_hex       VARCHAR(7)   -- #1E90FF
description_el, description_en
```

### statements (MOD-02)
```sql
text_el, text_en
explanation_el, explanation_en
category        VARCHAR(50)  -- Υγεία, Περιβάλλον...
display_order   INTEGER
```

### party_positions (MOD-02)
```sql
party_id, statement_id (composite PK)
position        SMALLINT     -- -1, 0, 1
```

### parliament_bills (MOD-03)
```sql
id              VARCHAR(50)  -- GR-2024-0042
title_el, title_en
pill_el, pill_en             -- 1 sentence
summary_short_el/en          -- 3 paragraphs
summary_long_el/en           -- Full analysis
categories      JSONB
party_votes_parliament JSONB -- {"ΝΔ": "ΝΑΙ", ...}
status          ENUM(ANNOUNCED, ACTIVE, WINDOW_24H, PARLIAMENT_VOTED, OPEN_END)
parliament_vote_date DATETIME
```

### citizen_votes (MOD-04)
```sql
nullifier_hash  VARCHAR(64)
bill_id         VARCHAR(50)
vote            ENUM(YES, NO, ABSTAIN, UNKNOWN)
signature_hex   VARCHAR(128) -- Ed25519 Signature
UNIQUE(nullifier_hash, bill_id) -- Prevents double voting
```

### bill_relevance_votes (MOD-14)
```sql
nullifier_hash, bill_id (composite PK)
signal          SMALLINT     -- +1 or -1
```

### survey_responses (MOD-02)
```sql
user_hash       VARCHAR(64)
age_group, region, gender_code
answers         JSONB        -- {statement_id: -1|0|1}
```

### bill_status_logs (MOD-03)
```sql
bill_id, from_status, to_status, changed_at
```

## Migrations
```bash
cd apps/api
alembic upgrade head    # Apply all migrations
alembic history         # Show history
```

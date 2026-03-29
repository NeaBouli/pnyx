<!--
@wiki-page DATABASE
@update-hint Update on schema changes (new tables, columns).
@ai-anchor WIKI_DATABASE
-->

# Σχήμα Βάσης Δεδομένων / Database Schema
# Copyright (c) 2026 Vendetta Labs — MIT License

## Πίνακες / Tables (9 total)

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

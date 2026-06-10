# ADR-004: Versioned server identity nullifier KDF migration

Date: 2026-06-10
Status: Proposed
Tracking: GH#110 / NEA-335

## Context

The production Beta identity flow currently derives `identity_records.nullifier_hash`
with:

```text
SHA256(phone_number + ":" + SERVER_SALT)
```

The phone number is not stored, and `SERVER_SALT` is now guarded at startup so the
API fails closed if the salt is missing, weak, or a known default. This materially
reduces operational risk, but the derivation is still not memory-hard. If
`SERVER_SALT` is ever disclosed, Greek mobile numbers are a bounded search space
and can be brute-forced offline.

Client-side voting nullifier roots are a separate mechanism. This ADR concerns
the server-side identity duplicate-prevention nullifier only.

## Threat Model

Protected against:

- Database-only compromise: attacker sees nullifier hashes but not phone numbers.
- Accidental weak production salt: already mitigated by startup guard.
- Future offline brute force if the database leaks and `SERVER_SALT` later leaks.

Not solved by this ADR:

- A malicious live server can still observe the submitted phone number during HLR
  verification.
- A compromised HLR provider may observe lookup metadata.
- Existing SHA256-derived records cannot be re-derived into Argon2id without the
  original phone number, which is intentionally not stored.

## Constraints

- Do not break existing voters or vote history.
- Do not weaken duplicate-prevention during migration.
- Do not require storing phone numbers.
- Do not rewrite historical vote nullifiers.
- Keep `citizen_votes`, `diavgeia_votes`, `polis_identity_keys`, and evaluation
  tables stable unless a separate design explicitly migrates them.
- Rollback must not create a second active identity for the same phone number.

## Decision

Use a versioned identity-nullifier scheme.

### New derivation

For new registrations after the migration:

```text
identity_nullifier_v2 =
  "v2:" + Argon2id(
    input = normalized_e164_phone_number,
    salt = HMAC_SHA256(SERVER_SALT, "ekklesia:identity-nullifier:v2"),
    memory_cost = production-calibrated,
    time_cost = production-calibrated,
    parallelism = 1
  )
```

If Argon2id is operationally too heavy for the API container, use `scrypt` as the
fallback KDF, still version-prefixed:

```text
"v2s:" + scrypt(...)
```

The KDF parameters are part of the versioned protocol. Once deployed, the
Argon2id/scrypt memory/time/parallelism parameters must be treated as immutable
for that version. Changing them requires a new prefix (`v3`, `v3s`, ...) and a
new migration path, otherwise re-verification of existing v2 identities will no
longer match.

### Database shape

Add fields instead of mutating the existing column in place:

```text
identity_records.nullifier_hash        -- existing v1 SHA256 value, keep for compatibility
identity_records.nullifier_hash_v2     -- nullable, unique, new KDF value
identity_records.nullifier_version     -- "v1" or "v2"
identity_records.nullifier_migrated_at -- nullable timestamp
```

New registrations store both:

- `nullifier_hash`: v1 SHA256 compatibility value
- `nullifier_hash_v2`: v2 KDF value
- `nullifier_version`: `v2`

The v1 compatibility value is intentionally retained for duplicate detection
against existing records until the Beta population is fully rotated.

### Lookup rules

On `/identity/verify`:

1. Normalize the submitted phone number.
2. Compute v1 and v2 nullifiers.
3. Check for an existing active record by `nullifier_hash_v2 = v2`.
4. Also check `nullifier_hash = v1` for legacy records.
5. If a legacy v1 record exists:
   - update that same row with `nullifier_hash_v2 = v2`,
   - set `nullifier_version = "v2"`,
   - preserve duplicate-prevention identity continuity,
   - continue the existing re-registration/revocation semantics.
6. If no record exists, create a new v2 record with both values.

This avoids a window where the same phone can register once under v1 and once
under v2.

## Rollback

Rollback plan:

- Keep the v1 `nullifier_hash` column populated for all v2 records.
- If the v2 path must be disabled, set an env flag:

```text
IDENTITY_NULLIFIER_KDF_VERSION=v1
```

- The API falls back to the existing v1 lookup and write path.
- The v2 columns remain unused but harmless.

Never drop v1 compatibility fields until a separate deprecation ADR proves that
all downstream references no longer depend on them.

## Tests Required Before Implementation

Unit tests:

- Phone normalization produces identical v1/v2 for equivalent E.164 inputs.
- v2 derivation is deterministic with fixed test salt.
- v2 differs from v1 and uses a version prefix.
- weak/missing salt still fails closed.

API tests:

- New phone creates a v2 identity record with both v1 and v2 populated.
- Existing v1 identity re-registers into the same row, not a second row.
- Duplicate active phone is still prevented.
- Revocation and re-registration semantics remain unchanged.
- Existing vote status, Polis, Diavgeia, and evaluation queries still work.

Migration tests:

- Alembic upgrade adds nullable v2 fields and unique index.
- Alembic downgrade removes only v2 fields/indexes.
- Backward-compatible read path works with pure v1 rows.

Operational tests:

- Production-like Argon2id cost benchmark inside the API container.
- HLR verification latency budget with KDF enabled.
- Rollback env flag tested on staging or local prod clone.

## Preliminary Production-Container Benchmark

Measured on 2026-06-10 inside the running `ekklesia-api` container, with a test
phone value and a non-secret test salt. No DB or identity state was touched.

```text
python 3.12.13
argon2_spec True
scrypt True
scrypt n=16384 r=8 p=1 maxmem=128MiB ms=61.9
scrypt n=32768 r=8 p=1 maxmem=128MiB ms=96.0
scrypt n=65536 r=8 p=1 maxmem=128MiB ms=196.2
argon2id t=2 m=16384KiB p=1 ms=28.4
argon2id t=2 m=32768KiB p=1 ms=50.7
argon2id t=2 m=65536KiB p=1 ms=107.8
argon2id t=2 m=131072KiB p=1 ms=216.0
```

Preliminary conclusion: `argon2-cffi` is already available in the production API
image. Argon2id with `time_cost=2`, `memory_cost=65536 KiB`, `parallelism=1`
appears operationally plausible for identity verification latency, but this is
not a final parameter decision. The final implementation must pin parameters as
part of the versioned prefix and re-run the benchmark before enabling v2.

## Non-Goals

- No historical vote nullifier migration.
- No phone-number storage.
- No ZK/Semaphore implementation.
- No change to Ed25519 vote signatures.

## Implementation Order

1. Benchmark Argon2id and scrypt in the API container.
2. Add migration fields/indexes.
3. Add KDF helpers with version prefixes and tests.
4. Add dual-lookup/dual-write verify path behind an env flag defaulting to v1.
5. Run focused identity/voting/Polis/Diavgeia/evaluation tests.
6. Deploy with env flag still v1.
7. Flip env flag to v2 only after live smoke and rollback tag.

## Current Recommendation

Do not implement this during a broad hardening session. The safe next step is a
focused implementation ticket using this ADR as the checklist.

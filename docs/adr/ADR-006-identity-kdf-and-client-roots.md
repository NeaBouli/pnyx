# ADR-006: Identity KDFs, client roots and versioned vote envelopes (EVA-007)

Date: 2026-10-16
Status: Proposed. Owner decisions D1–D4 below are open (Gio).
Tracking: EVA-007 (P1, audit 2026-10-11); related: ADR-004, EVA-001/003/006/008/010/037

## Context

The audit finding EVA-007 says that the mobile key hierarchy uses the phone number as root entropy, and asks for a versioned KDF, cross-implementation KATs, and a migration that keeps vote history and replay protection. A code analysis on 2026-10-16 (checkout `ff72b86b`; facts report `.fleet/reports/EVA-007-facts-codex.md`, every claim with file:line) found the following.

### What exists

| Derivation | Construction | Status |
|---|---|---|
| Mobile `deriveNullifierRoot` (`apps/mobile/src/lib/crypto-native.ts`) | PBKDF2-SHA256(phone, **public** salt `ekklesia.gr:registration:2026:v1`, 100k) → root → HMAC chain: identity commitment, per-bill vote nullifier, **ephemeral private signing seed**, linkage tag, POLIS seed | **Dormant**: only `registerTier1` calls it, and nothing calls `registerTier1`. The released app verifies with `POST /api/v1/identity/verify` and stores a random server-issued key. |
| TS package `deriveNullifierRoot` (`packages/crypto/src/nullifier.ts`) | Argon2id(phone, same public salt, t=3, m=64 MiB) | Library and tests only; no app consumer. Its Tier-1 signed bytes differ from mobile/API (K7, asserted by tests). |
| Server identity v1 (`packages/crypto/nullifier.py`) | `SHA256(phone + ":" + SERVER_SALT)` | **Live**; it is the compatibility anchor for votes, POLIS, municipal votes and evaluations. It hashed the **raw** request string (fixed by EVA-037, #601). |
| Server identity v2 | Argon2id(normalized phone, salt = SHA256(context ‖ SERVER_SALT), t=2, m=64 MiB) | **Live** in prod (`IDENTITY_NULLIFIER_KDF_VERSION=v2`; 16 v2 rows, 15 v1-only on 2026-10-16). It is written next to v1, and v1 stays the anchor. |

### What follows from it

1. **Phone-derived client roots must never go live in their current form.** Anyone who knows (or enumerates: ~10^8 = 26.6 bits) a phone number can compute the public-salt root offline. Every HMAC child follows from it, including per-bill **private** signing seeds and vote nullifiers. Domain separation adds no entropy. Argon2id only raises the cost per guess.
2. **The live risk sits server-side.** A DB leak alone links all votes of one identity across bills (the stable anchor is stored next to each choice; that is EVA-006). A DB leak **plus `SERVER_SALT`** lets an attacker enumerate the fast v1 SHA-256 (also for v2 rows, because v1 is still stored) and map phone → identity → individual votes. The operator sees the phone at verification anyway.
3. **Legacy reads/writes widen exposure:**
   - (a) `GET /api/v1/vote/{bill}/status` without a signature returns the stored choice, because `VOTE_STATUS_REQUIRE_SIGNED` is unset in prod. The cutoff is prepared: `.fleet/reports/GATE-VOTE-STATUS-REQUIRE-SIGNED.md`.
   - (b) Legacy vote signatures (`bill:choice:nullifier`) carry no timestamp, nonce or version. A captured earlier signature can be replayed in an update window to revert a correction.
4. **Inconsistencies:**
   - ADR-004 specifies the v2 salt as `HMAC_SHA256(SERVER_SALT, context)`; the code uses `SHA256(context ‖ SERVER_SALT)`. The deployed v2 values are authoritative, so the ADR text is wrong, not the code.
   - The two client-root implementations use the same `ekklesia:v1` label for different KDFs.

## Decision (proposed)

### A. Client roots (Tier-1): random device root, never phone-derived
- `deriveNullifierRoot`/`registerTier1` (mobile) and the package's phone-root registration get marked **deprecated/forbidden**. A test asserts that no app code path calls them (guard against accidental activation). Deleting them is a separate cleanup PR.
- If Tier-1 per-bill nullifiers are ever activated, the root is **32 random bytes generated on the device** (same pattern as the device keys from EVA-001 PR3/PR4). Phone verification authorizes the enrollment; it does not supply the entropy. A lost device means re-enrollment of a **new** root against the same eligibility/history record; the spent-vote ledger stays shared, and there is no recovery of the old root.
- **Rejected:** an OPRF root (RFC 9497). It protects against outsiders, but the operator holding the OPRF key can still evaluate known numbers. It needs authorization and rate limiting as an online enumeration service, and it does not solve the server-side anchor (point 2). Its complexity isn't justified while Tier-1 is dormant.

### B. Server deduplication: v3 with a dedicated key, then retire the fast v1
- **v3** = `HMAC-SHA256(K_dedupe, "ekklesia:identity-dedupe:v3:" ‖ E164(phone))`, optionally followed by Argon2id with fixed parameters. `K_dedupe` is a new 32-byte random secret, separate from `SERVER_SALT` and outside the DB. It is used **only** for lookup and duplicate prevention. Canonical E.164 comes from **one** shared function (`normalize_greek_number`). The normalization drift between v1, v2 and HLR led to EVA-037.
- Dual lookup v3 → v2 → v1 (canonical + legacy forms, as in EVA-037) into the **same row**; the vote anchor (`nullifier_hash`) stays unchanged (ADR-004 continuity).
- **Retiring the v1 verifier** (owner decision D2): after a cutoff (all active identities have v3), the v1 anchor stays only as an opaque history key. **New** derivations from `SERVER_SALT` stop. Then a leak of DB + `SERVER_SALT` no longer allows phone enumeration via v1 for new or migrated identities. Already-leaked values can't be repaired.
  - Downside: identities without v3 at the cutoff can't be found via v1 any more, so re-verifying would create a new identity (a duplicate on open bills). That's why the cutoff must work like the app cutoff (D4, ≥ 95 % / 60 days) with an in-app notice, and old rows get deactivated rather than kept as orphans.
- The v1 anchor next to the vote stays (EVA-006 is about separating identity and ballot; out of scope here).

### C. Versioned vote envelope (replay protection)
- New signed message for votes and corrections: `ekklesia:vote:v2:{bill_id}:{CHOICE}:{nullifier}:{timestamp_ms}:{nonce}` with a ±5-minute window. The server stores the last accepted `(timestamp, nonce)` per row and rejects anything older or equal.
- The legacy format is accepted during a transition window (flag `VOTE_LEGACY_SIGNATURE_ACCEPTED`), then rejected after the same cutoff as D4.

### D. KATs and specification
- One specification per protocol: server dedupe v1/v2/v3, device root, vote envelope v2. Each fixes normalization, encoding, salt construction, Argon2 version and parameters, and domain strings.
- Cross-implementation KATs (Python/TS/mobile) for every protocol several clients compute (vote envelope v2, device-root children). Server-only KATs for dedupe.
- ADR-004 gets a correction note for the v2 salt (the code is authoritative).

## Owner decisions (open)
- **D1:** Mark the phone-derived client roots as forbidden now (plus guard test), delete later. *Recommendation: yes.*
- **D2:** v3 with a dedicated `K_dedupe` + retire v1 after a cutoff. Needs a new secret (Gio: secret handling). *Recommendation: yes, after the EVA-001 series.*
- **D3:** Vote envelope v2 with timestamp/nonce + legacy window. App release needed (store gate). *Recommendation: yes, bundled with the next app release that brings device keys.*
- **D4:** Cutoff policy for v1 lookup and legacy signatures: as for EVA-001 D4 (≥ 95 % migrated active clients, at the latest 60 days) with an in-app notice.

## Consequences
- No behavior change from this ADR itself; every step is its own flag-guarded PR with a migration test.
- Remaining risks until B/C are implemented: points 2 and 3. 3(a) is mitigated by the planned `VOTE_STATUS_REQUIRE_SIGNED` switch.
- Ballot secrecy against the operator and against a DB leak (stable anchor next to the choice) stays open and is handled in the EVA-006 ADR.

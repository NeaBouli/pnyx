# ADR-006: Identity KDFs, client roots and versioned vote envelopes (EVA-007)

Date: 2026-10-16
Status: Proposed. Owner decisions D1–D6 below are open (Gio).
Tracking: EVA-007 (P1, audit 2026-10-11); related: ADR-004, EVA-001/003/006/008/010/037,
`docs/security/VOTE_STATUS_READ_MIGRATION.md`

## Context

EVA-007 says the mobile key hierarchy uses the phone number as root entropy, and asks for a versioned KDF, cross-implementation KATs, and a migration that keeps vote history and replay protection. The basis is a code analysis on 2026-10-16 (baseline `ff72b86b`, plus EVA-037 from `8f48ed03`; source references below) and separate read-only production checks (*Receipts*). "Merged" ≠ "deployed": production runs `b343adfa`.

Source references: `apps/mobile/src/lib/crypto-native.ts` (`deriveNullifierRoot`, `registerTier1`, `getOrDerivePolisKey`, `signVoteEphemeral`), `packages/crypto/src/nullifier.ts` + `types.ts` (package roots, Tier-1 payload), `packages/crypto/nullifier.py` (v1/v2, `normalize_phone_number`), `packages/crypto/hlr.py` (`normalize_greek_number`), `apps/api/routers/identity.py` (`_v1_anchors`, `_v2_anchors`, verify/revoke), `apps/api/routers/voting.py` + `apps/api/crypto/nullifier.py` (legacy and Tier-1 votes), `apps/api/routers/polis_qr.py` (QR proxy), `apps/api/models.py` (`identity_records`, `citizen_votes`, uniqueness `(nullifier_hash, bill_id)`), `packages/crypto/tests/vectors/eka22_kat_v1.json` (KATs).

### Derivations in the code

| Derivation | Construction | Reachability |
|---|---|---|
| Mobile `deriveNullifierRoot` (`apps/mobile/src/lib/crypto-native.ts`) | PBKDF2-SHA256(phone, **public** salt `ekklesia.gr:registration:2026:v1`, 100k) → root → HMAC chain: identity commitment, per-bill vote nullifier, **ephemeral private signing seed**, linkage tag, POLIS seed | Only `registerTier1` calls it, and nothing calls `registerTier1`. Registration uses `POST /api/v1/identity/verify` with a random server-issued key. **But:** `getOrDerivePolisKey` reads an already stored root if present. How many installs have one is unknown. |
| TS package `deriveNullifierRoot` (`packages/crypto/src/nullifier.ts`) | Argon2id(phone, same public salt, t=3, m=64 MiB) | Library and tests only. Its Tier-1 signed bytes differ from mobile/API (K7, asserted by tests). |
| Server identity v1 (`packages/crypto/nullifier.py`) | `SHA256(phone + ":" + SERVER_SALT)` | Live. It is the anchor (`nullifier_hash`) for votes, POLIS binding, municipal votes and evaluations. Since EVA-037 (#601, `8f48ed03`) it is derived from the normalized number; older spellings are only looked up. |
| Server identity v2 | Argon2id(normalized phone, salt = SHA256(context ‖ SERVER_SALT), t=2, m=64 MiB) | Live when `IDENTITY_NULLIFIER_KDF_VERSION=v2`. Written next to v1; v1 stays the anchor. |

The API also accepts optional **Tier-1 metadata** (vote nullifier, linkage tag, ephemeral signature) on votes. Validation checks format, freshness, uniqueness and the ephemeral signature, but **not** that it belongs to an enrolled root or commitment.

### Consequences

1. **Phone-derived client roots must never go live in their current form.** Anyone who knows (or enumerates: ~10^8 ≈ 26.6 bits) a phone number can compute the public-salt root offline. Every HMAC child follows from it, including per-bill **private** signing seeds. Domain separation adds no entropy; Argon2id only raises the cost per guess.
2. **The live risk sits server-side.**
   - A DB leak alone links all votes of one identity across bills, because the stable anchor sits next to each choice (EVA-006).
   - A DB leak **plus `SERVER_SALT`** makes every stored v1 anchor computable offline from a phone number. That covers v2 rows too, because their v1 anchor is still stored. It maps phone → identity → individual votes.
   - **This exposure belongs to the stored anchor values. Changing the lookup policy can't repair it; only giving historical anchors new values or keeping the salt secret can.**
3. **Legacy reads/writes:**
   - (a) The unsigned `GET /api/v1/vote/{bill}/status` returns the stored choice while `VOTE_STATUS_REQUIRE_SIGNED` is not `true` (migration plan: `docs/security/VOTE_STATUS_READ_MIGRATION.md`).
   - (b) Legacy vote signatures (`bill:CHOICE:nullifier`) carry no timestamp, nonce, version or operation. A captured earlier signature can be replayed in an update window, or submitted to the correction route.
4. **Online takeover (EVA-010):** HLR doesn't prove possession of the SIM, and v1 re-registration replaces an ACTIVE key without the old key or an OTP. Random entropy (whether server- or device-generated) prevents offline derivation, not this online takeover.
5. **Inconsistencies:**
   - ADR-004 specifies the v2 salt as `HMAC_SHA256(SERVER_SALT, context)`; the code uses `SHA256(context ‖ SERVER_SALT)`. The deployed values are authoritative, so the ADR text is wrong.
   - Both client-root implementations use the same `ekklesia:v1` label for different KDFs.

## Decision (proposed)

### A. Client roots: never phone-derived (D1)
- `deriveNullifierRoot`/`registerTier1` (mobile) and the package's phone-root registration are **forbidden**. A guard test checks that no app path calls them. Removal comes in a cleanup PR.
- `getOrDerivePolisKey` keeps reading existing stored roots: removing that would change pk_polis for those users. New installs can't create a root.
- If Tier-1 per-bill nullifiers are ever activated, the root is **32 random bytes generated on the device**, and enrollment needs
  - (i) authorization by the current identity key, or the OTP possession proof (EVA-001 PR1b), and
  - (ii) proof of possession of the new key.

  Lost-device recovery is its own flow (OTP + cooldown + audit). The spent-vote ledger is per eligibility record (not per root), so a new root can't vote again on bills already voted on.
- Until then, the Tier-1 metadata on votes gets **ignored or rejected** (flag), because nothing proves it belongs to an identity (D6).
- **Rejected: OPRF root (RFC 9497).** It protects against outsiders, but the operator holding the key can still evaluate known numbers. It needs authorization and rate limiting as an online enumeration service, and it doesn't solve point 2.

### B. Server anchors and deduplication (D2, D5)
- **New identities get a random anchor:** `nullifier_hash` = 32 random bytes as **64 lowercase hex**, the same format as today. That keeps `String(64)` and every hex64 validator (voting, QR, POLIS, rotation, key-check) compatible; a new column `anchor_kind` (`v1` | `random`) tells them apart. Deduplication runs through a new lookup column **v3** = `HMAC-SHA256(K_dedupe, "ekklesia:identity-dedupe:v3:" ‖ E164(phone))`, with a **unique index**, and `K_dedupe` as a new 32-byte secret outside the DB (not `SERVER_SALT`).
  - Registration is atomic: lock on v3, look up v3 → v2 → v1, insert. That replaces the uniqueness that deterministic anchors gave implicitly.
  - Writers that don't know v3 (old API versions) must not be running during rollout or rollback: no mixed operation, and rollback only to a version with v3 lookup.
  - A DB leak then doesn't link a new anchor to a phone number. With `K_dedupe` as well, only the v3 column can be enumerated, so `K_dedupe` belongs in a secret store separate from the DB credentials.
- **Existing identities:** dual lookup v3 → v2 → v1 (canonical + legacy forms, EVA-037) into the **same row**. On the next verification the row receives v3. The v1 anchor next to historical votes stays as it is (ADR-004 continuity), and so does its exposure from point 2.
- **D5, deliberately rewriting historical anchors:** a one-off migration replaces each v1 anchor in every table with a random anchor (no mapping kept; anchor columns have no FK, so every table needs an explicit migration). **Alone that isn't enough**, because other artifacts remain as oracles:
  - (i) `nullifier_hash_v2` (computable with `SERVER_SALT`);
  - (ii) stored legacy vote signatures over `bill:CHOICE:nullifier`, which confirm a guessed old anchor together with the stored public key;
  - (iii) for installs with an existing phone-derived root (kept by §A for POLIS compatibility), the POLIS public key computable from a guessed phone, via the stored POLIS binding (`polis_identity_keys`) to the rewritten anchor. This works **without** `SERVER_SALT`. How many installs are affected is unknown; the remedy is a POLIS rebind for those installs (EVA-001 POLIS design TODO).

  An effective rewrite also requires removing v2 after the cutoff and removing or re-signing old signatures, which in turn gives up the ability to re-check old votes (ADR-004 continuity). Owner decision, with its own section (backup, rollback, audit consequences).
- **No duplicates at cutoff (fail closed):** v1/v2 lookup is retired only after a cutoff (by server state: share of identities without v3, not by app versions).
  - A verification without a v3 match then doesn't create an ACTIVE identity; it lands in `PENDING_LEGACY_REVIEW`.
  - A review can only **positively** confirm a legacy match (standard forms, EVA-037). A **negative** result does **not** authorize activation, because v1 rows from exotic spellings stay unreachable. Unresolved cases stay pending until an owner-defined review (e.g. confirmation via the old identity key or explicit owner approval). Completion happens atomically against the original eligibility record (adopt v3, keep its anchor).
  - **Prerequisite for taking `SERVER_SALT` offline:** today it is also used by the invite-code hash (`services/invite_codes.py`, y802), push registration (`services/push_registration.py`), vote receipts (`routers/voting.py`), the ZK tier lock (`services/zk_tier_lock.py`, `routers/zk.py`), gov.gr (`routers/govgr.py`), admin paths (`routers/admin*.py`) and the startup check. Each needs a dedicated key with its own migration plan before then, because replacing it invalidates existing keyed values. The rate-limit/log-reference HMAC (`apps/api/ip_utils.py`) falls back to `SERVER_SALT` when `RATE_LIMIT_SALT` is unset, and without both to a **public** development literal. So `RATE_LIMIT_SALT` must be provisioned and validated at startup before `SERVER_SALT` is removed.

### C. Versioned vote envelope (D3)
- Signed message: `ekklesia:vote:v2:{op}:{bill_id}:{CHOICE}:{nullifier}:{revision}:{timestamp_ms}:{nonce}`.
  - `op ∈ {cast, update, correct}`, so an update can't be redeemed as a correction.
  - `revision` is the revision of the vote row that the client had seen. Writes are **compare-and-swap on that revision**: stale intents fail instead of overwriting newer state.
  - For the **QR proxy**, the expected revision and the operation get bound to the QR authorization when the session is created (signed by the app), and they survive retries. The proxy doesn't fill in the current revision, so a delayed QR request can't overwrite a newer signed update.
  - The timestamp (±5 min) only prevents stale replays; equal timestamps are resolved by the revision.
- **Protocol floor:** once an identity has written with v2, the server no longer accepts legacy signatures for it (column `vote_protocol_min` on `identity_records`). Floor check, floor raise and vote commit run under an **identity-wide lock** (row lock on the identity record) for every writer. Otherwise a legacy write on bill A could read the old floor while a v2 write on bill B raises it. For identities that haven't moved up, the legacy replay risk remains until the global cutoff (documented).
- The legacy format is accepted within a transition window (flag `VOTE_LEGACY_SIGNATURE_ACCEPTED`), then rejected.

### D. KATs and specification
- One specification per protocol: dedupe v1/v2/v3, random anchor, device root, vote envelope v2. Each fixes normalization (one shared `normalize_greek_number`), encoding, salt construction, Argon2 version and parameters, and domain strings.
- Cross-implementation KATs (Python/TS/mobile) for every protocol several clients compute (vote envelope v2, device-root children). Server-only KATs for dedupe and anchor.
- ADR-004 gets a correction note for the v2 salt (the code is authoritative).

## Owner decisions (open)
- **D1:** Phone-derived client roots forbidden now (guard test), removal later. *Recommendation: yes.*
- **D2:** Random anchor for new identities + v3 lookup with a dedicated `K_dedupe` (a new secret, so Gio's secret handling applies). *Recommendation: yes, after the EVA-001 series.*
- **D3:** Vote envelope v2 (op, revision CAS, protocol floor) + legacy window; needs an app release (store gate). *Recommendation: yes, bundled with the device-key release.*
- **D4:** Cutoff for v1/v2 lookup by server state (share without v3), then `SERVER_SALT` into cold storage and `PENDING_LEGACY_REVIEW` (fail closed).
- **D5:** Re-key historical anchors (ends the phone link of old votes after a leak, breaks ADR-004 continuity). *Recommendation: decide together with the EVA-006 ADR.*
- **D6:** Ignore/reject Tier-1 metadata on votes until there is an enrollment proof. *Recommendation: yes (flag, no client sends it today).*

## Receipts (production, read-only, 2026-10-16)
- `IDENTITY_NULLIFIER_KDF_VERSION`: value `v2` in `/opt/ekklesia/.env.production` and in the running API container (only the value was read, no secrets).
- `identity_records` by `nullifier_version`: 16 × `v2`, 15 × `v1`. Of the 15 v1-only rows, 3 have votes; read-only pattern check (counts only) found no identity pair with ≥ 2 shared bills and identical choices.
- `VOTE_STATUS_REQUIRE_SIGNED` in the running API container: unset.
- API image `ekklesia-api:api-b343adfa-20261015T203837Z`; EVA-037 (#601) is merged but not yet deployed.

## Consequences
- No behavior change from this ADR itself; every step is its own flag-guarded PR with a migration test.
- Until B/C/D5 are in place, points 2–4 remain residual risks. 3(a) is mitigated by the planned `VOTE_STATUS_REQUIRE_SIGNED` switch, and 4 by the EVA-001 OTP decision (PR1b).
- Ballot secrecy against the operator and a DB leak (stable anchor next to the choice) is handled in the EVA-006 ADR.

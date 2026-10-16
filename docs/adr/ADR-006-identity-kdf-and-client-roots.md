# ADR-006: Identity KDFs, client roots and versioned vote envelopes (EVA-007)

Date: 2026-10-16
Status: Proposed. Owner decisions D1–D6 below are open (Gio).
Tracking: EVA-007 (P1, audit 2026-10-11); related: ADR-004, EVA-001/003/006/008/010/037,
`docs/security/VOTE_STATUS_READ_MIGRATION.md`

## Context

EVA-007 says the mobile key hierarchy uses the phone number as root entropy, and asks for a versioned KDF, cross-implementation KATs, and a migration that keeps vote history and replay protection. A code analysis on 2026-10-16 (checkout `ff72b86b`, every claim with file:line) gives this picture. The production values come from separate read-only checks (see *Receipts*).

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
- **New identities get a random anchor:** `nullifier_hash = "r1:" + 32 random bytes (hex)`, unrelated to the phone number. Deduplication runs through a separate lookup column **v3** = `HMAC-SHA256(K_dedupe, "ekklesia:identity-dedupe:v3:" ‖ E164(phone))`, with `K_dedupe` as a new 32-byte secret outside the DB, not `SERVER_SALT`. A DB leak then doesn't link a new anchor to a phone number. With `K_dedupe` as well, only the lookup column can be enumerated, and the anchor would also have to be joined. That's why `K_dedupe` belongs in a secret store separate from the DB credentials.
- **Existing identities:** dual lookup v3 → v2 → v1 (canonical + legacy forms, EVA-037) into the **same row**. On the next verification the row receives v3. The v1 anchor next to historical votes stays as it is (ADR-004 continuity), and so does its exposure from point 2.
- **D5, deliberately rewriting historical anchors:** a one-off migration replaces each v1 anchor in every table with a random `r1:` anchor, with no mapping kept. That ends the phone link of all historical votes after a leak, but breaks the continuity ADR-004 requires (audit/re-checking old signatures against the anchor). Needs an owner decision and its own ADR section with a backup and rollback plan.
- **No duplicates at cutoff (fail closed):** v1/v2 lookup is retired only after a cutoff, and `SERVER_SALT` then moves to **offline/cold storage** rather than being deleted. A verification that finds no v3 match doesn't create an ACTIVE identity. It lands in `PENDING_LEGACY_REVIEW` until a separate offline step with the cold `SERVER_SALT` has checked for an existing v1/v2 row. Eligibility continuity therefore doesn't depend on a client adoption rate. The cutoff is about server state (share of identities without v3), not about app versions.

### C. Versioned vote envelope (D3)
- Signed message: `ekklesia:vote:v2:{op}:{bill_id}:{CHOICE}:{nullifier}:{revision}:{timestamp_ms}:{nonce}`.
  - `op ∈ {cast, update, correct}`, so an update can't be redeemed as a correction.
  - `revision` is the row revision currently known to the server. Writes are **compare-and-swap on the revision** (atomic, for all writers including the QR proxy, which sets the revision on the server side). That defines order, equal timestamps, retries and concurrency cleanly; the timestamp (±5 min) only prevents stale replays.
- **Protocol floor:** once an identity has written with v2, the server no longer accepts legacy signatures for it (column `vote_protocol_min`). There is no downgrade replay against identities that have moved up. For identities that haven't, the legacy replay risk remains until the global cutoff (documented).
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

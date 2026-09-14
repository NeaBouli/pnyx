# ekklesia.gr / pnyx — Cryptography Deep Audit

**Auditor:** Collateral Web3 Open Audits
**Client:** NeaBouli / ekklesia.gr (pnyx)
**Date:** 2026-09-15
**Baselines:** repo `NeaBouli/pnyx` @ `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` · prior art read: `docs/adr/` (ADR-004 nullifier KDF migration, ADR-022 Tier-1, NEA-249 ZK hybrid)
**Companion documents:** full-scope security audit (EKA-01…20) · integration, content coherence, AI readiness audits (register continues EKA-26+)
**Report version:** 1.0

Scope: every cryptographic construction in the monorepo — Python identity layer
(`packages/crypto`: Ed25519 keypair/sign/verify, nullifier v1 SHA-256 + v2 Argon2id,
demographic hash, HLR), TypeScript Tier-1 protocol (`packages/crypto/src`: Argon2id root
derivation, HMAC-SHA256 nullifier chain, ephemeral Ed25519 vote keys, POLIS ticket crypto),
mobile native crypto (`apps/mobile/src/lib/crypto-native.ts`), the server-side Semaphore
Groth16/BN254 verifier and ZK storage layer, Arweave publication payloads, and the client
compass encryption (AES-256-GCM/HKDF).

**Verdict: SOUND with one structural drift.** The constructions themselves are correct and
conservative — domain-separated HMAC everywhere, fail-closed ZK verification against a
hash-pinned verification key, DB-unique anchors on every double-spend path, recursive
leak checks before any Arweave publication. The material problem is not a broken primitive
but **three diverging KDF implementations** of the same "nullifier root" across server,
web and mobile.

**Findings: 0 Critical · 0 High · 1 Medium · 1 Low · 3 Informational (EKA-21 … EKA-25)**

| # | Severity | Title | Status |
|---|----------|-------|--------|
| EKA-21 | Medium | Three diverging nullifier-root KDF implementations (Argon2id t=2 server / t=3 web / PBKDF2-100k mobile) | Open |
| EKA-22 | Low | No cross-implementation test vectors or published KATs for any crypto path | Open |
| EKA-23 | Informational | Residual risk: low-entropy phone-number space bounds all nullifier KDFs (quantified) | Accepted (ADR-004/022) |
| EKA-24 | Informational | `computeNullifier(phone, serverSalt)` exported in web bundle (unused outside tests) | Open |
| EKA-25 | Informational | Server-side political position derivation (CPLM) vs "compass never leaves client" framing | Tracked in content audit |

---

## 1. What is proven correct (lead-verified)

**Python identity layer (`packages/crypto/`)**
- v1 nullifier: `SHA256(f"{phone}:{SERVER_SALT}")` (`nullifier.py:37-51`) — exactly as
  documented; dev-salt default exists but production startup fails closed on it
  (`security_startup.py:31-37`).
- v2 nullifier: Argon2id `Type.ID`, t=2, m=64 MiB, p=1, 32 B output, KDF salt
  `SHA256("ekklesia:identity-nullifier:v2" + SERVER_SALT)`, E.164-normalized input,
  `"v2:"` prefix (`nullifier.py:54-82`). DB schema carries v1+v2 side-by-side with version
  marker and migration timestamp (`models.py:53-56`) — the migration design itself is
  exemplary (dual-write, guarded operator window scripts `scripts/gh111-*`).
- Ed25519 helpers are thin PyNaCl wrappers; private keys are generated server-side and
  returned exactly once (legacy flow), never stored.

**TypeScript Tier-1 protocol (`packages/crypto/src/`)**
- Root: Argon2id(t=3, 64 MiB, p=1) over E.164-normalized phone with the *public*
  `REGISTRATION_SALT` — explicitly documented as cost-based, not secrecy-based
  (`types.ts:22-27`).
- Chain: `identity_commitment = HMAC(root, DOMAIN.IDENTITY_COMMITMENT)` — the only value
  sent to the server; `vote_nullifier = HMAC(root, "ekklesia:vote_nullifier:v1:"+billId)`;
  two-stage linkage tag; deterministic per-bill ephemeral Ed25519 keypairs with key
  zeroization after signing (`nullifier.ts:176,218,237,252,307-323`). All domain
  separators distinct and versioned (`types.ts:31-39`).
- POLIS: separate domain (`POLIS_KEY` → `POLIS_TICKET_KEY`), ticket + vote nullifiers,
  2000-char content cap (`polis.ts:59-187`).

**Semaphore ZK (server side)**
- Pure-Python Groth16 verifier over BN128 (py-ecc); verification key **SHA-256-pinned**
  (`6ef3f6ae…ca2319`) and checksum-enforced at load — fail-closed
  (`zk_groth16_verifier.py:29-39`). Public-input hashing matches
  `@semaphore-protocol/proof` (`keccak256(...) >> 8`, `:42-47`). Handles the Mopro/Android
  snake_case proof shape (`:50-59`).
- Scope/merkle: Semaphore-compatible LeanIMT/Poseidon roots (no placeholder hashes),
  per-scope groups, proof↔scope↔commitment binding enforced at vote time
  (`zk.py:1001-1010`), published OPEN root required (`:1012-1032`), double-vote anchor
  `UNIQUE(vote_scope_id, semaphore_nullifier)` (`models.py:317-322`).
- Cross-tier guard: `tier_guard_hash = HMAC-SHA256(SERVER_SALT,
  "ekklesia:vote-tier-lock:v1:{scope}:{tier1_nullifier_hash}")`, salt length ≥32 enforced
  (`zk_tier_lock.py:38-56`); ZK opt-in is Ed25519-signed against the legacy identity,
  locks the legacy path before the ZK path opens (`zk.py:761-828`).
- Rollout discipline: 8 independent env flags, canary scope allowlist, canary receipts
  never published, min anonymity-set 5, forbidden-field recursive leak check raising
  before any payload leaves (`zk_arweave_payload.py:44-48,74-92`,
  `zk_arweave_publisher.py:63-85`).

**Arweave**
- Bill audit-trail publisher never includes individual votes/nullifiers
  (`arweave.py:3-8,39`); wallet mounted read-only; dry-run without wallet; TX id format +
  reachability re-verified after upload (`arweave.py:88-148`).

**Client compass encryption**
- AES-256-GCM with HKDF-SHA256(Ed25519 private key, salt `"ekklesia-compass-v1"`, info
  `"aes-256-gcm"`), random 12-byte IV per save (`apps/web/src/lib/compass/storage.ts:24-52`).
  Construction correct; its practical protection is bounded by key storage — tracked as
  EKA-07/EKA-08 in the full-scope report, not re-counted here.

**Crypto hygiene repo-wide**
- No circuits, `.zkey`, `.wasm` or trusted-setup material committed; the 23 MB vendored
  `libsemaphore_bindings.so` is the only opaque binary (provenance: zkmopro build —
  see surfaces audit).
- `py-ecc 8.0.0`, `PyNaCl 1.6.2`, `cryptography 50.0.1`, `@noble/curves` — current,
  mainstream, no vendored primitives.

## 2. Findings

### EKA-21 — Three diverging nullifier-root KDF implementations
- **Severity:** Medium · **Likelihood:** certain (it is the shipped state) · **Status:** Open
- **Components:** `apps/mobile/src/lib/crypto-native.ts:100-112` ·
  `packages/crypto/src/nullifier.ts:130-139` + `types.ts:13-19` ·
  `packages/crypto/nullifier.py:54-82`

The same logical value — the root secret derived from a citizen's phone number — is
computed three different ways:

| Consumer | KDF | Parameters | Salt |
|---|---|---|---|
| Mobile app (`crypto-native.ts`) | **PBKDF2-SHA256** | 100 000 iterations, 32 B | `REGISTRATION_SALT` (public) |
| Web Tier-1 (`packages/crypto/src`) | **Argon2id** | t=**3**, m=64 MiB, p=1 | `REGISTRATION_SALT` (public) |
| Server identity v2 (`packages/crypto` Py) | **Argon2id** | t=**2**, m=64 MiB, p=1 | `SHA256("ekklesia:identity-nullifier:v2"+SERVER_SALT)` (secret-derived) |

Mobile ships a `TODO: Replace with Argon2id(t=3, m=65536) when native module configured`
with a production PBKDF2 fallback; web and server both use Argon2id **but with different
time cost** (3 vs 2), which already produces different outputs for identical input even
before the salt difference.

Consequences, each verified against the calling code:

1. **Cross-client identity break (Tier-1).** The same phone number yields different
   `nullifier_root` values on web vs mobile ⇒ different `identity_commitment`,
   different Semaphore commitments, different vote nullifiers. A citizen who registers
   Tier-1 on mobile cannot vote Tier-1 from the web and vice versa. Vote *integrity*
   holds only because the server-side tier lock is derived from the **legacy**
   `nullifier_hash` (`zk.py:777-794`), not from the Tier-1 root — i.e. the drift is
   currently masked by the legacy binding. Any future design that anchors deduplication
   on the Tier-1 commitment instead silently inherits a one-person-two-identities
   Sybil surface per phone number (one per client KDF).
2. **Weakest-link cost.** Offline brute-force cost against a leaked Tier-1 commitment is
   set by the cheapest implementation an attacker may target: PBKDF2-100k
   (mobile) ≈ 2-3 orders of magnitude cheaper per guess than Argon2id-64 MiB, and it is
   GPU-friendly, unlike the memory-hard path the documentation advertises.
3. **Interop trap.** Server v2 (t=2) and web Tier-1 (t=3) will never agree on a digest
   even given the same salt — any planned "client computes v2" unification must pin
   parameters first.

**Fix:** declare one canonical KDF (the natural choice: Argon2id t=3/64 MiB/p=1 with
`REGISTRATION_SALT`, as the web Tier-1 path), implement it natively for mobile
(the vendored semaphore module already ships heavy native code; Argon2 via
`react-native-argon2` or the same Rust/WASM path planned for `crypto-rs`), delete the
PBKDF2 fallback, and add cross-implementation known-answer tests (EKA-22) that would
have caught this on day one. Until then, document the drift in ADR-022.

### EKA-22 — No cross-implementation test vectors
- **Severity:** Low · **Status:** Open
- **Components:** `packages/crypto/src/crypto.test.ts` (48 tests), `packages/crypto/tests/test_crypto.py` (12+13), `apps/web/src/lib/crypto.test.ts`

All three suites test within one implementation using in-memory constants
(`TEST_ROOT = 0xab…`). There are no published known-answer vectors binding Python ↔
TypeScript ↔ mobile for nullifiers, vote messages, or signature payloads — exactly the
class of test that surfaces EKA-21-class drift. The canonical string formats
(`"{bill_id}:{VOTE}:{nullifier}"`, `"municipal:{ada}:{VOTE}:{nullifier}"`,
`"compass_personal:{nullifier}"`, Discourse/POLIS payloads) are likewise asserted only
per-side. **Fix:** a `docs/adr/kat-vectors.json` generated from the Python reference,
consumed by all client suites (and CI-diffed).

### EKA-23 — Residual risk: phone-number entropy bounds every nullifier KDF (Info)
Greek mobile numbers after normalization are effectively `+30 69` + 8 digits ≈ 10^8
candidates. Offline brute-force against any captured commitment/nullifier therefore
costs approximately:

| Target | Cost model | Rough wall-clock (attacker budget: 1 000 parallel workers) |
|---|---|---|
| v1 (SHA-256, if `SERVER_SALT` leaks) | ~10^8 hashes | seconds |
| v2 (Argon2id t=2, 64 MiB) | memory-hard, ~0.3-0.5 s/guess/worker | ~8-14 h per target |
| Tier-1 web (Argon2id t=3, 64 MiB) | ~0.5 s/guess/worker | ~14 h per target |
| Tier-1 mobile today (PBKDF2-100k) | ~0.05-0.1 s/guess/worker, GPU-amenable | ~1-2 h per target |

This is inherent to phone-anchored identity, is openly discussed in ADR-004/022 and the
v1→v2 migration (GH#111) addresses the worst row. Recorded so the public wiki/whitepaper
statements about unlinkability can be worded against these numbers (content audit
cross-reference). Mitigations that remain on the table: rate-limited commitment
registration, commitment rotation, and never publishing per-user commitments
(today only hashes/aggregates are public — verified).

### EKA-24 — `computeNullifier(phone, serverSalt)` exported in the web bundle (Info)
`apps/web/src/lib/crypto.ts:62-70` implements the *server-side v1* nullifier with the
salt as a caller-supplied parameter. Usage scan: referenced only by
`apps/web/src/lib/crypto.test.ts` — no production caller, no salt is or could be shipped.
Keep as test utility (move into the test file) or delete; as exported production API it
invites a future developer to wire a salt into the client bundle.

### EKA-25 — Server-derived political positions vs client-only framing (Info)
`apps/api/services/cplm.py` recomputes per-nullifier political positions server-side from
cast votes (`cplm_history` table) and exposes them via the signature-gated
`POST /compass/personal` (`voting.py:1106-1143`, signature over
`"compass_personal:{nullifier_hash}"`, history capped at 50). Clients indeed never
*upload* compass data (verified: no network call in any compass path except a static
party-positions JSON) — but the server *derives* an equivalent profile from public vote
rows. This is a design choice, not a leak; it is registered here because public framing
("Kompass niemals auf dem Server") should describe derivation, not only upload. The
coherence audit assesses the wording; no code change demanded.

---

## 3. Out of scope / limitations

No circuit-source review (Semaphore circuits are upstream, pinned by vkey hash); no
side-channel analysis of the vendored native `.so`; no formal verification of the
pure-Python pairing code against a second implementation (recommended as follow-up:
differential test `verify_semaphore_proof` vs `snarkjs verify` on a vector set); live
flag state (which ZK flags are actually on) is deployment-side and assessed in the
surfaces audit. The legacy server-side keygen flow (private key returned once over TLS)
is a documented Beta trust assumption, retained for the record here — elimination is the
stated purpose of the `crypto-rs` Rust/WASM roadmap item.

*— End of cryptography deep audit. Register continues EKA-26+.*

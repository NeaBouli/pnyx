# Security & Consistency Deep Audit — 2026-06-10

## Scope / Method

Read-only audit of the current `NeaBouli/pnyx` workspace at HEAD `5f4bbe4`.

Checked:
- local source code under `apps/api`, `apps/mobile`, `packages/crypto`, `docs`, `README.md`, `CLAUDE.md`
- public repository metadata via `gh repo view NeaBouli/pnyx`
- public release metadata via `gh release list`
- live response headers for `https://ekklesia.gr` and `https://ekklesia.gr/el/bills`

Not done:
- no code fixes
- no deploy
- no DB mutation
- no secret values printed or stored

## Executive Summary

The deepest audit finding is not that the live repo is fake or stale. The public GitHub repo is current, public, and has releases. The external-audit claim that `NeaBouli/pnyx` is "massively outdated" appears to be based on stale cached/old README data and is no longer accurate for the current repository.

However, the audit found real consistency and privacy/security wording issues:

1. **HIGH:** Server-side identity nullifier is still `SHA256(phone:SERVER_SALT)`, not Argon2id. Public "non-reversible" wording is too strong for a small phone-number search space if the salt leaks.
2. **MEDIUM:** The implemented verification flow is HLR-only, but some code comments and docs/UI still say SMS or SMS/HLR. That is a material promise mismatch.
3. **MEDIUM:** Public privacy wording that IP is "never" collected is not safe. API code uses client IP for global rate limiting and public API key-generation throttling.
4. **LOW:** Security headers are generally good, but CSP still permits `unsafe-inline`; `Referrer-Policy` and `Permissions-Policy` were not present in the checked responses.
5. **LOW:** Several secondary docs are stale (`docs/WHITEPAPER.md`, `docs/ROADMAP.md`, `docs/wiki/api.html`, `docs/wiki/roadmap.html`) even though `README.md` is mostly current.

## Findings

### A — Nullifier truth: SHA256 vs Argon2id

Severity: **HIGH**

Evidence:
- `packages/crypto/nullifier.py`
  - `SERVER_SALT = os.environ.get("SERVER_SALT", "dev-salt-change-in-production")`
  - `generate_nullifier_hash(phone_number)` builds `raw = f"{phone_number}:{SERVER_SALT}"` and returns `hashlib.sha256(raw.encode("utf-8")).hexdigest()`.
- `apps/api/routers/identity.py`
  - `verify_identity()` calls `generate_nullifier_hash(req.phone_number)` and stores that value as `IdentityRecord.nullifier_hash`.
- `apps/mobile/src/lib/crypto-native.ts`
  - File header says Argon2id, but the actual mobile `deriveNullifierRoot()` currently uses PBKDF2-SHA256 with 100,000 iterations as a fallback.
- `packages/crypto/src/nullifier.ts`
  - Browser/package implementation does use `argon2id` from `hash-wasm`, but this is not the API identity-router path that currently stores `IdentityRecord.nullifier_hash`.

Impact:
- The server-side de-duplication identifier is SHA256 over phone number plus server salt.
- If `SERVER_SALT` leaks, Greek mobile numbers are a bounded search space and can be brute-forced offline.
- The public claim "non-reversible" is therefore too absolute for the current production identity nullifier.

Recommendation:
- Do not claim plain SHA256 phone nullifiers are non-reversible in an absolute sense.
- Either:
  - migrate server-side identity nullifier derivation to a slow KDF such as Argon2id or at least PBKDF2/scrypt with versioned migration, or
  - document the current threat model honestly: safe while salt remains secret, vulnerable to offline enumeration if salt leaks.
- Treat this as a design/security task, not a quick text-only fix.

### B — MOD-01 truth: SMS or HLR?

Severity: **MEDIUM**

Evidence:
- `packages/crypto/hlr.py` explicitly documents: "Verifiziert griechische Mobilnummern ohne SMS."
- `apps/api/routers/identity.py` implementation calls `verify_greek_number(req.phone_number)` and tracks HLR usage.
- No OTP/SMS sending path was found in the identity verification implementation.
- Stale/ambiguous text remains:
  - `apps/api/routers/identity.py` module docstring: `SMS Verifikation -> Ed25519 Keypair`
  - `apps/mobile/src/screens/VerifyScreen.tsx` header comment: `SMS -> Ed25519 Keypair`
  - `apps/mobile/src/screens/OnboardingScreen.tsx`: Greek bullet says SMS verification
  - `docs/wiki/roadmap.html`: says user receives an SMS code and re-verifies with SMS
  - Some docs say `SMS/HLR`, mixing two different verification models.

Impact:
- HLR and SMS OTP are materially different security and privacy promises.
- HLR proves that a Greek SIM/number appears active; it does not prove possession via OTP.
- Public wording that implies SMS OTP overstates the current verification proof.

Recommendation:
- Standardize wording everywhere to "HLR lookup / active Greek SIM check, no SMS is sent" unless an OTP flow is actually implemented.
- Keep any "SMS" wording only where it means "SIM/phone verification tier" and explicitly define that meaning.

### C — IP logging / IP usage

Severity: **MEDIUM**

Evidence:
- `apps/api/main.py`
  - `_get_real_ip()` reads `x-forwarded-for` and uses it for the global SlowAPI limiter.
  - `limiter = Limiter(key_func=_get_real_ip, default_limits=["60/minute"])`.
  - Sentry filter removes `X-Forwarded-For` before sending events, which is good, but local/API rate-limiting still uses IP.
- `apps/api/routers/public_api.py`
  - `rate_limit_check()` uses `request.client.host` when no API key is provided.
  - `/keys/generate` stores Redis key `ratelimit:keygen:{ip}`.
- `apps/api/routers/contact.py`
  - comment says `max 3 per IP per hour`; code uses `request.client.host`.
- `apps/api/routers/agent.py` and `apps/api/routers/claude_agent.py`
  - rate limits by real IP / forwarded IP.

Impact:
- The strict public wording "IP is never collected" is not accurate if IPs are used as rate-limit identifiers, even if not persisted long-term or not linked to votes.
- The safer claim is: IP addresses are not linked to votes/identity and are only used transiently or with TTL for abuse protection, if that is the intended policy.

Recommendation:
- Audit production Traefik/Cloudflare/Discourse retention separately.
- Update privacy wording from "never collected" to an accurate statement about transient abuse-protection logging/rate limiting and non-linkage to votes.
- Consider hashing IP rate-limit keys with rotation if Redis keys expose raw IPs.

### D — Security headers

Severity: **LOW**

Evidence from `curl -sI https://ekklesia.gr` and `/el/bills`:
- Present:
  - `Content-Security-Policy`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
- CSP includes:
  - `script-src 'self' 'unsafe-inline'`
  - `style-src 'self' 'unsafe-inline'`
  - `frame-ancestors 'none'`
- Not observed in checked responses:
  - `Referrer-Policy`
  - `Permissions-Policy`
- `X-Powered-By: Next.js` is present on `/el/bills`.

Impact:
- Headers are generally good, especially HSTS and frame protections.
- `unsafe-inline` weakens CSP and is particularly relevant because browser-side crypto and local key material exist in parts of the project.
- Missing `Referrer-Policy` and `Permissions-Policy` are hardening gaps, not immediate blockers.

Recommendation:
- Track as hardening, not emergency.
- Eventually remove `unsafe-inline` via nonce/hash based CSP if compatible with Next.js setup.
- Add `Referrer-Policy: strict-origin-when-cross-origin` or stricter.
- Add an explicit `Permissions-Policy`.
- Consider hiding `X-Powered-By`.

### E — Public repo vs reality

Severity: **LOW**

Evidence:
- `git remote -v`: `https://github.com/NeaBouli/pnyx.git`
- `gh repo view NeaBouli/pnyx`:
  - public repo
  - default branch `main`
  - recently pushed/updated on 2026-06-10
- `gh release list`:
  - latest release `εκκλησία v1.0.3 (vC30)`
  - older release `v1.0.0`
- Current `README.md` already says:
  - Next.js 16
  - Mobile App Beta
  - 70+ endpoints
  - 25 modules
  - Direct APK live
  - Google Play internal testing / review pending
  - F-Droid MR !38007
  - ZK V2 blocked on mobile prover

Correction to external audit:
- The claim that the public GitHub README still says "Mobile TODO", "Next.js 14", "no releases", and "13 endpoints" is not true for the current local/public state.
- It may reflect an old cached page or an old audit snapshot.

Actual issue:
- Several secondary docs are stale:
  - `docs/WHITEPAPER.md` still references Next.js 14.
  - `docs/ROADMAP.md` still uses "SMS HLR" / "SMS Verification" wording.
  - `docs/wiki/api.html` says 62 endpoints / 22 modules while README says 70+ / 25.
  - `docs/wiki/roadmap.html` says SMS code flow.
  - `CLAUDE.md` still has "Beta — SMS Verifikation" and `/verify -> SMS -> Key -> Success`.

Recommendation:
- Treat this as a documentation consistency cleanup.
- Prioritize public-facing pages first: landing, wiki privacy/security/roadmap/API, README.

### F — API auth / rate limiting / CORS

Severity: **INFO**

Evidence:
- `apps/api/main.py`
  - SlowAPI global limiter configured at `60/minute`, using real IP from `X-Forwarded-For`.
  - CORS middleware configured in the same file.
- `apps/api/dependencies.py`
  - admin auth accepts only `Authorization: Bearer <key>`.
  - query-param admin key removed.
  - fail-closed in production if `ADMIN_KEY` is absent or default.
- Admin routers use `Depends(verify_admin_key)` or wrappers around it.
- `apps/api/routers/public_api.py`
  - public API has in-memory per-process rate limiting for anonymous/API-key access.
  - API key generation is limited by IP in Redis.
- `apps/api/routers/agent.py` and `apps/api/routers/claude_agent.py`
  - AI/agent endpoints have explicit low limits (`5/minute`, `3/minute`).

Impact:
- Auth posture for admin endpoints looks improved and fail-closed.
- Rate limiting exists globally and on sensitive public/AI endpoints.
- Remaining caveat: in-memory limiter in `public_api.py` is acceptable only for single API instance; if horizontally scaled, move to Redis.

Recommendation:
- Keep current guardrails.
- Add explicit tests for admin fail-closed and public API rate-limit behavior if not already covered.

## Open Questions

1. Is production `SERVER_SALT` rotated and protected as a high-value secret?
2. Are Traefik access logs enabled in production, and what is retention?
3. Does Discourse retain user/post IPs, and should privacy copy mention forum-specific logging separately?
4. Should the current server `generate_nullifier_hash()` be migrated to a versioned slow-KDF format?
5. Should mobile registration be migrated away from legacy server-returned private key flow toward local-only key generation?

## Do Not Fix Yet / Guardrails

- Do not change the nullifier derivation casually. This affects duplicate prevention, account recovery/re-registration, vote status, and existing identity records.
- Do not edit security/privacy copy until the production logging and nullifier migration decision is clear.
- Do not change active voting behavior without Golden Path checks:
  - VoteScreen NAI/OXI/ΑΠΟΧΗ
  - already-voted lock
  - 24h correction banner
  - sourceResolver fallback
  - Ed25519 signature payload compatibility
- ZK/Mopro remains disabled unless explicitly enabled by a separate guarded rollout.

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

---

## Second Auditor — Supplementary Evidence & New Findings (2026-06-10, Claude Sonnet 4.6)

This section adds exact file:line evidence and findings not captured in the first-pass above.
No files were modified. Method: Grep + Read + live curl.

---

### A — Nullifier: Supplementary evidence

**Server-side SHA256 confirmed** — exact implementation:

`packages/crypto/nullifier.py:11-28`
```python
SERVER_SALT = os.environ.get("SERVER_SALT", "dev-salt-change-in-production")

def generate_nullifier_hash(phone_number: str) -> str:
    raw = f"{phone_number}:{SERVER_SALT}"
    result = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    del raw
    del phone_number
    gc.collect()
    return result
```

**Fallback in `SERVER_SALT`:** literal string `"dev-salt-change-in-production"`. If `SERVER_SALT` env var is unset in production, all nullifiers are computed with this known string. Status in prod: **unverifiable remotely — must be confirmed**.

**Client-side Argon2id confirmed** — `packages/crypto/src/nullifier.ts:130-140`:
```typescript
export async function deriveNullifierRoot(phone: string): Promise<Uint8Array> {
    const normalized = normalizePhone(phone);
    const result = await argon2id({
        password: normalized,
        salt: REGISTRATION_SALT,  // "ekklesia.gr:registration:2026:v1" — public constant
        time: 3, memory: 65536, parallelism: 1, hashLen: 32,
    });
```

**Mobile (`apps/mobile/src/lib/crypto-native.ts`) — PBKDF2 fallback:**
File header references Argon2id but native mobile path uses PBKDF2-SHA256 (100k iterations) as fallback for environments without hash-wasm. PBKDF2 is stronger than plain SHA256 but weaker than Argon2id for memory-hard resistance.

**Demographic hash also SHA256** — `packages/crypto/nullifier.py:34-42`:
```python
def generate_demographic_hash(age_group, region, gender_code):
    raw = f"{age_group}_{region}_{gender_code}_{SERVER_SALT}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```
Age group + region + gender is a much smaller search space than phone numbers. SHA256 with known SERVER_SALT would trivially invert this. Severity: **HIGH** (smaller brute-force space than phone).

---

### C — IP Logging: NEW finding — IP in Brevo email body

**Severity: MEDIUM — not in first audit pass**

`apps/api/routers/contact.py:85,113,143`:
```python
client_ip = request.client.host if request.client else "unknown"
_check_rate_limit(client_ip)
# ...
f"<p style='color:#999;font-size:0.8em'>IP: {client_ip} | Consent: {body.consent}</p>"
# ...
logger.info("[CONTACT] Contact from %s — %s (%s)", client_ip, full_name, body.org)
```

IP is embedded verbatim in the HTML body of every contact form email sent to **Brevo** (3rd-party email processor). This means:
- Brevo stores the IP as part of email content (not just metadata)
- This is a 3rd-party data transfer under GDPR Art. 28
- Privacy policy must cover this processing; "IP never collected" language is inconsistent with this

Additionally, `logger.info` writes IP to **server logs** on every contact submission. Log retention policy determines persistence.

**Sentry is correctly filtered** (`main.py:27-35`): `X-Forwarded-For` is explicitly popped before sending to Sentry. ✅

**Redis rate-limit keys** in `public_api.py:103`: `ratelimit:keygen:{ip}` — ephemeral (TTL), acceptable.

**DB and Arweave: IP never stored** — confirmed via export.py:199 `never_exported` list. ✅

---

### D — Security Headers: Supplementary evidence

**Full header snapshot — 2026-06-10T06:39:52Z:**

`https://ekklesia.gr` (root):
```
content-security-policy: default-src 'self' https://api.ekklesia.gr https://donate.stripe.com;
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https://api.ekklesia.gr https://api.coingecko.com
    https://arweave.net https://api.github.com
    https://polis-oauth-proxy.bergamolia.workers.dev;
  frame-ancestors 'none'
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
```

`https://ekklesia.gr/el/bills` (additional):
```
x-powered-by: Next.js
set-cookie: NEXT_LOCALE=el; Path=/; SameSite=lax   ← missing Secure flag
```

**Missing headers confirmed:**
- `Referrer-Policy` — absent from both responses
- `Permissions-Policy` — absent from both responses
- Source: `apps/web/next.config.mjs` has **no `headers()` block** — no custom security headers set at framework level

**NEW finding — NEXT_LOCALE cookie missing `Secure` flag** · Severity: MEDIUM
`set-cookie: NEXT_LOCALE=el; Path=/; SameSite=lax` — no `Secure` attribute.
HSTS preload provides a backstop but the `Secure` flag is defence-in-depth.
Fix: add `Secure` attribute to locale cookie in Next.js middleware/config.

**NEW finding — `img-src https:` in CSP** · Severity: LOW
`https:` as img-src matches any HTTPS image host. Allows hot-linking/tracking pixels from arbitrary third-party domains if markup injection is achieved.
Better: enumerate whitelisted image origins.

**Note on `polis-oauth-proxy.bergamolia.workers.dev`** in CSP `connect-src`:
This Cloudflare Worker domain is included in the allowed connection origins. Purpose not documented in any file found during audit. External 3rd-party proxy origins in CSP should be documented and reviewed — any data sent to it is outside the operator's control.

---

### F — API Security: NEW findings

**NEW — CORS wildcard methods + headers with credentials** · Severity: MEDIUM

`apps/api/main.py:530-542`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ekklesia.gr", "https://www.ekklesia.gr",
                   "https://api.ekklesia.gr", "https://dashboard.ekklesia.gr",
                   "https://test.ekklesia.gr"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_credentials=True` combined with `allow_methods=["*"]` and `allow_headers=["*"]` is overly permissive. Origin whitelist is strict (mitigates risk currently), but if any new origin is ever added carelessly, wildcard methods/headers amplify the blast radius. Best practice: enumerate explicitly.

**Admin fail-closed logic confirmed correct** (`apps/api/dependencies.py:15-32`):
- Raises HTTP 403 in production if `ADMIN_KEY` unset or equals `"dev-admin-key"` (line 21-24)
- `"dev-admin-key"` is only accepted when `ENVIRONMENT != "production"` (line 26)
- This is the only auth path used by all admin routers via `Depends(verify_admin_key)`

**In-memory rate limiters (confirmed gap from first audit)**:
`contact.py` and `public_api.py` use per-process in-memory dicts for rate limiting. Under multi-worker uvicorn deployment, effective limit = configured limit × number of workers. Move to Redis-backed slowapi for consistency.

**Rate-limit key for API key generation uses raw IP** (`public_api.py:103`):
`ratelimit:keygen:{ip}` — raw IP stored as Redis key prefix. Acceptable given TTL, but worth noting for privacy review.

---

### Summary of NEW findings vs first audit

| ID | Finding | Severity | Status in first audit |
|----|---------|----------|----------------------|
| C2 | IP embedded verbatim in Brevo contact emails | MEDIUM | Not captured |
| D7 | NEXT_LOCALE cookie missing `Secure` flag | MEDIUM | Fixed live 2026-06-10 (`8b15177`) |
| D8 | `img-src https:` CSP too permissive | LOW | Not captured |
| D9 | `polis-oauth-proxy` in CSP — undocumented | INFO | Not captured |
| F2 | CORS allow_methods/allow_headers=* with credentials | MEDIUM | Fixed live 2026-06-10 (`d01be5f`) |
| A4 | Demographic hash also SHA256 (smaller brute-force space than phone) | HIGH | Not captured |

All other findings from the first audit are **confirmed** with exact file:line evidence above.

*Second audit completed: 2026-06-10 | Claude Code (Sonnet 4.6) | Read-only | No fixes applied*

---

## Third Pass — Open Audit Questions A/C/E/F Closed With Evidence (2026-06-10)

This section answers the questions that remained after the wording/header fix at `9f99f9b`
and the handover note at `e1a4622`.

Method:
- local grep/source review
- GitHub CLI metadata check
- production SSH checks that printed only booleans/lengths, never secret values
- live `curl -I` response header check
- independent Claude Code read-only review

### Production / repo state

Public repository:
- `origin/main`: `e1a462263a038c5b81dea165f6771f2ebb39ade0`
- local HEAD: `e1a462263a038c5b81dea165f6771f2ebb39ade0`
- GitHub repo: `NeaBouli/pnyx`, visibility `PUBLIC`, default branch `main`, pushed `2026-06-10T07:15:00Z`

Verdict: public GitHub repo is current with local Codex state.

Production checkout:
- `/opt/ekklesia/app` HEAD: `dd70c52` (`fix(GH#105): use official text fallback instead of AI summary tab`)
- production app checkout has untracked files:
  - `apps/api/routers/identity.py.bak`
  - `docs/community.html.bak`
  - `docs/download/backups/`
  - `docs/download/ekklesia-latest.apk`
  - `docs/download/ekprosopos-latest.apk`
  - `packages/crypto/hlr.py.bak`
  - `tmp/`
- containers before any deploy:
  - `ekklesia-web`: running, up 34h
  - `ekklesia-api`: running, up 36h

Verdict: the latest security wording/header fix is pushed but **not live** yet. Live response still shows old headers:
- `x-powered-by: Next.js` present on `/el/bills`
- no `Referrer-Policy`
- no `Permissions-Policy`

### A — SERVER_SALT truth

Production check (no secret value printed):
- `SERVER_SALT` set: YES
- length: 64
- default/weak value (`dev-salt-change-in-production`, `dev-salt`, empty): NO
- `/opt/ekklesia/.env.production` permissions: `600 ekklesia:ekklesia`
- `FORUM_SSO_SALT` set: YES
- `ADMIN_KEY` set: YES
- `ADMIN_KEY` default: NO

Residual risks confirmed by source:
- There is no startup fail-closed guard for weak/missing `SERVER_SALT`.
- Defaults are inconsistent:
  - `packages/crypto/nullifier.py`: `dev-salt-change-in-production`
  - `apps/api/routers/admin_account.py`: `dev-salt`
  - `apps/api/routers/govgr.py`: `dev-salt`
  - `apps/api/routers/voting.py`: empty string fallback
- `apps/api/config.py` also contains `server_salt: str = "dev-salt-change-in-production"`.

Verdict: production is currently configured with a non-default 64-char salt and protected file permissions.
The design still needs a separate hardening task: fail-closed startup validation and unified no-default behavior.

### C — IP logging / rate-limiting truth

Confirmed flows:
- Global SlowAPI limiter in `apps/api/main.py` uses `_get_real_ip()` from `X-Forwarded-For`.
- Sentry filter removes `X-Forwarded-For` and `Cookie` before sending events.
- `apps/api/routers/agent.py` and `apps/api/routers/claude_agent.py` also trust `X-Forwarded-For`.
- `apps/api/routers/contact.py` uses `request.client.host`, rate-limits in-memory, embeds `IP: {client_ip}` in Brevo email content, and logs IP with full name/org.
- `apps/api/routers/public_api.py` uses `request.client.host` for anonymous public API rate limiting and Redis key `ratelimit:keygen:{ip}` for key generation.

Production network check:
- `ekklesia-api` port `8000/tcp` is **not** bound to host ports.
- Traefik is the public entrypoint on ports 80/443.

Verdict:
- XFF spoofing is not an acute direct-port exposure right now, because API port is internal-only.
- The infra invariant is important: API must remain internal behind Traefik.
- Contact/public API rate limiting is inconsistent behind proxy because they use socket IP rather than the shared real-IP helper.
- Brevo contact emails/logs include IP plus contact PII; privacy policy wording must cover this, and retention should be understood.

### E — Public repo trust

Verdict: GO.
- Public repo is current with local HEAD.
- External claim that the GitHub repo is only a stale mirror is not supported by current evidence.
- Separate issue: production checkout is behind the public repo until a deploy is performed.

### F — API security

Admin auth:
- `apps/api/dependencies.py` is fail-closed in production if `ADMIN_KEY` is missing or equals `dev-admin-key`.
- Bearer-only auth; query-param admin key removed.
- Admin routes use `Depends(verify_admin_key)` or wrappers.

CORS:
- Origin allowlist is explicit (`ekklesia.gr`, `www`, `api`, `dashboard`, `test`).
- `allow_credentials=True`.
- `allow_methods` and `allow_headers` are now explicit (`d01be5f`), not wildcards.
- Live verification: allowed preflight from `https://ekklesia.gr` returns 200; unknown header and `TRACE` preflights return 400.

Rate limiting:
- Global SlowAPI: present.
- Agent routes: limited.
- Contact/public API: in-memory and inconsistent real-IP extraction; should be unified and preferably Redis-backed.

Verdict: no immediate auth bypass found; hardening tasks remain.

### Follow-up candidates

1. `SERVER_SALT` fallback cleanup:
   - startup guard is implemented after this audit (`security_startup.py`)
   - remaining cleanup: unify all weak fallback strings to no default in follow-up
2. Real-IP helper consolidation:
   - one trusted helper for proxy-aware IP extraction
   - contact/public API use the same helper or Redis-backed limiter
   - document "API must remain internal behind Traefik"

---

## Fourth Pass — IP Helper + Redis Rate-Limit Hardening (2026-06-10)

Status: **implemented in code, deploy pending**.

Scope:
- API-only privacy/rate-limit hardening.
- No voting, identity, nullifier, DB, forum, web, mobile, or Arweave logic changes.

Implemented:
- Added shared `apps/api/ip_utils.py`.
- Consolidated proxy-aware IP extraction for:
  - global SlowAPI limiter (`apps/api/main.py`)
  - citizen agent limiter (`apps/api/routers/agent.py`)
  - Claude agent limiter (`apps/api/routers/claude_agent.py`)
- Contact form (`apps/api/routers/contact.py`):
  - in-memory per-worker limiter replaced with Redis fixed-window limiter
  - rate-limit key uses daily HMAC bucket, not raw IP
  - Brevo email body now contains `Request ref: ipref:...`, not raw IP
  - server log line now contains `Contact ref=ipref:...`, not raw IP
- Public API (`apps/api/routers/public_api.py`):
  - anonymous/API-key rate limits moved from in-memory dict to Redis
  - key-generation limiter uses daily HMAC bucket, not `ratelimit:keygen:{ip}`
  - invalid API keys are treated as anonymous traffic for rate limiting, preventing per-fake-key bypass
- Redis limiter uses Lua so `INCR` and `EXPIRE` are atomic.

Verification:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_ip_utils.py apps/api/tests/test_rate_limit_privacy.py apps/api/tests/test_cors_config.py apps/api/tests/test_security_startup.py -q`: **20 passed**.
- `apps/api/.venv/bin/python -m py_compile ...`: **OK**.
- `git diff --check`: **OK**.
- Grep check found no remaining raw `request.client.host`, duplicate `_get_real_ip`, `ratelimit:keygen:{ip}`, or contact-email `IP:` usage outside the centralized helper.
- Claude Code reviewed the diff and confirmed:
  - voting/nullifier paths untouched
  - no raw IP in contact emails/logs
  - tests cover raw-IP non-leakage and daily rotation
  - Redis atomicity concern resolved by Lua script

Remaining caveat:
- `TRUSTED_PROXY_COUNT=1` assumes the current single Traefik public-entrypoint topology.
- If a CDN/load balancer is added in front of Traefik, update `TRUSTED_PROXY_COUNT` and re-test IP extraction.
3. Deploy pushed security wording/header fix:
   - server currently behind at `dd70c52`
   - web/API rebuild required for live headers/API-agent wording
4. `NEXT_LOCALE` cookie `Secure` flag:
   - fixed live 2026-06-10 (`8b15177`)
   - verified header: `NEXT_LOCALE=el; Path=/; Secure; SameSite=lax`

*Third pass completed: 2026-06-10 | Codex + Claude Code | Mostly read-only; no production mutation*

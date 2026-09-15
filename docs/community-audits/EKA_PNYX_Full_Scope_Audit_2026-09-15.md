# ekklesia.gr / pnyx — Full-Scope Security Audit

**Auditor:** Collateral Web3 Open Audits
**Client:** NeaBouli / ekklesia.gr (pnyx)
**Date:** 2026-09-15
**Baselines:** repo `NeaBouli/pnyx` @ `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` (2026-09-13, main HEAD at audit start) · live surfaces probed 2026-09-15 (anonymous GET/HEAD only) · prior internal baseline: `AUDIT_MUST_READ/pnyx_MASTER_AUDIT_20260503.md` (Codex, 2026-05-03)
**Companion documents:** crypto deep audit, integration & surfaces audit, content coherence audit, AI readiness audit (same date, register continues EKA-21+)
**Report version:** 1.0

This document is the full-scope security review of the pnyx monorepo: FastAPI backend
(32 routers, ~188 endpoints), Next.js 16 web + dashboard, Expo/React-Native mobile +
representative apps, Cloudflare worker, Docker/Traefik infra and CI/CD. The dedicated
cryptography audit (nullifier constructions, Ed25519 flows, Semaphore/Groth16, Arweave)
is a separate document; findings here cover application/infrastructure security.

**Publication note:** `SECURITY.md` asks for private disclosure. The repository owner
explicitly authorized full public publication of this audit series (2026-09-15) so the
project dev can work through findings as issues/PRs.

---

## 1. Executive summary

ekklesia.gr is an anonymous civic-voting platform (Ed25519 proof-of-possession instead of
accounts) with an unusually mature security posture for a beta: the two CRITICAL findings
of the 2026-05-03 internal audit (admin keys in URLs) are verifiably fixed — admin auth is
now HTTP-Bearer-only with a production fail-closed guard, the dashboard proxies admin calls
server-side with role checks, and the public web admin page is a redirect stub. Fail-closed
design is consistent: CORS is a 5-origin allowlist, ZK voting sits behind 8 env flags with
canary allowlists, Stripe webhooks are signature-checked and gated, destructive admin
endpoints require typed confirmation, no secrets are committed anywhere in git history.

The findings below are therefore concentrated in (a) input/output handling at the edges
(representative WebView XSS, residual unescaped sinks), (b) unauthenticated or weakly
authenticated auxiliary endpoints (newsletter, push, flag, webhook), and (c) cost-exposure
and operational hygiene. None of them touches the core vote integrity: double-vote
protection is a DB `UNIQUE(nullifier_hash, bill_id)` plus a Redis/DB tier lock, and the
Ed25519 signature gate on every state-changing citizen endpoint is uniformly applied.

**Bottom line:** solid beta posture; the High finding (stored-XSS surface in the
representative WebView) should be fixed before the representative app rolls out beyond the
current pilot, and the Medium cluster is one focused hardening sprint.

**Findings: 0 Critical · 1 High · 7 Medium · 7 Low · 5 Informational (EKA-01 … EKA-20)**

| # | Severity | Title | Status |
|---|----------|-------|--------|
| EKA-01 | Medium | Tier-1 advisory vote validation is dead code (signature mismatch swallowed) | Open |
| EKA-02 | High | Representative WebView renders unescaped API data into innerHTML with live token in storage | Open |
| EKA-03 | Medium | Nullifier used as bearer credential; transmitted in URL query strings | Open |
| EKA-04 | Medium | Newsletter subscribe has no rate limit (email-bombing via Brevo) + plaintext email in logs | Open |
| EKA-05 | Medium | Push registration unauthenticated with predictable device_id (token hijack) | Open |
| EKA-06 | Medium | HLR cost exposure: no dedicated verify rate limit + public credits endpoint | Open |
| EKA-07 | Medium | Web client stores Ed25519 private key as plaintext hex in localStorage | Open |
| EKA-08 | Medium | Compass profile silently falls back to unencrypted localStorage | Open |
| EKA-09 | Low | Brevo webhook accepts unauthenticated event injection | Open |
| EKA-10 | Low | Municipal vote race yields 500 instead of 409 | Open |
| EKA-11 | Low | gov.gr OAuth state in per-process dict (breaks CSRF check under 2 workers when activated) | Dormant |
| EKA-12 | Low | `verify_signature` swallows bare `Exception` | Open |
| EKA-13 | Low | dashboard + monitor containers run as root; ollama/docker-proxy images unpinned | Open |
| EKA-14 | Low | Residual unescaped remote-data sinks in static docs (polis.js error path, GitHub user fields) | Open |
| EKA-15 | Low | Dead admin-key-in-query client helpers still shipped in web bundle | Open |
| EKA-16 | Low | PII (name/org/email) written to application logs | Open |
| EKA-17 | Informational | HLR credential env names inverted (primary uses `HLR_FALLBACK_*`) | Open |
| EKA-18 | Informational | Dev compose publishes Postgres/Redis with default credentials | By design (dev) |
| EKA-19 | Informational | Package-ID drift persists: Android `ekklesia.gr` vs iOS `gr.ekklesia.app` (PNYX-MED-05 still open) | Open |
| EKA-20 | Informational | 2026-05-03 master audit re-baseline: 2 CRIT + 1 MED fixed, 1 MED resolved, 2 partial, 1 open | Recorded |

---

## 2. Scope and method

Reviewed at the pinned commit: all of `apps/api` (routers, services, middleware, scheduler,
dependencies, config), `apps/web`, `apps/dashboard`, `apps/mobile`, `apps/representative`,
`cloudflare-worker`, `infra/`, `.github/workflows/`, dependency manifests, `docs/` static
surface (input-handling review). Method: three parallel deep-recon passes followed by
lead-verification of every candidate at the exact code line (all line references below were
opened and quoted by the lead auditor). Live probing limited to anonymous GET/HEAD.
No secret-class files were read (repo policy); no state-changing requests were made.

## 3. Verified strengths (spot-verified, not exhaustive)

- **Admin auth (2026-05-03 PNYX-CRIT-01) — FIXED.** `apps/api/dependencies.py:15-32`
  accepts only `Authorization: Bearer`, fails closed in production when `ADMIN_KEY` is
  unset or `"dev-admin-key"`. All 16 admin consumers use the dependency. Dashboard calls
  flow through a server-side proxy (`apps/dashboard/src/app/api/proxy/[...path]/route.ts`)
  requiring a GitHub-OAuth session with `SUPER_ADMIN` role and injecting the Bearer key
  from server env — the key never reaches the browser. (Residual: EKA-15.)
- **Public web admin page (PNYX-CRIT-02) — FIXED.** `apps/web/src/app/[locale]/admin/page.tsx`
  is a 5-line redirect to `dashboard.ekklesia.gr`.
- **greek_topics_scraper (PNYX-MED-03) — RESOLVED.** Module absent from index and disk;
  scheduler import is defensive (`main.py:500-527`), health endpoint reports disabled.
- **Dashboard logs/explain wiring (PNYX-MED-02) — FIXED** (`(dashboard)/logs/page.tsx:186`).
- CORS: explicit allowlist of 5 ekklesia.gr origins, no wildcard (`main.py:738-751`).
- Stripe webhook: signature verification, fail-closed without secret, amount/purpose
  validation, Redis idempotency, intake gate (`payments.py:944-1074`).
- Destructive admin endpoint production-blocked + typed `CONFIRM_DELETE` (`admin.py:375-383`).
- Discourse SSO: DiscourseConnect HMAC, one-time nonces in Redis, Ed25519 challenge,
  return-URL allowlist, fail-closed startup (`sso.py:31-192`).
- No committed secrets: full-history filename scan clean; keystore referenced by build
  script is not tracked; Arweave wallet mounted read-only from host path only.
- CI: Gitleaks full-history, npm audit high across lockfiles, pip-audit with a single
  documented scoped exception, Dependabot weekly; deploy is `workflow_dispatch` only.

## 4. Findings

### EKA-01 — Tier-1 advisory vote validation is dead code
- **Severity:** Medium · **Likelihood:** certain (fires on every Tier-1 vote) · **Status:** Open
- **Component:** `apps/api/routers/voting.py:440-456` × `apps/api/crypto/nullifier.py:122-127`

`submit_vote` calls, when Tier-1 fields are present:

```python
from crypto.nullifier import validate_vote
tier1_result = validate_vote(pk_eph=..., vote_nullifier=..., linkage_tag=...,
    bill_id=..., choice=..., signature=..., timestamp_ms=...)
```

but `validate_vote` is defined as `validate_vote(payload: VotePayload, used_nullifiers:
Set[str], *, now_ms=None)`. The keyword arguments do not match, so every call raises
`TypeError`, which is swallowed by `except Exception` and logged as a "non-blocking"
warning. The ADR-022 advisory validation layer has therefore never executed a single
check; the log message additionally masks the defect as routine noise.

Core double-vote protection is unaffected (DB `UNIQUE(nullifier_hash, bill_id)` at
`models.py:227-231` + tier-lock guard at `voting.py:432-437`), so this is defense-in-depth
loss, not vote-integrity loss. **Fix:** either wire the call to the real signature
(constructing a `VotePayload` and passing the used-nullifier set) or remove the block
until Tier-1 validation is meant to enforce; make the exception handler log at error
level with the exception type.

### EKA-02 — Representative WebView renders unescaped API data into innerHTML with a live token
- **Severity:** High · **Likelihood:** low-medium (requires a malicious bill title or question
  string entering via scraper/admin) · **Status:** Open
- **Component:** `apps/representative/web/index.html:177,179,181,196,255-256` (served at
  `ekklesia.gr/representative/index.html`, loaded inside the representative app's WebView)

Bill titles and evaluation questions are interpolated directly into `innerHTML`:

```js
html+='<div class="bill-card" onclick="loadResults(\''+b.id+'\')">';   // :177 id into JS-attr
html+='<h3>'+b.title_el+'</h3>';                                       // :179 title raw
html+='<div class="meta">'+b.id+' · '+(b.governance_level||'NATIONAL') // :181
html+='<div class="bill-card"><h3>'+d.title_el+'</h3>';                // :196
html+='<div class="cat">'+q.category+'</div>';                         // :255
html+='<div class="q">'+q.question_el+'</div>';                        // :256
```

`b.title_el` originates from parliament/Diavgeia scrapers (external, unsanitized input).
The representative bearer token sits in WebView `localStorage` (`:138-143`). A stored XSS
in a bill title steals the token and grants the attacker's script full access to the
`/api/v1/rep/*` endpoints as that representative for up to 24 h (viewing aggregate
results pre-publication, toggling evaluation consent). Not exploitable for vote casting,
which keeps this below Critical. **Fix:** render with `textContent`/DOM builders or escape
every interpolated value; move the token out of WebView-accessible storage (postMessage
bridge to SecureStore on demand); sanitize scraper-imported titles at ingest.

### EKA-03 — Nullifier used as a bearer credential; transmitted in URL query strings
- **Severity:** Medium · **Likelihood:** medium (nullifiers leak via logs/history by design of the URL API) · **Status:** Open
- **Component:** `apps/api/routers/parliament.py:455-490`, `apps/api/routers/voting.py:517-520`

Two combined weaknesses:

1. `POST /api/v1/bills/{bill_id}/flag` authenticates solely by a bare `X-Nullifier`
   header — no Ed25519 signature, unlike every other citizen write endpoint. Whoever
   learns an active nullifier can file flags as that identity (and has no rate limit).
2. `GET /api/v1/vote/{bill_id}/status?nullifier_hash=…` places the nullifier in a URL
   query string, where it is captured by browser history, proxy logs (Traefik access
   logs), analytics and referrer headers. CORS explicitly allows the `X-Nullifier`
   header (`main.py:749`), so any origin the user visits with a crafted page can replay
   a stolen nullifier against the flag endpoint.

Impact: flag-count manipulation under a foreign identity; vote-status (voted/not-voted
per bill) readable for any known nullifier. **Fix:** require the standard Ed25519
signature (`flag:{bill_id}:{nullifier}`) on the flag endpoint; prefer POST-with-body for
status, or document the nullifier as low-sensitivity and rate-limit flagging.

### EKA-04 — Newsletter subscribe: no rate limit + plaintext email logging
- **Severity:** Medium · **Likelihood:** medium (trivially scriptable) · **Status:** Open
- **Component:** `apps/api/routers/newsletter.py:95-173` (`:172` logging)

`/subscribe` sends a real Brevo confirmation email to any address on every call, protected
only by the global 60/min IP limit (easily rotated). This enables third-party email-bombing
using ekklesia's sender reputation and burns Brevo quota. Double opt-in prevents list
poisoning but not the mail flood. The success path also logs the full recipient address
(`logger.info(f"[MOD-19] Opt-in email sent to {req.email}")`) — unnecessary PII at rest in
logs. **Fix:** per-email + per-IP Redis limiter (e.g. 3/day per address, 10/h per IP);
log a truncated hash instead of the address.

### EKA-05 — Push registration: unauthenticated + predictable device_id
- **Severity:** Medium · **Likelihood:** medium · **Status:** Open
- **Component:** `apps/api/routers/notify.py:48-56`, `apps/mobile/src/lib/notifications.ts:292`

`POST /api/v1/notify/register` writes `push_tokens:{device_id}` (90-day TTL) with no
authentication, and the mobile client builds `device_id` as `${Platform.OS}-${Device.modelName}`
— e.g. `android-SM-G991B`. Anyone can overwrite the push token of every device of a given
model, redirecting or silencing their notification pings (push content itself is
content-free by design, capping impact). Unbounded distinct keys also allow slow Redis
filling. **Fix:** random per-install UUID as device_id (stored in SecureStore), plus a
registration signature or at least per-IP rate limiting.

### EKA-06 — HLR cost exposure: no dedicated verify limit + public credits oracle
- **Severity:** Medium · **Likelihood:** medium · **Status:** Open
- **Component:** `apps/api/routers/identity.py:167-286` (verify), `:342-405` (credits)

`POST /api/v1/identity/verify` performs a paid HLR lookup (~0.006 €/query) and a Brevo-free
but real provider call per attempt, guarded only by the global 60/min IP slowapi limit and
a 90 s per-nullifier lock (which resets per new phone number). An attacker with rotating
IPs can burn HLR credits continuously. The public `GET /api/v1/hlr/credits` endpoint
reports remaining credits, EUR balance and failover state for both providers — a perfect
oracle telling the attacker exactly when the primary provider is exhausted and failover
engages. (The endpoint is intentional transparency for a community tile; trade-off noted.)
**Fix:** stricter per-endpoint limit on verify (e.g. 5/min + daily IP cap + per-number
cooldown), consider hiding exact balances behind coarse buckets.

### EKA-07 — Web client stores the Ed25519 private key as plaintext hex in localStorage
- **Severity:** Medium · **Likelihood:** medium (any XSS on the web origin = full identity theft) · **Status:** Open (documented as Beta trade-off)
- **Component:** `apps/web/src/lib/crypto.ts:128-142`

The web client persists `ekklesia_private_key` unencrypted in `localStorage`, with a code
comment `TODO: Replace with expo-secure-store …`. The mobile apps correctly use
SecureStore/Keystore. On the web origin — which also renders third-party data (GitHub
issue content in tickets, see EKA-14) — any successful XSS is immediate, silent,
unrecoverable identity theft (the key cannot be rotated; only revoke + re-verify with HLR
cost). **Fix:** non-extractable IndexedDB CryptoKey or at minimum passphrase-wrapped
storage; document the Beta limitation on the security wiki page (coherence item for the
content audit).

### EKA-08 — Compass profile silently falls back to unencrypted localStorage
- **Severity:** Medium (privacy) · **Likelihood:** certain for unverified users · **Status:** Open
- **Component:** `apps/web/src/lib/compass/storage.ts:86-96,100-117`

The political compass — the most sensitive data class the platform handles — is AES-256-GCM
encrypted only when a private key exists; otherwise `saveProfile` writes plaintext JSON.
The load path likewise accepts plaintext. Unverified users (who can still use VAA/compass)
store their political profile unencrypted. Additionally, since the encryption key is the
Ed25519 private key itself stored in the same localStorage (EKA-07), the encryption
currently obfuscates rather than protects against XSS. **Fix:** encrypt with a random
device key when no identity key exists; surface the protection state in the UI; long-term
decouple the compass key from the identity key.

### EKA-09 — Brevo webhook accepts unauthenticated event injection
- **Severity:** Low · **Likelihood:** medium · **Status:** Open
- **Component:** `apps/api/routers/newsletter.py:334-353`

`/webhook/brevo` has no signature/token check; anyone can POST fabricated
sent/opened/bounced events, inflating counters and invalidating the stats cache.
Impact limited to newsletter statistics integrity. **Fix:** shared-secret query token or
Brevo webhook signature verification.

### EKA-10 — Municipal vote race yields 500 instead of 409
- **Severity:** Low · **Likelihood:** low (requires concurrent double submit) · **Status:** Open
- **Component:** `apps/api/routers/municipal.py:229-241`

Duplicate check + `UNIQUE(ada, nullifier_hash)` (`models.py:523-526`) exist, but the
`IntegrityError` from a racing second request is not caught (unlike the parliament vote
path `voting.py:500-505`), producing a 500. Cosmetic. **Fix:** mirror the parliament
`try/except IntegrityError → 409`.

### EKA-11 — gov.gr OAuth state kept in a per-process dict
- **Severity:** Low (dormant — module inactive behind 9 gates) · **Status:** Dormant
- **Component:** `apps/api/routers/govgr.py:77-78`

OAuth `state` values are stored in a module-level dict; production runs uvicorn with
2 workers, so the callback can land on the other process and fail CSRF state validation
(availability bug) — and any leak of the dict breaks the CSRF guarantee. The code comment
already says "production: Redis". Recorded so it is fixed before the gates open, not after.

### EKA-12 — `verify_signature` swallows bare `Exception`
- **Severity:** Low · **Status:** Open
- **Component:** `packages/crypto/keypair.py:50`

`except (BadSignatureError, ValueError, Exception)` makes the first two redundant and maps
any library/internal error (e.g. malformed key length raising `nacl.exceptions.TypeError`/
runtime errors) to "invalid signature", hiding operational faults from monitoring. Every
caller treats False as an auth failure, so security posture is unchanged; it is an
observability defect. **Fix:** catch `BadSignatureError`/`ValueError` only, let the rest
raise into Sentry.

### EKA-13 — Container hygiene: root processes + floating tags
- **Severity:** Low · **Status:** Open
- **Component:** `apps/dashboard/Dockerfile.prod` (no `USER`), `apps/monitor/Dockerfile` (root),
  `infra/docker/docker-compose.prod.yml` (`ollama/ollama:latest`, `tecnativa/docker-socket-proxy:latest`)

api and web images run non-root with pinned bases; dashboard and monitor run as root, and
two infrastructure images float on `:latest`. The monitor additionally talks to the docker
socket proxy (read-only, mitigating). **Fix:** add `USER` directives, pin digests.

### EKA-14 — Residual unescaped remote-data sinks in static docs
- **Severity:** Low · **Status:** Open
- **Component:** `docs/tickets/polis.js:528` (`e.message` from a GitHub API error into
  `innerHTML`), `polis.js:336-337,430` (GitHub `login`/`avatar_url`), `docs/index.html:1926-1929`
  (GitHub user login/avatar), `docs/embed/qr-login.html:88` (API `d.detail`)

Issue titles/bodies/comments are properly escaped (`polis.js:363,405,411,432`,
`index.html:1758-1771`); the listed remnants are mostly constrained alphabets (GitHub
logins/URLs) except the `e.message` error path, which relays a remote API string.
**Fix:** route the error path through the existing `escapeHtml`, escape the rest for
consistency. (Representative app XSS is tracked separately as EKA-02.)

### EKA-15 — Dead admin-key-in-query helpers still shipped
- **Severity:** Low · **Status:** Open
- **Component:** `apps/web/src/lib/api.ts:292-300`

`adminApi.dashboard/bills/stats/reviewBill/transition` still build
`_get('/admin/dashboard?admin_key=${key}')` URLs. Unreferenced since the admin page became
a redirect, and the API no longer accepts query auth — but the helpers ship in the public
bundle and invite future re-wiring of a deprecated pattern. **Fix:** delete.

### EKA-16 — PII in application logs
- **Severity:** Low · **Status:** Open
- **Component:** `apps/api/routers/contact.py:154` (name/org), `newsletter.py:172` (email, EKA-04)

Contact form and newsletter paths log personal data in cleartext. HLR paths correctly log
masked numbers only. **Fix:** mask/hash consistently.

### EKA-17 — HLR credential env names inverted (Info)
`packages/crypto/hlr.py:100-101` reads the **primary** provider's credentials from
`HLR_FALLBACK_API_KEY`/`HLR_FALLBACK_API_SECRET` while the fallback reads
`HLRLOOKUPS_API_KEY/...`. Behavior is correct; the naming is an operations trap during
key rotation. Document or rename with a compat shim.

### EKA-18 — Dev compose publishes datastores with default credentials (Info)
`infra/docker/docker-compose.yml` publishes Postgres 5432 / Redis 6379 with
`devpassword`-class defaults. Dev-only file, production compose publishes nothing.
Accepted risk if developers do not run it on shared networks; note in README.

### EKA-19 — Package-ID drift persists (PNYX-MED-05 follow-up)
Android `package: "ekklesia.gr"` (`apps/mobile/app.json:29`) vs iOS
`bundleIdentifier: "gr.ekklesia.app"` (`:19`), mirrored by `fdroid/ekklesia.gr.yml` and
`metadata/gr.ekklesia.app`. Still unresolved since 2026-05-03; will collide with store
submission/F-Droid MR if not settled. Representative app repeats the pattern
(`ekklesia.representative` vs `gr.ekklesia.representative`).

### EKA-20 — 2026-05-03 master audit re-baseline (Info)
| Prior finding | Status @ c0efac7b |
|---|---|
| PNYX-CRIT-01 admin keys in URLs | **Fixed** (API Bearer-only; dashboard server proxy) |
| PNYX-CRIT-02 public web admin key | **Fixed** (redirect stub) |
| PNYX-HIGH-01 votes-timeline broad-except | **Partial** — narrowed to `(AttributeError, TypeError, ValueError)` (`analytics.py:247-249`); structured degraded status still missing |
| PNYX-HIGH-02 documentation drift | Re-assessed by this series' content coherence audit |
| PNYX-HIGH-03 secret-bearing files | **Clean** — no secret-class files in git index/history |
| PNYX-MED-01 Ollama/RAG live verification | Covered by this series' integration audit |
| PNYX-MED-02 logs/explain wiring | **Fixed** |
| PNYX-MED-03 greek_topics_scraper | **Resolved** (removed; defensive import) |
| PNYX-MED-04 docs innerHTML | **Partial** — see EKA-14 |
| PNYX-MED-05 package-ID drift | **Open** — see EKA-19 |

---

## 5. Out of scope / limitations

Cryptographic constructions (nullifier v1/v2, TS HMAC chain, Groth16 verifier, Arweave
payloads) are assessed in the companion crypto deep audit. Live deployment behavior,
dependency CVE posture and subdomain surface are assessed in the integration & surfaces
audit. No dynamic testing, no authenticated probing, no load testing. Deployment flags
(`ZK_*`, `AUTO_RECOVERY_*`, `TRUSTED_PROXY_COUNT`) were read as code defaults; production
values were not observable.

*— End of full-scope security audit. Register continues in the companion documents (EKA-21+).*

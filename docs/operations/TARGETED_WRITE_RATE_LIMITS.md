# Targeted write rate limits

2026-10-10, T-9052; owner decision: preserve the observed default-limit gap,
document it, and protect missing unauthenticated write entry points explicitly.
This is source/local validation, not a deployment or throughput guarantee.

## Coverage contract

FastAPI 0.142.2 wraps included routers in `_IncludedRouter` objects without a
top-level `endpoint`. SlowAPI 0.1.10's middleware handler lookup therefore skips
their default checks. **The configured 60/min default is not API-wide.** Direct
routes such as `/health` still have it. An enabled limiter alone does not prove
router coverage; explicit decorator wrappers and handler Redis guards do work.
No default, middleware, read quota or exemption policy is changed here.

| Entry point | Explicit control | Patch |
| --- | --- | --- |
| POST `/api/v1/agent/ask` | Shared SlowAPI, 5/min/IP | Existing reference, unchanged |
| POST `/api/v1/vote` | Shared SlowAPI, 120/min/IP | New decorator before identity lookup |
| POST `/api/v1/newsletter/subscribe` | Redis 10/IP/hour + 3/normalized-email/day | Existing guards retained; no second counter |
| POST `/api/v1/contact/ngo` | Redis 3/IP/hour | Existing guard retained; no second counter |
| POST `/api/v1/polis/register-key` | Shared SlowAPI, 120/min/IP | T-9058 decorator before identity lookup |
| POST `/api/v1/polis/tickets` | Shared SlowAPI, 120/min/IP | T-9058 decorator before key binding |
| POST `/api/v1/polis/tickets/{ticket_id}/votes` | Shared SlowAPI, 120/min/IP, fixed scope | T-9058 `shared_limit` before key binding |
| POST `/api/v1/bills/{bill_id}/flag` | Shared SlowAPI, 120/min/IP, fixed scope | T-9058 `shared_limit` before identity lookup |

SlowAPI's default `key_style="url"` buckets `limit()` by concrete path, so a
plain decorator on a path-parameter route would let rotating ticket/bill IDs
mint unlimited fresh buckets (observed locally before the fix). Those two
routes use `shared_limit` with a fixed scope; counters still hold only the
route scope plus HMAC-IP, never identities, nullifiers or body keys.

120/min is a deliberately generous initial per-IP voting ceiling for shared
carrier/NAT addresses, not a per-person entitlement or replacement for Ed25519,
ACTIVE identity, vote-nullifier uniqueness or lifecycle controls. Keys reuse the
existing trusted-proxy-aware, daily HMAC IP key; no raw IP is newly persisted.
Untrusted forwarded headers cannot select a fresh bucket. Redis outages and
the existing SlowAPI per-process memory fallback policy are unchanged; this
fallback is not a distributed/global guarantee.

There is no literal public `/feedback` or `/report` route in the tracked API,
web or mobile source. The semantic equivalents are signed identity-bound
`POST /api/v1/polis/tickets` and `POST /api/v1/bills/{bill_id}/flag`; they are
not silently reclassified or altered. Correction, relevance, consensus, ZK,
municipal voting and other siblings are outside this narrowly authorized patch
and must not be assumed covered by the default. No new endpoints are invented.

SSR GET `/api/v1/bills`, `/api/v1/vote/{bill_id}/results` and
`/api/v1/app/version` receive no new limiter. Public `/api/v1/public/*` reads
retain their separate shared 100/1000 quotas. Newsletter validation and the
already-confirmed early return remain unchanged.

## Validation and gates

Before the patch, an enabled original shared limiter on real `main.app` with
current routing packages returned 200 for agent calls 1..5, then 429 on call 6;
the same app returned 200 for all 61 app/version reads. Provider/model work was
stubbed and no lifespan startup or network was allowed.

Regression tests exercise the real included route wrappers and existing Redis
helper decisions using isolated memory stores, not a disabled limiter or a
replacement endpoint. They cover limit+1, unchanged auth rejection, IP bucket
separation/spoofing, GET controls and single counting of existing mail guards.
Cached routing overlays match FastAPI/Starlette/SlowAPI/limits; other cached
dependencies are not claimed to match the full lock. Exact-head CI and gio-dd
cross-review remain merge gates. No production tests, deployment, new secrets,
flag changes, paid calls or provider requests are authorized.

Focused local slice: **124 passed, 2 xfailed**, 26.14s, including all seven new
HTTP regressions and existing direct voting/crypto/mail tests. One cached
Starlette/httpx deprecation warning. The current repository crypto package is
also mounted read-only; a missing symbol in the old cached crypto copy is not
a product failure. Full dependency-lock CI and real deployment remain gates.

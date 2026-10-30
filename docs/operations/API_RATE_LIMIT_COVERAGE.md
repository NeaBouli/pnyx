# API rate-limit policy and acceptance — EKA-32 / B01

Reviewed 2026-10-30 against `30e20e6c` plus the uncommitted B01 changes. This is
source and local HTTP acceptance, not deployment verification. Limits are
endpoint-specific, with explicit exemptions. There is
**no universal 60/minute ceiling**. The coverage test traverses actual registered
routes, including FastAPI's lazy included routers, all HTTP methods and admin
authentication dependencies. It requires the real decorator wrapper and checks
that representative token authentication follows the limiter dependency.
New admin routes, public reads, methods or exemptions require an explicit policy;
the table below is checked against the registered application.

## Policy classes

| Class | Policy |
| --- | --- |
| `explicit` | Existing route decorators: 5, 10, 20, 30, 120 or 600/minute/IP. Shared scopes resist rotating target IDs. |
| `dedicated-redis` | Existing HLR, key generation, newsletter, contact and push registration counters; exact quotas below. |
| `public-shared-redis` | One combined budget across seven public-data GETs: 100/minute/anonymous IP or 1000/minute/valid key; invalid keys retain the IP bucket. |
| `public-read-exempt` | Public catalogues, paginated feeds and shared aggregates; retain access for SSR visitors sharing one server IP. These exemptions do not introduce a cache. |
| `provider-exempt` | Stripe signature, PayPal IPN verification, or authenticated Brevo event batches and existing deduplication; provider retries/bursts share source addresses. |
| `admin-exempt` | Exact listed routes require admin-key dependencies; operator batch/maintenance traffic retains its exemption from citizen-IP quotas. Authentication must remain present. |
| `direct-default` | Direct main-app endpoints, including health, use the existing 60/minute/IP per endpoint middleware default. |

Development-only `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, and `/redoc`
(including their automatic HEAD methods) use the same `direct-default` class when
enabled. Browser CORS preflight is handled outside the limiter and consumes no
quota. Unmatched URLs and method errors have no endpoint policy; WebSockets are
outside this HTTP inventory. `/api/v1/admin/sentry/status` has the direct default;
its namespace does not imply an authentication dependency.

## Proxy attribution and mobile behaviour

`TRUSTED_PROXY_CIDRS` allows immediate proxy peers (default loopback networks).
Untrusted peers cannot set their bucket through `X-Forwarded-For`.
`TRUSTED_PROXY_COUNT` bounds traversal from the right (default one). Every skipped
proxy hop must also be trusted; traversal stops at the nearest untrusted address.
Repeated forwarding fields form one ordered chain, so a client-supplied first
field cannot hide the peer appended by a trusted proxy in a later field.
Malformed required hops fall back to the socket peer rather than shifting a
client-supplied leftmost value into the selected position. Too-short chains use
the nearest valid asserted hop. Invalid CIDRs are ignored; invalid/nonpositive
counts use one. IPv6 text is canonicalized before hashing. Ensure the ASGI server
preserves the actual peer; any server-level proxy rewriting needs an independently
correct trust configuration. The application cannot recover a peer already
replaced by an overly broad server-level proxy setting.

Web SSR feeds retain their exemptions. Signed vote submission and signed status
preflight retain 120/minute/IP; the compatibility test exercises 120 valid signed
preflights for eleven identities sharing an IP. QR polling retains 30/minute per
validated session plus 600/minute/IP (six concurrent sessions at 2.5-second
intervals fit). `apps/mobile/src/lib/api.ts` retries only opted-in public GETs on
the mirror after 408/429/5xx; signed reads and writes do not automatically retry
or become unsigned. Key rotation has a separate foreground retry with a
60-second minimum interval, which fits its existing 10/minute quota and the
5/minute outage fallback. Notification acknowledgements retain their separate
single idempotent retry. No mobile code or normal-operation quotas are changed.

## Shared storage, fallback and privacy

All workers use the same `RATE_LIMIT_STORAGE_URI`, falling back to `REDIS_URL`;
`memory://` is the local-development default when neither is configured. Runtime
workers need a shared Redis URI and the same `RATE_LIMIT_SALT`/`SERVER_SALT`.
`RATE_LIMIT_ENABLED` defaults to `true`; disabling it bypasses SlowAPI policies,
while dedicated handler counters remain independent. API tests disable SlowAPI
by default and explicitly enable it in the enforcement/acceptance fixtures.
SlowAPI uses the `ekklesia-api` prefix and daily HMAC IP buckets. Redis fixed
windows use atomic INCR/EXPIRE Lua; dependent public-data routes share one key.
Redis connect/read waits for SlowAPI counters are bounded to 0.2 seconds each.

On counter-storage failure, SlowAPI and the common asynchronous Redis counter
helper allow **floor(normal quota / 2), minimum one**, in the original window
and scope. For example 10/minute becomes 5/minute and signed votes/status become
60/minute. Memory is **per process**, starts fresh, is lost on restart, and cannot
provide a global bound across workers. More workers can therefore increase the
overall outage allowance; this is a deliberately degraded mode. SlowAPI probes
for recovery and returns to the shared backend; local usage is not replayed.
The async helper retries Redis on each call; its bounded 10,000 live buckets
reject new buckets with 429 when full instead of evicting/resetting live quotas.
A failed expiry lookup while forming a 429 retains a conservative full-window
retry delay and never replaces the response with a storage 5xx.

This fallback applies to **rate counters**. Separate Redis session/key data,
registration persistence, newsletter locks and the atomic paid-HLR cost guard
retain their availability requirements. In particular paid HLR lookup remains
fail-closed with 503 when its dedicated multi-key guard is unavailable; a local
counter must not authorize paid provider work. A complete Redis data outage is
not a promise that Redis-dependent features remain available.

Limiter logs contain only a fixed event name and count, with no IP, bucket,
endpoint target, client identifier or exception text. Daily HMAC identifiers
remain in counters, not logs. Existing handler/provider logs are outside this
limiter logging contract.

## 429 response contract

Every raised quota HTTP exception and SlowAPI rejection uses:

```json
{"error":"Rate limit exceeded","detail":"Rate limit exceeded","retry_after":60}
```

`detail` preserves existing route-specific messages or the public API quota
object for compatibility. Header names are handled case-insensitively, with
exactly one `Retry-After` emitted. `retry_after` and `Retry-After` agree and are positive
seconds. Dedicated fixed-window counters give a conservative full window;
SlowAPI uses the remaining expiry, with a full-window bound if expiry lookup
fails. Translated handler errors retain their underlying counter's window.
Legacy/provider 429 errors without retry guidance use 60 seconds; an explicit
provider `Retry-After` (such as Brevo's 600 seconds) is preserved.

All five configured browser origins receive CORS allow-origin and exposed
`Retry-After`, including limiter early returns. Disallowed origins receive no
allow-origin. Preflight bypasses the counter. CSP, `X-Content-Type-Options:
nosniff`, and the existing noindex policy wrap responses as before. Other HTTP
exception statuses retain FastAPI's existing response shape.

## Registered HTTP policy table

200 method/path entries: admin-exempt 61, dedicated-redis 6, direct-default 6, explicit 58, provider-exempt 3, public-read-exempt 59, public-shared-redis 7.

<!-- route-policy:start -->
| Method | Registered path | Class | Limit or exemption reason |
| --- | --- | --- | --- |
| GET | `/` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
| GET | `/api/v1/admin/bills` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/bills` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| PATCH | `/api/v1/admin/bills/{bill_id}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/bills/{bill_id}/fetch-text` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/bills/{bill_id}/party-votes` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/bills/{bill_id}/review` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/bills/{bill_id}/set-text` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| DELETE | `/api/v1/admin/bills/{bill_id}/votes` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/compass/approve/{question_id}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/compass/generate-questions` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/compass/pending-review` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/compass/reject/{question_id}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/dashboard` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/diavgeia/convert-to-bills` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/diavgeia/decision/{ada}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/diavgeia/refresh-orgs-cache` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/diavgeia/refresh-orgs-cache/{job_id}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/diavgeia/resolve-orgs` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/diavgeia/scrape` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/forum/resync-all` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/forum/sync-new` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/hlr/credits` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/logs/containers` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/logs/explain` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/logs/ollama` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/logs/stream` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/maintenance/resolve-org-labels` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/audience` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/backfill` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/newsletter/dispatch-status` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/draft` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| PUT | `/api/v1/admin/newsletter/preferences` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/preview` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/newsletter/readiness` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/reconfirm` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/reconfirm/expire` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/newsletter/send` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/newsletter/stats` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/scraper/catch-up` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/scraper/enrich-all` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/scraper/heal-status` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/admin/sentry/status` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
| GET | `/api/v1/admin/stats` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/admin/test-account` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/agent/ask` | explicit | 5 per 1 minute |
| GET | `/api/v1/analytics/bill/{bill_id}` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/divergence-trends` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/info` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/overview` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/representation` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/top-divergence` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/analytics/votes-timeline` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/app/version` | public-read-exempt | Static client update metadata; retain existing polling access policy. |
| GET | `/api/v1/arweave/bill/{bill_id}` | public-read-exempt | Single stored archive pointer; no gateway/provider request. |
| GET | `/api/v1/arweave/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/auth/govgr/callback` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/family/verify` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/auth/govgr/info` | public-read-exempt | Static integration metadata. |
| GET | `/api/v1/auth/govgr/login` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/status` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/bills` | public-read-exempt | Paginated public feed; retain existing SSR access policy. |
| POST | `/api/v1/bills/admin/create` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/bills/sources/freshness` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/bills/trending` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/bills/{bill_id}` | public-read-exempt | Single public bill lookup. |
| POST | `/api/v1/bills/{bill_id}/flag` | explicit | 120 per 1 minute |
| GET | `/api/v1/bills/{bill_id}/summary` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/bills/{bill_id}/transition` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/claude/budget` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/consensus/representation` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/contact/ngo` | dedicated-redis | Existing Redis guard: 3/IP/hour before sending mail. |
| GET | `/api/v1/cplm/aggregate` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/cplm/history` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/decisions` | public-read-exempt | Paginated public decision feed. |
| GET | `/api/v1/export/bills.csv` | explicit | 30 per 1 minute |
| GET | `/api/v1/export/divergence.csv` | explicit | 30 per 1 minute |
| GET | `/api/v1/export/info` | public-read-exempt | Static format metadata; CSV downloads have explicit limits. |
| GET | `/api/v1/export/parties.json` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/export/results.json` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/health/modules` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
| GET | `/api/v1/identity/hlr/credits` | public-read-exempt | public cacheable read; SSR shares one IP |
| PATCH | `/api/v1/identity/profile/location` | explicit | 20 per 1 minute |
| POST | `/api/v1/identity/revoke` | explicit | 10 per 1 minute |
| POST | `/api/v1/identity/status` | explicit | 10 per 1 minute |
| POST | `/api/v1/identity/verify` | dedicated-redis | Atomic HLR Redis guard: 5/IP/min, 20/IP/day, 3/number/day and 300s cooldown. |
| GET | `/api/v1/mp/bill/{bill_id}` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/mp/compare/{party_abbr}` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/mp/info` | public-read-exempt | Static module metadata. |
| GET | `/api/v1/mp/parties` | public-read-exempt | Small public party catalogue. |
| GET | `/api/v1/mp/ranking` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/municipal/vote` | explicit | 20 per 1 minute |
| GET | `/api/v1/municipal/{dimos_id}/decisions` | public-read-exempt | Paginated public municipal decision feed. |
| GET | `/api/v1/municipal/{dimos_id}/voteable` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/newsletter/confirm/{token}` | explicit | 10 per 1 minute |
| GET | `/api/v1/newsletter/lists` | public-read-exempt | Static subscription options. |
| GET | `/api/v1/newsletter/stats` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/newsletter/subscribe` | dedicated-redis | Redis: 10/IP/hour and 3/email/day; confirmed subscriptions return without consuming quota. |
| POST | `/api/v1/newsletter/unsubscribe` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/newsletter/webhook/brevo` | provider-exempt | Authenticated Brevo event batches; preserve provider retries and bursts. |
| GET | `/api/v1/notifications/status` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/notifications/stream` | explicit | 30 per 1 minute |
| POST | `/api/v1/notifications/test/publish` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/notify/register` | dedicated-redis | Redis: 600/IP/hour before auth, 20/identity/day for changed device registrations. |
| POST | `/api/v1/notify/send` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/finance/btc` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/finance/events` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/finance/ltc` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/finance/overview` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/finance/server` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/admin/logs` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/payments/public/finance` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/payments/status` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/payments/webhook` | provider-exempt | Stripe signature verification and event deduplication; preserve provider retries and bursts. |
| POST | `/api/v1/payments/webhook/paypal` | provider-exempt | PayPal IPN verification and transaction deduplication; preserve provider retries and bursts. |
| GET | `/api/v1/periferia` | public-read-exempt | Small public region catalogue. |
| GET | `/api/v1/periferia/{periferia_id}/dimos` | public-read-exempt | Bounded public municipality catalogue for one region. |
| POST | `/api/v1/polis/qr-auth` | explicit | 10 per 1 minute |
| POST | `/api/v1/polis/qr-consensus` | explicit | 20 per 1 minute |
| GET | `/api/v1/polis/qr-session` | explicit | 10 per 1 minute |
| GET | `/api/v1/polis/qr-session/{session_id}` | explicit | 600 per 1 minute |
| POST | `/api/v1/polis/qr-vote` | explicit | 20 per 1 minute |
| POST | `/api/v1/polis/register-key` | explicit | 120 per 1 minute |
| GET | `/api/v1/polis/tickets` | public-read-exempt | Public ticket list capped at 100 records. |
| POST | `/api/v1/polis/tickets` | explicit | 120 per 1 minute |
| POST | `/api/v1/polis/tickets/{ticket_id}/votes` | explicit | 120 per 1 minute |
| GET | `/api/v1/politicians/` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/politicians/my-evaluations/bulk` | explicit | 10 per 1 minute |
| POST | `/api/v1/politicians/{ada_number}/evaluate` | explicit | 20 per 1 minute |
| GET | `/api/v1/politicians/{ada_number}/my-evaluation` | explicit | 10 per 1 minute |
| GET | `/api/v1/politicians/{ada_number}/questions` | public-read-exempt | Small public evaluation question catalogue; no personal scores. |
| GET | `/api/v1/politicians/{ada_number}/scores` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/public/bills` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/bills/{bill_id}/results` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/cplm` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/cplm/history` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/deepl/usage` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/info` | public-read-exempt | Static API metadata. |
| POST | `/api/v1/public/keys/generate` | dedicated-redis | Existing Redis guard: 5/IP/hour before generating a key. |
| GET | `/api/v1/public/keys/status` | explicit | 10 per 1 minute |
| GET | `/api/v1/public/mirrors/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/representation` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/scraper/status` | explicit | 30 per 1 minute |
| POST | `/api/v1/public/share` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/stats` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/public/vaa/parties` | public-shared-redis | Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key. |
| GET | `/api/v1/regions/{periferia_id}/decisions` | public-read-exempt | Paginated public regional decision feed. |
| POST | `/api/v1/rep/admin/invite` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/rep/admin/invites` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/rep/auth` | explicit | 10 per 1 minute |
| GET | `/api/v1/rep/bills` | public-read-exempt | Representative-authenticated public bill list capped at 100 records. |
| GET | `/api/v1/rep/divergence/{bill_id}` | explicit | 30 per 1 minute |
| POST | `/api/v1/rep/enable-evaluation` | explicit | 20 per 1 minute |
| GET | `/api/v1/rep/my-scores` | explicit | 10 per 1 minute |
| GET | `/api/v1/rep/results/{bill_id}` | explicit | 30 per 1 minute |
| POST | `/api/v1/rep/verify` | explicit | 10 per 1 minute |
| POST | `/api/v1/scraper/fetch` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/scraper/import` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/scraper/jobs` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/scraper/parliament/freshness` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/parliament/latest` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/test` | explicit | 30 per 1 minute |
| POST | `/api/v1/sso/discourse/callback` | explicit | 10 per 1 minute |
| GET | `/api/v1/sso/discourse/initiate` | explicit | 10 per 1 minute |
| POST | `/api/v1/sso/discourse/qr-complete` | explicit | 10 per 1 minute |
| POST | `/api/v1/vaa/match` | explicit | 20 per 1 minute |
| GET | `/api/v1/vaa/parties` | public-read-exempt | Small public party catalogue. |
| GET | `/api/v1/vaa/questions` | public-read-exempt | Bounded public question lookup. |
| GET | `/api/v1/vaa/statements` | public-read-exempt | Bounded public statement lookup. |
| GET | `/api/v1/version` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
| POST | `/api/v1/vote` | explicit | 120 per 1 minute |
| GET | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| GET | `/api/v1/vote/results/in-progress` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/vote/results/latest` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/vote/{bill_id}/consensus` | explicit | 20 per 1 minute |
| PUT | `/api/v1/vote/{bill_id}/correct` | explicit | 20 per 1 minute |
| GET | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/{bill_id}/relevance` | explicit | 30 per 1 minute |
| GET | `/api/v1/vote/{bill_id}/results` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/vote/{bill_id}/status` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/{bill_id}/status` | explicit | 120 per 1 minute |
| GET | `/api/v1/zk/canary/preflight/{vote_scope_id}` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| POST | `/api/v1/zk/opt-in` | explicit | 10 per 1 minute |
| GET | `/api/v1/zk/receipts/{vote_scope_id}` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/zk/receipts/{vote_scope_id}/publish-pending` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/zk/roots/{vote_scope_id}` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/zk/roots/{vote_scope_id}/members` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/zk/roots/{vote_scope_id}/publish` | admin-exempt | Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota. |
| GET | `/api/v1/zk/scopes/{vote_scope_id}/status` | public-read-exempt | public cacheable read; SSR shares one IP |
| GET | `/api/v1/zk/status` | public-read-exempt | public cacheable read; SSR shares one IP |
| POST | `/api/v1/zk/verify` | explicit | 10 per 1 minute |
| POST | `/api/v1/zk/vote` | explicit | 20 per 1 minute |
| POST | `/api/v2/identity/key-check` | explicit | 30 per 1 minute |
| POST | `/api/v2/identity/rotate-key` | explicit | 10 per 1 minute |
| POST | `/api/v2/identity/verify` | dedicated-redis | Uses the same atomic HLR Redis guard as v1 registration. |
| GET | `/health` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
| GET | `/robots.txt` | direct-default | 60/minute/IP per endpoint via SlowAPI middleware (including health). |
<!-- route-policy:end -->

## Local acceptance evidence (2026-10-30)

Commands run from `apps/api` with `TZ=UTC`:

```sh
python -m pytest tests/test_rate_limit_coverage.py tests/test_ip_utils.py tests/test_rate_limit_middleware.py tests/test_rate_limit_acceptance.py tests/test_rate_limit_privacy.py tests/test_rate_limit_route_enforcement.py tests/test_newsletter_subscribe_rate_limit.py tests/test_wiki_api_reference.py tests/test_agent_eka62_robustness.py tests/test_identity_hlr_cost_guard.py tests/test_notify_register.py tests/test_security_headers.py tests/test_native_telemetry_disabled.py -q --tb=short -rs
ENVIRONMENT=development python -m pytest tests/test_rate_limit_coverage.py -q --tb=short -rs
python -m pytest tests/ -q --tb=short -rs
```

Focused result: **287 passed, 3 skipped** in 42.67 seconds. Development policy
coverage: **13 passed** in 2.48 seconds, including the optional documentation
routes and their HEAD methods. The focused run includes the existing valid
signed-vote preflight and concurrent QR polling compatibility tests.

The full UTC suite completed once after correcting the test environment:
**4293 passed, 95 skipped, 25 xfailed, 32 warnings, 4 subtests passed** in
907.05 seconds. No failures or errors remain in that run. The skips include
the three real-Redis rate-limit gates and optional PostgreSQL/Redis tests.

Recorded summary tails:

```text
287 passed, 3 skipped, 1 warning in 42.67s
13 passed in 2.48s
4293 passed, 95 skipped, 25 xfailed, 32 warnings, 4 subtests passed in 907.05s (0:15:07)
```

The cached interpreter is Python 3.13.0 with Starlette 1.6.0, SlowAPI 0.1.10,
limits 5.8.0, Redis client 8.1.0 and pytest 9.1.1. The initial cached FastAPI
0.141.1 passed the limiter tests but stopped full-suite collection because it
lacks `fastapi.telemetry`. The subsequent runs use cached FastAPI 0.143.0 and its
OpenTelemetry API 1.45.1 dependency from a temporary `PYTHONPATH` directory.
No project dependencies were added. FastAPI 0.143.3 is declared by the project;
the complete exact-requirements matrix remains a CI release check. Pydantic
2.13.5 and SQLAlchemy 2.0.52 also differ from the declared versions. No production
deployment or paid-provider lookup was performed.

The three real-Redis gates cover independent limiter instances, separate worker
processes, and concurrent asynchronous Lua counters with expiry. They are gated
on `REDIS_URL` and must run against a disposable Redis service in CI/runtime
acceptance; the local sandbox has no accessible Redis server. They are not
claimed as passing local Redis integration. Fault injection and an unreachable
Redis connection exercise the production limiter, actual included routes and
asynchronous counter helper, including stricter limits, recovery, scope, expiry,
bounded local storage, counts-only logs and 429 browser headers.

All 33 `include_router` registrations in `main.py` are unchanged from
`30e20e6c` (#690), checked by comparing their parsed syntax trees.

# API rate-limit policy and acceptance — EKA-32 / B01

Reviewed 2026-10-30 for PR #706 / the B01 fix round. Every registered route
requires an explicit class; new public reads, admin routes, methods and exemptions
fail the coverage gate until classified. The audit checks actual wrappers on lazy
included routers and enforcement before representative/admin authentication.
Only five constant-cost endpoints are exempt; each has a one-line reason in the
policy table and an HTTP test forbidding database and provider access.

## Policy classes

| Class | Count | Policy |
| --- | ---: | --- |
| `public-read` | 23 | 120/minute/IP shared across ordinary reads. |
| `public-heavy` | 105 | 20/minute/IP shared across aggregates, analytics, searches, large feeds, exports, admin work and authenticated provider callbacks. |
| `generate` | 5 | 5/minute/IP shared plus 30/minute globally across all generation-capable routes. Includes the optional hybrid citizen agent. |
| `paypal-verify` | 1 | 10/minute/IP plus 60/minute globally; at most four outbound verifications/process, with immediate 429 on saturation. |
| `explicit` | 55 | Existing signed/action/polling policies, including 120/minute signed votes/status and 600/minute QR polling. Exact scopes below. |
| `dedicated-redis` | 6 | Existing HLR, key generation, newsletter, contact and push counters; exact quotas below. |
| `cheap-exempt` | 5 | Static greeting, health manifest, robots and two app-version endpoints; no DB or provider access. |

All shared classes use the same Redis store across workers. Public data reads
also retain their combined 100/minute anonymous-IP or 1000/minute valid-key
budget. Their read/heavy class applies first; API keys do not bypass it. Invalid
keys or an unavailable key validator use the anonymous IP counter, including the
local half quota during a Redis outage. Admin authentication, Stripe signatures,
Brevo authentication, PayPal verification and deduplication remain required.

Development-only `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, and `/redoc`
(including automatic HEAD methods) have the `framework-default` 60/minute/IP
policy when enabled. Browser CORS preflight consumes no quota. Unmatched URLs,
method errors and WebSockets are outside this registered HTTP inventory.
`/api/v1/admin/sentry/status` has a heavy class; its namespace is not authentication.

## Bounded request work

- Bill summaries accept only `el` and `en` (422 otherwise), producing just two
  language cache variants per bill. The generate class runs before DB/provider work.
- ZK members use a bounded 16-entry cache keyed by scope, published root, size
  and depth. Concurrent fills coalesce; Poseidon runs in a thread, with at most
  four different fills in flight per event loop. Membership changes still return
  409 for a stale root; cache hits compare members without rebuilding Poseidon.
- JSON and both result CSV exports default to 100 bills, cap at 500, and bound
  offset to 10,000. Pagination happens in SQL before aggregation; vote queries
  (including small-cell partitions) are restricted to that page's bill IDs.
  `min_votes` filters within the selected page; pagination follows bill order.
- VAA questions/statements default to 30, accept 1–100, and apply a SQL LIMIT
  before loading rows. `limit=0` no longer requests all statements.
- CPLM, representation and newsletter cache misses share one in-flight result
  per key/event loop. Each fill type also has a shared global quota of six fills
  per minute (three/process/minute on outage). Across workers, that quota bounds
  simultaneous independent leaders; single-flight itself is process-local.
  Followers share errors; cancelling a follower does not cancel the leader.
- Representation returns at most 200 bill details (titles at most 500 characters)
  while retaining aggregate totals over all eligible bills. A process-local,
  policy-keyed snapshot covers cache outages for at most 30 seconds from query
  start. Hits never renew expiry; normal invalidation clears these snapshots.
- PayPal retains its 15-second verification timeout. A semaphore rejects excess
  work immediately, with no unbounded queue; slots are released on all exits.

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

SSR reads now share the public classes; a busy SSR IP can receive 429.
Signed vote submission and signed status
preflight retain 120/minute/IP; the compatibility test exercises 120 valid signed
preflights for eleven identities sharing an IP. QR polling retains 30/minute per
validated session plus 600/minute/IP (six concurrent sessions at 2.5-second
intervals fit). `apps/mobile/src/lib/api.ts` retries only opted-in public GETs on
the mirror after 408/429/5xx; signed reads and writes do not automatically retry
or become unsigned. Key rotation has a separate foreground retry with a
60-second minimum interval, which fits its existing 10/minute quota and the
5/minute outage fallback. Notification acknowledgements retain their separate
single idempotent retry. Signed-action quotas are unchanged. Pending ZK scope
polling now uses a 15-second interval to leave room for other reads.
A normal tested session uses six heavy reads and two ordinary reads/minute,
well below 20/120. Pending ZK enrollment uses four polls/minute; including six
other heavy reads, two startup status reads and two proof-root reads totals
14/20 in the tested first-minute flow. A newly published root can take up to
15 seconds to appear through polling. Clients behind one IP share these budgets.
App-version checks are constant-cost exemptions and do
not consume either class. Tests also retain 120 valid signed preflights from
eleven identities/IP and six concurrent QR sessions at the client interval.

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
Both SlowAPI's fallback and the async helper cap storage at 10,000 live buckets.
New buckets receive 429 at capacity; live counters are never evicted or reset.
Expired capacity is reusable. SlowAPI admission/increment is atomic across
threads and does not allocate per-key locks or timers. The async helper retries
Redis on each call.
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

200 method/path entries: public-read 23, public-heavy 105, generate 5, paypal-verify 1, explicit 55, dedicated-redis 6, cheap-exempt 5.

<!-- route-policy:start -->
| Method | Registered path | Class | Limit or exemption reason |
| --- | --- | --- | --- |
| GET | `/` | cheap-exempt | Constant API greeting; no database or provider access. |
| GET | `/api/v1/admin/bills` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/bills` | public-heavy | 20 per 1 minute (public-heavy) |
| PATCH | `/api/v1/admin/bills/{bill_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/bills/{bill_id}/fetch-text` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/bills/{bill_id}/party-votes` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/bills/{bill_id}/review` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/bills/{bill_id}/set-text` | public-heavy | 20 per 1 minute (public-heavy) |
| DELETE | `/api/v1/admin/bills/{bill_id}/votes` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/compass/approve/{question_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/compass/generate-questions` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| GET | `/api/v1/admin/compass/pending-review` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/compass/reject/{question_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/dashboard` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/diavgeia/convert-to-bills` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/diavgeia/decision/{ada}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/diavgeia/refresh-orgs-cache` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/diavgeia/refresh-orgs-cache/{job_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/diavgeia/resolve-orgs` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/diavgeia/scrape` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/forum/resync-all` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/forum/sync-new` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/hlr/credits` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/logs/containers` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/logs/explain` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| GET | `/api/v1/admin/logs/ollama` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/logs/stream` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/maintenance/resolve-org-labels` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/audience` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/backfill` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/newsletter/dispatch-status` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/draft` | public-heavy | 20 per 1 minute (public-heavy) |
| PUT | `/api/v1/admin/newsletter/preferences` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/preview` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/newsletter/readiness` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/reconfirm` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/reconfirm/expire` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/newsletter/send` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/newsletter/stats` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/scraper/catch-up` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/scraper/enrich-all` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| POST | `/api/v1/admin/scraper/heal-status` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/sentry/status` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/admin/stats` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/admin/test-account` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/agent/ask` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| GET | `/api/v1/analytics/bill/{bill_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/divergence-trends` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/info` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/overview` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/representation` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/top-divergence` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/votes-timeline` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/app/version` | cheap-exempt | Static release metadata and environment feature flags; no database or provider access. |
| GET | `/api/v1/arweave/bill/{bill_id}` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/arweave/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/auth/govgr/callback` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/family/verify` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/auth/govgr/info` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/auth/govgr/login` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/status` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/bills` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/bills/admin/create` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/bills/sources/freshness` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/bills/trending` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/bills/{bill_id}` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/bills/{bill_id}/flag` | explicit | 120 per 1 minute (bill-flag) |
| GET | `/api/v1/bills/{bill_id}/summary` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| POST | `/api/v1/bills/{bill_id}/transition` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/claude/budget` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/consensus/representation` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/contact/ngo` | dedicated-redis | Existing Redis guard: 3/IP/hour before sending mail. |
| GET | `/api/v1/cplm/aggregate` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/cplm/history` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/decisions` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/export/bills.csv` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/export/divergence.csv` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/export/info` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/export/parties.json` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/export/results.json` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/health/modules` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/identity/hlr/credits` | public-read | 120 per 1 minute (public-read) |
| PATCH | `/api/v1/identity/profile/location` | explicit | 20 per 1 minute |
| POST | `/api/v1/identity/revoke` | explicit | 10 per 1 minute |
| POST | `/api/v1/identity/status` | explicit | 10 per 1 minute |
| POST | `/api/v1/identity/verify` | dedicated-redis | Atomic HLR Redis guard: 5/IP/min, 20/IP/day, 3/number/day and 300s cooldown. |
| GET | `/api/v1/mp/bill/{bill_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/mp/compare/{party_abbr}` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/mp/info` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/mp/parties` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/mp/ranking` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/municipal/vote` | explicit | 20 per 1 minute |
| GET | `/api/v1/municipal/{dimos_id}/decisions` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/municipal/{dimos_id}/voteable` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/newsletter/confirm/{token}` | explicit | 10 per 1 minute (newsletter:confirm_subscription) |
| GET | `/api/v1/newsletter/lists` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/newsletter/stats` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/newsletter/subscribe` | dedicated-redis | Redis: 10/IP/hour and 3/email/day; confirmed subscriptions return without consuming quota. |
| POST | `/api/v1/newsletter/unsubscribe` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/newsletter/webhook/brevo` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/notifications/status` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/notifications/stream` | explicit | 30 per 1 minute |
| POST | `/api/v1/notifications/test/publish` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/notify/register` | dedicated-redis | Redis: 600/IP/hour before auth, 20/identity/day for changed device registrations. |
| POST | `/api/v1/notify/send` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/finance/btc` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/finance/events` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/finance/ltc` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/finance/overview` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/finance/server` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/admin/logs` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/payments/public/finance` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/payments/status` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/payments/webhook` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/payments/webhook/paypal` | paypal-verify | 10 per 1 minute (paypal-verify); 60 per 1 minute (paypal-global) |
| GET | `/api/v1/periferia` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/periferia/{periferia_id}/dimos` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/polis/qr-auth` | explicit | 10 per 1 minute |
| POST | `/api/v1/polis/qr-consensus` | explicit | 20 per 1 minute |
| GET | `/api/v1/polis/qr-session` | explicit | 10 per 1 minute |
| GET | `/api/v1/polis/qr-session/{session_id}` | explicit | 600 per 1 minute (polis_qr:poll_qr_session) |
| POST | `/api/v1/polis/qr-vote` | explicit | 20 per 1 minute |
| POST | `/api/v1/polis/register-key` | explicit | 120 per 1 minute |
| GET | `/api/v1/polis/tickets` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/polis/tickets` | explicit | 120 per 1 minute |
| POST | `/api/v1/polis/tickets/{ticket_id}/votes` | explicit | 120 per 1 minute (polis-ticket-vote) |
| GET | `/api/v1/politicians/` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/politicians/my-evaluations/bulk` | explicit | 10 per 1 minute |
| POST | `/api/v1/politicians/{ada_number}/evaluate` | explicit | 20 per 1 minute (evaluation:evaluate_politician) |
| GET | `/api/v1/politicians/{ada_number}/my-evaluation` | explicit | 10 per 1 minute (evaluation:get_my_evaluation) |
| GET | `/api/v1/politicians/{ada_number}/questions` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/politicians/{ada_number}/scores` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/bills` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/bills/{bill_id}/results` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/cplm` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/cplm/history` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/deepl/usage` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/info` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/public/keys/generate` | dedicated-redis | Existing Redis guard: 5/IP/hour before generating a key. |
| GET | `/api/v1/public/keys/status` | explicit | 10 per 1 minute |
| GET | `/api/v1/public/mirrors/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/representation` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/scraper/status` | explicit | 30 per 1 minute |
| POST | `/api/v1/public/share` | explicit | 30 per 1 minute |
| GET | `/api/v1/public/stats` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/public/vaa/parties` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/regions/{periferia_id}/decisions` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/rep/admin/invite` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/rep/admin/invites` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/rep/auth` | explicit | 10 per 1 minute |
| GET | `/api/v1/rep/bills` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/rep/divergence/{bill_id}` | explicit | 30 per 1 minute (representative:get_rep_divergence) |
| POST | `/api/v1/rep/enable-evaluation` | explicit | 20 per 1 minute |
| GET | `/api/v1/rep/my-scores` | explicit | 10 per 1 minute |
| GET | `/api/v1/rep/results/{bill_id}` | explicit | 30 per 1 minute (representative:get_rep_results) |
| POST | `/api/v1/rep/verify` | explicit | 10 per 1 minute |
| POST | `/api/v1/scraper/fetch` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/scraper/import` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/scraper/jobs` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/scraper/parliament/freshness` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/parliament/latest` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/scraper/test` | explicit | 30 per 1 minute |
| POST | `/api/v1/sso/discourse/callback` | explicit | 10 per 1 minute |
| GET | `/api/v1/sso/discourse/initiate` | explicit | 10 per 1 minute |
| POST | `/api/v1/sso/discourse/qr-complete` | explicit | 10 per 1 minute |
| POST | `/api/v1/vaa/match` | explicit | 20 per 1 minute |
| GET | `/api/v1/vaa/parties` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/vaa/questions` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/vaa/statements` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/version` | cheap-exempt | Static legacy release metadata; no database or provider access. |
| POST | `/api/v1/vote` | explicit | 120 per 1 minute |
| GET | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| GET | `/api/v1/vote/results/in-progress` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/vote/results/latest` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/vote/{bill_id}/consensus` | explicit | 20 per 1 minute (voting:submit_consensus) |
| PUT | `/api/v1/vote/{bill_id}/correct` | explicit | 20 per 1 minute (voting:correct_vote) |
| GET | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute (voting:get_vote_receipt_deprecated) |
| POST | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute (voting:post_vote_receipt) |
| POST | `/api/v1/vote/{bill_id}/relevance` | explicit | 30 per 1 minute (voting:vote_relevance) |
| GET | `/api/v1/vote/{bill_id}/results` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/vote/{bill_id}/status` | explicit | 10 per 1 minute (voting:get_vote_status) |
| POST | `/api/v1/vote/{bill_id}/status` | explicit | 120 per 1 minute (voting:post_vote_status) |
| GET | `/api/v1/zk/canary/preflight/{vote_scope_id}` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/zk/opt-in` | explicit | 10 per 1 minute |
| GET | `/api/v1/zk/receipts/{vote_scope_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/zk/receipts/{vote_scope_id}/publish-pending` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/roots/{vote_scope_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/roots/{vote_scope_id}/members` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/zk/roots/{vote_scope_id}/publish` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/scopes/{vote_scope_id}/status` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/status` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/zk/verify` | explicit | 10 per 1 minute |
| POST | `/api/v1/zk/vote` | explicit | 20 per 1 minute |
| POST | `/api/v2/identity/key-check` | explicit | 30 per 1 minute |
| POST | `/api/v2/identity/rotate-key` | explicit | 10 per 1 minute |
| POST | `/api/v2/identity/verify` | dedicated-redis | Uses the same atomic HLR Redis guard as v1 registration. |
| GET | `/health` | cheap-exempt | Static module manifest and process liveness; no database or provider access. |
| GET | `/robots.txt` | cheap-exempt | Constant crawler policy; no database or provider access. |
<!-- route-policy:end -->

## Local acceptance evidence (2026-10-30, B01 fix round)

Focused API regressions, development route coverage, documentation gates and one
full UTC API run are recorded below after execution. Logs are local artifacts;
this is source/HTTP acceptance, not deployment verification.

The local interpreter is Python 3.11.5, with FastAPI 0.143.0 from
`/private/tmp/eka32-framework` (the project declares 0.143.3), Starlette 1.10.0,
SlowAPI 0.1.10, limits 5.8.0, Redis client 8.1.0, pytest 9.1.1, Pydantic 2.14.1
and SQLAlchemy 2.1.5. No project dependency files were changed; the exact declared
framework remains a CI release check. Real-Redis integration gates require `REDIS_URL` and a disposable
Redis service. Local fault injection exercises actual limiter routes, outage
fallback, cardinality, recovery and pre-work enforcement; it is not a claim of
passing unavailable external Redis integration.

Focused and documentation checks completed before the full API run:

```text
focused API: 444 passed, 3 skipped, 1 warning in 154.84s (0:02:34)
follow-up (representation alias, metadata, API wiki): 143 passed, 12 xfailed, 1 warning in 51.67s
development policy: 18 passed, 1 warning in 8.06s
Python docs: Ran 391 tests in 31.958s; OK (skipped=2)
Node docs: tests 130; pass 129; fail 0; skipped 1
sitemap ok
CSP inventory: current
project facts ok: api_endpoints 197 (source decorators); registered method/path entries 200
```

The three skipped API gates require external Redis; the two Python docs skips
require a browser installation. Node's skipped CSP browser case also requires its browser dependency.

Commands, with the local cached interpreter and FastAPI overlay described above:

```sh
# apps/api
TZ=UTC python -m pytest tests/test_b01_work_bounds.py tests/test_rate_limit_coverage.py tests/test_rate_limit_route_enforcement.py tests/test_rate_limit_middleware.py tests/test_rate_limit_acceptance.py tests/test_rate_limit_privacy.py tests/test_analytics_representation.py tests/test_public_small_cell_results.py tests/routers/test_export_results.py tests/routers/test_zk_verify_api.py tests/test_vaa.py tests/test_ip_utils.py tests/test_identity_hlr_cost_guard.py tests/test_notify_register.py tests/test_security_headers.py -q --tb=short -rs
TZ=UTC python -m pytest tests/test_b01_work_bounds.py tests/test_rate_limit_coverage.py tests/test_analytics_representation.py tests/test_wiki_api_reference.py tests/test_alpha_modules.py -q --tb=short
ENVIRONMENT=development TZ=UTC python -m pytest tests/test_rate_limit_coverage.py -q --tb=short
TZ=UTC python -m pytest tests/ -q --tb=short -rs
# scripts/redesign
python -m unittest discover -p 'test_*.py' -v
# repository root (working-tree flag preserves the no-commit requirement)
node scripts/public-seo.mjs --update --working-tree
node --test scripts/public-seo.check.mjs scripts/static-docs-remote-sinks.check.mjs scripts/redesign/community_payment_status.check.mjs scripts/csp-observe.check.mjs scripts/csp-docs.check.mjs
python scripts/csp-inventory.py --check
python scripts/project_facts.py --check
```

Single full UTC API run (no repeat):

```text
2 failed, 4348 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 799.44s (0:13:19)
```

Both failures were old unlimited-read expectations in
`test_signed_write_limits.py` and `test_targeted_write_limits.py`. They now
verify independent write/read budgets, 20 shared heavy reads, 120 shared
ordinary reads, pre-DB rejection and exempt app-version checks. No production
API changes were needed after the full run. The affected modules, final policy
(including all 61 preserved admin-authentication assertions) and mobile API
budget were then rerun:

```text
36 passed, 1 warning in 32.61s
```

The final mobile poll interval also passed three direct Node checks against the
actual TypeScript helper and screen wiring, plus its API HTTP budget regression:

```text
Node mobile budget: tests 3; pass 3; fail 0
API mobile budget: 1 passed, 1 warning in 3.01s
```

The corresponding budget test is included in the existing mobile Vitest file
for CI; the local checkout has no mobile `node_modules`, so the complete mobile
Vitest suite was not run. The API runtime was unchanged during these final
corrections. Both full-run failures are resolved by the focused rerun; the
original full-run tail above is retained without claiming a second green full run.

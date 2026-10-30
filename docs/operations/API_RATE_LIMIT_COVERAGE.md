# API rate-limit policy and acceptance — EKA-32 / B01

Reviewed 2026-10-30 for PR #706 / the B01 fix round. Every registered route
requires an explicit class; new public reads, admin routes, methods and exemptions
fail the coverage gate until classified. The audit checks actual wrappers on lazy
included routers and enforcement before representative/admin authentication.
Only three constant-cost endpoints are exempt; each has a one-line reason in the
policy table and an HTTP test forbidding database and provider access.

## Policy classes

| Class | Count | Policy |
| --- | ---: | --- |
| `client-flow` | 26 | 1200/minute/IP across core released-client requests; scope polling has an independent 1200/minute/IP bucket. Action sanity caps below still apply. |
| `public-read` | 17 | 120/minute/IP across other ordinary reads. |
| `public-heavy` | 97 | 20/minute/IP across optional analytics, exports, ranking/compare, admin work and provider callbacks. |
| `generate` | 5 | 5/minute/IP shared plus 30/minute globally across generation-capable routes. |
| `paypal-verify` | 1 | 10/minute/IP plus 60/minute globally; four verification slots/process. |
| `explicit` | 46 | Existing signed/action/polling policies outside the core client inventory. |
| `dedicated-redis` | 5 | Existing HLR, key generation, newsletter and contact counters. |
| `cheap-exempt` | 3 | Greeting, health manifest and robots; no DB or provider access. |

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

Released-client routes share **1200/minute/IP** (`client-flow`). Scope status
uses the independent **1200/minute/IP** `client-poll` scope within that class,
so 50 users polling every five seconds consume 600/minute without starving feeds,
proof members, results or startup. Both buckets include room for immediate polls
and startup bursts. Route IDs and query changes cannot reset either bucket.
Outage quotas are 600/minute/process in each bucket. SSR calls to these same
routes consume the same quota. Core routes never consume `public-heavy`.

Existing per-action sanity caps remain: signed Tier-1 votes 120/minute/IP,
corrections and consensus scores 20/minute/IP each, ZK vote acceptance 20/minute/IP,
and proof verification 10/minute/IP. These protect writes/cryptography rather
than public reads. Push registration retains 600/IP/hour and 20 changed
registrations/identity/day; same-value refreshes are idempotent. Signed status
reads, identity status, opt-in and eligible key rotation use client-flow capacity.
HLR enrollment remains a separate paid-provider action with its atomic guards.
QR polling keeps 30/minute/session and 600/minute/IP; it is a browser flow.

The mobile code in this PR is byte-for-byte unchanged from `origin/main`.
The installed 1.0.33–1.0.37 behaviour is the compatibility contract: pending
scope status polls immediately and every **5 seconds**. Scope status caches
counts/root readiness for at most five seconds, coalesces concurrent fills and
bounds the cache to 128 entries/process. Visibility is checked on every hit and
rollout flags/allowlists participate in the key. Other workers can retain an old
snapshot for five seconds; combined with the released five-second poll interval,
readiness can take up to ten seconds to appear without local invalidation.
Results cache vote totals for five seconds/128 entries, keyed by bill, vote
sources and privacy policy; visibility and suppression still run on every request.
Successful vote/root/opt-in commits invalidate both local caches through the
existing shared commit hook. Other workers observe changes within the TTL.
Proof members retain the existing cache by published root and stale-root checks.

### Released client-flow inventory

Source: `origin/main` at `30e20e6c7618cdca0c3c9e4f4c197c4d1320f9c3`, the
requested released 1.0.33–1.0.37 behaviour. Frequencies below are observed from
that source's effects, focus hooks and timers, not estimated user activity.
Paths in the source column are under `apps/mobile/src/` (screens unless stated).
The JSON fixture is `apps/api/tests/fixtures/released_mobile_client_flow.json`;
a test checks every row's actual registered class and this documentation table.
Compatibility aliases with no observed caller are marked explicitly.

<!-- client-flow:start -->
| Method | Route | Observed frequency per user | Released source |
| --- | --- | --- | --- |
| GET | `/api/v1/app/version` | 2-3/startup (Home, banner, eligible rotation); manual profile check | `HomeScreen.tsx:51; components/UpdateBanner.tsx:31; lib/key-rotation.ts:116` |
| GET | `/api/v1/version` | Legacy alias; no call in this snapshot | `server compatibility alias` |
| GET | `/api/v1/analytics/overview` | 1/Home mount | `HomeScreen.tsx:41` |
| GET | `/api/v1/bills` | 2/ALL first page or refocus; 1/page/filter; F-Droid +1/foreground at most 1/min | `BillsScreen.tsx:142-155; lib/notifications.ts:304` |
| GET | `/api/v1/bills/trending` | 1/Trending mount or refresh | `TrendingScreen.tsx:20` |
| GET | `/api/v1/bills/{bill_id}` | 1/vote detail mount | `VoteScreen.tsx:132` |
| POST | `/api/v1/vote/{bill_id}/status` | 1/vote detail mount with a verified identity; signed POST | `VoteScreen.tsx:163` |
| POST | `/api/v1/vote` | 1/confirmed vote | `lib/api.ts:358` |
| PUT | `/api/v1/vote/{bill_id}/correct` | 1/confirmed correction | `lib/api.ts:375` |
| POST | `/api/v1/vote/{bill_id}/consensus` | 1/confirmed DIAVGEIA score | `VoteScreen.tsx:783` |
| GET | `/api/v1/vote/{bill_id}/results` | 1/results focus or refresh | `ResultScreen.tsx:67-77` |
| GET | `/api/v1/consensus/representation` | 1/DIAVGEIA results focus or refresh | `DiavgeiaResultsScreen.tsx:48-67` |
| GET | `/api/v1/zk/status` | 1/vote detail or ZK screen mount | `VoteScreen.tsx:176; ZkSemaphoreScreen.tsx:74` |
| GET | `/api/v1/zk/scopes/{vote_scope_id}/status` | 1/detail + 1/opt-in completion + immediate pending poll, then every 5 s (12/min/user) | `VoteScreen.tsx:190,232,465-473` |
| GET | `/api/v1/zk/roots/{vote_scope_id}` | Compatibility root read; helper defined, proof path uses members | `lib/api.ts:291-296` |
| GET | `/api/v1/zk/roots/{vote_scope_id}/members` | 1/proof creation; verify and submit each create a proof | `lib/zkCanaryFlow.ts:64` |
| POST | `/api/v1/zk/opt-in` | 1/confirmed opt-in | `lib/api.ts:266` |
| POST | `/api/v1/zk/verify` | 1/explicit proof verification | `lib/api.ts:310` |
| POST | `/api/v1/zk/vote` | 1/confirmed ZK vote | `lib/api.ts:333` |
| POST | `/api/v1/identity/status` | 1/profile mount when verified | `ProfileScreen.tsx:62` |
| POST | `/api/v2/identity/rotate-key` | 1/eligible legacy startup; foreground retries at least 60 s apart | `lib/key-rotation.ts:192,227` |
| GET | `/api/v1/periferia` | 1/onboarding or profile mount | `OnboardingScreen.tsx:38; ProfileScreen.tsx:44` |
| GET | `/api/v1/periferia/{periferia_id}/dimos` | 1/selected region change | `OnboardingScreen.tsx:44; ProfileScreen.tsx:95` |
| POST | `/api/v1/notify/register` | 1/verified Home mount on push builds; at most 1 idempotent retry | `HomeScreen.tsx:43; lib/push-registration.ts:167` |
| GET | `/api/v1/notifications/status` | Compatibility status read; notifications acknowledge locally, no HTTP ACK | `lib/notifications.ts:markNotificationEventRead` |
| GET | `/api/v1/polis/tickets` | 1/POLIS tab mount, category change or refresh | `TicketsScreen.tsx:77` |
<!-- client-flow:end -->

Analytics overview is automatic on Home mount, so it is client-flow despite its
name. Optional MP ranking is fetched when the user opens the MP tab; compare,
additional analytics and exports remain public-heavy. Optional politician
questions/scores/evaluations and POLIS ticket writes retain their existing
policies; none is part of startup → bills → vote/results → bills. Account
verification (HLR), explicit profile location changes, share tracking and QR
browser login retain their dedicated action guards. Notification reads and
acknowledgements are local; the F-Droid foreground fallback reads `/bills` at
most once/minute and push builds register on verified Home mount.

The HTTP compatibility test uses the real included routes and enabled production
limiter with deterministic time and local DB/Redis/provider fixtures. It replays
startup, both first-page bills queries, detail, valid signed vote-status reads,
ZK status, encoded scope status, proof members, results and both return-to-bills
queries. **10 and 50 users behind one IP for five minutes** each get zero 429s,
including immediate and five-second polls and a core session every minute.
Three complete startup/core sessions also succeed (the reported 21-read case).
The same test exhausts public-heavy at 20 calls, verifies the next heavy route
returns 429, and checks that results and scope status still succeed.

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

200 method/path entries: client-flow 26, public-read 17, public-heavy 97, generate 5, paypal-verify 1, explicit 46, dedicated-redis 5, cheap-exempt 3.

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
| GET | `/api/v1/analytics/overview` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/analytics/representation` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/top-divergence` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/analytics/votes-timeline` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/app/version` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/arweave/bill/{bill_id}` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/arweave/status` | explicit | 30 per 1 minute |
| GET | `/api/v1/auth/govgr/callback` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/family/verify` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/auth/govgr/info` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/auth/govgr/login` | explicit | 10 per 1 minute |
| GET | `/api/v1/auth/govgr/status` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/bills` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/bills/admin/create` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/bills/sources/freshness` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/bills/trending` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/bills/{bill_id}` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/bills/{bill_id}/flag` | explicit | 120 per 1 minute (bill-flag) |
| GET | `/api/v1/bills/{bill_id}/summary` | generate | 5 per 1 minute (generate); 30 per 1 minute (generate-global) |
| POST | `/api/v1/bills/{bill_id}/transition` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/claude/budget` | public-read | 120 per 1 minute (public-read) |
| GET | `/api/v1/consensus/representation` | client-flow | 1200 per 1 minute (client-flow) |
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
| POST | `/api/v1/identity/status` | client-flow | 1200 per 1 minute (client-flow) |
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
| GET | `/api/v1/notifications/status` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/notifications/stream` | explicit | 30 per 1 minute |
| POST | `/api/v1/notifications/test/publish` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/notify/register` | client-flow | 1200 per 1 minute (client-flow) |
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
| GET | `/api/v1/periferia` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/periferia/{periferia_id}/dimos` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/polis/qr-auth` | explicit | 10 per 1 minute |
| POST | `/api/v1/polis/qr-consensus` | explicit | 20 per 1 minute |
| GET | `/api/v1/polis/qr-session` | explicit | 10 per 1 minute |
| GET | `/api/v1/polis/qr-session/{session_id}` | explicit | 600 per 1 minute (polis_qr:poll_qr_session) |
| POST | `/api/v1/polis/qr-vote` | explicit | 20 per 1 minute |
| POST | `/api/v1/polis/register-key` | explicit | 120 per 1 minute |
| GET | `/api/v1/polis/tickets` | client-flow | 1200 per 1 minute (client-flow) |
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
| GET | `/api/v1/version` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/vote` | client-flow | 120 per 1 minute; 1200 per 1 minute (client-flow) |
| GET | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| POST | `/api/v1/vote/compass/personal` | explicit | 10 per 1 minute |
| GET | `/api/v1/vote/results/in-progress` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/vote/results/latest` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/vote/{bill_id}/consensus` | client-flow | 20 per 1 minute (voting:submit_consensus); 1200 per 1 minute (client-flow) |
| PUT | `/api/v1/vote/{bill_id}/correct` | client-flow | 20 per 1 minute (voting:correct_vote); 1200 per 1 minute (client-flow) |
| GET | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute (voting:get_vote_receipt_deprecated) |
| POST | `/api/v1/vote/{bill_id}/receipt` | explicit | 10 per 1 minute (voting:post_vote_receipt) |
| POST | `/api/v1/vote/{bill_id}/relevance` | explicit | 30 per 1 minute (voting:vote_relevance) |
| GET | `/api/v1/vote/{bill_id}/results` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/vote/{bill_id}/status` | explicit | 10 per 1 minute (voting:get_vote_status) |
| POST | `/api/v1/vote/{bill_id}/status` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/zk/canary/preflight/{vote_scope_id}` | public-read | 120 per 1 minute (public-read) |
| POST | `/api/v1/zk/opt-in` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/zk/receipts/{vote_scope_id}` | public-heavy | 20 per 1 minute (public-heavy) |
| POST | `/api/v1/zk/receipts/{vote_scope_id}/publish-pending` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/roots/{vote_scope_id}` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/zk/roots/{vote_scope_id}/members` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/zk/roots/{vote_scope_id}/publish` | public-heavy | 20 per 1 minute (public-heavy) |
| GET | `/api/v1/zk/scopes/{vote_scope_id}/status` | client-flow | 1200 per 1 minute (client-poll) |
| GET | `/api/v1/zk/status` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/zk/verify` | client-flow | 10 per 1 minute; 1200 per 1 minute (client-flow) |
| POST | `/api/v1/zk/vote` | client-flow | 20 per 1 minute; 1200 per 1 minute (client-flow) |
| POST | `/api/v2/identity/key-check` | explicit | 30 per 1 minute |
| POST | `/api/v2/identity/rotate-key` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v2/identity/verify` | dedicated-redis | Uses the same atomic HLR Redis guard as v1 registration. |
| GET | `/health` | cheap-exempt | Static module manifest and process liveness; no database or provider access. |
| GET | `/robots.txt` | cheap-exempt | Constant crawler policy; no database or provider access. |
<!-- route-policy:end -->

## Local acceptance evidence (2026-10-30, B01 round 2)

Compatibility checks use the released source patterns and enabled production
limiter. Ten and fifty users each complete a five-minute simulation behind one
IP, polling every five seconds; all client-flow requests succeed. The three
startup → bills → vote/results → bills sessions succeed too. These are HTTP
checks with deterministic clocks and local DB/Redis/provider fixtures, not a
production throughput benchmark.

The interpreter is the existing `scratchpad/venv-fa/bin/python` (Python 3.11.5),
with `PYTHONPATH=/private/tmp/eka32-framework` (FastAPI 0.143.0; the project
requires 0.143.3), Starlette 1.10.0, SlowAPI 0.1.10, limits 5.8.0, pytest 9.1.1,
Pydantic 2.14.1 and SQLAlchemy 2.1.5. Dependency files are unchanged. External
Redis/PostgreSQL gates require their configured test services.

From `apps/api`, focused checks cover released compatibility, route coverage,
request work bounds, 429/CORS/outage acceptance, signed and targeted writes,
result privacy, ZK routes, notification registration, proxies and security
headers. The full API suite runs once with `TZ=UTC` after focused checks.

```sh
TZ=UTC PYTHONPATH=/private/tmp/eka32-framework ../../../venv-fa/bin/python -m pytest tests/test_released_mobile_client_flow.py tests/test_rate_limit_coverage.py tests/test_b01_work_bounds.py tests/test_rate_limit_acceptance.py tests/test_rate_limit_route_enforcement.py tests/test_targeted_write_limits.py tests/test_signed_write_limits.py tests/test_public_small_cell_results.py tests/test_voting_latest_results.py tests/test_zk*.py -q --tb=short
TZ=UTC PYTHONPATH=/private/tmp/eka32-framework ../../../venv-fa/bin/python -m pytest tests/test_rate_limit_middleware.py tests/test_rate_limit_privacy.py tests/test_ip_utils.py tests/test_notify_register.py tests/test_security_headers.py -q --tb=short
TZ=UTC PYTHONPATH=/private/tmp/eka32-framework ../../../venv-fa/bin/python -m pytest tests/ -q --tb=short -rs
```

Results (local log files use `/private/tmp/b01-r2-*.log`):

```text
Released compatibility, final: 34 passed in 180.00s (0:02:59)
Initial broad focused run: 3 failed, 250 passed, 1 warning in 597.00s (0:09:56)
Three focused corrections: 3 passed, 1 warning in 9.28s
Additional focused checks: 110 passed, 3 skipped, 1 warning in 8.30s
Production policy / wiki / fallback: 26 passed, 1 warning in 12.53s
Development policy: 16 passed, 1 warning in 7.74s
Full API, TZ=UTC, one run: 1 failed, 4371 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 1064.20s (0:17:44)
Identity rotation after assertion correction: 22 passed in 3.01s
Static documentation: 82 passed; zero failures
CSP inventory current; project facts current; git diff --check passed
```

The initial focused run exposed three test defects: a direct decorated call
without a Request, an audit expecting only one wrapper on a stacked policy,
and a missing URL in a fallback test. All three were corrected and passed.
The full run's sole failure was an old assertion that rotation still had the
10/minute IP limit. It now asserts 1200/minute with the `client-flow` scope;
all 22 identity-rotation tests pass. No production code changed after the full
run, and the full suite was not repeated. The 95 skips are listed in the full
log (external Redis/PostgreSQL gates); the 25 expected failures remain expected.
The API wiki source hash was refreshed after its policy text changed; all 82
static documentation tests pass. Mobile files match `origin/main`; HEAD remains
`a5f34964` and no commit was created.

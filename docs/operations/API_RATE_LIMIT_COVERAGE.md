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
| `client-flow` | 32 | 1200/minute/IP across core released-client requests; scope polling has an independent 1200/minute/IP bucket. Action sanity caps below still apply. |
| `public-read` | 17 | 120/minute/IP across other ordinary reads. |
| `public-heavy` | 93 | 20/minute/IP across optional analytics, exports, compare, additional analytics, admin work and provider callbacks. |
| `generate` | 5 | 5/minute/IP shared plus 30/minute globally across generation-capable routes. |
| `paypal-verify` | 1 | 10/minute/IP plus 60/minute globally; four verification slots/process. |
| `explicit` | 44 | Existing signed/action/polling policies outside the core client inventory. |
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
  and depth. Concurrent fills coalesce; Poseidon uses one dedicated 16-thread
  executor with completion-held submission permits shared across event loops.
  True CPU saturation after ten seconds returns 503 with `Retry-After: 1`.
  Membership changes still return
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
counts/root readiness with five-second freshness, coalesces concurrent fills and
bounds the cache to 128 entries/process. Visibility is checked on every hit and
rollout flags/allowlists participate in the key. Expired snapshots serve while
refreshing; readiness appears on a subsequent released five-second poll after
the refresh finishes. Failed refreshes preserve the last good snapshot only
until 30 seconds beyond its fresh TTL; older snapshots require a fresh read.
Results cache vote totals with five-second freshness/128 entries, keyed by bill, vote
sources and privacy policy; visibility and suppression still run on every request.
Successful vote/root/opt-in commits invalidate all local public caches through the
existing shared commit hook. Other workers refresh expired values in the background.
Proof members retain the existing cache by published root and stale-root checks.

### Released client-flow inventory

Source: `origin/main` at `7bef83431635042f3c01241840ab6cefac12b817`, the
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
| GET | `/api/v1/mp/ranking` | 1/MP mount (parties tab) | `apps/mobile/src/lib/api.ts:541` |
| GET | `/api/v1/politicians/` | 1/MP politicians tab activation | `apps/mobile/src/lib/api.ts:585` |
| GET | `/api/v1/politicians/my-evaluations/bulk` | 1/verified MP politicians tab activation; signed personal read | `apps/mobile/src/lib/api.ts:679` |
| GET | `/api/v1/politicians/{ada_number}/my-evaluation` | 1/verified politician detail mount; signed personal read | `apps/mobile/src/lib/api.ts:664` |
| GET | `/api/v1/politicians/{ada_number}/questions` | 1/politician detail mount | `apps/mobile/src/lib/api.ts:590` |
| GET | `/api/v1/politicians/{ada_number}/scores` | 1/politician detail mount; 1/confirmed evaluation refresh | `apps/mobile/src/lib/api.ts:622` |
<!-- client-flow:end -->

The released inventory is derived mechanically by
`scripts/released_mobile_inventory.py` from all production TS/TSX files under
`apps/mobile/src` in the working tree, including request helpers and direct fetches.
The inventory does not require Git refs in shallow CI checkouts. A separate test
compares `apps/mobile` against the merge base with `origin/main` when available;
only that change check skips when the ref or merge base is unavailable.
The fixture pins all **45 call sites / 38 HTTP patterns** with source lines.
The test regenerates that evidence, resolves every pattern against registered
routes, requires client-flow/polling for every automatic read, and fails on
missing, changed or unclassified calls. Compatibility aliases remain explicit.

MP mounts fetch party ranking. Activating politicians fetches the public list
and, for verified users, a signed personal evaluation summary. Politician detail
mounts fetch questions, public scores and a signed personal evaluation read.
All six reads use client-flow. Personal reads retain signature verification and
`private, no-store`; shared caches never contain their data or identity keys.

Eight explicit actions retain their action/provider guards: HLR enrollment,
profile location update, QR authorization, POLIS key registration, ticket
creation, ticket voting, evaluation submission and share tracking. Their exact
methods, paths and justifications are recorded in `justified_actions` in the
fixture. No automatic GET has an action exemption.

The HTTP compatibility test replays startup, both bills queries, trending,
consensus, detail, signed vote status, roots/members, results, return-to-bills
and MP → politicians → detail (including valid signed personal reads).
**10 and 50 users behind one IP for five minutes**, polling every five seconds
and repeating navigation every minute, get zero 429s. Public-heavy still exhausts
at 20 calls; its next call returns 429 while released reads continue to succeed.
These deterministic HTTP checks use local DB/Redis/provider fixtures and are
not a production throughput benchmark.

### Public cache work policy

Every client-flow/polling GET must either use a bounded public single-flight
cache or have a reviewed constant/point/private-read classification. A new
client read fails the policy test until reviewed. Existing results/scope/root
member caches retain their per-request visibility or stale-root checks.

New public caches cover overview, MP ranking, politician list/questions/scores,
bills/trending, consensus representation, region/municipality lists and tickets.
Results also cache regional population aggregates.
Caches for suppression-dependent result bodies operate only while
`PUBLIC_RESULTS_MIN_COUNT=0`, the current production setting.
Small-cell suppression is OFF in production; enabling it
requires the separate owner decision in #661.

With `PUBLIC_RESULTS_MIN_COUNT > 0`, suppression-dependent response bodies bypass
shared result cache reads and writes. Overview/window totals, analytics timelines
and divergence, per-bill results, consensus/representation, CPLM and MP/party vote
aggregates calculate fresh on every request. Identical concurrent calculations
may share in-flight work; the result/error is removed on completion. Rate limits
remain the protection. CPLM history returns no cached snapshots while suppression
is enabled because historical suppression inputs cannot be reconstructed safely.

The threshold is read at request time. A change purges affected process caches
and immediately retires Redis namespaces; each Redis cache family deletes its
old variants on its next access, retrying deletion after outages. A new namespace
also prevents an older in-flight write or failed deletion from restoring a stale
body when suppression is disabled again. Responses recheck the policy after work
and rebuild if it changed. Visibility/contributor revalidation remains mandatory
with suppression disabled. The cache freshness and stale-serving rules below
describe the `k=0` path; they never authorize cached suppressed bodies.

Follow-up before enabling #661: design and review proper suppression-aware
caching, including daily/window partitions and all source/derived suppression
inputs, runtime policy changes and racing fills. Until then, retain the fresh
calculation rule for every suppression-dependent body.

With suppression disabled, each public client cache is bounded to 128
entries/process with five-second freshness anchored before
work; hits do not renew it. Expired entries retain the last good value and serve
immediately while one background refresh runs with its own database session,
only until a hard stale deadline. Vote/status, eligibility-sensitive politician
reads, results/totals (including overview, ranking and consensus representation)
allow at most 30 seconds beyond freshness; other public aggregates allow ten
minutes. Beyond that deadline requests await fresh computation for at most ten
seconds and never return the old body. An unavailable fresh computation propagates
its error; an expired read exceeding that wait returns 504. Refresh failures never
extend the deadline. Fresh eligibility/visibility guards run before serving hits;
403/404/410 denials invalidate cached bodies immediately and fence off older
in-flight fills. Keys include every declared path/query argument
(including defaults), the visibility policy version and sensitive-term list,
small-cell threshold and the endpoint's anonymity thresholds. Unknown query
fields do not affect handlers and are never retained; request headers, sessions,
nullifiers and signatures are excluded. Only explicitly public endpoints can
use this wrapper. Returned payloads are copied so callers cannot mutate hits.

Concurrent identical misses share one result/error per process/event loop.
Ordinary async reads have 32 execution slots per loop; overview, ranking, consensus
representation and result aggregates use a separate eight-slot pool. Each pool
has a FIFO queue of at most 128 waiters with a ten-second admission deadline.
At the deadline, a cold request computes inline; background refreshes may defer
to the next request. Queue overflow waits out the same deadline without joining
the queue. Followers wait up to ten seconds for the single in-flight result,
then compute inline without cancelling the leader. Async I/O admission never
produces a capacity error. The 128-key single-flight registry also falls back through the pool
when full, without rejecting navigation.

CPU-bound ZK member tree builds use one dedicated 16-thread bounded executor
per process. Every submission, including a single-flight timeout fallback, must
acquire a permit. At most 16 jobs can be submitted and unfinished; no backlog
can accumulate in the executor's internal queue beyond that bound. Permits are
released by the underlying job's completion, even when its request or leader is
cancelled. Admission waits at most ten seconds; true proof/tree CPU saturation
returns 503 with `Retry-After: 1`. This exception applies only to CPU builds.
Other client-flow reads retain the no-cache-generated-429 rule. ZK member hits
still recheck current scope visibility, the published root and current members;
the immutable root validation cache never substitutes older response data.

Framework parameter validation and semantic bill/status/governance/geographic
validation run before any cache lookup, single-flight registration or budget
accounting. Invalid filters return 422. Only per-IP route limits may throttle
client-flow/polling traffic. Public fill budgets are local per-route soft
telemetry (600/minute by default); crossing a budget logs an event and never
rejects a fill. The heavy non-app routes retain their rate limits and hard fill
quotas. Single-flight, queues, stored payloads and soft counters are process-local.

Overview's 50 identical concurrent HTTP reads over 100 completed bills perform
100 bill aggregations and one bill scan, plus nine count SQL calls, in one fill.
Ranking computes each bill's majority once per fill, reused across parties.
The shared representation commit hook clears all local public caches after a
successful commit; evaluation/ticket writes clear them locally too. Failed
commits do not invalidate. Other workers refresh after five seconds and can
serve their last good policy-keyed value only within the route's hard stale window.

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
| Method | Route | Class | Limit / reason |
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
| GET | `/api/v1/mp/ranking` | client-flow | 1200 per 1 minute (client-flow) |
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
| GET | `/api/v1/politicians/` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/politicians/my-evaluations/bulk` | client-flow | 1200 per 1 minute (client-flow) |
| POST | `/api/v1/politicians/{ada_number}/evaluate` | explicit | 20 per 1 minute (evaluation:evaluate_politician) |
| GET | `/api/v1/politicians/{ada_number}/my-evaluation` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/politicians/{ada_number}/questions` | client-flow | 1200 per 1 minute (client-flow) |
| GET | `/api/v1/politicians/{ada_number}/scores` | client-flow | 1200 per 1 minute (client-flow) |
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

## Local acceptance evidence (2026-10-30, B01 round 3)

Compatibility checks replay the released mobile source with the production
limiter enabled and deterministic time. Ten and fifty users each complete
five minutes behind one IP, including MP/politician navigation, signed personal
reads, immediate/five-second polls, and a full navigation session every minute.
Both simulations report zero 429s. The heavy bucket still rejects its 21st call
while released routes continue to succeed.

The existing `scratchpad/venv-fa/bin/python` runs the API checks with
`TZ=UTC PYTHONPATH=/private/tmp/eka32-framework`. The local framework overlay
provides FastAPI 0.143.0 (the project requires 0.143.3). Dependency files and
mobile source are unchanged; external Redis/PostgreSQL gates require their
configured services. These fixture-backed HTTP checks are not a production
throughput benchmark.

From `apps/api`, the work/policy checks are reproducible with:

```sh
TZ=UTC PYTHONPATH=/private/tmp/eka32-framework ../../../venv-fa/bin/python -m pytest tests/test_released_mobile_client_flow.py tests/test_released_mobile_inventory.py tests/test_client_public_work.py tests/test_rate_limit_coverage.py tests/test_b01_work_bounds.py tests/test_rate_limit_route_enforcement.py tests/test_rate_limit_acceptance.py tests/test_signed_write_limits.py -q --tb=short
TZ=UTC PYTHONPATH=/private/tmp/eka32-framework ../../../venv-fa/bin/python -m pytest tests/ -q --tb=short -rs
```

From the repository root, the docs preservation gate is:

```sh
python3 -m unittest discover -s scripts/redesign -p 'test_*.py'
```

Round 3 local logs use `/private/tmp/b01-r3-*.log`:

- `core`: 174 passed (released HTTP/NAT, evaluation integrity/demo exclusion,
  consensus, small-cell privacy and bill contracts).
- `focused`: 224 passed, 3 skipped; four old expectations failed (three moved
  routes still listed as heavy, and one assertion requiring SQL on a cache hit).
- `corrections`: 43 passed, including the updated heavy inventory, source-derived
  route/cache policies, overview/ranking work bounds and regional population cache.
- `signed-correction`: the remaining updated cache-hit expectation passed.
- `docs-final`: 391 tests ran successfully, with 2 skipped.

The full API suite ran once after focused corrections with `TZ=UTC`:

```text
4386 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 1192.48s (0:19:52)
```

The 95 skips include external Redis/PostgreSQL checks without their configured
services. Complete output and skip reasons are in
`/private/tmp/b01-r3-full-api.log`. The final inventory diff, caches, file list
and log tails are recorded in `/private/tmp/b01-r3-final-stdout.txt`.

No production code changed after starting that full run. The existing API wiki
wording is registered through `scripts/redesign/approved_audit_delta.py`; its
HTML is unchanged in round 3. New limits/cache/inventory documentation is kept
in this operations file. No commit was created.

### Round 4 validation

Client-flow caches now use stale-while-revalidate, non-rejecting single-flight,
bounded FIFO worker admission and inline cold fallbacks at the wait deadline.
Semantic bill/geographic validation runs before cache accounting and returns
422 for invalid filters. Public fill budgets only log; the heavy non-app limits
remain in place. Background refreshes own their database sessions, and cache
invalidation separates in-flight generations.

The concurrent HTTP regressions use 20 ms mocked SQL behind one NAT IP:
20 distinct politician detail mounts (40 reads) and 50 localized Bills mounts
(100 reads) all return 200. Additional checks cover concurrent root-member
targets/followers, invalid filters from IP A followed by valid traffic from IP B,
cold bursts beyond cache capacity, FIFO/timeout/overflow behavior, aggregate
isolation, stale refresh failures, session lifetime and racing invalidation.
The released 10/50-user, five-minute polling replays also pass.

The initial focused run exposed three legacy assertions requiring hard fill
throttling or synchronous refreshes; those assertions now enforce the new
contract. Final focused tails (`TZ=UTC`):

```text
b01-r4-focused-final.log: 123 passed, 2 deselected, 2 xfailed, 1 warning in 79.12s (0:01:19)
b01-r4-corrections.log: 123 passed, 2 xfailed, 1 warning in 239.71s (0:03:59)
```

The full API suite ran once after the focused checks, with `TZ=UTC`, using the
same interpreter/framework overlay documented above. No implementation changed
after that full run started:

```text
4398 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 1213.18s (0:20:13)
```

Logs are in `/private/tmp/b01-r4-*.log`; the full output and skip reasons are in
`/private/tmp/b01-r4-full-api.log`. Design and final log tails are in
`/private/tmp/b01-r4-final-stdout.txt`. No commit was created.

### Round 5 validation

Hard stale deadlines now apply in `client_flow_cache`: 30 seconds beyond the
fresh TTL for status/eligibility/results/totals, ten minutes for other public
aggregates. Expired reads await fresh computation with a bounded wait. Fresh
politician/scope/result visibility checks precede hits, and refresh-time
403/404/410 responses invalidate entries and prevent older fills restoring them.

ZK tree builds use a dedicated bounded executor. Sixty cancelled fills leave
eight running jobs in an eight-worker test pool, zero queued jobs and zero
leaked threads after shutdown. Follower timeout fallbacks cannot bypass permits;
only true CPU saturation returns 503 with `Retry-After: 1`.

The mobile inventory scans working-tree source without Git refs. The separate
mobile change assertion uses a merge base only when available. Mobile source
remains unchanged. Focused tails (`TZ=UTC`, same local framework overlay):

```text
b01-r5-freshness.log: 13 passed in 5.43s
b01-r5-executor.log: 2 passed in 3.94s
b01-r5-inventory.log: 6 passed in 6.26s
b01-r5-focused.log: 240 passed, 1 warning in 372.82s (0:06:12)
b01-r5-post-full-corrections.log: 102 passed, 4 deselected in 12.38s
```

The full API suite ran once with `TZ=UTC`:

```text
5 failed, 4410 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 1181.49s (0:19:41)
```

Four failures exposed a redundant cold scope-status visibility lookup. The
correction preserves the per-request guard and checks background refreshes in
their own session. The fifth was a source-inspection artifact: after the running
process loaded the old file positions, the corrected file made inspection read
the preceding receipt handler instead of the root handler. All five cases pass
against the final files, without relaxing assertions or repeating the full suite:

```text
b01-r5-full-failures-recheck.log: 5 passed in 1.60s
```

The 95 skips cover unconfigured external PostgreSQL/Redis and optional service
checks. Complete output is in `/private/tmp/b01-r5-full-api.log`; per-item tails
are in `/private/tmp/b01-r5-final-stdout.txt`. No commit was created.

### Round 10 validation

Suppression-dependent bodies now bypass shared result cache reads and writes
when `PUBLIC_RESULTS_MIN_COUNT > 0`, retaining only concurrent in-flight
coalescing. Request-time policy changes purge local entries, retire Redis
namespaces, delete old variants on access and fence racing fills/writes.
The existing visibility/contributor guards and `k=0` caching remain in place.

The reproduced two-day 10/10/10/10 scenario corrects yesterday's YES to NO
and today's NO to YES without invalidation. All-time inputs stay unchanged;
the next `k=10` overview correctly withholds `today` and marks it suppressed.
Regressions also cover per-bill corrections, runtime toggles in both directions,
failed purges, late writes, shared-cache inventory guards, concurrent coalescing
and absence of completed-result reuse. Production suppression remains OFF;
proper suppression-aware caching is a follow-up before enabling #661.

API checks used `TZ=UTC` and the interpreter/framework overlay documented above.
The broader focused run had 475 passes and one old expectation requiring bill-list
cache hits with `k=10`. That test now checks the bypass and resumes cache-key/expiry
checks with `k=0`; the correction and final policy checks passed:

```text
b01-r10-focused-corrections.log: 79 passed in 18.52s
b01-r10-final-policy.log: 37 passed in 11.12s
b01-r10-docs.log: Ran 391 tests in 15.075s; OK (skipped=2)
```

The full API suite ran once after focused checks. No implementation changed
after that run started:

```text
4552 passed, 95 skipped, 25 xfailed, 21 warnings, 4 subtests passed in 1078.48s (0:17:58)
```

Full output and skip reasons are in `/private/tmp/b01-r10-api-full.log`;
final log tails are in `/private/tmp/b01-r10-final-stdout.txt`.
No commit was created.

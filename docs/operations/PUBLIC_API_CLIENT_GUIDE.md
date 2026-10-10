# Public API client guide

Use `/api/v1/public` for public data reads. An optional `X-API-Key` increases
one shared request budget; it does not authenticate an administrator, establish
a user session, or grant JWT-based access. Use HTTPS and send keys only in this
header, never in URLs, logs, screenshots, or copied command histories.

## Shared public-read budget

The following reads declare `Depends(rate_limit_check)` and share one counter.
Prefix these paths with `/api/v1/public`:

- `/bills`
- `/bills/{bill_id}/results`
- `/stats`
- `/vaa/parties`
- `/cplm`
- `/cplm/history`
- `/representation`

| Counter | Scope | Source budget |
|---|---|---|
| Public read dependency | All participating endpoints combined, by anonymous IP bucket or valid key | Anonymous: 100; valid key: 1000 per 60 seconds |

In the current route wiring, these reads are excluded from SlowAPI's default
60/minute limit. There is no additional 60/IP/endpoint ceiling on these reads.
The SlowAPI default still covers other default-covered routes, such as `/health`;
it must not be transferred to the participating public reads. This does not
establish the middleware behavior of every public or key-management route.
The IP subject is proxy-aware and stored as a daily HMAC bucket, not a raw IP.
A missing or invalid key on these reads uses the anonymous shared budget, not
a fresh budget for each arbitrary key value.

With fresh, active counters and no window expiry during the sequence:

- A valid-key client can make 61 `/vaa/parties` reads plus 61 `/cplm` reads:
  all 122 requests return HTTP 200 with successful data fixtures and remain
  below the shared 1000 budget, including each endpoint's 61st request.
- For one valid-key bucket, request 1000 is allowed and request 1001 returns 429.
- An anonymous client can make 60 parties plus 40 CPLM reads; the next CPLM
  read exceeds the shared 100 budget. There is no separate 60 ceiling here.

These are synthetic counter examples, not a production throughput guarantee.
Other participating reads, shared IPs, and shared keys can consume capacity;
anonymously, 100 is the combined ceiling, not 100 for each endpoint. Keep traffic
comfortably below the applicable shared budget.

## Credentials and advertised budgets

`GET /api/v1/public/info` lists `rate_limits`; key-generation and key-status
responses contain `rate_limit`. Their 100/1000 values describe the shared public
read budget only, not guaranteed request throughput.
Not every public route installs the read dependency; inspect its source contract.

`GET /api/v1/public/keys/status` without a key reports `authenticated: false`;
an invalid supplied key returns HTTP 401, unlike the anonymous fallback on reads.
`POST /api/v1/public/keys/generate` is a separate key-management write, limited
to five generations per IP per hour by its own counter. It is not a
read retry mechanism. Store the returned key securely; it is shown only once.

## Handling HTTP 429

Treat the HTTP status as authoritative. A rejection from the public read
dependency has this shape; the strings illustrate structure rather than a
general contract for other endpoints:

```json
{"detail": {"error": "Rate limit exceeded", "limit": 100, "window": "60s", "tip": "POST /api/v1/public/keys/generate for 1000 req/min"}}
```

The dependency's `limit` is 100 or 1000. Key generation itself can return a 429
with string `detail`. SlowAPI rejections on other default-covered routes have a
different JSON shape; they are not a second guard on the participating reads.
Do not assume a public read rejection supplies `Retry-After` or a reset time.
Cache suitable public responses, coalesce duplicate reads, and use bounded
backoff with jitter and a maximum retry count/time. Stop or defer work when that
budget is exhausted. Never rotate keys, IPs, proxies, or forwarding headers to
evade limits, and do not automatically repeat key-generation POST requests.

## Deployment scope and source

This guide describes current source wiring and owner/CI synthetic validation
using FastAPI 0.142.2, not production or real-Redis verification. Synthetic
fixtures cover the 61/122 valid-key sequence, anonymous 100/101 boundary, and
valid-key 1000/1001 shared boundary. Revalidate route integration when changing
the FastAPI/SlowAPI toolchain; older cached-toolchain results are not evidence
for the current wiring.
SlowAPI enablement depends on `RATE_LIMIT_ENABLED`; storage selects
`RATE_LIMIT_STORAGE_URI`, then `REDIS_URL`, then memory, with bounded in-memory
fallback enabled. The public dependency uses its own Redis-backed counter.
Storage availability, fallback/worker scope, and trusted-proxy configuration affect
deployment behavior; confirm them with the operator rather than assuming capacity.

Sources: [middleware wiring](../../apps/api/main.py),
[SlowAPI configuration](../../apps/api/rate_limit.py),
[public routes and key handling](../../apps/api/routers/public_api.py), and
[IP subjects and fixed-window helper](../../apps/api/ip_utils.py).
Existing [middleware regressions](../../apps/api/tests/test_rate_limit_middleware.py)
cover wiring, the default endpoint ceiling on default-covered routes, and bounded
fallback; that ceiling is not the public dependency's shared quota.

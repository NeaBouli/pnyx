# Public API client guide

Use `/api/v1/public` for public data reads. An optional `X-API-Key` increases
one shared request budget; it does not authenticate an administrator, establish
a user session, or grant JWT-based access. Use HTTPS and send keys only in this
header, never in URLs, logs, screenshots, or copied command histories.

## Two independent limits

Reads using `Depends(rate_limit_check)`, including `/vaa/parties` and `/cplm`,
must pass both layers below. Prefix these paths with `/api/v1/public`.

| Layer | Scope | Source default |
|---|---|---|
| SlowAPI middleware | Client IP and endpoint, independent of API key | 60 requests per minute |
| Public read dependency | All participating endpoints combined, by anonymous IP bucket or valid key | Anonymous: 100; valid key: 1000 per 60 seconds |

The middleware runs before the public read dependency. A middleware rejection
does not reach the dependency or the endpoint's data work. A valid key cannot
bypass the per-IP, per-endpoint ceiling; callers sharing an IP share that ceiling.
The IP subject is proxy-aware and stored as a daily HMAC bucket, not a raw IP.
A missing or invalid key on these reads uses the anonymous shared budget, not
a fresh budget for each arbitrary key value.

With fresh, active counters and no window expiry during the sequence:

- A valid-key client can make 60 `/vaa/parties` reads plus 60 `/cplm` reads:
  120 total is below the shared 1000 budget and each endpoint remains at 60.
- The 61st `/vaa/parties` read from that IP is rejected even with a valid key.
- An anonymous client can make 60 parties plus 40 CPLM reads; the next CPLM
  read exceeds the shared 100 budget while CPLM is still below its own 60 ceiling.

These are counter examples, not a throughput guarantee. The two windows need
not start or reset together. Other requests, shared IPs, and shared keys can
consume capacity; anonymously, 100 is the combined ceiling across participating
reads, not 100 for each endpoint. Keep traffic comfortably below both limits.

## Credentials and advertised budgets

`GET /api/v1/public/info` lists `rate_limits`; key-generation and key-status
responses contain `rate_limit`. Their 100/1000 values describe the shared public
read budget only, not exemption from middleware or guaranteed request throughput.
Not every public route installs the read dependency; inspect its source contract.

`GET /api/v1/public/keys/status` without a key reports `authenticated: false`;
an invalid supplied key returns HTTP 401, unlike the anonymous fallback on reads.
`POST /api/v1/public/keys/generate` is a separate key-management write, limited
to five generations per IP per hour, also subject to middleware. It is not a
read retry mechanism. Store the returned key securely; it is shown only once.

## Handling HTTP 429

Treat the HTTP status as authoritative. The two read-limit layers have different
JSON shapes; the strings below illustrate structure rather than fixed wording:

```json
{"error": "<middleware rate-limit message>"}
```

```json
{"detail": {"error": "Rate limit exceeded", "limit": 100, "window": "60s", "tip": "POST /api/v1/public/keys/generate for 1000 req/min"}}
```

The dependency's `limit` is 100 or 1000. Its key-generation tip does not override
the middleware limit. Key generation itself can return a 429 with string `detail`.
Do not assume either read response supplies `Retry-After` or a common reset time.
Cache suitable public responses, coalesce duplicate reads, and use bounded
backoff with jitter and a maximum retry count/time. Stop or defer work when that
budget is exhausted. Never rotate keys, IPs, proxies, or forwarding headers to
evade limits, and do not automatically repeat key-generation POST requests.

## Deployment scope and source

This guide describes source behavior, not a production or real-Redis verification.
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
cover wiring, the default endpoint ceiling, and bounded fallback.

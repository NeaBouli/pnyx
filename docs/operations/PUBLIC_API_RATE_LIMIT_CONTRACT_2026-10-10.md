# Public API layered quota contract — offline validation

2026-10-10, T-9050; source baseline `c727a3c8`. This follows the
needs-validation item in T-9049. Test/report-only: no limiter, advertisement,
Redis policy, provider, database, proxy or production configuration is changed.

## Question and hypotheses

Public API metadata says `100 req/min` anonymously or `1000 req/min` with a
valid key, while the shared middleware defaults to `60/minute` per endpoint.
The candidate explanations were:

1. Both quotas apply independently: an endpoint's middleware limit can deny a
   request before the public dependency's shared budget is exhausted.
2. Public routes are exempt from the default, leaving only 100/1000 applicable.
3. Disabled limiter settings in most API tests obscure the actual composition.

The narrow check uses the real `main.app`, registered SlowAPI middleware,
public routes, key verification, quota dependency and fixed-window helper.
Only Redis operations, database rows and the CPLM cache are synthetic; an
explicitly enabled in-memory middleware limiter replaces the storage backend.
No lifespan startup, public key generation, external service or live request
is involved.

## Boundaries exercised

| Dummy principal / budget | Real route sequence | Expected composition |
| --- | --- | --- |
| Valid key, empty budget | 60 VAA parties calls, then one more | Default 429 before any additional Redis/DB work |
| Valid key, empty budget | 60 calls per VAA and CPLM route | Separate middleware buckets, shared backend count 120 |
| Anonymous | 60 VAA + 40 CPLM, then CPLM again | Shared public budget 100 denies before the CPLM default is full |
| Invalid key | Anonymous/invalid-key requests share the same sequence | No fresh quota bucket or valid-key budget |
| Valid key, synthetic prior usage 999 | One VAA then one CPLM call | Shared 1000 boundary with only two actual requests |

Spies wrap the real helper rather than replace its decision: valid keys pass
1000 and a 60-second window; anonymous/invalid keys pass 100 and the same
window. Fake Redis models the existing atomic increment/expiry interface,
not an actual Redis/Lua implementation. App state and dependency overrides
are restored by the fixtures.

## Interpretation and scope

**Observed offline:** all five new cases pass with the actual router and
middleware composition. Hypothesis 1 is supported; no public-route exemption
was observed. The explicit enabled memory limiter prevents hypothesis 3 from
silencing the middleware in these tests.

The advertised public budget does not imply 1000 calls to one endpoint. The
default ceiling remains independent and may be reached first. API-facing
documentation should make both dimensions explicit before any promise of a
higher per-route quota. Changing or exempting the middleware is not justified
by this test-only task and remains a separate policy decision.

This is an offline contract check, not a load test, timing exploit, production
measurement, real Redis test or confirmed security vulnerability. Exact-lock
CI and gio-dd cross-review remain required before a head-bound merge. No
deployment or Codex Security scan is authorized.

## Validation evidence

`pytest` over middleware, limiter privacy, client-IP helpers and Admin Bearer
tests: **47 passed, 1 skipped**, 10.89s. The skip requires a real Redis service;
none was exposed. A Starlette/httpx deprecation warning was recorded.
Execution used cached image `4b50ab6021c0`, no network/install/pull, read-only
source/container, non-root, empty explicit synthetic environment and a scratch
tmpfs. Caps were 1 CPU, 512 MiB, 64 processes, 128 file descriptors, 1 MiB
file size, 32 MiB scratch and 90 seconds wall time. Cached FastAPI 0.136.1 /
httpx 0.28.1 / pytest 9.0.3 differ from the lock; exact-head CI is still required.
The fake executes the helper interface, not Redis Lua; production quota,
forwarded-peer attribution and outage behavior are not measured here.

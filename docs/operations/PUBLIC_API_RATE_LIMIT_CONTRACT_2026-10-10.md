# Public API shared quota contract — offline validation

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

The current framework boundary matters: FastAPI 0.142.2 includes the public
router as an `_IncludedRouter` without a direct `endpoint`. SlowAPI 0.1.10's
`_find_route_handler` inspects only top-level routes with that attribute;
`_should_exempt` skips its check when no handler is found. This is an observed
integration effect, not a newly added or intentionally configured exemption.
The existing public dependency still executes and enforces its shared budget.

## Boundaries exercised

| Dummy principal / budget | Real route sequence | Expected composition |
| --- | --- | --- |
| Valid key, empty budget | 60 VAA parties calls, then one more | 61st read returns 200; dependency/helper/DB count 61 |
| Valid key, empty budget | 61 calls per VAA and CPLM route | All reads return 200; one shared backend count 122 |
| Anonymous | 60 VAA + 40 CPLM, then CPLM again | Shared public budget 100 rejects request 101 before data work |
| Invalid key | Anonymous/invalid-key requests share the same sequence | No fresh quota bucket or valid-key budget |
| Valid key, synthetic prior usage 999 | One VAA then one CPLM call | Shared 1000 boundary with only two actual requests |

Spies wrap the real helper rather than replace its decision: valid keys pass
1000 and a 60-second window; anonymous/invalid keys pass 100 and the same
window. Fake Redis models the existing atomic increment/expiry interface,
not an actual Redis/Lua implementation. App state and dependency overrides
are restored by the fixtures.

## Interpretation and scope

**Correction after exact-head CI and owner reproduction:** the two original
default-ceiling assertions failed with `assert (200 == 429)`. Hypothesis 2,
not hypothesis 1, describes the observed current public-read integration:
the exercised public routes are outside the default 60/min ceiling and use
the dependency's shared 100/1000 budget. An enabled test limiter does not mean
its default is applied to every route. Other default-covered routes, such as
`/health`, retain their separate existing default-limit regressions.

The corrected tests require the 61st valid-key read to reach the real dependency
and endpoint, and require 61 reads on each of two routes to produce one shared
counter of 122. The seeded 999 -> 1000 -> 1001 test separately proves the keyed
boundary with two actual requests; it is not a 1001-request load/timing test.
This is consistent with the advertised public shared budget, not a guarantee
of successful data work or production throughput. No limiter or route exemption
is introduced or changed by this test-only correction.

This is an offline contract check, not a load test, timing exploit, production
measurement, real Redis test or confirmed security vulnerability. Exact-lock
CI and gio-dd cross-review remain required before a head-bound merge. No
deployment or Codex Security scan is authorized.

## Validation evidence

`pytest` over middleware, limiter privacy, client-IP helpers and Admin Bearer
tests originally reported **47 passed, 1 skipped**, 10.89s in cached image
`4b50ab6021c0` with FastAPI 0.136.1. **That evidence is withdrawn for the current
public-route/default contract:** the current FastAPI 0.142.2 CI job
`114156668516` instead reported the two failures above (2153 passed, 36 skipped,
25 xfailed). Cache/toolchain mismatch was a hypothesis requiring revalidation,
not grounds to publish the older behavior as current.

Corrected local suites: **47 passed, 1 skipped**, 12.58s, with one cached
Starlette/httpx deprecation warning. The real-Redis integration skip is expected
in the isolated offline run. Cached image `4b50ab6021c0` was overlaid read-only
with existing FastAPI 0.142.2, Starlette 1.7.0, SlowAPI 0.1.10 and limits 5.8.0
packages, matching the relevant routing versions installed in the failed CI
job. Other cached dependencies are not claimed to match the full CI matrix.
No download, install or provider call was performed. Execution used network
none, read-only source/root/toolchain, non-root, an empty explicit environment,
dropped capabilities/no-new-privileges, bounded resources and a 120s timeout.
The full local command and versions are recorded in the PR/Bridge handoff.
The fake executes the helper interface, not Redis Lua. Exact-head CI and owner
cross-review remain required; production quota, forwarded-peer attribution,
actual Redis and outage behavior are not measured here.

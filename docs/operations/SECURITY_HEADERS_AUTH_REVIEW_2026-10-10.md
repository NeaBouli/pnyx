# Bounded security headers, limits and Admin Bearer review

2026-10-10; T-9049; source baseline `5a266335`; manual source review, not a
Codex Security scan or penetration test. No production configuration, secrets,
authenticated requests, transactions or load tests were used. This is partial
coverage, not a claim that the system is free of vulnerabilities.

## Header observations

Exactly one unauthenticated HEAD per HTTPS host was made around 06:34Z,
without redirects, cookies or credentials. Only the status and security headers
were retained; bodies and Set-Cookie were not recorded.

| Control | `https://ekklesia.gr/` (200) | `https://api.ekklesia.gr/` (405) |
| --- | --- | --- |
| CSP | Present; self/explicit origins, inline scripts/styles | Not present |
| `frame-ancestors` | `'none'` in CSP | No CSP; X-Frame-Options DENY present |
| HSTS | 31536000; includeSubDomains; preload | Same |
| X-Content-Type-Options | nosniff | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin | Not present |
| Permissions-Policy | camera, microphone, geolocation, payment disabled | Not present |
| X-Frame-Options | DENY | DENY |

The API root is GET-only; HEAD's 405 is a method response, not a demonstrated
failure. Its policy observations apply only to that response, not all routes or
uncaught errors. Edge headers are configured in production Compose; the web's
Next configuration also supplies Referrer/Permissions policies. Mirror Nginx
is a separate sandbox surface, not the production web server. Missing API
browser policies alone are not a confirmed vulnerability for JSON responses.

## Findings and bounded hardening

- No new confirmed P1/P2 vulnerability established in this scope.
- **P3 / informational hardening:** the shared Admin Bearer dependency used
  ordinary string equality. This candidate switches only that comparison to
  `hmac.compare_digest` on UTF-8 bytes. Production fail-closed, development
  defaults, HTTPBearer parsing and 403 semantics are preserved. No remote
  timing exploit or authentication bypass has been demonstrated.
- **P3 / hardening backlog, not confirmed exploits:** CSP inline allowances
  remain necessary for existing pages until a scoped nonce/hash migration;
  the dashboard's separate login service has no application limiter shown in
  the inspected source; connection admission deserves a separately designed
  quota. No automatic CSP tightening or quota/policy change is included.

## Coverage and validation gaps

- All 54 shared Admin dependency call sites across 11 router modules were
  inspected; query parameters do not authenticate. Shared HTTP limiting is
  active at 60/minute/IP/endpoint, with Redis and bounded per-process fallback.
  Agent, HLR, public API, newsletter and contact paths add targeted controls.
  Failure propagation before protected side effects and daily HMAC IP buckets
  were checked in source. Dashboard NextAuth is a separate service.
- No live validation of Redis, proxy CIDRs/hop count, worker-shared outage
  budgets, webhook burst capacity, connection ceilings or error-response
  headers. Do not treat a configured limiter as a tested production quota.
- The public API advertises 100/1000/minute while the shared default appears
  stricter. The effective valid-key limit needs a mocked middleware test before
  a contract correction; do not remove protection to match documentation.
- Existing inline-CSP work is tracked by EKA-30; do not create a duplicate
  finding. Public telemetry-status projection under an admin-named URL needs
  its own policy classification; it is not evidence of shared-guard bypass.

## Candidate checks and integration gates

Sixteen offline tests exercise constant-time comparison dispatch, unequal and
Unicode inputs, missing/default production key, development default, real
HTTPBearer acceptance, Basic rejection and query-only rejection. Cached image
`4b50ab6021c0` ran with no network, read-only source/container, non-root user,
empty allowlisted environment, scratch-only writes and bounded resources.
Dependencies are cached FastAPI 0.136.1 / httpx 0.28.1 / pytest 9.0.3, not the
current lock matrix; exact-head CI remains required.

Final guard/IP/limiter-privacy run: **31 passed** in 1.59s. Substituting the
unchanged baseline dependency gives **2 comparison-dispatch regressions failed,
14 passed** (0.91s). This demonstrates the primitive change, not exploitation.
An initial baseline spy addressed a candidate-only module attribute; it was
corrected to spy on the standard library boundary before these final runs.

The specialist checks are source-only. gio-dd cross-review, all applicable
exact-head CI and head-bound merge remain gates. No deployment is authorized.
Codex Security is **NOT RUN**: no scan access/payload/cost authorization. The
lead's exception is limited to this manual, tested comparison hardening and
does not waive cross-review/CI or authorize any scanner/transfer/spending.

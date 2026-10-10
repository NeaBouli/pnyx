# Admin API authentication

This guide describes the current static-key contract for API routes that depend on
`dependencies.verify_admin_key`, directly or through `routers.admin.verify_admin`.
An `/admin` URL prefix alone does not establish that a route uses this dependency.
Historical audits and handovers describe their own snapshots, not this current contract.

## Request contract

Send the configured key only in the HTTP header `Authorization: Bearer <ADMIN_KEY>`.
The token is compared exactly and case-sensitively with the configured key.
There is no query-string or request-body authentication fallback in this dependency.
`?admin_key=...` is not an authentication input: without a valid Bearer header the
request is denied, even if the query value matches the configured key. A valid header
is not invalidated merely by an ignored query parameter.

The first four rows below assume an admissible key is configured; the production
configuration check runs before token validation.

| Condition | Authentication result |
|---|---|
| Configured key and matching Bearer token | Authentication passes; endpoint response still depends on its own logic/services |
| Missing header, empty token or non-Bearer scheme | HTTP 403, `Ungueltiger Admin-Key` |
| Wrong token, including a change in the key's letter case | HTTP 403, `Ungueltiger Admin-Key` |
| Query key only, without a valid Bearer header | HTTP 403, `Ungueltiger Admin-Key` |
| Missing key or built-in development placeholder, with `ENVIRONMENT=production` | HTTP 403, `Admin-Zugang nicht konfiguriert`, even with a supplied token |

If `ENVIRONMENT` is unset, this dependency treats it as `production`. For a value
other than the exact string `production`, a missing key falls back to the built-in
development placeholder, accepted only via Bearer authentication. This is a
configuration-dependent development behavior, not a URL/body fallback.

The following is a documentation-only, read-only GET template for an already
authorized local API. It has not been executed:

```sh
curl --request GET \
  --header 'Authorization: Bearer <ADMIN_KEY>' \
  http://127.0.0.1:8000/api/v1/admin/stats
```

`<ADMIN_KEY>` is a literal placeholder, not a shell variable or a usable key; sending
the template unchanged does not supply the configured credential. Never put actual
keys in URLs, logs, copied command histories or documentation.

## Dashboard access is separate

The Dashboard uses NextAuth GitHub OAuth and its own account/role checks. Its generic
API proxy requires a session and the `SUPER_ADMIN` role, then supplies the server-side
key in the upstream Bearer header. The proxy returns 401 for no session, 403 for a
disallowed role, and 503 for an absent proxy key; these are not the static API
dependency's error statuses. OAuth/session credentials are not an alternative
credential accepted by `verify_admin_key`.

## Source and regression references

- [Shared dependency](../../apps/api/dependencies.py) and
  [Admin wrapper and GET `/stats`](../../apps/api/routers/admin.py).
- [Dashboard OAuth](../../apps/dashboard/src/lib/auth.ts) and
  [generic proxy](../../apps/dashboard/src/app/api/proxy/%5B...path%5D/route.ts).
- Existing missing/wrong-header regressions:
  [Admin Diavgeia lookup tests](../../apps/api/tests/test_admin_diavgeia_lookup.py),
  `test_admin_diavgeia_lookup_requires_admin_key` and
  `test_admin_diavgeia_lookup_rejects_wrong_admin_key`.
- Read-only aggregate stats response:
  [Dashboard contract tests](../../apps/api/tests/test_dashboard_contracts.py),
  `test_admin_stats_exposes_only_aggregate_identity_counts`.

# Newsletter Brevo Webhook Bearer Auth (EKA-09)

Scope: source fix only in `apps/api/routers/newsletter.py`. The Brevo event
webhook (`POST /api/v1/newsletter/webhook/brevo`) now requires
`Authorization: Bearer <token>` matched against the server-side
`BREVO_WEBHOOK_TOKEN` environment value with `secrets.compare_digest`.

Behavior contract:
- `BREVO_WEBHOOK_TOKEN` unset/empty → 503 (fail closed, webhook disabled).
- Missing, malformed or wrong bearer credentials → 401 with
  `WWW-Authenticate: Bearer` challenge.
- No JSON parsing, Redis write, counter increment or cache deletion happens
  before successful authentication.
- Token material is never logged or returned.
- Accepted single/batched event payloads keep the previous counter and
  stats-cache-invalidation behavior; event semantics are unchanged.

Server configuration (empty by default; set only out of band, never commit):

```
BREVO_WEBHOOK_TOKEN=
```

## Rollout note

Source merge is not deployment. Production activation requires, as a
separately approved gate:

1. Configure `BREVO_WEBHOOK_TOKEN` in the API runtime environment with a
   high-entropy value delivered out of band. Environment-based rotation takes
   effect only after the API process is restarted or replaced.
2. Configure the identical bearer token as the Authorization header on the
   Brevo webhook in the Brevo console.
3. Only then roll out the API change. Until step 2 matches step 1, the
   endpoint returns 503 (unconfigured) or 401 (mismatch) — both fail closed.
4. Rollback: redeploy the previous API image/source; no state, schema or
   counter format changed, so rollback is a plain revert.
5. Live acceptance after rollout: unauthenticated POST returns 401, a POST
   with the configured bearer token returns `{"received": true, ...}`, and
   `newsletter:events` counters increment only for authenticated deliveries.

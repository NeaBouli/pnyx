# Optional source metadata provider

Ordinary Parliament discovery runs first. Deployments may opt into a local
metadata provider using `SOURCE_PROVIDER_SOCKET` (absolute Unix socket path).
An unset or invalid path keeps existing discovery behavior. Explicit source
robots exclusions prohibit the alternate request as well. If policy could not
be obtained through the ordinary transport, a configured provider must obtain
and enforce source policy independently before collecting content.

The provider receives no application or database credentials. It only returns
public source metadata to the existing scheduled validation and upsert. It must
restrict source destinations, enforce source policy, bound concurrent work and
request rates, and retain no application secrets. Its socket must permit only
the intended application peer; do not expose the protocol over a public port.

## Protocol

HTTP over the configured Unix socket: `POST /v1/collect`, JSON request:

```json
{"source":"PARLIAMENT","limit":20,"require_dates":true}
```

Limits are 1–20 rows, 120 seconds total, and 2 MiB of uncompressed JSON response.
Redirects and compressed responses are rejected. There is no automatic retry.

The success envelope contains `schema_version: 1`, `source: "PARLIAMENT"`,
`source_status: "ok"`, a timezone-aware ISO `captured_at`, and nonempty `bills`.
Each bill contains `law_id`, `title_el`, `url`, `date` and `submitted_date`;
`type`, `ministry` and `phase` are optional. Dates are ISO strings or null.
The capture must be no older than 15 minutes or over 2 minutes in the future.

The API validates unique nonzero UUIDs, official HTTPS legislative links bound
to the same UUID, bounded text and dates. Strict ingestion filters undated rows
before applying the requested limit. Provider-generated summaries, full text,
verification attestations and unknown fields are discarded. Metadata summaries
are produced by the existing application logic.

## Outcomes

Provider success uses the existing stable bill IDs, metadata upsert, content
ownership guards and ingestion success tracking. Direct HTTP cooldown remains
in effect for that access path. A single transport failure does not establish
that every configured provider is unavailable; all-path failure is recorded
after discovery completes. Source freshness advances only after successful
ingestion, not because a local service returned HTTP 200.

Malformed, stale, oversized, timed-out or unavailable provider responses fail
closed. Existing stored data remain available with their real freshness state.

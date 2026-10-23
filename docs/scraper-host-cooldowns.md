# Scraper host cooldowns (T-9168)

Scraper HTTP hooks read Redis before requests, including robots and redirect
requests. Hostnames are normalized; Parliament subdomains share one source
host. Request identity, headers, and fetching routes follow the existing policy.

A 403 stores `started_at` and `cooldown_until` as absolute UTC Unix seconds,
`reason: http_403`, and `consecutive_403`. Keys contain only the normalized
hostname. No URLs, paths, queries, response bodies, or free-form reasons are
stored. The `scraper:host:<host>:cooldown` key expires after the remaining
cooldown, rounded up to a second. The companion `:streak` record has no TTL:
it preserves the count across cooldown expiry and worker restarts until a
successful content fetch deletes both keys. Backoff is 6, 12, 24, then 48 hours,
capped at 48 hours. A 2xx or 304 content response resets the streak once the
previous cooldown has expired. Robots revalidation does not reset it.

Redis WATCH transactions preserve increments from concurrent workers and keep
a delayed success from clearing a newer active block. Each Parliament 403,
including an access-denied body detected by the existing policy, counts once.
Local pacing and Retry-After continue to use monotonic time.

**Outage decision:** fail closed for every unreadable or invalid host record,
including unknown hosts after restart and hosts previously observed as clean.
Restricting this to a recent 403 remembered in memory would allow a restarted
worker to request a blocked source during a Redis outage. Local cooldown state
is retained for status and failed writes are retried before the next request;
local expiry alone never authorizes access while Redis is unavailable. Redis
connections have one-second connect and command timeouts. Redis must be
available before scraping can resume; persistence still depends on the Redis
service's own durability configuration.

Both `/api/v1/scraper/jobs` and `/api/v1/scraper/status` include `host_cooldowns`
for Parliament and Diavgeia. Each host exposes only `cooldown_until` and
`consecutive_403`. No block is `null` / `0`; unavailable state without local
403 evidence is `null` / `null`. During outages, remembered 403 metadata is
returned, even if its timestamp has elapsed; requests remain deferred until
Redis recovers. Status reads do not write state or fetch source content.

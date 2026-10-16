# API rate-limit coverage — T-9136 / EVA-011

Source audit of all **186 registered router HTTP endpoints: 132 public, 54 admin**. Admin status follows actual dependency chains, including admin-only routes outside `/admin`. WebSockets and framework metadata are outside this HTTP inventory. PATCH is included alongside POST/PUT/DELETE.

Every public GET is classified. Limits are per IP unless a valid-key or identity/email quota is stated. “Main” below means the base `HEAD` behavior; “staged” means the original uncommitted T-9136 implementation before this correction. This is local source/test evidence, not deployment verification.

## Class changes

| Class of the 62 newly limited GETs | Count | Original staged policy | Corrected policy |
| --- | ---: | --- | --- |
| (a) Personal/identity/token oracle or auth-session operation | 13 | Usually 10/min; QR status 30/min | Keep 10/min; QR status 120/min for polling |
| (b) Expensive download, live provider probe, detailed representative analysis or SSE subscription | 13 | 5–30/min | 30/min |
| (c) Public cacheable read | 36 | 10–120/min | Remove the new per-IP decorator; restore main behavior |

“Public cacheable” describes data shared by visitors; it does **not** introduce caching or weaken visibility rules. In particular, the SSR helpers still fetch `no-store`. Public analytics/MP/CPLM/consensus aggregates remain class (c), including DB aggregation work. CSV generation, external provider fan-out and representative-only detailed analytics are class (b). `/export/results.json` is class (c) despite its export-shaped URL: it is the web results page's shared public feed. `/export/parties.json` is a small public catalogue. ZK receipt lists and public roots/members are public audit material, unlike token-based personal vote receipts. HLR credits reads coarse Redis counters, not a live HLR provider, and is class (c).

| Public route category | Main | Original staged | Corrected |
| --- | ---: | ---: | ---: |
| Explicitly decorated writes | 9 | 32 | 32 |
| Writes with existing Redis guards | 6 | 6 | 6 |
| Writes with neither decorator nor Redis guard | 26 | 3 provider webhooks | 3 provider webhooks |
| Explicitly decorated GETs | 0 | 62 | 26 |
| GETs with existing shared Redis quota | 7 | 7 | 7 |
| Other GETs without explicit limits | 84 | 22 | 58 |

All 23 new explicit write limits, nine established write decorators, six existing Redis write guards and three verified provider-webhook exceptions are preserved. The seven `/public` data routes keep their existing shared **100/minute anonymous IP or 1000/minute valid API key** quota; no second limiter is added.

## SSR, client IP and polling audit

`infra/docker/docker-compose.prod.yml:90` sets `NEXT_PUBLIC_API_URL=https://api.ekklesia.gr`. `apps/web/src/lib/api.ts` uses that same public origin. `src/lib/initial-data.ts` sends only `Accept: application/json`, with no cookies, identity or visitor forwarding headers. The web server makes one upstream GET per rendered view, with `cache: "no-store"`.

`rate_limit_key_for_ip` calls `get_client_ip` in `apps/api/ip_utils.py`. It trusts `X-Forwarded-For` **only when `request.client.host` belongs to `TRUSTED_PROXY_CIDRS`** (default loopback networks). It validates each address, then selects the `TRUSTED_PROXY_COUNT`-th address from the **right** (default 1), rather than the spoofable leftmost value. If the peer is untrusted or forwarding data is unusable, it uses the peer address. The resulting limiter key is a daily HMAC, not a raw IP.

With a trusted Traefik peer and count 1, an SSR call is attributed to the web server's address/NAT egress, so all visitors rendered by that web process share the same IP bucket. If Traefik is not trusted, calls instead share Traefik's peer bucket, which can aggregate even more traffic. Compose explicitly sets the hop count to 1 and loads a private production env file; that file's CIDRs and any Uvicorn proxy env overrides are not available in this local worktree. No live deployment assertion is made. Either path is unsafe for a new low per-IP quota on SSR reads; forwarding arbitrary visitor headers is not part of this fix. The 11 client-IP helper tests verify trust, spoof resistance and hop selection.

The audit grepped `apps/web/src` for `fetch`, axios/API calls, server components, `generateMetadata`, `use server`, and route handlers, then followed imports and client boundaries. The only API reads in server components are the following two helpers. Metadata is static; there are no API-fetching `generateMetadata`, server actions or route handlers in this tree. Client components invoke writes from effects or user actions, not during server rendering.

| Caller | Endpoint / request pattern | Calculation and corrected policy |
| --- | --- | --- |
| Web bills server page → `getInitialBills` | GET `/api/v1/bills?limit=11&offset=0&include_institutional=true[&status=…]` | V views/minute = V requests/minute from one server IP. No new limit; same as main. |
| Web results server page → `getInitialResults` | GET `/api/v1/export/results.json?min_votes=1` | V views/minute = V requests/minute from one server IP. The staged 10/min would reject view 11. No new limit. Client fallback uses the same endpoint. |
| Web bill/results/trending/analytics/MP/municipal clients | Public results, bills, analytics, MP and consensus aggregates | Shared public data; class (c), no new per-IP limit. The staged latest/result 120/min decorators were new, not established exceptions. |
| Web `QRCodeVoteStub` and SSO QR page | GET `/api/v1/polis/qr-session/{session_id}` every 2500 ms | 60,000 / 2,500 = 24 polls/minute per flow; conservatively add one initial request. Four concurrent flows use at most 4 × 25 = 100, below 120/minute/IP. Session IDs share one handler bucket; rotating IDs does not reset it. |
| QR session creation | GET `/api/v1/polis/qr-session` once per user attempt | 10/minute; polling never creates another session. Normal 5-minute QR sessions do not approach this quota. |
| Mobile `VoteScreen` | GET `/api/v1/zk/scopes/{scope}/status` immediately, then every 5000 ms while a root is pending | 12 polls/minute plus initial/status-load requests already exceeds staged 10/minute. Public scope state is class (c); limit removed. |
| Mobile `UpdateBanner` | GET `/api/v1/app/version` initially, then every 30 minutes | One initial request + 1/30 request/minute; existing no-limit policy retained. |
| Mobile QR scanner | POST `/api/v1/polis/qr-auth` after scan | One authentication per scan; no mobile QR-status polling loop exists in current source. Existing new 10/minute write guard retained. |
| Personal vote/identity/key/evaluation reads | User action or screen load; no periodic loop found | Tight 10/minute (existing signed key-check 30/minute); the 5-second mobile loop reads public ZK scope status, not personal vote status. |
| Web `LiveNotifications` | One browser EventSource GET `/api/v1/notifications/stream` per mount | 30/minute counts connections, not messages/30-second heartbeats. One browser's default 3-second reconnect is at most 20 attempts/minute. No SSR call. |
| Static community page provider tiles | Mirrors every 30s; Arweave and DeepL every 60s | At most 3, 2 and 2 requests respectively in a minute including the initial load, each below its separate 30/minute handler quota. Public scraper health is loaded once. HLR/newsletter/finance/budget public state has no new quota. |

QR status retains a finite shared-IP budget: the calculation covers four concurrent polling views with 20 requests/minute to spare, not arbitrary NAT concurrency. No remaining new limiter is on an SSR API path or on the mobile 5-second poll. CSV/representative/live-scraper GETs have no web SSR or mobile periodic caller. No newly limited POST/PUT/PATCH/DELETE is called server-side by the web app. Web identity migration, vote/status/correction/relevance/consensus, VAA match, QR and SSO writes run in client effects or event handlers.

## Policy and privacy

- The configured SlowAPI default remains **60/minute**. FastAPI 0.142.2 lazy included routers and SlowAPI 0.1.10 do not apply it to these router endpoints; no row claims default protection. Direct app routes such as `/health` retain their established behavior.
- Parameterized limited routes use fixed-scope `shared_limit`; changing target IDs cannot mint fresh IP budgets. The shared limiter, daily HMAC-IP keys, trusted-proxy logic, Redis storage and memory fallback policy are unchanged.
- Ordinary new writes retain 20–30/minute; personal/auth/proof writes retain 10/minute. Established revocation/rotation (10), signed key-check (30), agent (5) and voting/POLIS/bill-flag (120) decorators are unchanged.
- Atomic HLR, mail, API-key and push Redis guards remain single-counted. Verified Stripe/PayPal/Brevo webhooks retain provider retries and bursts without a new shared-source-IP quota.

## Complete inventory

`Explicit` means a decorator (`limit` or fixed-scope `shared_limit`). `None; Redis` means an independent handler/dependency quota, without SlowAPI coverage. Existing limits are shown as main behavior. All **74 exceptions** (65 GET + 9 write) have checked reasons in `tests/test_rate_limit_coverage.py`. Removed public GET decorators use the reason **"public cacheable read; SSR shares one IP"**.

### Public POST / PUT / PATCH / DELETE (41)

| Router | Method and endpoint | Before | Current limit / exception reason |
| --- | --- | --- | --- |
| `agent.py` | POST `/api/v1/agent/ask` | Explicit: 5 per 1 minute | Explicit: 5 per 1 minute |
| `contact.py` | POST `/api/v1/contact/ngo` | None; Redis | None; Redis — Existing Redis guard: 3/IP/hour before sending mail. |
| `evaluation.py` | POST `/api/v1/politicians/{ada_number}/evaluate` | None | Explicit: 20 per 1 minute |
| `identity.py` | PATCH `/api/v1/identity/profile/location` | None | Explicit: 20 per 1 minute |
| `identity.py` | POST `/api/v1/identity/revoke` | Explicit: 10 per 1 minute | Explicit: 10 per 1 minute |
| `identity.py` | POST `/api/v1/identity/status` | None | Explicit: 10 per 1 minute |
| `identity.py` | POST `/api/v1/identity/verify` | None; Redis | None; Redis — Atomic HLR Redis guard: 5/IP/min, 20/IP/day, 3/number/day and 300s cooldown. |
| `identity.py` | POST `/api/v2/identity/key-check` | Explicit: 30 per 1 minute | Explicit: 30 per 1 minute |
| `identity.py` | POST `/api/v2/identity/rotate-key` | Explicit: 10 per 1 minute | Explicit: 10 per 1 minute |
| `identity.py` | POST `/api/v2/identity/verify` | None; Redis | None; Redis — Uses the same atomic HLR Redis guard as v1 registration. |
| `municipal.py` | POST `/api/v1/municipal/vote` | None | Explicit: 20 per 1 minute |
| `newsletter.py` | POST `/api/v1/newsletter/subscribe` | None; Redis | None; Redis — Redis: 10/IP/hour and 3/email/day; confirmed subscriptions return without consuming quota. |
| `newsletter.py` | POST `/api/v1/newsletter/webhook/brevo` | None | None — Authenticated Brevo event batches; preserve provider retries and bursts. |
| `notify.py` | POST `/api/v1/notify/register` | None; Redis | None; Redis — Redis: 600/IP/hour before auth, 20/identity/day for changed device registrations. |
| `parliament.py` | POST `/api/v1/bills/{bill_id}/flag` | Explicit: 120 per 1 minute | Explicit: 120 per 1 minute |
| `payments.py` | POST `/api/v1/payments/webhook` | None | None — Stripe signature verification and event deduplication; preserve provider retries and bursts. |
| `payments.py` | POST `/api/v1/payments/webhook/paypal` | None | None — PayPal IPN verification and transaction deduplication; preserve provider retries and bursts. |
| `polis_qr.py` | POST `/api/v1/polis/qr-auth` | None | Explicit: 10 per 1 minute |
| `polis_qr.py` | POST `/api/v1/polis/qr-consensus` | None | Explicit: 20 per 1 minute |
| `polis_qr.py` | POST `/api/v1/polis/qr-vote` | None | Explicit: 20 per 1 minute |
| `polis_tickets.py` | POST `/api/v1/polis/register-key` | Explicit: 120 per 1 minute | Explicit: 120 per 1 minute |
| `polis_tickets.py` | POST `/api/v1/polis/tickets` | Explicit: 120 per 1 minute | Explicit: 120 per 1 minute |
| `polis_tickets.py` | POST `/api/v1/polis/tickets/{ticket_id}/votes` | Explicit: 120 per 1 minute | Explicit: 120 per 1 minute |
| `public_api.py` | POST `/api/v1/public/keys/generate` | None; Redis | None; Redis — Existing Redis guard: 5/IP/hour before generating a key. |
| `public_api.py` | POST `/api/v1/public/share` | None | Explicit: 30 per 1 minute |
| `representative.py` | POST `/api/v1/rep/auth` | None | Explicit: 10 per 1 minute |
| `representative.py` | POST `/api/v1/rep/enable-evaluation` | None | Explicit: 20 per 1 minute |
| `representative.py` | POST `/api/v1/rep/verify` | None | Explicit: 10 per 1 minute |
| `sso.py` | POST `/api/v1/sso/discourse/callback` | None | Explicit: 10 per 1 minute |
| `sso.py` | POST `/api/v1/sso/discourse/qr-complete` | None | Explicit: 10 per 1 minute |
| `vaa.py` | POST `/api/v1/vaa/match` | None | Explicit: 20 per 1 minute |
| `voting.py` | POST `/api/v1/vote` | Explicit: 120 per 1 minute | Explicit: 120 per 1 minute |
| `voting.py` | POST `/api/v1/vote/compass/personal` | None | Explicit: 10 per 1 minute |
| `voting.py` | POST `/api/v1/vote/{bill_id}/consensus` | None | Explicit: 20 per 1 minute |
| `voting.py` | PUT `/api/v1/vote/{bill_id}/correct` | None | Explicit: 20 per 1 minute |
| `voting.py` | POST `/api/v1/vote/{bill_id}/receipt` | None | Explicit: 10 per 1 minute |
| `voting.py` | POST `/api/v1/vote/{bill_id}/relevance` | None | Explicit: 30 per 1 minute |
| `voting.py` | POST `/api/v1/vote/{bill_id}/status` | None | Explicit: 10 per 1 minute |
| `zk.py` | POST `/api/v1/zk/opt-in` | None | Explicit: 10 per 1 minute |
| `zk.py` | POST `/api/v1/zk/verify` | None | Explicit: 10 per 1 minute |
| `zk.py` | POST `/api/v1/zk/vote` | None | Explicit: 20 per 1 minute |

### Public GET (91)

| Router | Endpoint | Class | Main | Original staged | Corrected policy / reason |
| --- | --- | --- | --- | --- | --- |
| `analytics.py` | GET `/api/v1/analytics/bill/{bill_id}` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/divergence-trends` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/info` | (c) | None | None | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/overview` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/representation` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/top-divergence` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `analytics.py` | GET `/api/v1/analytics/votes-timeline` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `app_version.py` | GET `/api/v1/app/version` | (c) | None | None | None — Static client update metadata; retain existing polling access policy. |
| `arweave.py` | GET `/api/v1/arweave/bill/{bill_id}` | (c) | None | None | None — Single stored archive pointer; no gateway/provider request. |
| `arweave.py` | GET `/api/v1/arweave/status` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Live wallet/gateway balance lookup. |
| `claude_agent.py` | GET `/api/v1/claude/budget` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `consensus_results.py` | GET `/api/v1/consensus/representation` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `cplm.py` | GET `/api/v1/cplm/aggregate` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `cplm.py` | GET `/api/v1/cplm/history` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `diavgeia.py` | GET `/api/v1/municipal/{dimos_id}/decisions` | (c) | None | None | None — Paginated public municipal decision feed. |
| `diavgeia.py` | GET `/api/v1/regions/{periferia_id}/decisions` | (c) | None | None | None — Paginated public regional decision feed. |
| `evaluation.py` | GET `/api/v1/politicians/` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `evaluation.py` | GET `/api/v1/politicians/my-evaluations/bulk` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `evaluation.py` | GET `/api/v1/politicians/{ada_number}/my-evaluation` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `evaluation.py` | GET `/api/v1/politicians/{ada_number}/questions` | (c) | None | None | None — Small public evaluation question catalogue; no personal scores. |
| `evaluation.py` | GET `/api/v1/politicians/{ada_number}/scores` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `export.py` | GET `/api/v1/export/bills.csv` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Full result materialization and CSV serialization; download only. |
| `export.py` | GET `/api/v1/export/divergence.csv` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Full result materialization, ranking and CSV serialization; download only. |
| `export.py` | GET `/api/v1/export/info` | (c) | None | None | None — Static format metadata; CSV downloads have explicit limits. |
| `export.py` | GET `/api/v1/export/parties.json` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `export.py` | GET `/api/v1/export/results.json` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `govgr.py` | GET `/api/v1/auth/govgr/callback` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `govgr.py` | GET `/api/v1/auth/govgr/family/verify` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `govgr.py` | GET `/api/v1/auth/govgr/info` | (c) | None | None | None — Static integration metadata. |
| `govgr.py` | GET `/api/v1/auth/govgr/login` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `govgr.py` | GET `/api/v1/auth/govgr/status` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `identity.py` | GET `/api/v1/identity/hlr/credits` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `mp.py` | GET `/api/v1/mp/bill/{bill_id}` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `mp.py` | GET `/api/v1/mp/compare/{party_abbr}` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `mp.py` | GET `/api/v1/mp/info` | (c) | None | None | None — Static module metadata. |
| `mp.py` | GET `/api/v1/mp/parties` | (c) | None | None | None — Small public party catalogue. |
| `mp.py` | GET `/api/v1/mp/ranking` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `municipal.py` | GET `/api/v1/decisions` | (c) | None | None | None — Paginated public decision feed. |
| `municipal.py` | GET `/api/v1/municipal/{dimos_id}/voteable` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `municipal.py` | GET `/api/v1/periferia` | (c) | None | None | None — Small public region catalogue. |
| `municipal.py` | GET `/api/v1/periferia/{periferia_id}/dimos` | (c) | None | None | None — Bounded public municipality catalogue for one region. |
| `newsletter.py` | GET `/api/v1/newsletter/confirm/{token}` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `newsletter.py` | GET `/api/v1/newsletter/lists` | (c) | None | None | None — Static subscription options. |
| `newsletter.py` | GET `/api/v1/newsletter/stats` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `notifications.py` | GET `/api/v1/notifications/status` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `notifications.py` | GET `/api/v1/notifications/stream` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Long-lived SSE subscription; heartbeats do not consume new requests. |
| `parliament.py` | GET `/api/v1/bills` | (c) | None | None | None — Paginated public feed; retain existing SSR access policy. |
| `parliament.py` | GET `/api/v1/bills/trending` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `parliament.py` | GET `/api/v1/bills/{bill_id}` | (c) | None | None | None — Single public bill lookup. |
| `parliament.py` | GET `/api/v1/bills/{bill_id}/summary` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `payments.py` | GET `/api/v1/payments/public/finance` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `payments.py` | GET `/api/v1/payments/status` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `polis_qr.py` | GET `/api/v1/polis/qr-session` | (a) | None | 10/minute | Explicit: 10 per 1 minute — auth-session creation (state-changing GET). |
| `polis_qr.py` | GET `/api/v1/polis/qr-session/{session_id}` | (a) | None | 30/minute | Explicit: 120 per 1 minute — polling allowance; 24/min/flow. |
| `polis_tickets.py` | GET `/api/v1/polis/tickets` | (c) | None | None | None — Public ticket list capped at 100 records. |
| `public_api.py` | GET `/api/v1/public/bills` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/bills/{bill_id}/results` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/cplm` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/cplm/history` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/deepl/usage` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Live authenticated DeepL provider request. |
| `public_api.py` | GET `/api/v1/public/info` | (c) | None | None | None — Static API metadata. |
| `public_api.py` | GET `/api/v1/public/keys/status` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `public_api.py` | GET `/api/v1/public/mirrors/status` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Live fan-out HTTP mirror probes. |
| `public_api.py` | GET `/api/v1/public/representation` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/scraper/status` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Health aggregation including a live Arweave wallet lookup when configured. |
| `public_api.py` | GET `/api/v1/public/stats` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `public_api.py` | GET `/api/v1/public/vaa/parties` | (c) | None; Redis | None; Redis | None; Redis — existing combined 100/min/IP or 1000/min/valid key. |
| `representative.py` | GET `/api/v1/rep/bills` | (c) | None | None | None — Representative-authenticated public bill list capped at 100 records. |
| `representative.py` | GET `/api/v1/rep/divergence/{bill_id}` | (b) | None | 30/minute | Explicit: 30 per 1 minute — Representative-token-protected detailed divergence analysis. |
| `representative.py` | GET `/api/v1/rep/my-scores` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `representative.py` | GET `/api/v1/rep/results/{bill_id}` | (b) | None | 30/minute | Explicit: 30 per 1 minute — Representative-token-protected detailed results and hourly timeline. |
| `scraper.py` | GET `/api/v1/scraper/jobs` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `scraper.py` | GET `/api/v1/scraper/parliament/freshness` | (b) | None | 5/minute | Explicit: 30 per 1 minute — Live external Parliament freshness scrape. |
| `scraper.py` | GET `/api/v1/scraper/parliament/latest` | (b) | None | 5/minute | Explicit: 30 per 1 minute — Live external Parliament scrape. |
| `scraper.py` | GET `/api/v1/scraper/status` | (b) | None | 10/minute | Explicit: 30 per 1 minute — Live Ollama availability probe. |
| `scraper.py` | GET `/api/v1/scraper/test` | (b) | None | 5/minute | Explicit: 30 per 1 minute — Live Parliament scraping and Ollama probe. |
| `sso.py` | GET `/api/v1/sso/discourse/initiate` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `vaa.py` | GET `/api/v1/vaa/parties` | (c) | None | None | None — Small public party catalogue. |
| `vaa.py` | GET `/api/v1/vaa/questions` | (c) | None | None | None — Bounded public question lookup. |
| `vaa.py` | GET `/api/v1/vaa/statements` | (c) | None | None | None — Bounded public statement lookup. |
| `voting.py` | GET `/api/v1/vote/compass/personal` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `voting.py` | GET `/api/v1/vote/results/in-progress` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `voting.py` | GET `/api/v1/vote/results/latest` | (c) | None | 120/minute | None — public cacheable read; SSR shares one IP |
| `voting.py` | GET `/api/v1/vote/{bill_id}/receipt` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `voting.py` | GET `/api/v1/vote/{bill_id}/results` | (c) | None | 120/minute | None — public cacheable read; SSR shares one IP |
| `voting.py` | GET `/api/v1/vote/{bill_id}/status` | (a) | None | 10/minute | Explicit: 10 per 1 minute — personal/token/auth operation. |
| `zk.py` | GET `/api/v1/zk/receipts/{vote_scope_id}` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `zk.py` | GET `/api/v1/zk/roots/{vote_scope_id}` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |
| `zk.py` | GET `/api/v1/zk/roots/{vote_scope_id}/members` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `zk.py` | GET `/api/v1/zk/scopes/{vote_scope_id}/status` | (c) | None | 10/minute | None — public cacheable read; SSR shares one IP |
| `zk.py` | GET `/api/v1/zk/status` | (c) | None | 30/minute | None — public cacheable read; SSR shares one IP |

## Verification

The audit walks the registered FastAPI app and nested effective route contexts. It checks both limiter registration and the wrapper actually bound to each route, catches reversed decorators, and identifies admin routes by dependencies. Unreviewed GETs and unprotected writes fail; stale, redundant or reasonless allowlist entries fail too.

HTTP regressions use the original limiter with isolated memory storage on the real app. They exercise write/oracle limit+1 enforcement, independent client IPs, target/key rotation, rejection before DB/Redis handler work, HMAC-only storage, 150 public GETs from one shared SSR source and four concurrent QR polling flows. CSV coverage now checks the 30/minute policy. Existing quota/privacy/auth/visibility tests remain in the requested API slice. No production handler body changed.

Adding `public` to the selected API tests exposed two existing incomplete Redis mocks in the invalid-key and key-roundtrip tests. A local in-memory Redis hash stub now supplies those tests' reads/writes, alongside the already-staged key-generation stub. Their first run failed on sandbox-blocked `localhost:6379` access; production key storage and quotas are unchanged.

Commands use the existing cached Python environment; no installation, network, commit or push:

```sh
cd apps/api && python -m pytest -q tests -k "rate or limit or vote or identity or public"
cd apps/api && python -m pytest -q tests/test_ip_utils.py
cd scripts/redesign && python -m unittest discover -p 'test_*.py' -v
node scripts/public-seo.mjs --update && node scripts/public-seo.mjs --check
node --test scripts/public-seo.check.mjs scripts/static-docs-remote-sinks.check.mjs scripts/redesign/community_payment_status.check.mjs
```

The SEO updater initially rejected the modified uncommitted page, as designed. Its exported hash/render helpers refreshed only the API page fingerprint while preserving the already-staged `2026-10-16` lastmod. The requested `--update && --check` then passed. The generator and history assertion are unchanged: the separate Node history check cannot pass while that date is newer than the page's last source commit (`2026-10-15`). This task explicitly prohibits creating a commit. The exact API-page redesign approval hash was refreshed for the authorized EL/EN policy correction.

```text
API: 970 passed, 61 skipped, 1907 deselected, 6 xfailed, 31 warnings in 298.66s (0:04:58)
Client IP: 11 passed in 0.25s
Redesign: Ran 358 tests in 16.596s; OK (skipped=2)
SEO --update: wrote scripts/sitemap.sources.json and docs/sitemap.xml
SEO --check: sitemap ok
Node documentation gates: 116 passed, 1 failed
  docs/wiki/api.html: lastmod 2026-10-16 > last commit 2026-10-15
```

The original staged changes remain in the index; corrections are unstaged on top. No commit, push or external network operation was performed. All 75 router write definitions match the original staging exactly, and all production handler bodies plus the nine established decorators match `HEAD`. `git diff --check` and the staged whitespace check pass.

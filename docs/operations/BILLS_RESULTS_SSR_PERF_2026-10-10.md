# /bills and /results first-page SSR — local lab comparison (T-9080)

Local lab comparison of base `9a6d9678` (BEFORE) and the T-9080 working tree
(AFTER). Both use the same local fixture API and the same build mode. This is
**not** production, **not** Lighthouse, and **not** Core Web Vitals field data.

## Change

- `apps/web/src/app/[locale]/bills/page.tsx` and `results/page.tsx` are now Server
  Components. Each calls `apps/web/src/lib/initial-data.ts` and passes a
  serialisable seed to the unchanged client UI (`BillsClient.tsx`, `ResultsClient.tsx`).
- The server fetch uses the same public GET and query as the client:
  `/api/v1/bills?limit=11&offset=0&include_institutional=true[&status=…]` and
  `/api/v1/export/results.json?min_votes=1`. It uses native `fetch` with
  `next.revalidate = 60`, only an `Accept` header and no cookies. The origin is the existing `API_URL`.
- Bills are prefetched only for the five known `?status=` values. Unknown values
  take the previous client-only path, so the number of server cache keys stays bounded.
- On a non-2xx response, a network error, a timeout or a malformed body, the
  server passes `null` and the client mount fetch runs as before. A failure is
  never shown as an empty list.
- **Freshness (fail closed):** `revalidate = 60` is not a staleness bound. Next 16.3.8
  serves an expired cache entry while it refreshes in the background, and keeps the
  old entry when that refresh fails. So the helper checks the origin `Date` header
  (plus `Age`, if present) of every response, including cache hits. The Next fetch
  cache keeps the original headers. If the body is older than 120 s, or `Date` is
  missing or malformed, or `Date` is more than 5 s in the future, or `Age` is
  malformed, the server passes `null` and the client loads live data. 120 s is two
  revalidate windows, so data that refreshes normally stays under the limit. A
  failing or idle API only costs the SSR seed. This bound uses the API clock against
  the web server clock (the same host in the Compose setup). The bound is checked in
  code and was not verified against live production headers.
- **Remaining staleness:** within those 120 s, the SSR HTML can still show a result
  that the API has hidden since (#456). The client's own later fetches still follow the API.
- **Timeout scope:** the page waits at most 3 s for the helper (`AbortSignal.timeout`
  plus a deadline inside the same helper). Next's background revalidation drops the
  caller's signal, so a refresh to a slow API can outlive the request. It does not
  delay the page. There is no global timeout guarantee.

## Method

| Item | Value |
|---|---|
| Builds | `next build` (Turbopack, Next 16.3.8), served with `next start` on 127.0.0.1. Node v22.23.3 (`.nvmrc`), `npm ci --ignore-scripts`. Same `NEXT_PUBLIC_API_URL` set to the local fixture for both builds |
| Fixture | Local Node HTTP server on 127.0.0.1: 25 bills, 12 results, 300 ms fixed latency on every API response; `/api/v1/notifications/stream` returns 404 on both builds |
| Browser | Chromium headless via cached Playwright 1.63 (nothing installed) |
| Context | Fresh anonymous context per navigation (cold browser cache), 390×844, DPR 3, `isMobile`, `hasTouch`, `el-GR` |
| Throttling | CDP latency 150 ms, 200 KiB/s down, 75 KiB/s up, CPU 4× |
| Window | `domcontentloaded`, then 8 s settle, then one `performance` read |
| Interception | Requests to anything other than 127.0.0.1 are aborted (no external fonts, analytics or APIs) |
| Server cache | AFTER server fetch cache was warm, within the 60 s revalidate window. A cold server render adds the fixture latency to TTFB |
| Samples | Run 2: 3 samples per page per build, with BEFORE/AFTER order alternating. Run 1 (3 samples, sequential) gave the same picture |

"First card in DOM" is the `performance.now()` at which a `MutationObserver` first
sees `main h2`. This is DOM insertion, not paint; paint is bounded below by FCP.

## Results (run 2, values per sample in ms)

| Page | Build | First card in DOM | FCP | LCP (observed) | LCP element | CLS | TBT proxy | API GETs |
|---|---|---|---|---|---|---|---|---|
| /el/bills | BEFORE | 4912 / 4268 / 3437 | 2296 / 1088 / 1324 | = FCP | subtitle `<p>` | 0.037 | 1398 / 1469 / 797 | 3 |
| /el/bills | AFTER | 259 / 377 / 299 | 1092 / 1340 / 1096 | = FCP | subtitle `<p>` | 0 | 413 / 247 / 327 | 2 |
| /el/results | BEFORE | 3310 / 2974 / 3064 | 792 / 944 / 936 | = FCP | footer `<p>` | 0.132 | 729 / 540 / 545 | 2 |
| /el/results | AFTER | 482 / 420 / 249 | 1460 / 1352 / 900 | = FCP | first result `<h2>` | 0 | 505 / 1591 / 772 | 1 |

Encoded bytes per navigation were 280–310 KB in both builds and did not differ meaningfully.

**Measured:** the cards are in the initial HTML, so the first card enters the DOM
about 3–4.5 s earlier under this throttle. CLS falls to 0 on both pages. There is
one fewer client API GET per page, and no mount fetch after hydration.

**Not shown:** an LCP improvement. In this fixture the LCP element is text that
paints at FCP in both builds: the subtitle `<p>` on /bills, the footer `<p>` on
BEFORE /results and the first result `<h2>` on AFTER /results. FCP/LCP vary by
±0.5 s between samples. /results AFTER can paint slightly later because the HTML is larger. Production LCP depends on real
API latency, real content and server cache state, and has not been measured here.

## Raw HTML / cache evidence (AFTER, `curl`, no JS)

- `/el/bills`, `/en/bills`, `/el/bills?status=OPEN_END`: fixture bill titles are
  present and the loading skeleton is absent. `/el/results` and `/en/results`: fixture result titles are present.
- `/el/bills?status=BOGUS`: skeleton present, no server fetch (client path).
- Upstream counts at the fixture: 10 page requests within 60 s caused 3 upstream
  GETs, one per cache key (default bills, `OPEN_END` bills, results).
- JS-disabled Chromium at 390: `/el/bills` 10 cards and `/el/results` 12 cards.
- BEFORE raw HTML: no fixture titles; the bills page contains the skeleton.

## Freshness and fallback evidence (final head, local production build)

The perf table above and the raw-HTML list come from commit `b88fd622`. They were not
re-measured. The freshness check adds only a header comparison to the seeded path.
The following checks were rerun on the final head (`next build` + `next start`,
local fixture only):

- **Real elapsed time, Node fixture `Date` header:** the first render caused one upstream
  GET per key, and the next 4 renders per page were cache hits with no upstream GET.
  The cached entries in `.next/cache/fetch-cache` keep the origin `Date`. Then the API
  hid one result and answered 503. At t+66 s the stale entry (under 120 s old) was
  still rendered, including the hidden result. Next made one background refresh per
  request, and each refresh failed. Then the API was taken down. At t+130–144 s, with
  the API down or answering 503, `/en/results` and `/en/bills` raw HTML had no fixture
  cards. They showed the loading state, never "no results". After the API recovered,
  the first render was still `null` and started the refresh, and the next renders
  showed fresh data without the hidden result. Over 13 SSR page renders,
  each key caused at most one upstream GET per page render.
- **Backdated origin `Date` (−200 s, fixture switch):** once a refresh stored the
  backdated body, raw HTML had no cards and the client made one fallback GET and
  rendered all cards (390 and 1280). Without JS, the page showed the loading state.
- **Page-return bound:** with the API answering after 10 s on an uncached key, the
  page returned in 3.04 s without cards. The background refresh is not bounded.
- **Locale:** with 25 800 votes, `/el/results` shows `25.800` in an `en-US` browser and
  `/en/results` shows `25,800` in an `el-GR` browser, with and without JS, and there
  are no hydration errors.
- **Controls:** 390 and 1280, EL and EN. Seeded cards are present, there is no mount
  fetch, a status change makes one fetch, page 2 and the results filter, sort and links
  work, and there is 0 px horizontal overflow.

Raw JSON, screenshots and traces stay private and are not committed.

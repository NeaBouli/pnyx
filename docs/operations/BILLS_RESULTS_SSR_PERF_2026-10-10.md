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
  `next.revalidate = 60`, `AbortSignal.timeout(3000)`, only an `Accept` header and
  no cookies. The origin is the existing `API_URL`.
- Bills are prefetched only for the five known `?status=` values. Unknown values
  take the previous client-only path, so the number of server cache keys stays bounded.
- On a non-2xx response, a network error, a timeout or a malformed body, the
  server passes `null` and the client mount fetch runs as before. A failure is
  never shown as an empty list.
- **Staleness:** SSR HTML can be up to 60 s (+3 s timeout) behind the API. The API's
  #456 result-visibility rules still decide what is published, but a hide can
  reach the SSR HTML up to about 60 s late.

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

**Not shown:** an LCP improvement. In this fixture the LCP element is a text
paragraph that paints at FCP in both builds, and FCP/LCP vary by ±0.5 s
between samples. /results AFTER can paint slightly later because the HTML is larger. Production LCP depends on real
API latency, real content and server cache state, and has not been measured here.

## Raw HTML / cache evidence (AFTER, `curl`, no JS)

- `/el/bills`, `/en/bills`, `/el/bills?status=OPEN_END`: fixture bill titles are
  present and the loading skeleton is absent. `/el/results` and `/en/results`: fixture result titles are present.
- `/el/bills?status=BOGUS`: skeleton present, no server fetch (client path).
- Upstream counts at the fixture: 10 page requests within 60 s caused 3 upstream
  GETs, one per cache key (default bills, `OPEN_END` bills, results).
- JS-disabled Chromium at 390: `/el/bills` 10 cards and `/el/results` 12 cards.
- BEFORE raw HTML: no fixture titles; the bills page contains the skeleton.

Raw JSON, screenshots and traces stay private and are not committed.

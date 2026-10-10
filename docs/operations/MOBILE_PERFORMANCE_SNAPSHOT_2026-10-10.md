# Mobile performance snapshot — 2026-10-10 (T-9063)

Observational, read-only lab snapshot of five public production pages viewed by
an anonymous browser at 390 px width under declared throttling. This is **not** a
Lighthouse run, there is **no score**, and these are **not** Core Web Vitals
field values (CWV are percentiles from real users). Each value comes from one
navigation in one run. No production change was made.

## Method

| Item | Value |
|---|---|
| Run window (UTC) | 2026-10-10 11:02:37 → 11:03:30 (52 s total browser run) |
| Browser | Chromium 153.0.8010.12 headless, via cached Playwright 1.63.0 (nothing installed) |
| Context | One fresh anonymous non-persistent context: no cookies, no profile, no login, TLS checks on |
| Viewport | 390×844, DPR 3, `isMobile`, `hasTouch`, locale `el-GR` |
| Network (CDP `Network.emulateNetworkConditions`) | latency 150 ms, download 204 800 B/s (200 KiB/s), upload 76 800 B/s (75 KiB/s) |
| CPU (CDP `Emulation.setCPUThrottlingRate`) | 4× |
| Cache | Shared across the sequence: page 1 was cold, pages 2–5 could reuse cache (mixed cold/warm) |
| Window per page | `goto` until `domcontentloaded` (30 s deadline), then exactly 8 s settle, then one read-only `performance` read |
| Interaction | None: no taps, form fills, submits, votes, downloads or SSO |
| Request policy | Only GET/HEAD to `ekklesia.gr` / `api.ekklesia.gr`; admin/auth/identity/agent/claude/translate/provider/checkout/webhook/login/sso/vote paths blocked; caps 10 documents / 20 API GETs / 200 resources |
| Budget used | 5 documents, 16 API GETs, 91 resources; cap not reached; 0 redirects; 0 retries |

Metrics come from the Navigation Timing, Paint Timing, `largest-contentful-paint`,
`layout-shift` and `longtask` APIs. LCP is the last candidate seen inside the
8 s window. "Bytes (CDP)" is the sum of `encodedDataLength` over requests that
reported one; this may include cache-served responses. Requests with no value
are counted as unknown, not as zero. Raw metrics and the request list stay private
and are not committed. URLs below are origin and path only.

## Results

All times are in ms from navigation start.

| # | URL | HTTP | TTFB | FCP | DCL | LCP (observed) | CLS (observed) | Long tasks (count / ms) | Requests (API) | Bytes (CDP), known / unknown records |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | https://ekklesia.gr/ (cold) | 200 | 1423 | 2992 | 3929 | 2992 | 0 | 1 / 139 | 15 (3) | 1 573 611 B, 15 / 2 |
| 2 | https://ekklesia.gr/el/bills | 200 | 405 | 1732 | 1496 | 5976 | 0.037 | 6 / 1469 | 29 (3) | 311 169 B, 27 / 2 |
| 3 | https://ekklesia.gr/wiki/index.html (substitute, see below) | 200 | 125 | 536 | 528 | 536 | 0 | 2 / 223 | 5 (0) | 1 393 378 B, 5 / 0 |
| 4 | https://ekklesia.gr/el/results | 200 | 583 | 1660 | 1654 | 4892 | 0.132 | 1 / 51 | 29 (2) | 285 885 B, 25 / 4 |
| 5 | https://ekklesia.gr/community.html | 200 | 123 | 1328 | 1747 | 1328 | 0 | 0 / 0 | 13 (8) | 1 417 736 B, 13 / 3 |

Notes:

- **Bill detail substituted.** The rendered `/el/bills` page had no
  `/el/bills/<id>` anchor in its DOM after the 8 s window. As the brief requires,
  `/wiki/index.html` was measured in its place, with no extra API probe. Later,
  `/el/results` did render detail anchors. An absent selector does not establish
  whether list rendering was late or whether its links use different markup.
- On `/el/bills` the FCP (1732) is later than DCL (1496) because the client
  may render after DOMContentLoaded; paint timing alone does not establish the cause.
- `load` event: 9487 (home), 3330 (bills), 7274 (wiki), 2388 (results),
  7401 (community).
- Every non-document response was HTTP 200. No genuine production errors were seen.
- One EventSource (`api.ekklesia.gr/api/v1/notifications/stream`) opened on each
  Next.js page (bills, results).
- One-off lab numbers vary between runs. Do not treat them as a baseline without
  repeated runs.

### Blocks caused by the measurement (not production faults)

| Page | Blocked request | Reason |
|---|---|---|
| home | `api.ekklesia.gr/api/v1/vote/results/latest`, `/api/v1/vote/results/in-progress` | Probe deny-list matched `/vote/` (these are public GETs; the deny-list was conservative) |
| community | `api.coingecko.com/api/v3/simple/price` | Origin not on the allowlist |
| community | `api.ekklesia.gr/api/v1/identity/hlr/credits`, `/api/v1/claude/budget` | Probe deny-list (identity/claude) |

These blocks mean home and community did less API work than a real visitor would
trigger, so their numbers may be slightly optimistic. `net::ERR_ABORTED` on
`/el/mp`, `/el/bills`, `/el/results` and `/el/bills/GR-b36e777b` were Next.js
link prefetches cancelled by the next navigation. They are not server failures.

## Production build identity

Not verified. The source here is `63924b53`. The last owner-confirmed live
receipt was `550549c7`. This snapshot makes no claim about which commit is
serving production.

## Quick-win proposals (not implemented; each needs its own point)

1. **`docs/pnx.png` is 1 379 712 B (1024×1024) but is shown at 40–64 px.**
   Measured: home, wiki and community each report about 1.39–1.57 MB, and
   `pnx.png` is the only large file shared by all three. On wiki it is the only
   image. At 200 KiB/s this is several seconds of transfer.
   - Source hops: `docs/index.html` (logo `<img>` and footer 64 px `<img>`,
     `apple-touch-icon`), `docs/wiki/index.html` nav logo,
     `docs/community.html` nav logo. Served from `docs/` via the Web Docker
     static COPY.
   - Proposal: add a small derivative (e.g. 128/192 px PNG or WebP, along the
     lines of the existing `docs/favicon-192.png`) and point the nav and footer
     `<img>` at it. Keep the 1024 px file for the JSON-LD `logo`.
   - Benefit hypothesis: far fewer bytes on every static page and earlier `load`.
     Not measured.
   - Required for a future point: redesign hash and inventory updates if HTML
     changes, the existing `scripts/redesign/*` checks, UI at 390 and 1280, then
     a fresh measurement with the same method.
2. **`/el/bills` and `/el/results`: LCP is about 3–4.3 s after FCP, and bills
   had 6 long tasks totalling 1469 ms.** The client renders the list after
   its own rendering path; hydration/fetch causality is unverified. Hypothesis: server-render or stream the
   first page of bills so the LCP element is in the HTML. This needs a source
   analysis of the `apps/web` bills/results pages first. It is not a trivial
   quick win and no patch is proposed here.
3. **`/el/results` CLS 0.132 within 8 s** (above the 0.1 "good" threshold, one
   lab sample). Hypothesis: reserve space for the late list or cards. The
   shifting element was not identified; attributing it needs a `layout-shift`
   sources capture in a later run.
4. **Measurement hygiene.** Rerun with `/vote/results/*` GETs allowed, take a
   median of 3+ runs, and add a bill-detail page found from `/el/results`.

## Not checked

Field CWV and traffic popularity of routes, WebKit/Firefox, 1280 px, a fully
cold cache per page, the actual bill detail page, server-side timings, and
whether the measured build matches any given commit.

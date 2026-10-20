# Enforced CSP observation — T-9156

`scripts/csp-observe.mjs` observes the deployed policy without changing it. Only
gio-dd may run production observation. Agents must use the offline commands below;
no production observation was performed while implementing this tool.

## Run

Use Node.js 22 and an already installed Playwright with Chromium and WebKit
binaries (Playwright 1.48+ is needed for WebSocket routing). The module is loaded
from `PLAYWRIGHT_MODULE` when set, otherwise from `playwright` using Node module
resolution. The environment variable accepts an absolute module directory or file.
The observer never installs packages or downloads browsers.

These commands need neither Playwright nor network access:

```sh
node --test scripts/csp-observe.check.mjs
node scripts/csp-observe.mjs --list
node scripts/csp-observe.mjs --help
```

The default invocation is also a local-only page list. `--observe` explicitly
enables browsing. **For gio-dd only**, with an existing Playwright installation:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/node_modules/playwright \
  node scripts/csp-observe.mjs --observe --out-dir /tmp/csp-observation
```

Every public `<loc>` in the local `docs/sitemap.xml`, its locale alternates,
`/el`, `/en`, `/el/bills`, `/el/results`, `/en/analytics`, `/tickets/`, and every
local `docs/wiki/*.html` page is visited in both Chromium and WebKit at widths
390 and 1280 pixels. Paths are deduplicated; queries and fragments are removed.
The sitemap is read from disk, not fetched. The observer reads public anchor URLs
on `/el/bills` to find one bill detail without clicking. To select a known public
bill instead, add `--bill-path /el/bills/ACTUAL_PUBLIC_ID` (replace the placeholder).
A discovered detail is included in each subsequent browser/width pass. If discovery
succeeds only in a later pass, the observer fills the missing detail visits in the
earlier combinations. If no detail link is found, coverage is incomplete; rerun
with an explicit public detail path.

Visits are sequential, with a fresh anonymous context for every page. The default
observation window is three seconds after `load`; `--settle-ms 10000` allows more
time for asynchronous scripts. Navigation times out after 30 seconds; individual
resource fetches time out after 15 seconds. There are no clicks, form input,
scrolling, login, voting, persistent profiles, or imported browser state.

Outputs in the chosen local directory:

- `csp-observation.json`: normalized observations and counts, browser/width counts
  per observation, and visit coverage including HTTP status and presence of both
  policy headers. `pagePaths` and `matrix` describe intended coverage.
- `csp-observation.md`: counts grouped by directive and source path/line, with DOM
  events and console diagnostics separated, plus the coverage table.

Exit status is zero only when every intended visit succeeds, every visit has a
Content-Security-Policy response header, no Content-Security-Policy-Report-Only
header, and a bill detail was covered in all four combinations.
Violations themselves do not cause failure: they are the observation result.
Partial results are written if a browser fails after observation starts. A missing
module, invalid argument, or unreadable local input fails before browsing; the CLI
emits a generic error so raw browser errors cannot expose URLs or local user paths.

## Data minimisation

The observer collects no PII, account identifiers, cookies, form contents, page
bodies, screenshots, traces, console arguments, or complete console messages in its
output. It records only the visited page path, directive names, blocked resource
origin, source file path, positive source line (or zero when unavailable), a short
code sample, disposition, and aggregate counts. Query strings, fragments,
credentials and blocked resource paths are discarded before aggregation. Opaque
URLs such as `data:` are recorded as an empty blocked URI; `inline` and `eval`
remain literal markers, and `blob:` retains only its embedded origin.

The sample comes only from the DOM event's `sample` (`script-sample`), never from
the page body or console. String/template literals, URLs and email addresses are
redacted before retaining at most the first 40 characters. With the current
policy, samples may be empty because `report-sample` is not configured. Full policy
strings, nonces, hashes, referrers and error messages are not retained. The browser
must transiently receive public pages and resource responses to render them; those
responses are not saved in artifacts.

Nothing collected is sent anywhere: the binding passes event fields directly to
the local Node process in memory, and both artifacts stay on disk. There is no
report receiver, telemetry, upload, or CSP/header change. Browsing itself makes
only read-only HTTPS GET requests to the exact `https://ekklesia.gr` origin,
including public assets and public GET APIs used by those pages. Other origins
(including `api.ekklesia.gr`), non-GET requests, authentication/account/voting
paths, WebSockets, and service workers are blocked. Request cookies, authorization
and referrers are stripped, response `Set-Cookie` is removed before browser
fulfillment, and page scripts cannot read or write cookies. Query parameters needed
by the page's public resource GETs may travel to that origin but are never logged.

Redirects are fetched one step at a time with the same allowlist and header
stripping, with a maximum of five hops. The final response is fulfilled at the
original requested URL, so a path-changing redirect can affect relative resource
resolution; the coverage table counts redirects. Prefer a final canonical path
when investigating such a page. Response bodies and both CSP headers are preserved.

## Reading results against the inventory

Use [CSP_INVENTORY.md](CSP_INVENTORY.md) from the same checkout as a source index;
deployed HTML line numbers can differ from this checkout. `effectiveDirective`
identifies the blocked action; `violatedDirective` records the browser's reported
directive. `sourceFile` contains only a path and `line` is one-based (console
locations are converted from Playwright's zero-based line numbering).

| Observation | Inventory item / follow-up |
| --- | --- |
| Static HTML `script-src-elem` / `script-src`, `blockedURI: inline` | For pre-migration runs, match the old path/line to `scripts/csp-migration.json`. `/` maps to `docs/index.html`; `/tickets/` maps to `docs/tickets/index.html`. The current inventory permits no executable static inline blocks. |
| `script-src-attr`, `inline` | Current controls use data attributes and external listeners. A new inline-attribute violation indicates stale HTML or a regression. Load-only observation does not exercise all controls. |
| Ticket-generated handlers | `docs/tickets/polis.js` and tickets-board.js now emit data attributes. Runtime lines can identify the document/insertion site rather than the template line. Public data from blocked external origins may not render. |
| `/el`, `/en`, locale bills/results/analytics; bootstrap or Flight snippets | Match “Next.js nonce and rendering”. Bootstrap/Flight scripts must carry the response nonce, and the dynamic header must survive Traefik. React callback props are not string handlers. |
| `docs/legal.html` or `docs/municipality/article.html` inline block | These blocks now load legal-language.js and municipality-article.js. The old inline hashes have been removed from the target. |
| JSON-LD source line | JSON-LD is inert data and needs no script authorization; retain it inline and distinguish it from nearby executable scripts. |
| Other directives or blocked origins | Review the inventory's enforced policy/rollback strategy and “Evidence and regression checks”, including the representative app on the shared origin. Scheme/opaque resource details are deliberately unavailable. |

DOM events are captured using `addInitScript` before application code and the
`securitypolicyviolation` listener. `disposition: report` belongs to Report-Only;
`enforce` belongs to the active enforced policy. New responses should have no
Report-Only header; historical report dispositions remain readable. Console messages mentioning
Content-Security-Policy / Content Security Policy are a second evidence channel:
only recognizable fields are extracted; unavailable directive/source fields stay
empty, and an ambiguous disposition is `null`. They can duplicate DOM events and
must not be added to event counts to estimate unique violations. The markdown
summary groups by effective directive (falling back to violated directive), source,
evidence channel and disposition; JSON also distinguishes blocked origins/samples.

This is load-time coverage of public routes under the restricted request policy.
Blocked dependencies, unclicked handlers, deferred/lazy interactions, translations,
service worker updates and authenticated pages remain outside that coverage. Zero
observations alone do not validate all interactions; review the coverage/header
tables and supplement load-time coverage with the checks below.

## Current policy and deployment

Production already ran with the strict target enforced through the old overlay;
the owner reported zero observed violations. T-9156 folds that enforcement into
`docker-compose.prod.yml` and removes the duplicate Report-Only header. This
change performs no deployment or new production observation. The old
`docker-compose.csp-enforce.yml` is a compatibility no-op, so existing deployment
commands can continue to include it.

| Surface | Enforced `script-src` | Additional directives |
| --- | --- | --- |
| Static HTML, Traefik `ekklesia-static-csp` | `'self'` | `font-src 'self'; object-src 'none'; base-uri 'self'` |
| Embed HTML, Traefik `ekklesia-embed-csp` | `'self'` | Same strict directives; `frame-ancestors *` |
| Next HTML, `src/proxy.ts` | `'self' 'nonce-<fresh 256-bit value>'` | Same strict directives; `frame-ancestors 'none'` |

Every response must contain exactly one Content-Security-Policy header and no
Content-Security-Policy-Report-Only header. The general Next router has no Traefik
CSP writer. Static and embed routers each attach their own single CSP writer,
which replaces Next's fallback response policy. The embed router has no
X-Frame-Options; arbitrary parents and the QR child's ancestor chain remain allowed.
Static and dynamic non-embed pages retain frame-deny and `frame-ancestors 'none'`.
Inline styles remain allowed. Scripts have no `unsafe-inline`, `unsafe-eval`,
`unsafe-hashes` or `strict-dynamic` allowance.

Next enforces unless `CSP_ENFORCE` is explicitly `false`. Its proxy replaces
untrusted request CSP/nonce values and forwards a fresh nonce policy through
next-intl so bootstrap, Flight and streaming scripts match the response CSP.
`next.config.mjs` retains the legacy response fallback for assets, redirects and
runtime rollback; middleware replaces it on dynamic responses by default.
Never emit the legacy policy from the proxy in rollback mode: Next's router would
copy it over the nonce-bearing render request policy.

For **gio-dd**, use the usual deployment env-file path (from the repository root):

```sh
docker compose --env-file infra/docker/.env \
  -f infra/docker/docker-compose.prod.yml \
  up -d --no-deps web
```

Including the old enforce overlay has no effect. Verify the single enforced
header on landing, wiki, ticket, embed and Next HTML responses, absence of
Report-Only, and fresh matching bootstrap/Flight nonces on repeated Next responses.
The observer now requires an enforced header and rejects Report-Only duplicates.
The WebKit warning about Report-Only without report-to is removed at its source;
no report receiver was added. Historical Chromium diagnostics still use the
narrow missing-receiver warning filter; actual violation events are retained.

To roll back **Next** enforcement without rebuilding, recreate `web` with an
explicit false value (the base Compose environment forwards it):

```sh
CSP_ENFORCE=false docker compose --env-file infra/docker/.env \
  -f infra/docker/docker-compose.prod.yml \
  up -d --no-deps web
```

This restores the legacy enforced Next response policy, keeps nonce rendering
and private/no-store caching, and emits no Report-Only header. It does not relax
static/embed edge enforcement. If edge rollback is required, override only the
two existing `contentSecurityPolicy` labels with the legacy values from
`apps/web/csp.mjs`, replacing `frame-ancestors 'none'` with `frame-ancestors *` for
embed. Keep one writer per router and no Report-Only labels. Removing the old
no-op overlay does not roll back enforcement.

Static docs have no executable inline blocks or string handlers. JSON-LD remains
inert inline data. Local font fallbacks require no external font origins. All
locale routes render per request, including dotted bill identifiers and unknown
localized routes. PWA start-URL/navigation caching is disabled; HTML/Flight must
never be served from old document caches. Confirm worker activation with both a
clean browser and an upgraded existing profile, and keep dynamic HTML out of any
proxy/CDN document cache.

The restricted observer cannot validate all interactions or authenticated flows.
Supplement observation with hydration/navigation, error and streamed responses,
language controls, FAQ/roadmap, legal/contact modals, newsletter/chat, ticket
login/QR/create/vote, embed and representative controls, and service-worker
upgrade checks.

## Targeted offline gates

These checks need no downloads or network:

```sh
python3 -m unittest scripts/redesign/test_csp_inventory.py
python3 scripts/csp-inventory.py --check
node --test scripts/csp-observe.check.mjs scripts/csp-docs.check.mjs
(cd apps/web && npm test -- src/proxy.nonce.test.ts src/next-config.csp.test.ts src/lib/csp.test.ts src/static-docs.csp.test.mjs)
```

With an **already installed** Playwright and browser binaries, the optional docs
browser regression fulfills requests from local files or aborts them, with no
HTTP fetches. It checks JSON-LD, EL/EN, FAQ and generated demo controls under a
single enforced policy:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/existing/playwright \
  node --test scripts/csp-docs.check.mjs
```

The production render gate below checks unset/default, explicit true and explicit
false rollback using Next's real router. It asserts exactly one enforced response
policy, absence of Report-Only, matching fresh HTML/Flight nonces, and private
no-store behavior in every mode. Run it after a production build with the pinned
dependencies. Local environments may have older installed dependencies; report
the versions used and any unavailable build/browser validation.

## Second-review checks (#638)

Compared `git show origin/main:<page>` at local `4ff02f8c` for all 13 extracted
language scripts (including the prior external mirror script). The old toggles
initialize Greek and never read/write localStorage. No persistence regression
occurred; adding persistence would change the old behavior. Landing also used
`textContent` before extraction, deliberately keeping attribute text literal.
The language regression tests pin those defaults and both toggle directions.

Every external classic script now uses `defer`, including config/vendor scripts,
in its original dependency order. Optional initialization nodes have null guards.
The dispatcher runs only the nearest matching action. Embed API titles, pills,
statuses and result fields use text nodes; numeric widths are finite and clamped.
QR credentials target the same-origin parent explicitly; the receiving widget
requires both that origin and its actual QR child window. Vote notifications use
the embedding page's referrer origin and are omitted when that origin is absent.

`createNonce()` uses Web Crypto `getRandomValues` on 32 bytes (256 bits, exceeding
the 128-bit minimum), once per matched request. No report endpoint exists;
observation still records browser violation events instead of sending reports.
All Next pages inherit `force-dynamic` from `[locale]/layout.tsx`, with no child
static/ISR override: `/el` and `/en`, and both locales' `bills`, `bills/[id]`,
`results`, `analytics`, `municipal`, `mp`, `admin`, and `sso-verify` pages. Unknown
localized routes render dynamic errors. Static docs and their redirects have no
nonce. `private, no-store` on dynamic HTML/Flight is intentional: this gives up
full-page and downstream document caching; static assets retain their caching.

Targeted regressions are `apps/web/src/{proxy.nonce,lib/csp,next-config.csp}.test.ts`,
`apps/web/src/static-docs.csp.test.mjs`, `scripts/csp-docs.check.mjs` and
`scripts/redesign/test_csp_inventory.py`.
The Workbox test runs real `generateSW` and checks the generated route registrations,
rather than only mocking its schema. The Compose gate checks default strict
policies and embed framing, rejects Report-Only and duplicate/shared CSP writers,
and requires the compatibility overlay to remain a no-op.

The production renderer check uses Next request/response mocks and the compiled
proxy, without listening on a socket or making HTTP requests:

```sh
NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 node --test scripts/csp-render.check.mjs
```

Run this after the web production build. It checks two sequential renders each
for bills, SSO, analytics and an unknown localized URL in default, explicit true
and rollback modes. Every HTML/Flight script must match the fresh proxy nonce;
responses must have private/no-store caching and no `x-nextjs-cache` HIT/STALE.
The build manifest must not prerender any locale route. Unknown localized paths
use the catch-all under the dynamic locale layout so error scripts also carry
the response nonce.

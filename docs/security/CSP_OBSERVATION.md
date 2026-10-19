# CSP Report-Only observation — T-9141

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
Report-Only response header, and a bill detail was covered in all four combinations.
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
| Other directives or blocked origins | Review the inventory's policy/promotion strategy and “Evidence and rollout gate”, including the representative app on the shared origin. Scheme/opaque resource details are deliberately unavailable. |

DOM events are captured using `addInitScript` before application code and the
`securitypolicyviolation` listener. `disposition: report` belongs to Report-Only;
`enforce` belongs to the existing enforced policy. Console messages mentioning
Content-Security-Policy / Content Security Policy are a second evidence channel:
only recognizable fields are extracted; unavailable directive/source fields stay
empty, and an ambiguous disposition is `null`. They can duplicate DOM events and
must not be added to event counts to estimate unique violations. The markdown
summary groups by effective directive (falling back to violated directive), source,
evidence channel and disposition; JSON also distinguishes blocked origins/samples.

This is load-time coverage of public routes under the restricted request policy.
Blocked dependencies, unclicked handlers, deferred/lazy interactions, translations,
service worker updates and authenticated pages remain outside that coverage. Zero
observations do not establish readiness to enforce the candidate policy; retain the
inventory's remaining work and review the coverage/header tables first.

## T-9149: next observation and promotion

Run 2 covered 132 visits in Chromium/WebKit at 390/1280. It predates the
externalization and nonce work. Its script violations map to the migrated docs
assets and Next bootstrap; the municipality style violations came from Google
Fonts links, now removed in favor of the existing local fallbacks. No JSON-LD
source lines were reported as script violations; those 26 inert data blocks stay
inline with their exact original bytes. New SSO script requests also set
`referrerpolicy="no-referrer"` so the verification nonce query does not reach
asset-request referrers. A new observation is required for this revision before
enforcement.

The target header now has these differences from the original enforced policy:

| Surface | `script-src` | Additional directives |
| --- | --- | --- |
| Static HTML, Traefik `ekklesia-static-csp` | `'self'` | `object-src 'none'; base-uri 'self'` |
| Next HTML, `src/proxy.ts` | `'self' 'nonce-<fresh 256-bit value>'` | `object-src 'none'; base-uri 'self'` |

The two old static script hashes are gone. Every other directive is preserved,
including `frame-ancestors 'none'` and inline **styles**. Scripts have no
`unsafe-inline`, `unsafe-eval`, `unsafe-hashes` or `strict-dynamic` allowance.
The existing enforced header remains unchanged in the default production Compose
configuration. Dynamic responses carry their own nonce Report-Only header; a
shared fixed target at Traefik would overwrite it and block Next bootstrap.

Next 16's proxy forwards the nonce and CSP through next-intl's request-header
updates. The renderer reads the request CSP and stamps bootstrap/Flight scripts.
There are no authored inline scripts or `next/script` components; future ones
must receive `(await headers()).get('x-nonce')` as their `nonce` prop. The locale
layout is `force-dynamic`, so formerly static client routes render per request.
Nonce-bearing HTML cannot use prerender/ISR document caching; current SSR data
fetches already use `no-store`. Static docs remain static and need no nonce.
Bill detail identifiers containing dots also pass through the proxy matcher.

PWA configuration now uses the plugin's supported `workboxOptions` nesting.
Start-URL and navigation caching are disabled, HTML is excluded from precaching,
and the same-origin runtime rule accepts only script/style/image/font requests.
It never reads cached document or Flight responses. Before promotion, confirm
the new service worker has activated and repeat checks with a clean browser and
an existing profile upgraded from the previous worker. Avoid caching dynamic
HTML at another proxy/CDN layer.

The observer ignores Chromium's specific “Report-Only has no report-uri / no
effect” configuration warning, which is not an execution violation. Run 2 also
has 66 `default-src` console diagnostics; the aggregate omits raw messages, so
their cause cannot be conclusively classified. This warning is one possible
source. The new filter matches only that specific warning; real DOM events and
script refusal messages are still collected. No report endpoint was added.
Compare DOM events and console evidence separately.

Additional offline checks (no downloads or network):

```sh
python3 scripts/csp-inventory.py --check
node --test scripts/csp-observe.check.mjs scripts/csp-docs.check.mjs
```

With an **already installed** Playwright and browser binaries, the optional docs
browser regression fulfills every request from local files or aborts it; it
performs no HTTP fetches. It checks JSON-LD, EL/EN, FAQ and generated demo controls
first with Report-Only and then enforcement:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/existing/playwright \
  node --test scripts/csp-docs.check.mjs
```

The local macOS sandbox denied Chromium's Mach port during launch, so this browser
regression could not run here. Dependency-free listener tests and Next middleware /
actual Flight-stream emission tests ran offline. The available dependency tree
uses Next 16.3.8 and Vitest 5.0.2; the repository pins Next 16.4.1 and Vitest 5.0.4.
No package installation or production build was attempted. Run the browser checks
and a production render with pinned dependencies before approving enforcement.

For **gio-dd**, after deploying the default Report-Only revision, rerun the
observation command above. Require complete coverage, matching target headers,
zero actual violations, and successful hydration, navigation, errors and streamed
responses. Supplement load-only observation with language, FAQ/roadmap, legal and
contact modals, newsletter/chat, ticket login/QR/create/vote, embed and
representative controls, plus service-worker upgrade checks. The restricted
observer blocks third-party API requests and does not exercise authenticated
flows; zero load-time observations alone cannot validate those interactions.

Only in a separate deploy after that evidence, add the override **after** the
production Compose file (run from the repository root):

```sh
docker compose --env-file infra/docker/.env \
  -f infra/docker/docker-compose.prod.yml \
  -f infra/docker/docker-compose.csp-enforce.yml \
  up -d --no-deps web
```

Use the deployment's usual env-file path if different. The override merges
mapping labels: it disables the shared legacy CSP writer, enables the static
strict enforced header and sets `CSP_ENFORCE=true` for Next's nonce-aware enforced
header. Both surfaces keep their Report-Only target. Confirm both final HTTP
headers; Next's nonce must match its bootstrap/Flight script attributes and change
on repeated responses. Roll back by recreating `web` with only the base production
file. Nothing in T-9149 promotes enforcement or deploys these changes.

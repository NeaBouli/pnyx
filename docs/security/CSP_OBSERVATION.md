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
| Static HTML `script-src-elem` / `script-src`, `blockedURI: inline` | Match `docs` + source path and nearby line to “Every remaining block and handler”. `/` maps to `docs/index.html`; `/tickets/` maps to `docs/tickets/index.html`. Externalize the listed executable block, preserving order and globals. |
| `script-src-attr`, `inline` | Match literal handlers or generated handler sites. Move to listeners or delegation. Load-only observation does not trigger all handlers; their absence here does not clear inventory items. |
| Ticket-generated handlers | Check “Generated handlers in external docs scripts”, including `docs/tickets/polis.js`. Runtime lines can identify the document/insertion site rather than the template line. Public data from blocked external origins may not render. |
| `/el`, `/en`, locale bills/results/analytics; bootstrap or Flight snippets | Match “Next.js app inventory and nonce prerequisite”. Runtime bootstrap is response-dependent; plan the per-response nonce and rendering/cache work there. React callback props are not string handlers. |
| `docs/legal.html` or `docs/municipality/article.html` inline block | Compare the inventory's two approved stable hashes with deployed bytes. Their approved blocks should not violate; other blocks, including JSON-LD, are separate items. |
| JSON-LD source line | Match the separately listed inert JSON-LD item; retain SEO data and follow the inventory's hash guidance if authorization is required. |
| Other directives or blocked origins | Review the inventory's policy strategy and “Work remaining before enforcement”, including other HTML on the shared origin. Scheme/opaque resource details are deliberately unavailable. |

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

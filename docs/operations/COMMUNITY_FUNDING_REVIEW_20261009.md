# Community funding: bounded source review (2026-10-09)

Baseline: `03c4913fe9fb3f09d7015ab9d1b342e3c9048955`. Scope: the public
server/domain/reserve projection, its consumers in `docs/community.html`,
the bilingual cost labels, and paused payment links. No live payments,
Stripe API calls, production configuration changes, or deployment were performed.

## Findings

| Priority | Source evidence | Follow-up |
| --- | --- | --- |
| P2, display gap | `payment_status()` in `apps/api/routers/payments.py` returns a monetary `reserve`. `community.html::fetchPaymentStatus()` only consumes `server` and `domain`; the HLR "reserve" labels refer to provider credits, not this money. | Add an explicitly labelled monetary-reserve consumer with agreed wording and fixture-based browser tests. Do not infer a zero balance from the missing tile. |
| P2, inconsistent public cost basis (source fix merged, not deployed) | On the baseline, `public_finance_overview()` uses administrative `HETZNER_MONTHLY`, while allocation/status use `SERVER_COST_MONTHLY`. Different configured values give inconsistent cost/runway figures. | PR #503 (`ba7658a9`) merged after independent review and green CI; twelve mock cases verify public endpoint consistency. Administrative provider costs are unchanged. This report does not approve deployment or establish the actual CX43 invoice cost. |
| P3, untranslated label | The CX43 cost row contains literal `~€10/μ` without bilingual attributes. The English toggle therefore keeps the Greek month abbreviation. | Use explicit EL/EN month labels through the established content-review gates. |
| P3, unavailable-data ambiguity | `fetchPaymentStatus()` does not inspect `response.ok`; its catch keeps unmarked initial balances (`0/-10` for server and `0/-9.30` for domain). An unavailable endpoint can look like a known funding deficit. | Distinguish loading/unavailable from known balances; preserve the last valid snapshot on refresh failure. Test HTTP errors and transport errors separately. |
| Decision required, allocation policy | The allocation documentation describes overflow going to reserve, but `allocate_donation()` adds the overflow to the server bucket. | Obtain an explicit accounting-policy decision before changing allocation or published claims. This review does not move money or reclassify records. |

## Existing controls traced

- Funding links target `#payment-intake-paused` and carry `aria-disabled="true"`;
  the EL/EN pause notice explains the pending legal recipient and documentation.
- The webhook verifies signatures before converting the Stripe event to a dict.
  Closed intake rejects Checkout before recording; refund/dispute handling is
  separate. No signed event or customer record was fetched from a live account.
- Public projections filter for verified live support and exclude identity and
  provider-event fields. Source tracing is not a live accounting reconciliation.

## Verification status and gates

Source review completed. The local responsive-browser check is **BLOCKED / needs
validation**, not PASS. The prepared Playwright 1.62.1 harness supplies eleven
dummy responses for EL/EN at 390 and 1280 px, paused-link navigation and an
intentional payment-status HTTP 503. No successful document snapshot was obtained.

The first attempt failed because the toolchain mount did not resolve
`playwright-core`; the corrected mount resolved both packages at 1.62.1. The
second attempt closed the target during the first document navigation. An
instrumented third attempt successfully rendered a minimal DOM, then recorded
Chromium termination with **SIGXFSZ** during that navigation. Docker reported
`OOMKilled=false`; this was not the 150-second timeout. The offending browser
file is unidentified, so the source findings above are not browser reproductions.
An additional isolated retry served all three real local Redesign CSS files and
used the existing shared-memory budget instead of Playwright's
`--disable-dev-shm-usage` default, with every OS cap unchanged. It also terminated
with SIGXFSZ during the first navigation; no document/layout PASS was obtained.

All attempts used external networking disabled, read-only source/toolchain, an
empty environment with a dummy/scratch allowlist, unprivileged user, dropped
capabilities, no-new-privileges, 2 GiB memory, one CPU, 192-process limit, 256 MiB
shared memory and scratch budgets, 10 MiB per-file and 1024-open-file limits.
No control was relaxed to obtain a PASS. Early attempts stubbed the external and
local stylesheet responses, so they would not have proved the full layout even
without the crash; the final prepared harness serves the three local stylesheets.
Real fonts, live data and OEM/device
behaviour are outside this fixture check. No live accounting or layout receipt
is claimed.

Any HTML/content correction needs the existing content-review and successful
responsive-browser gates. Static docs are embedded
in the web image: a checkout update alone is not deployment, and a later web
rebuild/rollout needs its own approval and rollback/live-verification receipt.

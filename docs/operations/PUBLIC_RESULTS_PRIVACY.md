# Public vote results: small-cell suppression

ADR-007 S2 / EVA-006 / T-9128. Owner decision: Gio, 16 October 2026.

Set `PUBLIC_RESULTS_MIN_COUNT=10` in the **API process environment** to enable
this policy. Unset or `0` keeps legacy numeric values. A negative or malformed
integer disables it with a warning that never contains the supplied value.
The API reads the setting at response/publication time; no API migration is required.
The database monitor views embed their release threshold when reconciled:
before enabling/raising the API setting, update those views with the same k
using [DB_ROLES_RUNBOOK.md](DB_ROLES_RUNBOOK.md). Readers cannot override that database threshold.
The templates default to `0`; this change does not activate production.

## Response contract

Existing keys remain present. With the flag enabled, affected aggregate objects
add `suppressed: boolean` and `suppression_k: integer`. Suppressed numbers and
percentages are JSON `null`, never zero. CSV represents null as an empty field.
With the flag disabled, no suppression metadata fields are added, including
through the HTTP `BillResults` response model.

* One function (`services.small_cell.publishable_set`) selects publishable
  bills/scopes. Every choice cell in the combined population and in **each
  present source** (ordinary/Tier-1 and ZK, including enumerable receipts) must
  reach k. Zero choice cells in a present source count as small; a source with
  no votes is absent, so ordinary-only bills can qualify.
* If any check fails, the whole bill is suppressed: all choices, percentages,
  totals, tier subtotals and derived values are null. Its ZK enumeration and
  future ZK/Arweave publication are withheld. A token-based lookup of one's own
  receipt remains available.
* All derived outputs use only the publishable set: CPLM positions, voter and
  vote counts, caches and history; platform vote sums and timelines; rankings,
  divergence, representation, MP comparisons and exports. Suppressed bills
  never contribute to another bill's or the platform's aggregate.
* `suppressed` indicates withheld results. Nulls may be secondary suppression;
  clients show `—` and a withheld breakdown notice, without claiming every
  hidden cell itself has fewer than k votes.
* Dates, titles, parliament/authority votes, and other public metadata retain
  their previous meaning. Existing results-visibility checks still apply.

Example (k=10, choices 39/1/10/10, sources 59/1):

```json
{
  "yes": null, "no": null, "abstain": null, "unknown": null,
  "total": null, "yes_pct": null, "no_pct": null,
  "abstain_pct": null, "unknown_pct": null,
  "tier1_total": null, "zk_total": null,
  "suppressed": true, "suppression_k": 10
}
```

## Endpoint rules

| Surface | Rule and flag location |
| --- | --- |
| `GET /api/v1/vote/{bill}/results` | Full choice/source rule; flags at response root. `divergence=null` when choices are hidden. `representativity=null` when total is hidden, including its embedded total and participation percentages. Numeric fields are nullable in OpenAPI. |
| `GET /api/v1/vote/results/latest` | Total and choice percentages follow the rule; flags at root. No-result sentinel (`bill_id=null,total_votes=0`) remains unchanged. |
| `GET /api/v1/vote/results/in-progress` | Effective admission threshold is max(existing ticker threshold, k). Choice percentages follow the rule; flags on each bill. |
| `GET /api/v1/public/stats`; analytics `overview` turnout | Counters sum only bills with publishable all-time choice cells and total, before combining bills. Window counters additionally follow the time-complement rule below. Small/withheld counters are null; flags inside `stats` / `votes`. Overview hides both window counters if either is withheld, and hides the average when its total is hidden. |
| `GET /api/v1/public/bills/{bill}/results` | Full choice/source rule; flags inside `citizen_votes`. `divergence_score=null` when choices are hidden. |
| `GET /api/v1/analytics/votes-timeline` | Each daily bucket follows the full choice rule over the **all-time** daily partition, including days outside the requested window. If any day has hidden choices/totals, that partition is withheld throughout the bill series. Platform series exclude bills with suppressed cells **before** combining days across bills. Flags are per bucket. |
| `GET /api/v1/analytics/bill/{bill}` | Full choice/source rule in `votes`; divergence withheld with choices. Weekday counts retain the existing minimum 10, raised to k if larger; if any observed weekday is below that minimum, all observed weekday counts become null with per-row flags. |
| Analytics `divergence-trends`, `top-divergence`, `overview`, `representation`; public `representation` | Suppressed-choice bills contribute no divergence score or ranking entry; existing minimum 10 still applies. Representation's total excludes every suppressed bill. |
| `GET /api/v1/export/results.json` and `bills.csv` | Exclude suppressed bills first, independently of caller minimum. Apply `min_votes` only among publishable bills; probing different minima cannot reveal suppressed totals. Flags per row. While enabled, exports use combined Tier-1/ZK counts just like ordinary results (ZK only for Parliament), preventing subtraction between different populations. Flag off preserves legacy Tier-1 export behavior. |
| `GET /api/v1/export/divergence.csv` | Same admission rule, including `min_votes=0`; omit rows with suppressed/unavailable divergence. CSV adds suppression columns while enabled. |
| `GET /api/v1/municipal/{dimos}/voteable` | Three published choice cells and total follow the rule; flags inside each decision's `votes`. `/decisions` has no individual-vote aggregates. |
| `GET /api/v1/mp/bill/{bill}` | Full choice rule; flags in `citizen_votes`; hide majority, yes/no counts/share and party matches when the breakdown is suppressed. While enabled, counts use the same combined population as results. |
| MP `compare/{party}` and `ranking` | Suppressed-choice bills contribute no comparison/ranking entry; existing minimum 10 still applies. |
| Future aggregate Arweave audit snapshots | Same full choice rule and null divergence; flags in `citizen_votes`. Lifecycle publisher uses the combined public population while enabled. |

Future Telegram bill notifications and SSE milestones require a publishable bill. While enabled, monthly newsletters omit their separate vote-count table and turnout counter and link readers to the guarded public results.

Web bill reports/results and mobile results handle nullable values. A hidden
overall total is shown as `—`, or `< 10` when it is known to be below the
returned threshold; secondary suppression shows a withheld breakdown notice.

## Time windows and release policy

Flag-enabled windows use UTC calendar-day boundaries. Before publishing any
`last_7_days`, `today`, or daily-series window, evaluate the all-time partition
for the same bill/population. For each cell, all-time minus window must be at
least k; an empty complement is exempt because no complement cell is released.
A zero observed choice cell is still suppressed under the ordinary choice rule.
If a nonempty complement is below k, withhold the window value as JSON null.
Overview withholds both window counters if either is unsafe.

The daily partition is evaluated over **all history**, then sliced for the
requested series. A suppressed daily choice hides choices in every window;
a suppressed daily total hides totals in every window. Platform sums exclude
such bills before combining. This deliberately conservative release policy
covers successive and overlapping window queries on unchanged data: different
window lengths must not select different suppression baselines or release a
small daily difference. Empty dates are not published as numeric zero buckets.
CPLM points and historical snapshots are computed only from publishable bills,
and additionally require at least k distinct voters; otherwise
coordinates, counts, quadrant and trend are null with suppression metadata.
Flag-enabled CPLM caches/history use a new `publishable-v1` namespace per k;
legacy snapshots without this policy envelope are withheld. Flag-off cache keys
and response bytes remain unchanged.

## Scope and remaining limits

Evaluation aggregates (existing k=10), consensus (own minimum), signed personal
reads, authenticated representative reads, and admin outputs are unchanged.
Single ZK receipt lookup by its own token remains available; public enumeration
and future Arweave publication follow the full per-choice/source rule above.

This is suppression at publication time, not differential privacy. Previously
published exports, cached responses and immutable Arweave records cannot be
retracted or made private by this flag.
Changing the flag on a live deployment requires an operational review of old
publications and caches. Residual risk remains from observing changes over time:
exact outputs at/above k can change as votes arrive, and differencing releases on changing data is not
prevented by this policy. This is not a historical-release privacy budget.

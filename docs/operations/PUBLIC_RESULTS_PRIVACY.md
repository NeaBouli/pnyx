# Public vote results: small-cell suppression

ADR-007 S2 / EVA-006 / T-9128. Owner decision: Gio, 16 October 2026.

Set `PUBLIC_RESULTS_MIN_COUNT=10` in the **API process environment** to enable
this policy. Unset or `0` keeps legacy numeric values. A negative or malformed
integer disables it with a warning that never contains the supplied value.
The setting is read at response/publication time; no migration is required.
The templates default to `0`; this change does not activate production.

## Response contract

Existing keys remain present. With the flag enabled, affected aggregate objects
add `suppressed: boolean` and `suppression_k: integer`. Suppressed numbers and
percentages are JSON `null`, never zero. CSV represents null as an empty field.
`BillResults` always includes the two metadata fields (false/0 when disabled).

* Counts below k, **including zero**, are small cells. If any choice is small,
  **all** choice counts, percentages, and derived citizen majorities/divergence
  are withheld. This includes UNKNOWN where the population supports that choice.
* The overall total is published exactly only when it is at least k. It may
  remain visible when choices are withheld: no other choice count/share is
  available to subtract from that total.
* Tier-1 and ZK totals form a separate partition. If either is below k, **both**
  are withheld to prevent recovering one from the total minus the other.
* `suppressed` indicates at least one withheld field, not necessarily a hidden
  total. A particular null can be **secondary** suppression even if that cell
  has at least k votes. Clients must not label every null choice as "< k";
  show a withheld breakdown notice. A null per-bill overall total means "< k";
  null timeline totals can also be complementary suppression of larger days.
* Dates, titles, parliament/authority votes, and other public metadata retain
  their previous meaning. Existing results-visibility checks still apply.

Example (k=10, choices 39/1/10/10, sources 59/1):

```json
{
  "yes": null, "no": null, "abstain": null, "unknown": null,
  "total": 60, "yes_pct": null, "no_pct": null,
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
| `GET /api/v1/public/stats`; analytics `overview` turnout | Counters sum only per-bill totals at/above k in their requested window, so subtracting visible bills cannot recover a below-k bill total. Small counter values are null; flags inside `stats` / `votes`. Overview hides both window counters if either is small, and hides the average when its total is hidden. |
| `GET /api/v1/public/bills/{bill}/results` | Full choice/source rule; flags inside `citizen_votes`. `divergence_score=null` when choices are hidden. |
| `GET /api/v1/analytics/votes-timeline` | Each daily bucket follows the full choice rule. If any day has hidden choices, choices are withheld across **all** returned days. If any daily total is below k, totals are withheld across **all** returned days. Flags are per bucket. Applies both to bill and platform series. |
| `GET /api/v1/analytics/bill/{bill}` | Full choice/source rule in `votes`; divergence withheld with choices. Weekday counts retain the existing minimum 10, raised to k if larger; if any observed weekday is below that minimum, all observed weekday counts become null with per-row flags. |
| Analytics `divergence-trends`, `top-divergence`, `overview`, `representation`; public `representation` | Suppressed-choice bills contribute no divergence score or ranking entry; existing minimum 10 still applies. Representation's total excludes bill totals below k. |
| `GET /api/v1/export/results.json` and `bills.csv` | Filter rows using max(caller minimum, k), then apply the full choice rule and null divergence. Flags per row. While enabled, exports use combined Tier-1/ZK counts just like ordinary results (ZK only for Parliament), preventing subtraction between different populations. Flag off preserves legacy Tier-1 export behavior. |
| `GET /api/v1/export/divergence.csv` | Same admission rule, including `min_votes=0`; omit rows with suppressed/unavailable divergence. CSV adds suppression columns while enabled. |
| `GET /api/v1/municipal/{dimos}/voteable` | Three published choice cells and total follow the rule; flags inside each decision's `votes`. `/decisions` has no individual-vote aggregates. |
| `GET /api/v1/mp/bill/{bill}` | Full choice rule; flags in `citizen_votes`; hide majority, yes/no counts/share and party matches when the breakdown is suppressed. While enabled, counts use the same combined population as results. |
| MP `compare/{party}` and `ranking` | Suppressed-choice bills contribute no comparison/ranking entry; existing minimum 10 still applies. |
| Future aggregate Arweave audit snapshots | Same full choice rule and null divergence; flags in `citizen_votes`. Lifecycle publisher uses the combined public population while enabled. |

Future Telegram bill notifications suppress totals below k; SSE milestones only publish at/above k. While enabled, monthly newsletters omit their separate vote-count table and turnout counter and link readers to the guarded public results.

Web bill reports/results and mobile results handle nullable values. A hidden
overall total is shown as `< 10` / `λιγότερες από 10 ψήφοι` (using the returned
threshold); secondary suppression shows a withheld breakdown notice.

## Scope and remaining limits

Evaluation aggregates (existing k=10), consensus (own minimum), signed personal
reads, authenticated representative reads, and admin outputs are unchanged.
Public ZK verifier receipts are a separate publication
protocol, not aggregate results, and are unchanged.

This is suppression at publication time, not differential privacy. Previously
published exports, cached responses, immutable Arweave records, and observations
across changing time windows cannot be retracted or made private by this flag.
Changing the flag on a live deployment requires an operational review of old
publications and caches. Exact totals at/above k remain observable over time.

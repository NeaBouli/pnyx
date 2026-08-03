# Forum Topic Data Catalog

The forum monitor treats a missing topic as a data state, not automatically as
an incident. Every `parliament_bills` row with `forum_topic_id IS NULL` is
assigned to exactly one category before an alert decision is made.

## Categories

| Category | Meaning | Alerting |
| --- | --- | --- |
| `public_actionable` | Public bill in a forum-relevant lifecycle state and past its synchronization grace period | Yes |
| `technical_test` | ZK canary or another explicitly marked technical test row | No |
| `demo_legacy` | Legacy row whose ID starts with `DEMO-` | No |
| `operator_hidden` | Row explicitly hidden by an operator | No |
| `sensitive_diavgeia` | DIAVGEIA row excluded by the patient/AMKA/insurance-fund privacy guard | No |
| `sync_grace` | Public candidate still inside the normal synchronization grace period | No |
| `lifecycle_not_eligible` | Row in a lifecycle state that does not currently require a forum topic | No |

Classification precedence is: technical test, demo/legacy, operator hidden,
sensitive DIAVGEIA, public actionable, synchronization grace, then lifecycle
not eligible. The implementation checks technical and demo identity before
visibility flags so test data remains recognizable even when it is also
operator-hidden.

## Privacy And Transparency

- The catalog is read-only. It does not delete, publish, hide, or modify rows.
- Alerts are generated only for `public_actionable` rows.
- Non-public categories are reported as aggregate counts only. Sensitive titles,
  summaries, and identifiers are not included in alert messages.
- The complete category map is emitted as a structured monitor log entry named
  `FORUM_CATALOG`, allowing operators to audit why raw totals differ from public
  incident counts.
- Changes to category definitions require code review and tests because they
  affect monitoring semantics.

The catalog deliberately gives the detailed per-bill check and the aggregate
completeness check the same lifecycle and grace rules. Previously, the detailed
check alerted immediately for `ACTIVE` rows while the aggregate check waited
for the normal 1-hour Parliament or 6-hour non-Parliament synchronization
window. The shared `public_actionable` category removes that contradiction and
also covers overdue `WINDOW_24H` and `OPEN_END` rows consistently.

The public incident metric is therefore:

```text
public actionable bills without forum topic
```

It must never be presented as the raw count of all database rows without a
topic.

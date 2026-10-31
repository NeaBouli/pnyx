# DIAVGEIA organization labels (#714)

The municipal snapshot is a geographic allowlist, not a complete organization
directory. The old importer copied its `[unknown:uid]` result directly into
`pill_el`, although it cleaned the separate `org_label` column. `_resolve_org`
resolves geography only. Neither manual repair route was scheduled. The older
route looked up each bill through `organizations/{uid}.json`, silently ignored
non-200 responses, and retained positive results only in process memory. The
newer maintenance route repaired decision labels and NULL institutional
`org_label` values but never changed pills. The endpoint was already
`organizations`, not `units`; the new resolver uses the extensionless public
endpoint from the production diagnosis. The old URL variant's actual response
status was not established in this checkout.

`resolve_org_label(uid)` now serves scraping, conversion, historical import,
both admin repairs and this backfill. It checks the unmodified municipal
snapshot, then a per-UID Redis hash, then
`https://diavgeia.gov.gr/opendata/organizations/{uid}` with JSON Accept and the
existing scraper User-Agent and HTTP hooks. Only numeric public organization
UIDs are sent. Each attempt has a 10-second deadline; there are at most three
attempts with 2/4-second backoff for transport errors, timeouts, 429 and 5xx.
Existing host pacing/cooldowns apply in addition to a shared Redis 500ms slot
(at most two requests per second across workers, including retries/redirects).
Transport failures release the attempt's host lease before retrying.

Redis avoids a schema migration and shares labels between workers, jobs and
operator runs. Each `diavgeia:org-label:v1:{uid}` hash has its own anchored TTL:
30 days for labels, one day for a 404 or invalid JSON/UID/label response.
Transient HTTP failures are observable by status/error type and are not
negative cached. Cache/pacing outages fall back safely; live dispatch requires
Redis admission. New live labels never enter the geographic snapshot.
Official labels, including Latin text, remain outside the generated prose gate.
Import uses a clean stored decision label if live resolution fails, otherwise
the neutral `Διαύγεια` pill with a NULL label. The raw UID already exists on
`diavgeia_decisions.organization_uid`; it is never put in the display label.
The raw decision's existing NOT NULL `organization_label` uses an empty string
on lookup failure; the manual maintenance repair also retries those blanks.

All display-label writers use `clean_org_label`: remove Unicode control/format
characters (including NUL, C0/C1 and bidi controls), collapse whitespace and
normalize to NFC before detecting empty/unknown/numeric placeholders. Labels
containing angle-bracket markup are rejected. The bound comes from the models:
`pill_el` is varchar(200), while `org_label` and `organization_label` are Text.
The common label limit is therefore 190 characters, including a final ellipsis
when truncated, leaving room for `Διαύγεια: `. React renders pills as escaped
text; static embeds use text nodes. Labels are not stored as HTML entities,
which would display double-escaped in those consumers.

Each scrape, conversion and historical import shares a cumulative three-second
lookup budget across distinct UIDs, including cache access, HTTP, pacing and
backoff. A run lock protects both budget accounting and UID memoization. Budget
exhaustion or an API/cache outage opens the breaker for the rest of that run;
HTTP cancellation allows at most 100ms for host-lease cleanup. Imports continue
using clean stored labels or neutral pills and commit normally. Both admin
repair routes also retry neutral bills using the numeric UID joined from their
decision, so a later healthy run can repair these fallbacks. Admin update
counts come from rowcount and report concurrent skips separately.

## Operator commands

Run from the deployment checkout with the API Python environment active and
`DATABASE_URL` and `REDIS_URL` configured. These commands are provided for the
operator; development does not run them against production.

```sh
cd apps/api
python scripts/backfill_diavgeia_org_labels.py --samples 10
python scripts/backfill_diavgeia_org_labels.py \
  --plan-csv /tmp/diavgeia-org-labels-714-plan.csv --samples 10
```

Both runs use a read-only database transaction and may warm Redis. Review the
counts, sample IDs and every `new_pill` in the plan, including neutral fallbacks.
The plan header is
`id,old_pill_sha256,old_org_label_sha256,uid,new_pill`; its file mode is 0600.
The label digest hashes its raw JSON value, distinguishing SQL NULL, empty
strings and literal `null`. Plans made before this header change must be
regenerated.
The known production count was 6,746 on 2026-10-31; the explicit bound below is
that observation, not a default. Choose another bound only after reviewing a
fresh plan. Paths must be new files; existing files are never overwritten.

```sh
python scripts/backfill_diavgeia_org_labels.py --apply \
  --expect-from /tmp/diavgeia-org-labels-714-plan.csv \
  --max-rows 6746 \
  --backup-csv /tmp/diavgeia-org-labels-714-backup.csv
```

Apply performs no organization HTTP lookups and writes exactly the reviewed
pill values. It only considers `source = 'DIAVGEIA'` rows with the entire pill
matching `Διαύγεια: [unknown:<numeric uid>]`, with the same ID/UID/old pill
digest and raw-label digest in the approved plan. A clean existing `org_label`
is preserved after normalization; NULL/blank/unknown labels are filled from the reviewed pill (or cleared to NULL
for a neutral fallback). Default planning can also reuse a clean stored
`org_label` if live resolution fails.

Before any UPDATE, all attempted rows' old pills and old labels are written to
an exclusive 0600 backup and fsynced. `old_org_label_json` distinguishes SQL
NULL from an empty string. Apply skips labels changed since planning, and
updates recheck the exact old pill, source and NULL-safe old label again,
then commit in batches of 100. Concurrently changed rows are skipped;
the backup can therefore include attempted rows that were not changed. More
matching rows than `--max-rows` aborts before backup or database writes. A
repeated apply skips already repaired rows. Each committed changed batch
invalidates the existing representation/client-flow/visibility caches. After
a failed batch, earlier committed batches remain recorded in the backup and
have already invalidated their caches; the failed batch rolls back.

The repair assigns only `pill_el` and `org_label`, including no `updated_at`.
It never changes titles, summaries, provenance, sensitivity flags or overrides.
Migration z904 (#715) declares its sensitivity trigger with `UPDATE OF source,
title_el, summary_short_el, summary_long_el, sensitive_public_block,
sensitive_override, sensitive_override_reason`; neither repair column appears.
The PostgreSQL regression installs that actual trigger event list with a
function that raises on any invocation, then compares every other column.
Run it on a disposable database:

```sh
PNYX_TEST_POSTGRES_URL=postgresql+asyncpg://postgres:t@127.0.0.1:55433/pnyx_test_714 \
  python -m pytest -q -p no:cacheprovider tests/scripts/test_backfill_diavgeia_org_labels_pg.py
```

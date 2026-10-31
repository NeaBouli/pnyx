# Persisted bill sensitivity (#715)

Public bills use this predicate everywhere (ORM, raw SQL, object checks and the
`idx_bills_public_metadata_v3` partial covering index):

```sql
admin_hidden IS NOT TRUE
AND coalesce(sensitive_override, sensitive_public_block) IS NOT TRUE
```

`sensitive_public_block` is a non-null historical sensitivity latch. An override
of `NULL` follows that latch, `true` hides, and `false` publishes despite it.
`admin_hidden = true` always hides, including when the override is false.
Public queries do not evaluate titles or summaries to decide membership.
Raw DIAVGEIA decisions are a separate dataset; their subject guard is unchanged.

## Migration and rollout

Apply `z904a2b3c4d5` after `z903a2b3c4d5`, before deploying the application that
reads the new columns. Keep DIAVGEIA regeneration paused until migration and
deployment have both completed. No production migration or regeneration is
performed by the implementation task.

The columns and trigger are installed together in a short transaction. PostgreSQL
uses a constant false default without rewriting the table. Backfill then commits
at most 1,000 IDs per statement, using database collation for keyset boundaries.
It calls the frozen `public_bill_sensitive()` function over all three original
fields. `IS NOT FALSE` maps both true and NULL outcomes to a hidden flag: the old
`NOT public_bill_sensitive(...)` predicate excluded both. In particular, a NULL
source with a marker stays hidden; a NULL source without markers stays visible.

The trigger covers inserts and updates of source, all three text fields, and the
flag itself. It ORs the old flag, supplied flag, and new sensitivity. During
backfill a temporary version also checks old prose, protecting rows modified
before backfill reaches them. After backfill the normal function replaces that
version, so removing an old marker cannot undo an explicit admin clear.
Direct SQL, ORM writes, and cleanup scripts cannot clear a latch
by removing prose or assigning a false flag. The ORM fetches the trigger's
decision before publishing hooks use the object.

The new index is built concurrently before v2 is dropped concurrently, with the
same INCLUDE columns. Existing valid or invalid replacement indexes are refused;
an invalid index from this attempt's failed build is cleaned up while preserving
the original exception and the previous index. A failed upgrade can leave the
columns, trigger and completed backfill batches committed; retry preserves
latched flags and overrides. Inspect any surviving index before removing it.
Downgrade builds v2 concurrently first, then removes v3, the trigger, its helper
and columns. It retains `public_bill_sensitive()`. Downgrade deliberately restores
the old prose policy and loses admin decisions/history in these columns; audit
entries remain. Pause text rewriting before a rollback.

## Administrative decisions

Use the existing admin Bearer authentication with:

```http
PATCH /api/v1/admin/bills/{bill_id}/sensitivity
Content-Type: application/json

{"sensitive_override": false, "reason": "Reviewed synthetic example"}
```

The decision field is required, including when setting it to `null` to clear an
override. Every change requires a nonblank reason, retained in
`sensitive_override_reason`. The endpoint locks the bill row and writes an
`AuditLog` entry with action `bill.sensitivity_override`, actor `admin_api_key`,
target ID, reason and before/after decisions in the same transaction. After
commit it invalidates representation/public caches through the existing shared
hook, including the public visibility generation.

An explicit latch clear uses the same endpoint with
`"clear_sensitive_public_block": true`. Only that flag-only flush sets
`SET LOCAL pnyx.allow_sensitive_public_block_clear = 'on'`; it resets the setting
before commit, and PostgreSQL also resets it at transaction end. Even with the
setting on, a simultaneous text/source change cannot bypass detection. A later
text write can latch sensitivity again; use a reasoned false override for a
durable publication decision. This setting is an application admin convention,
not a PostgreSQL privilege boundary: trusted direct database operators can also
set it and must use the audited endpoint for administrative decisions.

The text-quality audit still reports/skips `skipped_sensitive`; that safeguard
is retained independently of public visibility. Its operator text scanner and
the sensitive-topic redaction scanner intentionally continue to inspect prose.

## Call-site audit

“Privacy finding” means the prior code could expose a sensitive bill when matching
rows existed. This source audit does not establish whether a production email,
push, or forum publication actually occurred. All previously shared prose guards
also had the original regeneration vulnerability; z904 closes it globally.
The changes gate future publication; they do not retract previously delivered
emails/pushes or existing forum/Arweave copies.
There was a second shared-guard inconsistency: the old object guard treated NULL
source as Parliament and allowed marker-bearing rows that the old SQL guard
excluded. The new object guard follows the backfilled flag and closes that
point-lookup bypass. ZK's additional explicit Parliament restriction already
rejected such rows.

| Site / calls | Before | After | Previously leaked sensitive bills? |
| --- | --- | --- | --- |
| `newsletter_service.send_monthly_report`: top votes | Only `b.admin_hidden IS NOT TRUE` | Shared raw flag guard | **Privacy finding: yes**, DIAVGEIA titles and counts could enter the newsletter. |
| Same function: new/voted/archive/vote counts, new/upcoming bill lists | Shared ORM prose guard | Shared ORM flag guard | No additional bypass. |
| `main.scheduled_notify_new_bills` | Status only | Status + shared ORM flag guard | **Privacy finding: yes**, private titles and IDs could be pushed. |
| `main.scheduled_notify_results` | Status only | Status + shared ORM flag guard | **Privacy finding: yes**, private titles and IDs could be pushed. |
| `routers/parliament.transition_bill` → `notifications.publish_bill_event`, admin test publisher, vote milestones → SSE/WebSocket | Status/admin publication could broadcast any bill ID without public membership; k=0 milestone helper accepted no DB | Fresh scalar shared flag query at the event publisher; all callers pass the DB; missing DB rejects publication | **Privacy finding: yes**, private IDs/status could enter public streams. |
| `main.scheduled_push_categories`, `scheduled_weekly_digest` | Shared ORM prose guard | Shared ORM flag guard | No additional bypass. |
| `zk_arweave_publisher.list_pending_public_parliament_scopes` | `admin_hidden IS FALSE` + Parliament source | Shared ORM flag guard + Parliament source | No DIAVGEIA disclosure: source restriction and final object guard already protected publication. Candidate query was incomplete. |
| `zk_arweave_publisher.ensure_public_parliament_scope`, `_is_public_parliament_bill_scope` | Shared object prose guard + rollout/results rules | Shared object flag guard + same rules | No additional bypass. |
| `bill_lifecycle._lifecycle_candidate_statement`, `_catchup_arweave`, `is_arweave_eligible` and downstream notification/archive hooks | Shared query/object prose guards | Shared flag guards | Scheduler queries were protected; the object-only eligibility helper allowed NULL-source markers. Legacy `admin_hidden` rejection label is retained for compatibility. |
| `routers/zk._is_public_parliament_bill_scope` / `_ensure_production_scope_allowed` and scope validation | Shared object prose guard + source/status rules | Shared object flag guard + same rules | No additional bypass. Canary `admin_hidden` checks enforce private isolation; admin preflight merely reports it. |
| `discourse_sync.resync_all_topics`, `sync_changed_bills_to_forum`, `sync_new_bills_to_forum` | Shared ORM prose guard | Shared ORM flag guard | No additional bypass in the existing callers. |
| `discourse_sync.create_discourse_topic`, `update_discourse_topic` | Depended on guarded caller | Also check shared object flag guard at publishing entry | No demonstrated independent caller leak; defense against a refreshed candidate becoming hidden. |
| `routers/export.get_all_results` (CSV/JSON) | Shared ORM prose guard | Shared ORM flag guard | No additional bypass. |
| `routers/parliament` list/search/trending, detail/source-text, flagging | Shared query/object prose guards | Shared flag guards | **Privacy finding:** object-only point checks allowed NULL-source markers; list queries were protected. Search still searches prose for relevance, never for visibility. |
| `routers/public_api.public_bills`, `public_bill_results`, stats/health/archive/forum counts | Shared query/object prose guards | Shared flag guards | **Privacy finding:** object-only results check allowed NULL-source markers; list/count queries were protected. |
| `routers/voting` submit/status/correction/relevance/consensus/results checks | Shared object prose guard | Shared object flag guard | **Privacy finding:** object-only point checks allowed NULL-source markers. |
| `routers/voting.get_latest_results`, `get_votes_in_progress` (landing feeds) | Shared ORM/raw prose guards | Shared ORM/raw flag guards | No sensitive DIAVGEIA bypass. Old raw helper inconsistently scanned all sources; it now follows the single persisted policy. |
| `routers/analytics` overview/timeline/turnout/per-bill/representation | Shared query/object/metadata prose guards, including snapshot rechecks | Same helpers with flags | **Privacy finding:** object-only bill/timeline checks allowed NULL-source markers; query/snapshot guards were protected. |
| `routers/consensus_results` coverage/representation | Shared metadata SQL guard | Shared metadata flag guard | No additional bypass. Candidate IDs are intersected with the public snapshot. |
| `routers/mp` ranking, breakdown and bill comparison | Shared query/object prose guards | Shared flag guards | **Privacy finding:** object-only bill check allowed NULL-source markers; aggregate queries were protected. |
| `routers/representative` bill checks and aggregate query | Shared query/object prose guards | Shared flag guards | **Privacy finding:** object-only bill check allowed NULL-source markers; aggregate query was protected. |
| `routers/polis_qr` bill retrieval checks | Shared object prose guard | Shared object flag guard | **Privacy finding:** object-only checks allowed NULL-source markers. |
| `routers/arweave` bill archive lookup | Shared object prose guard | Shared object flag guard | **Privacy finding:** object-only check allowed NULL-source markers. |
| `routers/agent` bill search/context | Shared ORM prose guard | Shared ORM flag guard | No additional bypass. |
| `services/compass_generator`, `cplm`, `zk_vote_aggregation`, `public_result_windows` | Shared ORM prose guards | Shared ORM flag guards | No additional bypass. |
| `public_bill_snapshot.visibility_snapshot_query`, `public_bill_response` capture/revalidation, `filter_public_bill_rows` | Shared ORM prose guard | Shared ORM flag guard, using v3 | No additional bypass, including stale cache revalidation. |
| Sitemaps (`scripts/sitemap.sources.json`, `docs/sitemap.xml`) | Static public page/route inventory, no bill rows | Unchanged; linked bill routes use guarded API | No bill data exposed. No separate RSS/bill sitemap query exists. |
| Raw DIAVGEIA endpoints | Subject marker guard for `DiavgeiaDecision` | Unchanged | Separate dataset; no generated-summary visibility dependency. |
| Admin/scraper management, ZK preflight scripts, canary preparation, sensitive-topic redaction and text audit | Authenticated/operator reads or protective writes | Unchanged except new admin decision endpoint | Not public bill exposure paths; their diagnostic/protective `admin_hidden` and text checks remain intentional. |

## Validation

`tests/test_bill_sensitivity_pg.py` uses disposable schemas and synthetic data
with `PNYX_TEST_POSTGRES_URL`: old/new membership across NULL/source/marker/admin
combinations, multiple backfill batches, text-removal race, ORM/raw latching,
attempted direct clear, override/audit/cache behavior and explicit admin clear.
`test_public_bill_snapshot_pg.py` runs the z902/z903/z904 chain and z904 round trip;
the cold, unvacuumed TOAST fixture checks public counts and snapshots at k=0/5
against v3 with normal planner settings. Existing generic prepared-plan tests
also continue to run. CI rejects PostgreSQL skips when configured.

Unit tests execute synthetic newsletter, publisher/export and notification
queries, check forum/lifecycle/ZK guards, exercise authenticated admin validation
and audit creation, and verify concurrent-index failure cleanup/refusal/order.
SQLite fixture schemas include the same flags; PostgreSQL owns trigger behavior.

T-9166 representation performance

Round 6 of PR #706 adds a persistent Redis public-visibility generation. Every
inventoried committing boundary below increments it best-effort after commit,
before deleting representation keys. Increment and deletion failures are
independent. Both process-local public bodies and Redis representation bodies
record the generation they were built under. Requests check the generation
before and after cache work; a mismatch discards the body and joins a fresh
calculation under single-flight, with a ten-second deadline. Fills racing with
a generation bump cannot authorize the old body. Redis generation read failure
forces fresh calculation, without storing or reusing an outage snapshot.

`/bills`, `/bills/trending`, and `/analytics/representation` also query the current
public visibility of their candidate primary keys before returning rows, including
`last_bill`. This check uses the shared SQL visibility predicate and scalar IDs,
so it cannot reuse visibility from the ORM identity map. Empty lists need no
query. Check failures propagate. Filtering copies the response instead of
changing the cached body. A warm nonempty representation response now performs
one indexed visibility query; the historical zero-query measurement below
predates this defence. The benchmark asserts this new query count.

The original function loaded every public `PARLIAMENT_VOTED`/`OPEN_END` bill,
including long summaries and bills without votes. It then awaited one grouped
Tier-1 count per bill and another grouped ZK count per Parliament bill. Query
count was `1 + eligible bills + eligible Parliament bills`. The existing
`idx_votes_bill` and `idx_zk_receipts_scope` indexes support those individual
lookups, but cannot remove their sequential round trips.

The replacement uses parameterized raw SQL: count each choice while grouping
each vote source by its indexed bill/scope,
combine the source counts per bill, then join the totals to the bill primary key.
Conditional counts avoid sorting the full vote populations by choice. Only
public bill metadata and aggregate counts leave SQL. Tier-1 and ZK choice counts
remain separate until `VoteTotals.publishable` checks the source partitions.
DIAVGEIA sensitivity checks, eligible statuses, the minimum ten votes, party vote
ties, and the existing two-stage rounding remain intact. No index or migration
is needed to remove the repeated queries.

The endpoint stores only its public aggregate response in Redis until 30 seconds
after the aggregation starts. Query time is subtracted from the TTL (rounded down
to whole seconds); expired snapshots are not cached. Hits do not extend expiry.
Every inventoried bill/vote/receipt committing writer also deletes all
representation policy keys through the shared best-effort boundary below. The anchored TTL bounds staleness
if invalidation fails or an in-flight aggregation fills after deletion. Expiry
refreshes vote counts, bill metadata and visibility; changes to the small-cell
policy select a separate cache key. Redis
reads and writes each have a 100 ms deadline and 50 ms socket/connect timeouts;
Redis failures fall back to the database. Database failures propagate without
being cached. Empty results also have the same finite TTL.

## Write inventory and invalidation boundaries (round 2)

`representation_query()` reads exactly three persisted tables:

| Table | Columns read by the aggregate |
| --- | --- |
| `parliament_bills` | `id`, `title_el`, `source`, `status`, `admin_hidden`, `summary_short_el`, `summary_long_el`, `party_votes_parliament` |
| `citizen_votes` | `bill_id`, `vote` |
| `zk_vote_receipts` | `vote_scope_id`, `vote_commitment` |

Party votes live in the bill JSON; there is no separate party-vote table in this
query. ZK tallies are computed from receipts, not a stored tally table. Result
visibility, flags, dates, provenance, consensus values, forum IDs and publication
metadata are conservatively invalidated with other writes to these three tables.
Separate relevance, municipal vote, consensus vote, identity, tier-lock, root,
raw DIAVGEIA and VAA tables are not aggregate inputs. Their writers only need an
invalidation boundary when they also change a bill or receipt listed below.

All paths below use `services.representation_cache.commit_and_invalidate_representation`
at every commit in the writing function. It commits first, propagates DB failures,
then awaits the shared best-effort invalidator. That invalidator catches ordinary
exceptions, including Redis construction, scan, delete, timeout and close failures,
and deletes every `analytics:representation:v1:k*` policy variant. It does not log
bound SQL values or cache contents. Cancellation still propagates. The existing
30-second expiry remains anchored to aggregation start, including empty results;
cache hits and slow fills cannot renew that bound. Invalidation is deliberately
conservative, including metadata-only commits in these functions.

Paths are relative to the repository root. The table lists both direct writers
and the shared committing callers of mutation-only helpers.

| File | Every writer / committing boundary | Mutation / callers |
| --- | --- | --- |
| `apps/api/routers/admin.py` | `admin_create_bill` | Insert a bill. |
| same | `admin_update_bill` | PATCH any supplied bill field, including party-vote clearing and sensitive text. |
| same | `admin_review_summary` | Review flag and generated-content provenance. |
| same | `admin_set_party_votes` | POST `/party-votes`, including an empty JSON object. |
| same | `admin_set_bill_text` | POST `/set-text`; updates long text. |
| same | `admin_reset_votes` | Delete a bill's `CitizenVote` rows. |
| same | `admin_resolve_orgs`, `admin_resolve_org_labels` | Raw SQL updates of bill pills and organization metadata. |
| `apps/api/routers/parliament.py` | `flag_bill`, `transition_bill`, `create_bill` | Flag counter; status and optional Arweave commit; bill insertion. |
| `apps/api/routers/scraper.py` | `fetch_and_store`, `import_parliament_bills` | Insert bills or update title, text, summaries, dates, source URL and other metadata. |
| `apps/api/routers/voting.py` | `submit_vote`, `correct_vote` via `_commit_vote_write` | Insert or correct `CitizenVote`; preserves existing conflict mapping and rollback. |
| same | `_apply_tier1_fields`, `_ensure_same_tier` | Mutation-only vote metadata helpers; committed by the same vote boundary. |
| same | `submit_consensus` | Updates bill consensus fields alongside separate consensus rows. |
| `apps/api/routers/polis_qr.py` | `qr_web_vote`, `qr_web_consensus` | Insert a `CitizenVote`; update bill consensus fields. |
| `apps/api/routers/zk.py` | `accept_zk_vote` | Insert accepted ZK receipt, including its scope and commitment. |
| `apps/api/main.py` | `scheduled_scrape`, `scheduled_completeness_check` | Scheduled bill insert/update and long-text enrichment. |
| `apps/api/services/parliament_fetcher.py` | `enrich_bill_with_text`, `enrich_all_bills` | Commit enriched text. Shared by admin `/fetch-text`, `admin_enrich_all`, and direct service use. |
| `apps/api/services/bill_lifecycle.py` | `_transition_bill` via `run_bill_lifecycle`; `_hook_arweave_snapshot` via `run_bill_lifecycle`, `_catchup_arweave` and router `transition_bill` | Deferred status/publication mutations. Both lifecycle commit sites invalidate; also covers `scheduled_bill_lifecycle` and post-scrape catch-up. |
| `apps/api/services/diavgeia_scraper.py` | `_sync_existing_decision_bill_scopes` via `convert_decisions_to_bills` | Raw SQL scope repair, committed together with any converted bills. |
| same | `convert_decisions_to_bills`, `backfill_diavgeia_bill_dates` | Bill insertion and raw SQL date repair. Covers `scheduled_diavgeia_scrape`, admin conversion and DIAVGEIA scrape-and-convert. |
| `apps/api/services/content_provenance.py` | `record_generated_content`, `clear_generated_content`, `apply_generated_content` | Deferred bill provenance/summary changes; committing callers are admin updates/review, scraper import/scheduled scrape, and forum sync. |
| `apps/api/services/discourse_sync.py` | `_record_matching_existing_topic_body`, `create_discourse_topic`, `update_discourse_topic` via `resync_all_topics`, `sync_changed_bills_to_forum`, `sync_new_bills_to_forum` | Deferred provenance changes; forum-sync commit boundaries also cover `forum_topic_id`. |
| `apps/api/services/zk_arweave_publisher.py` | `publish_pending_zk_receipts_for_scope` | Receipt publication metadata. Shared by manual publication and `publish_auto_zk_arweave_receipts`. |
| `apps/api/scripts/prepare_zk_canary_scope.py` | `_apply_values` via `prepare_canary_scope` | Create/update hidden canary bill, clearing party votes, source links and publication metadata. Both existing-row and new-row commits invalidate. |
| `apps/api/scripts/redact_sensitive_diavgeia_public_topics.py` | `_mark_hidden` | Commit `admin_hidden` after forum redaction. |
| `apps/api/seeds/seed.py`, `apps/api/seeds/seed_real_bills.py` | each module's `seed` | Seed bill rows, statuses, summaries and party votes; each commit in the seed function invalidates. |
| `apps/api/scripts/backfill_parliament_metadata_summaries.py` | `apply_update` | asyncpg autocommit summary/pill update; invalidate immediately after each `execute`, including direct helper use. |
| `scripts/backfill_summary_short.py`, `scripts/backfill_summary_ollama.py` | each module's `main` | asyncpg autocommit summary/pill updates; invalidate after either SQL branch for each row. |
| `scripts/backfill_analysis_claude.py` | `main` | asyncpg autocommit long-text/summary/analysis updates; invalidate after either SQL branch for each row. Dry runs never invalidate. |
| `apps/api/alembic/versions/m601a2b3c4d5_bill_org_label.py` | `upgrade` via Alembic runner | Raw SQL bill organization-label backfill. |
| `apps/api/alembic/versions/u401a2b3c4d5_zk_receipt_vote_commitment_not_null.py` | `upgrade` via Alembic runner | Raw SQL receipt commitment backfill. |
| `apps/api/alembic/env.py` | `run_async_migrations` after `do_run_migrations` returns | Invalidate after the migration transaction commits, covering existing and future data migrations without changing historical revisions. |

`tests/test_representation_invalidation_guard.py` scans production Python throughout
the repository with ASTs, including services, schedulers, scrapers, scripts, seeds
and Alembic revisions. It detects raw INSERT/UPDATE/DELETE/TRUNCATE (including
schema-qualified SQL and module SQL constants), ORM construction, Core DML,
instance assignment, `setattr` and deletes. It traces model query results and
local aliases, and follows mutation-only helpers through every caller to an
invalidating boundary. Naked commits in those functions or their callers fail the
guard, even if another call in the function already invalidates. Migration writers
are checked against the shared post-transaction Alembic boundary. Test fixtures
and vendor code are excluded. Synthetic negative tests prove the guard rejects new
unguarded SQL/ORM writes and an unguarded caller of a shared mutation helper.
This is a static guard for the repository's SQL/ORM patterns, not arbitrary dynamic
SQL generation or external database clients; the anchored TTL remains the backstop.

The HTTP regressions populate both policy caches, commit through `/set-text`,
`/fetch-text`, PATCH party votes and POST `/party-votes`, and assert the affected row
is absent on the next read. The same routes succeed when invalidation raises an
unexpected adapter error; the cached row then disappears at the original expiry.
Additional checks cover a rejected DB commit, invalid Redis configuration, existing
visibility edits, scheduled/manual transitions and the unchanged TTL cases.

Round-2 validation on 2026-10-23 (`TZ=UTC`, Python 3.12.8): the focused
slice passed with **463 passed, 7 xfailed**; the final AST guard run passed
with **15 passed**. The full API suite was run once with
`python -m pytest tests -q -p no:cacheprovider`: **3,856 passed, 85 skipped,
25 xfailed, 31 warnings**, exit status 0, in 670.80 seconds. The anchored TTL
implementation is unchanged. `git diff --check` passes; no commit was created.

Local measurement on 2026-10-23: Python 3.12, SQLAlchemy 2.0.48, SQLite in memory,
20,000 eligible bills (1,000 Parliament bills with votes, 19,000 DIAVGEIA bills
without votes), 400,000 Tier-1 votes, 200,000 ZK votes, existing bill/scope indexes,
and 1.2 KB synthetic long summaries per bill. The benchmark executes the original
router function from an unchanged copy and asserts full response equality against
the replacement. Other validation ran concurrently.

| Path | Local time | Database queries |
| --- | ---: | ---: |
| Original function | 49,211.68 ms | 21,001 |
| New aggregate, uncached (three runs) | 400.41 / 456.56 / 459.79 ms | 1 |
| New aggregate, uncached median | 456.56 ms | 1 |
| Cached response, median of 20 reads | 2.46 ms | 0 |

The cached timing uses a memory double for Redis and includes JSON decoding,
response equality checking, and the endpoint's cache control flow. Real Redis
network latency and HTTP serialization require separate measurement. All three
uncached runs are below 500 ms on this SQLite fixture. The short TTL
cache serves repeated requests without that aggregation cost. Production
PostgreSQL and Redis latency remain to be verified.
PostgreSQL 14 and 17 could not initialize locally because the sandbox denies
shared-memory creation, including with mapped-memory settings.

SQLite `EXPLAIN QUERY PLAN` shows one indexed scan per vote source without
sorting its full population, a temporary B-tree for merging the per-bill source
totals (at most two rows per bill), then primary-key lookups for bills with
totals. No correlated subquery or per-bill count remains. PostgreSQL can use sequential
scans/hash aggregates for these whole-source groups; actual plan choice depends
on its statistics and work memory.

Reproduce from `apps/api` with the project's Python environment:

```sh
PR_BASE=abf433abfac97fdf6dae714c5eba68e5acba1a94
git show "${PR_BASE}:apps/api/routers/analytics.py" > /tmp/representation-before.py
PYTHONPATH=. python tests/benchmark_analytics_representation.py /tmp/representation-before.py
```

`PR_BASE` is PR #681's base commit, before the aggregate implementation. Keep it
pinned when rerunning from the PR branch or after merge so the original function
is compared against the replacement.

Endpoint tests execute the raw SQL with visibility, mixed-source, ZK-only,
invalid-receipt, privacy, contract and rounding fixtures. Cache tests use a
controlled clock to verify expiry at 30 seconds, delayed fills (including fills
past expiry), unchanged expiry on hits, policy changes, visibility changes,
write-path invalidation, failure fallback and closure. A 100-bill
fixture asserts one SQL statement independently of cache hits.

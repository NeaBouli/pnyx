T-9166 representation performance

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
Committed admin visibility/text edits and manual or scheduled status transitions
also delete all representation policy keys. The anchored TTL bounds staleness
if invalidation fails or an in-flight aggregation fills after deletion. Expiry
refreshes vote counts, bill metadata and visibility; changes to the small-cell
policy select a separate cache key. Redis
reads and writes each have a 100 ms deadline and 50 ms socket/connect timeouts;
Redis failures fall back to the database. Database failures propagate without
being cached. Empty results also have the same finite TTL.

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

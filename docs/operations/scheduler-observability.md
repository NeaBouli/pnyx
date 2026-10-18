# Scheduler observability (T-9146)

All 14 jobs registered in the API lifespan use the shared scheduler wrapper,
including the weekly/monthly cron jobs and short-interval jobs. Catch-up changes
the registered job's next execution instead of launching a separate body.

Redis lifecycle state lives under `scheduler:<job>:`. This separates scheduling
outcomes from the existing `scraper:<job>:last_outcome` scrape-quality metadata
(`clean`, `degraded`, `failed`), which remains available to existing health readers.

| Field | Meaning |
| --- | --- |
| `last_started` | UTC body start, also written atomically to `scraper:<job>:last_run`; unchanged for coordination failures or cadence skips |
| `last_finished` | UTC completion, including coordination failure, cadence skip, or cancellation; contention preserves it |
| `last_outcome` | `success`, `failed`, `skipped`, or `interrupted` (legacy `lock_busy` values remain readable) |
| `last_duration_s` | Elapsed seconds, measured with a monotonic clock for live runs |
| `next_run` | APScheduler's next run, including coordination failure retries; standby contention retries stay local |
| `consecutive_failures` | Incremented on failure/interruption, reset on success, preserved on skip/contention |
| `last_lock_busy_at` | UTC timestamp of the most recent standby contention; leaves shared run state unchanged |
| `last_coordination_failure_at` | UTC timestamp of the most recent coordination failure, including failures beside an active worker |
| `consecutive_coordination_failures` | Incremented on coordination failure; reset after successful coordination starts a body or records a cadence skip |

Lifecycle fields do not expire. Startup marks an unfinished attempt interrupted
when no active worker owns its lease. Recovery uses an atomic comparison so a
concurrent worker's start/completion cannot be overwritten. If a hard-killed
worker's lease survives startup, the next lease holder recovers it after expiry,
even when the attempt-based cadence is not due yet. Legacy attempts that predate
this instrumentation have no completion evidence and are not retroactively
classified as interrupted.

The default job timeout is 3,600 seconds and the lease adds a 30-second margin,
independent of the scheduling interval. Shorter timeouts are 510 seconds for
forum sync, 240 for finance export, and 1,200 for notification/category pushes
and ZK publication. The wrapper releases only its own token on exit, including
cancellation. Contention and coordination errors retry in 300–600 seconds.
Contention records only `last_lock_busy_at`, preserving the shared outcome,
timestamps, next run, and failure streak even if the active worker finishes
before the contention write arrives. Schedule event publication skips standby
retries and checks the lease atomically before writing a date. Coordination
failures increment both failure counters and record a failure timestamp; an
atomic lease check protects a peer's outcome, completion, and next run. When
Redis is entirely unavailable, persistence is best effort and standby schedule
events do not advance the last known shared date. Direct forum calls
retain their existing lease; scheduled calls reuse the wrapper's lease.

The existing read-only `GET /api/v1/scraper/jobs` response contains all jobs and
the lifecycle fields above. `last_run` remains the start time. Scrape quality is
exposed separately as `last_scrape_outcome`, with existing reason/count metadata
retained. Dashboard overview cards, the monitor, and the system Scheduler Jobs list show
completion, outcome/duration, next run, and failure streak. Old Redis data stays
readable, and reads do not mutate state.

The dedicated `scheduler` logger has its own INFO handler and emits one line at
start and end, for example:

```text
event=end job=parliament outcome=success duration_s=12.340 next_run=2026-10-18T21:00:00+00:00
```

The root logger's configuration is preserved. `httpx`, `httpcore`, and
`apscheduler` stay at WARNING.

The monitor alerts only when `now > next_run + grace`,
`consecutive_failures >= 3`, or `consecutive_coordination_failures >= 3`.
Coordination alerts use the same per-job incident and cooldown as body failures
and misses, even when a retry is still in the future. Grace defaults to 900 seconds and is configurable
with `SCHEDULER_MISS_GRACE_SECONDS`. Missing/malformed timestamps are unknown;
a single failed/degraded outcome or old `last_success` alone no longer alerts.
Source freshness checks remain separate. Alerts reuse `scraper_job_errors`, the
existing Telegram channel, and its per-job cooldown/resolution handling (six-hour
notification cooldown by default). Both conditions for one job form one incident;
different jobs remain separate. These alerts do not trigger automatic restarts.

Validation used existing local Python/TypeScript environments, without network
access, installs, or live services. Redis was faked; the restart/coordination
tests used real APScheduler jobs. Targeted test tails:

```text
114 passed in 7.68s
7 passed, 87 deselected in 2.72s
1 passed in 1.42s
dashboard: 10 passed, 0 failed
```

The Python runs covered lifecycle/restart, scraper readers/quality, monitor
misses/deduplication, selected forum lease tests, the disabled push path, and
recovery before cadence recheck. Shared dashboard libraries passed `tsc
--noEmit`; the three changed dashboard views passed TSX syntax checks. No full
application build or live Redis/provider test was run.

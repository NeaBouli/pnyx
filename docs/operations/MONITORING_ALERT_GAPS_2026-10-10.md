# Monitoring / alert gap analysis — 2026-10-10

- Base commit: `fbbf59687711d0f4796b41651f1b5a6f89c842e5` (main)
- Scope: **source-only** review of `apps/monitor/monitor.py`, `apps/api/main.py`
  (lifespan scheduler + `scheduled_*` jobs, `/health`, `/api/v1/health/modules`),
  `apps/api/services/scraper_state.py`, `apps/api/routers/payments.py` (Stripe webhook)
  and `infra/docker/docker-compose.prod.yml`. No production, SSH, live HTTP, Stripe or
  Telegram calls. Architecture node: monitor boundary (EKA13 — monitor, private
  docker-proxy, Tier-2 recovery off). Docs-only; nothing implemented.
- **Decision: NO-GO to claiming complete unattended alert coverage. This is not a deploy
  decision** and not an operational launch certification.

## 1. Health endpoints

| Endpoint | Source | Semantics | Failure behaviour |
|---|---|---|---|
| `/health` | `apps/api/main.py::health` (L987) | Static liveness: returns `status: ok` without touching DB/Redis | Cannot report dependency failure; only proves the process answers |
| `/api/v1/health/modules` | `apps/api/main.py::health_modules` (L1021) | Passive per-module panel for wiki indicators; scraper modules derived from `scraper:<name>:*` Redis keys (`error` = circuit open, `degraded` = errors, else `ok`) | Redis exception inside `scraper_status` is swallowed and reported as `status: ok` (L1042); many modules are hard-coded `ok` (MOD-01/02/04/05). Not an alert source — no outbound dispatch |

Neither endpoint is a readiness probe. The monitor polls API liveness through
`check_api_health` (monitor.py L928-938: `GET {API_URL}/api/v1/bills?limit=1`, a DB-backed
read), not `/health` itself; `/health` is curled only by the manual script
`infra/hetzner/health_check.sh` (no schedule proven in source). `/health/modules` is a
passive panel. No fresh runtime proof of DB/Redis health exists in this review.

## 2. Monitor checks actually wired (`apps/monitor/monitor.py::run_checks`, L1205)

Cadence: `CHECK_INTERVAL` = `MONITOR_INTERVAL_SECONDS` default 1800 s (L70), loop wraps
`run_checks()` in `except Exception` and sleeps (main loop, ~L1318-1323). Dispatch:
`send_telegram` (L401) only; returns `False` and logs on missing token/chat or non-200.
Repeat suppression: `ALERT_NOTIFY_COOLDOWN_SECONDS` default 21600 s (L94).

| Check | Signal | Threshold | Notes / blind spot |
|---|---|---|---|
| `check_api_health` (L928-938) | GET `/api/v1/bills?limit=1` | non-200 / exception → critical | Polled liveness + DB-backed read proxy |
| `check_vote_results_health` (L943) | GET `/api/v1/vote/results/latest` | non-200 → warning | — |
| `check_web_urls` (L1026) | Landing, `/el/bills`, `/el/results`, API bills | per-URL failure | Fetches public domain from inside the host: not an external vantage point |
| `check_scraper_stale` (L612) | `scraper:parliament:last_success` | > 48 h | Only fires if key exists; missing key = silent |
| `check_diavgeia_scraper` (L1012) | `scraper:diavgeia_municipal:last_run` | > 96 h (2× 48 h interval) | Uses **last_run**, not last_success; missing key = silent |
| `check_scraper_jobs` (L1083) | `scraper:<job>:error_count` for parliament, diavgeia_municipal, bill_lifecycle, cplm_refresh, greek_topics, notify_new_bills, notify_results | > 20 | See P2-2 (circuit interplay) |
| `check_forum_sync_errors` (L917) | `scraper:forum_sync:error_count` | > 10 | — |
| `check_parliament_source_freshness`, `check_no_new_bills`, `check_lifecycle_stuck`, `check_lifecycle_fast_forward`, `check_forum_missing`, `check_forum_completeness`, `check_arweave_pending`, `check_arweave_wallet`, `check_hlr_credits`, `check_db_consistency`, `check_zk_canary_health` | DB / outcome-level business checks | various (see source) | Outcome checks partially cover job failures (e.g. lifecycle stuck covers `bill_lifecycle` effects) |
| `check_disk_usage` (L981) | `shutil.disk_usage("/")` in monitor container | > 90 % → critical | Scope = container root FS, not proven to be host / docker-data volume; exceptions swallowed (`except: pass`) |
| DB / Redis | connections opened in `run_checks` L1212-1215 **before** its `try` | failure → daemon loop `except` (L1318-1323): log + sleep | No dedicated Redis/DB alert; whole cycle aborted, **log-only** |
| Redis `restart_count` (L536-539) | Tier-2 recovery attempt counter | — | Counts recovery attempts, **not** container/daemon restarts |

## 3. Scheduler jobs (`apps/api/main.py` lifespan, L849-862) vs. monitor coverage

| Job id | Trigger | Redis heartbeat (`record_run`/`success`/`failure`) | Monitor coverage |
|---|---|---|---|
| parliament_scrape (`parliament`) | 12 h | yes, circuit-guarded | stale 48 h + error_count |
| diavgeia_municipal | 48 h | yes, circuit-guarded; see P2-1/P2-2 | last_run 96 h + error_count |
| bill_lifecycle | 1 h | yes | error_count + lifecycle outcome checks; no staleness |
| notify_new_bills | 30 min | yes | error_count only |
| notify_results | 1 h | yes | error_count only |
| cplm_refresh | 6 h | yes | error_count only |
| greek_topics | 6 h | yes, circuit-guarded; gate-off path records success | error_count only |
| forum_sync | 10 min | yes; disabled path (`FORUM_SYNC_ENABLED`/key unset) records run+success (intentional idle) | error_count > 10 + forum outcome checks |
| completeness_check | 6 h | yes | none on the heartbeat |
| push_categories | 30 min | no `scraper_state` calls; exceptions log-only | none |
| weekly_digest | cron Mon 07:00 | no `scraper_state` calls; log-only | none |
| finance_export | 5 min | no `scraper_state`; `FinanceExportError`/`Exception` → `logger.warning` (L837-840), quarantine → `logger.error` | none |
| zk_arweave_publication | 30 min | internals not inspected in depth | `check_zk_canary_health` / arweave checks (outcome) |
| monthly_newsletter | cron day 1 09:00 | no `scraper_state`; False → `logger.warning`, exception → `logger.error` (main.py L704-717) | none |

Scope: for inspected job bodies (all rows except zk_arweave_publication internals) no job
records duration and no monitor check compares `last_run` vs `last_success` (hung run); no
APScheduler misfire listener found in the lifespan. Gate-off paths (forum_sync disabled,
greek_topics gate, PUSH flags, finance_export's **own** gate — distinct from
`PAYMENTS_INTAKE_GATE`) are intentional no-ops, not failures.

## 4. Findings

Priority note: no P1 is assigned. Nothing here is a proven active incident or security
issue; structural notification/job gaps are **P2** (impact + missing receipts), refinements
**P3**. Proposals go to Gio (owner); nothing is assigned to a service.

**P2-1 Diavgeia partial failures masked.** `scheduled_diavgeia_scrape` (main.py L541-581)
logs `len(result.errors)` and the first three errors, then calls `record_success` even when
`result.errors` is non-empty; the NEA-199 conversion/backfill block catches exceptions as
"non-blocking" warnings and also ends in `record_success`, which resets `error_count` to 0
(scraper_state.py L33-34). Masking condition: the scrape call itself does not raise. Then
per-item failures (e.g. the owner-reported CheckViolation class addressed by migration
`y801a2b3c4d5`, #516 — Prod deployment **not** inferred) are invisible to
`check_scraper_jobs`, `check_diavgeia_scraper` and `/health/modules`. No new leak and no
runtime occurrence is claimed. *Proposal:* `items_failed` / `conversion_failed` counters +
last partial-error time; alert on count/ratio.

**P2-2 Circuit breaker vs. counters/staleness.** `is_circuit_open` trips at
`CIRCUIT_BREAKER_THRESHOLD = 3` and resets after a 24 h cooldown (scraper_state.py L12,
L55-70); guarded jobs return without `record_failure` while open. Under steady sequential
default scheduling the count therefore tends to stay ≤ 3, so `error_count > 20` is
unlikely (not impossible: check and increment are non-atomic across processes, manual or
catch-up runs). For **diavgeia (48 h interval > 24 h cooldown)** the circuit can reset
before each run, so repeated total failures still execute, update `last_run` and may keep
`error_count` near 1 — the 96 h `last_run` stale check does **not** catch regularly
failing runs. Parliament (12 h) and greek_topics (6 h) differ: open-circuit skips do not
update `last_run`; parliament is caught by 48 h `last_success`, greek_topics has no
staleness check. *Proposal:* alert on `last_success` age per job, circuit-open state and
consecutive error outcomes, gate-off/catch-up aware.

**P2-3 Jobs without monitored heartbeat.** push_categories, weekly_digest, finance_export,
monthly_newsletter (log-only per §3) and completeness_check (writes heartbeat, not
consumed). *Proposal:* uniform outcome + duration + `last_success`, gate-aware deadline =
actual interval × 2 + grace, explicit `idle (gate off)` state. PAYMENTS_INTAKE / PUSH /
finance-export flags untouched.

**P2-4 Telegram delivery and cooldown.** `prepare_alert_notifications` (monitor.py
L284-291) writes `:last_sent` **before** delivery; default cooldown 21600 s (L94).
`send_telegram` (L401-417) returns False on absent config, non-200 or exception, but
`escalate` (L575-576) and the summary send (L1276) ignore the bool. If the Redis write
succeeded and cooldown > 0, a failed delivery can suppress that alert for 6 h unless
severity changes. `send_resolved_notifications` (L346-349) clears incident, membership and
cooldown even after a False send → no resolved-notice retry. HTTP 200 alone counts as
success; no Telegram body `ok` check or readback. *Proposal:* commit cooldown only after a
True send, offline False-send counter + retry; retain resolved state until delivered.

**P2-5 No independent dead-man in module/Compose.** No watchdog for the monitor exists in
`apps/monitor` or `infra/docker/docker-compose.prod.yml`; external watchers are unverified
and unchanged (not "none anywhere"). `infra/hetzner/health_check.sh` is a manual curl
script, not evidence of active scheduling. DB/Redis connection errors (L1212-1215) and
cycle exceptions (L1318-1323) are log + sleep; the monitor's own restart policy is not a
dead-man. *Proposal:* per-cycle heartbeat to an independent receiver that alerts on
absence (owner decision).

**P2-6 Container restart loops.** `restart: unless-stopped` restarts but does not alert;
production docker-proxy denies `CONTAINERS`, `EVENTS`, `POST` (compose L166-169) and
`AUTO_RECOVERY_T2=false` (monitor L76/L522); Redis `restart_count` (L536-539) counts T2
attempts, not daemon restarts. Do **not** widen the proxy or enable auto-recovery;
*proposal:* host-side aggregate restart-count observer, owner-run.

**P2-7 Stripe webhook outcomes not aggregated.** `payments.py` webhook (L948 ff.): 503
secret missing (`logger.error`, L960); 400 missing/invalid signature or bad payload
(noise, `logger.warning`); 503 "awaiting legal recipient approval" when the intake gate is
closed (L989, expected/legal); 503 claim/projection retry states. No webhook-specific
aggregate alert is wired in the inspected monitor; external Sentry/ingress alert policies
and actual exception delivery are unverified, not assumed absent.
*Proposal:* low-cardinality counters `{status_class, reason_label}` only (no payload,
headers, customer, email, event id, amount); exclude legal gate-closed 503; alert on
unexpected 5xx > 0 and signature-failure bursts.

**P3-1 Host disk scope.** Owner-reported 78 % (not re-measured). `check_disk_usage` reads
`shutil.disk_usage("/")` in the monitor container, > 90 % critical, exceptions swallowed;
the container backing FS may match the host but named volumes/docker-data are not proven.
Keep the strict 90 % threshold; *proposal:* separate host disk/inode check (owner).
**P3-2** `/health` is liveness-only; `/health/modules` reports `ok` on Redis error — mark as
passive panels or return `unknown`. **P3-3** Missing Redis keys silence staleness checks;
treat missing as `unknown` after grace.


### Repository follow-up — public status readers (T-9071, not deployed)

`apps/api/services/scraper_state.py::get_all_states` (`/api/v1/scraper/jobs`) and `apps/api/main.py::health_modules` (`/api/v1/health/modules`) now return the whitelisted latest-outcome fields (unknown/invalid values → `unknown`/`null`, count clamped 0..10000, tz-aware UTC ISO times only; no raw text in new fields). A degraded/failed latest outcome yields `warning` (jobs) / `degraded` (module) even with `error_count` 0; legacy count/circuit precedence is unchanged. Missing outcome telemetry or unreadable counts yield `unknown` unless a known nonclean outcome or legacy counter already proves warning/error; Redis errors yield `unknown`, never a false `ok`; `last_success` alone is not clean evidence. `overall` precedence: error > degraded > unknown > ok (disabled/deferred excluded). Until each job records an outcome after deploy, its module can read `unknown` rather than optimistic `ok`. Dashboard adapters still discard the extra fields and the jobs table derives status from `error_count`, so rendered visibility, real Redis and browser behaviour are unverified.

## 5. Offline test / acceptance plan (no live fault injection, no paid calls)

1. Unit test with fake Redis + stub `scrape_decisions` returning `errors=[...]` → counters
   written, monitor alert raised; conversion raising → `conversion_failed` recorded.
2. Fake Redis with `error_count=3` and fresh `last_error_time` → circuit-open alert fires.
3. Per-job deadline table test: derived from the lifespan `add_job` triggers; gate-off
   fixture yields `idle`, not `stale`.
4. Webhook counter tests with synthetic short test secrets: invalid sig → 4xx bucket;
   gate closed → excluded bucket; forced handler exception → 5xx bucket; assert no
   payload fields in Redis keys or logs.
5. Dead-man: simulate missed heartbeat in a local fixture.
6. Delivery: `send_telegram` stub returning False → failure counter incremented, cooldown
   **not** committed, resolved state retained for retry; stub 200 with body `ok:false` → failure.
7. Diavgeia 48 h fixture: repeated total failures across circuit resets → `last_success`
   age alert fires although `last_run` is fresh.

## 6. Rollout / rollback

Each proposal ships as a separate small PR behind defaults that keep current behaviour;
rollback = revert PR / unset new env. Deploy only via Gio's gate (`deploy.yml` is
`workflow_dispatch`). Host-side daemons and external dead-man are owner (Gio) decisions.

## 7. NOT VERIFIED (operational unknowns)

Deployed monitor parity with this source; actual env thresholds/interval; Telegram
config, delivery and readback; host disk and docker-data usage; container restart history;
whether #516/`y801a2b3c4d5` is applied in production; Stripe webhook traffic.

## 8. Repository follow-up — scheduler/scraper outcomes (T-9069, not deployed)

The candidate adds `scraper:<job>:last_outcome`, `last_outcome_reason`, `last_outcome_count`, `last_outcome_time` and historical `last_nonclean_time` (14-day TTL) in the existing success/failure pipeline. Outcomes are `clean/degraded/failed`; only fixed reason codes, bounded counts and timestamps enter new fields/warnings. Diavgeia partial scrape errors and caught main conversion exceptions become degraded, first tracked full failures become failed, and the next clean run clears the latest warning. Existing circuit counters/intervals are unchanged; legacy `last_success` still means run completed, not necessarily clean.
The monitor reuses per-job `scraper_job_errors` warnings without auto-recovery. Focused offline tests include the actual scheduler function body loaded via AST with shared fake DB/Redis → monitor; app startup/registration, real Redis transactions, deployment parity and actual alert delivery remain unverified. Inner per-row conversion skips, health-module exposure and untracked finance/digest/push jobs remain separate gaps. No channel/secret/proxy/restart change or production action is included.

## Repository follow-up: notification delivery state (T-9070)

P2-4's candidate commits incident cooldowns only after a sender acknowledgement and retains failed resolved notices for the next ordinary monitor cycle. HTTP 200 alone is insufficient: Telegram's JSON `ok` must be `true`. Legacy markers without acknowledged severity trigger a conservative resend; expired incident payloads are not sent as identity-only resolutions.
Focused offline Redis/HTTP fakes exercise this contract; no provider delivery, real Redis runtime, production configuration or deployment is verified. Cross-review, exact-head CI and a separate Gio deployment gate remain required.

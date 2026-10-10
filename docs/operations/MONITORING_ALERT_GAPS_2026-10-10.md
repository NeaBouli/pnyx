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

Neither endpoint is a readiness probe; the monitor does not poll either of them.

## 2. Monitor checks actually wired (`apps/monitor/monitor.py::run_checks`, L1205)

Cadence: `CHECK_INTERVAL` = `MONITOR_INTERVAL_SECONDS` default 1800 s (L70), loop wraps
`run_checks()` in `except Exception` and sleeps (main loop, ~L1318-1323). Dispatch:
`send_telegram` (L401) only; returns `False` and logs on missing token/chat or non-200.
Repeat suppression: `ALERT_NOTIFY_COOLDOWN_SECONDS` default 21600 s (L94).

| Check | Signal | Threshold | Notes / blind spot |
|---|---|---|---|
| `check_api_health` (L930) | GET `/api/v1/bills?limit=1` | non-200 / exception → critical | Real readiness proxy (DB-backed read) |
| `check_vote_results_health` (L943) | GET `/api/v1/vote/results/latest` | non-200 → warning | — |
| `check_web_urls` (L1026) | Landing, `/el/bills`, `/el/results`, API bills | per-URL failure | Fetches public domain from inside the host: not an external vantage point |
| `check_scraper_stale` (L612) | `scraper:parliament:last_success` | > 48 h | Only fires if key exists; missing key = silent |
| `check_diavgeia_scraper` (L1012) | `scraper:diavgeia_municipal:last_run` | > 96 h (2× 48 h interval) | Uses **last_run**, not last_success; missing key = silent |
| `check_scraper_jobs` (L1083) | `scraper:<job>:error_count` for parliament, diavgeia_municipal, bill_lifecycle, cplm_refresh, greek_topics, notify_new_bills, notify_results | > 20 | See P1-2 (unreachable for circuit-guarded jobs) |
| `check_forum_sync_errors` (L917) | `scraper:forum_sync:error_count` | > 10 | — |
| `check_parliament_source_freshness`, `check_no_new_bills`, `check_lifecycle_stuck`, `check_lifecycle_fast_forward`, `check_forum_missing`, `check_forum_completeness`, `check_arweave_pending`, `check_arweave_wallet`, `check_hlr_credits`, `check_db_consistency`, `check_zk_canary_health` | DB / outcome-level business checks | various (see source) | Outcome checks partially cover job failures (e.g. lifecycle stuck covers `bill_lifecycle` effects) |
| `check_disk_usage` (L981) | `shutil.disk_usage("/")` in monitor container | > 90 % → critical | Scope = container root FS, not proven to be host / docker-data volume; exceptions swallowed (`except: pass`) |
| DB / Redis | implicit: `get_db()` / `get_redis()` in `run_checks` | connection failure → loop exception, logged | No dedicated Redis/DB alert; a connection failure aborts the cycle and is **log-only** |

## 3. Scheduler jobs (`apps/api/main.py` lifespan, L849-862) vs. monitor coverage

| Job id | Trigger | Redis heartbeat (`record_run`/`success`/`failure`) | Monitor coverage |
|---|---|---|---|
| parliament_scrape (`parliament`) | 12 h | yes, circuit-guarded | stale 48 h + error_count |
| diavgeia_municipal | 48 h | yes, circuit-guarded; see P1-1 | last_run 96 h + error_count |
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
| zk_arweave_publication | 30 min | not inspected in depth | `check_zk_canary_health` / arweave checks (outcome) |
| monthly_newsletter | cron day 1 09:00 | not inspected in depth | none found |

No job records duration; no check detects a hung run (`last_run` newer than
`last_success` for longer than the job's interval) or APScheduler misfires.

## 4. Findings

**P1-1 Diavgeia partial failures masked.** `scheduled_diavgeia_scrape` (main.py L541-581)
logs `len(result.errors)` and the first three errors, then calls `record_success` even when
`result.errors` is non-empty; the NEA-199 conversion/backfill block catches all exceptions as
"non-blocking" warnings and also ends in `record_success`. `record_success` resets
`error_count` to 0 (scraper_state.py L33-34). Result: per-item failures (such as the
owner-reported CheckViolation class addressed by migration `y801a2b3c4d5`, #516 — Prod
deployment **not** inferred here) and total conversion failure are invisible to
`check_scraper_jobs`, `check_diavgeia_scraper` and `/health/modules`. Masked whenever the
scrape call itself does not raise. *Proposal:* record `items_failed`/`conversion_failed`
counters + `last_partial_error_time` in Redis; monitor alerts on ratio/absolute count.

**P1-2 `error_count > 20` unreachable for circuit-guarded jobs.** `is_circuit_open` returns
true at `CIRCUIT_BREAKER_THRESHOLD = 3` (scraper_state.py L12, L55-70) and the job then
returns **without** `record_failure`; after the 24 h cooldown the count is reset to 0. For
parliament, diavgeia_municipal and greek_topics the counter therefore stays around 3, so
`check_scraper_jobs` (> 20) never fires; only staleness checks remain (parliament 48 h,
diavgeia 96 h last_run — and a skipped run does not update last_run, so this one does fire
eventually; greek_topics has none). *Proposal:* alert on "circuit open" state directly.

**P1-3 Unmonitored jobs.** push_categories, weekly_digest, finance_export,
monthly_newsletter, completeness_check have no heartbeat consumed by the monitor; failures
are log-only. *Proposal:* uniform `record_run/success/failure` + duration, and a
gate-aware deadline per job = actual interval × 2 (+ grace), with an explicit
"gate-off / intentional idle" state distinct from success (PAYMENTS_INTAKE / PUSH flags
remain untouched).

**P1-4 No independent dead-man.** Alert path is monitor → Telegram only. If the monitor
container, its loop (exceptions only logged), Redis/DB connectivity, or Telegram delivery
fails, nothing is sent; `send_telegram` failure is log-only and no delivery receipt or
"monitor alive" heartbeat exists. Cooldown (6 h) also delays re-notification.
*Proposal:* external dead-man (monitor pushes a heartbeat each cycle to an independent
receiver that alerts on absence), plus a daily "all-clear" digest.

**P2-1 Host disk scope unproven.** Owner-reported 78 % disk (not re-measured). `check_disk_usage`
measures the monitor container root FS at 90 %; host and docker-data volume are not proven
covered. *Proposal:* host-level disk/inode check outside the container (host cron/daemon
owned by Gio), lower warning at 80 %.

**P2-2 Container restart loops invisible.** Services use `restart: unless-stopped`
(compose L11/L30/L47…); production docker-proxy denies `CONTAINERS`, `EVENTS`, `POST`
(compose L166-169) and Tier-2 restart is off (`AUTO_RECOVERY_T2=false`, monitor L76/L522).
A crash-looping container is only seen indirectly (API/web check failing at the sampled
moment). Do **not** widen the proxy or enable auto-recovery; *proposal:* host-side
restart-count observer (outside the monitor) reporting aggregate counts.

**P2-3 Stripe webhook errors not aggregated.** `payments.py` webhook (L948 ff.): 503 (L960) when
secret missing (`logger.error`), 400 missing/invalid signature (`logger.warning`), 400 bad
payload, 503 "awaiting legal recipient approval" (L989) when `PAYMENTS_INTAKE_GATE` is closed
(expected/legal), 503 for claim/projection retry states. No counter, no monitor check;
unexpected 5xx is log-only. *Proposal:* low-cardinality Redis counters by
`{status_class, reason_label}` only (no payload, headers, customer, email, event id, amount),
exclude the legal gate-closed 503 from alerting, alert on 5xx-unexpected > 0 and on
signature-failure bursts.

**P3-1** `/health` is liveness-only and `/health/modules` reports `ok` on Redis error;
document as non-alerting panels or return `unknown`. **P3-2** Missing Redis keys
(fresh Redis / flush) silence staleness checks; treat missing as `unknown` after grace.

## 5. Offline test / acceptance plan (no live fault injection, no paid calls)

1. Unit test with fake Redis + stub `scrape_decisions` returning `errors=[...]` → counters
   written, monitor alert raised; conversion raising → `conversion_failed` recorded.
2. Fake Redis with `error_count=3` and fresh `last_error_time` → circuit-open alert fires.
3. Per-job deadline table test: derived from the lifespan `add_job` triggers; gate-off
   fixture yields `idle`, not `stale`.
4. Webhook counter tests with synthetic short test secrets: invalid sig → 4xx bucket;
   gate closed → excluded bucket; forced handler exception → 5xx bucket; assert no
   payload fields in Redis keys or logs.
5. Dead-man: simulate missed heartbeat in a local fixture; `send_telegram` stub returning
   False increments a delivery-failure counter.

## 6. Rollout / rollback

Each proposal ships as a separate small PR behind defaults that keep current behaviour;
rollback = revert PR / unset new env. Deploy only via Gio's gate (`deploy.yml` is
`workflow_dispatch`). Host-side daemons and external dead-man are owner (Gio) decisions.

## 7. NOT VERIFIED (operational unknowns)

Deployed monitor parity with this source; actual env thresholds/interval; Telegram
config, delivery and readback; host disk and docker-data usage; container restart history;
whether #516/`y801a2b3c4d5` is applied in production; Stripe webhook traffic.

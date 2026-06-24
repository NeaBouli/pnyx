# Server Cleanup Policy — ekklesia.gr

Date: 2026-06-24
Scope: `root@135.181.254.229`, ekklesia/pnyx runtime and shared Docker host.

## Current Finding

The disk pressure is real but not caused by PostgreSQL row growth or `/opt/ekklesia`
application code.

Latest read-only measurement:

- `/`: 75G total, 67G used, 5.3G free, 93%.
- Inodes: 17% used, not a problem.
- `/opt/ekklesia`: about 1.4G.
- `/var/lib/docker/volumes`: about 5.8G.
- `/var/lib/containerd`: about 40G.
- Docker images: about 42G, all currently attached to running containers.
- Docker build cache: about 2.8G, but only old cache is auto-cleaned.
- Journald: about 220M.
- `/var/lib/snapd/cache`: about 2.0G.

Main ekklesia-related cleanup result:

- `volumes_ekklesia_ollama`: about 11G before qwen removal, 1.9G after.
- Ollama models:
  - `qwen2.5:14b`: removed on 2026-06-20 after explicit Gio confirmation.
  - `llama3.2:3b`: retained; current `OLLAMA_MODEL`.
- Cross-project/runtime check:
  - Ollama is not exposed on a host port (`11434/tcp` has no host binding).
  - Only containers on `net_ekklesia` can reach the `ollama` network alias.
  - Running container env inspection found only `ekklesia-api` with
    `OLLAMA_URL=http://ollama:11434` and `OLLAMA_MODEL=llama3.2:3b`.
  - Ollama logs over the checked window showed health/tag/ps calls, no generate
    calls for `qwen2.5:14b`.
  - The manual `scripts/backfill_summary_ollama.py` no longer hardcodes qwen;
    it defaults to `OLLAMA_MODEL` or `llama3.2:3b` and accepts `--model`.
  - Targeted project scan found no Ollama/qwen references in `/opt/parlay`,
    `/opt/vlabs`, `/opt/stealthx`, `/opt/inferno`, or `/opt/plausible`.
  - `/opt` scan found remaining qwen references only in historical release
    artifacts (`/opt/ekklesia/release-builds/pnyx-vc35`) and old migration/
    architecture notes (`/opt/hetzner-migration`), not in running env, cron, or
    the current `/opt/ekklesia/app` executable code.

Smaller project artifact candidates:

- `/opt/ekklesia/build-artifacts`: about 98M.
- `/opt/ekklesia/release-builds`: about 154M.
- `/opt/ekklesia/downloads`: about 145M.
- `/opt/ekklesia/backups`: about 354M.
- `/opt/ekklesia/app/docs/download/backups`: about 353M.

## Safety Classification

### Never Auto-Delete

These must not be deleted by an automatic cleanup job:

- Docker volumes for databases:
  - `volumes_ekklesia_postgres`
  - `volumes_ekklesia_redis`
  - Discourse, Listmonk, Plausible, ClickHouse, Parlay DB volumes
- `/opt/ekklesia/arweave-wallet.json`
- `/opt/ekklesia/.env.production`
- current direct APK: `/opt/ekklesia/app/docs/download/ekklesia-latest.apk`
- current public download copy: `/opt/ekklesia/downloads/ekklesia-latest.apk`
- current Git checkout and `.git`
- security/canary DB backups unless explicitly archived off-site first
- active Docker images/containers
- Hetzner snapshots: they are external rollback points and do not explain root
  filesystem usage.

### Safe Automatic Cleanup

These are safe candidates for a weekly low-risk job:

- `docker image prune -f` for dangling, unreferenced images only.
- `docker container prune -f --filter until=24h` for stopped containers only.
- `docker builder prune -af --filter until=168h` for old build cache only.
- `apt-get clean`.
- `journalctl --vacuum-size=500M`.
- read-only disk report into Bridge/operator logs.

This job must not use `docker system prune -a` and must not prune Docker volumes.

### Manual Confirmation Cleanup

These can free meaningful space but require explicit operator confirmation:

- remove unused Ollama model `qwen2.5:14b` if production remains on
  `llama3.2:3b` or Claude API:
  - expected reclaim: about 9G.
  - command: `docker exec ekklesia-ollama ollama rm qwen2.5:14b`.
- prune old APK/AAB copies while keeping:
  - latest Play AAB/APK,
  - latest direct APK,
  - GitHub release asset hashes,
  - one previous known-good APK.
- remove disabled snap revisions and snap cache after checking `snap list --all`.
- remove unused Docker volumes only after inspecting `docker volume ls -qf dangling=true`
  and verifying they are not DB/runtime volumes.

### Not Trash / Capacity Planning

These are large but functional:

- `ollama/ollama` image: about 10G; needed while local LLM service remains enabled.
- Discourse image/container: large but live forum dependency.
- Parlay/other project images: shared host usage, not ekklesia trash.
- `/var/lib/containerd`: mostly active image/snapshot data for running Docker
  workloads. Do not delete manually.

## Installed Hourly Guard

Production has an hourly host-level guard:

- Timer: `safe-disk-guard.timer`
- Service: `safe-disk-guard.service`
- Script: `/usr/local/sbin/safe-disk-guard`
- Repo source: `scripts/safe-disk-guard`
- Log: `/var/log/safe-disk-guard.log`
- Status: `/var/log/safe-disk-guard.status`

The guard is intentionally conservative. At or above `CLEAN_PERCENT=90`, it only:

- rotates Docker container logs using `/etc/logrotate.d/docker-containers`;
- caps journald via `journalctl --vacuum-size=300M`;
- runs `apt-get clean`;
- prunes old Docker builder cache with `docker builder prune -af --filter until=72h`.

It does **not** prune Docker volumes, active images, active containers, backups,
database data, Arweave data, or `/var/lib/containerd` snapshots directly.

As of 2026-06-24, the guard writes an explicit status when safe cleanup is not
enough:

- `state=cleanup_ineffective`: usage stayed at or above cleanup threshold and
  did not decrease after safe cleanup. This means manual capacity review is
  required; likely active Docker/containerd data is outside the automatic policy.
- `state=cleanup_incomplete`: usage decreased but remains at or above cleanup
  threshold. This also requires manual capacity review before deleting active
  images, volumes, backups, or project data.

Verification on 2026-06-24:

- Rollback copy: `/usr/local/sbin/safe-disk-guard.rollback-20260624-211233`.
- Test run: `/` usage `93% -> 93%`.
- Status written:
  `state=cleanup_ineffective before=93% after=93% threshold=90% action=manual_capacity_review`.

## Proposed Continuous Cleanup Design

1. Keep monitor `disk_critical` at 90% for T3 escalation.
2. Add a non-mutating weekly disk audit report for:
   - `df -h /`
   - Docker image/container/volume/build-cache usage
   - `/opt/ekklesia` artifact directories
   - Ollama model list
   - snap/apt/journal cache size
3. Add an optional weekly safe cleanup with explicit environment gate:
   - `EKKLESIA_DISK_CLEANUP_CONFIRM=EKKLESIA-SAFE-CLEANUP`
   - only safe automatic cleanup commands listed above.
4. Keep Ollama model deletion and old APK/AAB retention as manual operator tasks,
   because they change rollback/build comfort.
5. Do not enable automatic volume pruning.

## Completed qwen Cleanup

`qwen2.5:14b` was removed manually on 2026-06-20 after final prechecks:

- no model loaded in `ollama ps`;
- running container env referenced only `OLLAMA_MODEL=llama3.2:3b`;
- no cron/systemd qwen job found;
- targeted project scan found no other active project using Ollama/qwen;
- `llama3.2:3b` remained installed after removal;
- monitor single run passed 17 checks with no alerts.

Result:

- `/` improved from 91% used / 6.7G free to 79% used / 16G free.
- Ollama volume improved from 11G to 1.9G.
- No service restart, deploy, Docker prune, volume deletion, or backup deletion
  was performed.

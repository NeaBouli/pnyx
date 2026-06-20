# Server Cleanup Policy — ekklesia.gr

Date: 2026-06-20
Scope: `root@135.181.254.229`, ekklesia/pnyx runtime and shared Docker host.

## Current Finding

The disk pressure is real but not caused by PostgreSQL row growth or `/opt/ekklesia`
application code.

Latest read-only measurement:

- `/`: 75G total, 64G used, 8.4G free, 89%.
- Inodes: 17% used, not a problem.
- `/opt/ekklesia`: about 1.4G.
- `/var/lib/docker/volumes`: about 14G.
- `/var/lib/containerd`: about 30G.
- Docker images: about 31G, all currently attached to running containers.
- Docker build cache: 0B at measurement time.
- Journald: about 220M.
- `/var/lib/snapd/cache`: about 2.0G.

Main ekklesia-related candidate:

- `volumes_ekklesia_ollama`: about 11G.
- Ollama models present:
  - `qwen2.5:14b`: about 9.0G, not the configured production model.
  - `llama3.2:3b`: about 2.0G, current `OLLAMA_MODEL`.
- Cross-project/runtime check:
  - Ollama is not exposed on a host port (`11434/tcp` has no host binding).
  - Only containers on `net_ekklesia` can reach the `ollama` network alias.
  - Running container env inspection found only `ekklesia-api` with
    `OLLAMA_URL=http://ollama:11434` and `OLLAMA_MODEL=llama3.2:3b`.
  - Ollama logs over the checked window showed health/tag/ps calls, no generate
    calls for `qwen2.5:14b`.
  - The manual `scripts/backfill_summary_ollama.py` no longer hardcodes qwen;
    it defaults to `OLLAMA_MODEL` or `llama3.2:3b` and accepts `--model`.

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

## Immediate Recommendation

The safest high-impact cleanup is removing `qwen2.5:14b`, because it was already
rejected for release-quality Greek analysis and the configured production model
is `llama3.2:3b`. The previous manual backfill script qwen default has been
removed, so current code has no hard qwen runtime dependency.

Do not remove it automatically. Operator should confirm after checking no current
job depends on `qwen2.5:14b`.

Expected result if removed: about 9G recovered, likely moving `/` from 89% to
about 77-78% used without touching databases or backups.

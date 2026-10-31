# Production container runtime — EKA-13 / B13

2026-10-31: **source fixed; rollout pending per-service dry run**. This change
does not deploy anything. The production observations below were supplied by the
operator; local source tests do not establish production acceptance.

| Service | Image default identity | Application write paths | Runtime contract |
|---|---|---|---|
| dashboard | `nextjs:nextjs`, uid/gid **1001:1001** | `/app/.next/cache` only, created and owned by nextjs | Standalone `node server.js`; `EXPOSE 3001` unchanged; application/static files remain root-owned and readable |
| monitor | `monitor:monitor`, uid/gid **10001:10001**, no home | None | `python monitor.py`; `PYTHONDONTWRITEBYTECODE=1`; code and installed libraries remain root-owned |
| ollama | Root, unchanged | Existing `ollama-data:/root/.ollama` | `ollama/ollama:0.21.2`, pinned to the exact running digest below |

Dashboard and monitor have no production bind mounts or volumes. The monitor's
`run_checks()` and `--once` entry point use DB/Redis/HTTP, `shutil.disk_usage("/")`
(a read), and logging's default stderr handler. There are no file opens for
writing or file log handlers. Alert state and cooldowns live in Redis. Disabling
bytecode generation also removes Python's optional cache writes. This is source
inspection; a complete read-only-container cycle remains a rollout gate.

The host cron remains:

```sh
docker exec ekklesia-monitor python3 monitor.py --once >> /var/log/ekklesia-health.log
```

`docker exec` inherits the image's default user; it needs no root shell or home.
The host shell opens the log, so the container user needs no access to
`/var/log/ekklesia-health.log`. This existing redirect captures stdout; Python
logging uses stderr. Preserve the cron command and its current logging setup.
`--once` still exits 1 when alerts remain and 0 when none remain.

The socket proxy remains byte-for-byte unchanged in production Compose: pinned
`v0.4.2@sha256:1f3a6f303320723d199d2316a3e82b2e2685d86c275d5e3deeaf182573b47476`,
private internal `docker-api` network, monitor as its only peer, no published
ports, all Docker API namespaces disabled, `POST=0`. Monitor uses TCP
`DOCKER_HOST=tcp://docker-proxy:2375`, has no socket mount, and keeps Tier 2 off.
Ollama is pinned to
`ollama/ollama@sha256:2038a264392af4d21f7f14e1568e8dd9aa0f2bd0f31d7d9a59a8cca1e9829663`;
there is no Ollama version or ownership migration. No Compose `user:` overrides
are added.

## Local gates

```sh
python3 -m unittest discover -s scripts/redesign -p 'test_prod_container_runtime.py' -v
python3 -m pytest --noconftest -q apps/api/tests/test_prod_docker_proxy_boundary.py
python3 -m unittest discover -s scripts/redesign -p 'test_*.py'
docker build -t ekklesia-dashboard:eka-b13-local -f apps/dashboard/Dockerfile.prod apps/dashboard
docker build -t ekklesia-monitor:eka-b13-local -f apps/monitor/Dockerfile apps/monitor
```

The standalone proxy file uses no API fixtures; `--noconftest` avoids loading
unrelated API database dependencies. The policy tests use PyYAML, as do the
existing proxy boundary tests. They check
final-stage users and fixed IDs, dashboard cache ownership, unchanged commands
and exposed port, absence of application mounts/user overrides, both exact
image digests, and absence of `:latest` image references. The existing proxy
tests additionally check its complete isolation and API policy.

Local results (2026-10-31): the six new policy tests passed; the existing proxy
boundary file passed all eight tests with `--noconftest`; full redesign discovery
ran 428 tests, OK with two skips. Both Docker builds exited 0. Runtime probes
confirmed dashboard uid/gid 1001, successful cache writes and root-owned,
non-writable `server.js`; monitor uid/gid 10001 and successful imports with a
read-only root filesystem, no mounts and bytecode generation disabled.
All 13 runbook shell blocks passed `bash -n`; `git diff --check` passed. The
ordinary proxy pytest invocation hit unrelated API conftest/SQLAlchemy
`async_sessionmaker` incompatibility. A full synthetic `--once` launcher was
denied Docker API access by the sandbox; full-cycle and production-env internal
network dry runs remain pending. No production service was changed.

## Future rollout preparation (operator runbook; not executed here)

Run from the approved checkout on the Docker host; stop on any failed gate.
Reconcile the candidate with
the deployed revision and record its image IDs and exact Compose project/file
chain using single-field inspect output. Retain any existing overrides in every
command below. The example uses project `docker` and the checked-in base file;
adapt the function to the recorded chain before proceeding.

The dashboard's supplied runtime port is 3001, while checked-in Compose labels
route to 3000. This batch preserves both existing settings. Confirm the actual
listener, effective `PORT`, and deployed routing override before switching; a
failed routing check blocks rollout and needs separate reconciliation.

```sh
umask 077
b13_stamp=$(date -u +%Y%m%dT%H%M%SZ)
export B13_RELEASE="/opt/ekklesia/releases/eka-b13-$b13_stamp"
mkdir -m 700 "$B13_RELEASE"
b13_compose() {
  docker compose -p docker --env-file /opt/ekklesia/.env.production \
    -f infra/docker/docker-compose.prod.yml "$@"
}
git rev-parse HEAD > "$B13_RELEASE/source-revision.txt"
for b13_service in dashboard monitor ollama; do
  b13_old_id=$(docker inspect --format '{{.Image}}' "ekklesia-$b13_service")
  docker tag "$b13_old_id" "ekklesia-$b13_service:rollback-b13-$b13_stamp"
  printf '%s %s\n' "$b13_service" "$b13_old_id" >> "$B13_RELEASE/old-images.txt"
done
cat > "$B13_RELEASE/compose.release.yml" <<EOF
services:
  dashboard:
    image: ekklesia-dashboard:eka-b13-$b13_stamp
  monitor:
    image: ekklesia-monitor:eka-b13-$b13_stamp
EOF
cat > "$B13_RELEASE/compose.rollback.yml" <<EOF
services:
  dashboard:
    image: ekklesia-dashboard:rollback-b13-$b13_stamp
  monitor:
    image: ekklesia-monitor:rollback-b13-$b13_stamp
  ollama:
    image: ekklesia-ollama:rollback-b13-$b13_stamp
EOF
docker build -t "ekklesia-dashboard:eka-b13-$b13_stamp" -f apps/dashboard/Dockerfile.prod apps/dashboard
docker build -t "ekklesia-monitor:eka-b13-$b13_stamp" -f apps/monitor/Dockerfile apps/monitor
b13_ollama_image=ollama/ollama@sha256:2038a264392af4d21f7f14e1568e8dd9aa0f2bd0f31d7d9a59a8cca1e9829663
docker pull "$b13_ollama_image"
```

Check that the old Ollama image's RepoDigests contains this exact digest; stop
if it differs. There is no Ollama build: pulling this digest retrieves the
already verified 0.21.2 artifact. Retain rollback tags; do not prune images.

Prepare private per-service env files from **rendered production Compose**,
including the recorded override chain. Passing only `.env.production` would
miss service mappings such as `DASHBOARD_SECRET` → `NEXTAUTH_SECRET`. Do not
print rendered config or credentials. Compare the effective runtime settings
with the live containers privately before continuing.

```sh
b13_compose config --format json | python3 -c '
import json, os
from pathlib import Path
import sys
services = json.load(sys.stdin)["services"]
release = Path(os.environ["B13_RELEASE"])
for name in ("dashboard", "monitor", "ollama"):
    lines = []
    for key, value in (services[name].get("environment") or {}).items():
        if value is None:
            continue
        value = str(value)
        if "\n" in value or "\r" in value:
            raise SystemExit("Multiline environment needs a private equivalent launcher")
        lines.append(key + "=" + value + "\n")
    target = release / (name + ".env")
    target.write_text("".join(lines))
    target.chmod(0o600)
'
b13_dry_network="eka-b13-dry-$b13_stamp"
docker network create --internal "$b13_dry_network"
```

Dry runs have unique container names, no published ports, no Traefik labels,
and only this new internal network. Never connect them to `net_ekklesia` or the
live `docker-api` network. Preserve production configuration except the listed
fixture endpoint and side-effect overrides. No commands below have been run
against production as part of this source change.

## Dashboard: dry run, health, switch, rollback

```sh
docker run -d --name "b13-dashboard-dry-$b13_stamp" \
  --network "$b13_dry_network" --env-file "$B13_RELEASE/dashboard.env" \
  "ekklesia-dashboard:eka-b13-$b13_stamp"
docker exec "b13-dashboard-dry-$b13_stamp" node -e '
const fs = require("fs");
if (process.getuid() !== 1001 || process.getgid() !== 1001) process.exit(1);
const cache = "/app/.next/cache";
if (fs.statSync(cache).uid !== 1001 || fs.statSync(cache).gid !== 1001) process.exit(1);
fs.writeFileSync(cache + "/b13-probe", "ok"); fs.unlinkSync(cache + "/b13-probe");
try { fs.accessSync("/app/server.js", fs.constants.W_OK); process.exit(1); }
catch (err) { if (err.code !== "EACCES") throw err; }
fetch("http://" + (process.env.HOSTNAME || "127.0.0.1") + ":" + (process.env.PORT || "3000") + "/login")
  .then(r => { if (r.status !== 200) process.exit(1); })
  .catch(() => process.exit(1));'
```

Wait for readiness before the probe. Also request a representative static
asset and a configured image-optimisation/ISR URL if used; review private logs
for permissions errors and `docker diff` for writes outside `.next/cache`.
OAuth and external API calls cannot succeed on this isolated network; test
their configured public flows after switching. Dashboard has no Compose
healthcheck; login HTTP response and cache writes are explicit acceptance gates.

After all dashboard gates pass, switch **dashboard only**:

```sh
b13_compose -f "$B13_RELEASE/compose.release.yml" up -d --no-deps --no-build --pull never dashboard
docker exec ekklesia-dashboard id
```

Verify uid/gid 1001, the candidate image ID, stable running state, the existing
public login/authorised overview flow, routing/listener agreement, and no
permission errors. On failure, restore only dashboard:

```sh
b13_compose -f "$B13_RELEASE/compose.rollback.yml" up -d --no-deps --no-build --pull never dashboard
```

## Monitor: dry run, health, switch, rollback

First provide disposable **DB, Redis and API fixtures** with aliases `db`,
`redis`, `api` on the new internal network only. The database must include the
monitor role/views and representative synthetic rows; an empty PostgreSQL
database cannot exercise the cycle. Use a separately prepared fixture or
isolated restored copy, never live DB/Redis mounts or endpoints. Define
`B13_FIXTURE_MONITOR_DATABASE_URL` as that fixture's PostgreSQL URL. The API
fixture must serve the read endpoints used by the monitor. These fixture
prerequisites are required before running `--once`.

```sh
docker run -d --name "b13-monitor-dry-$b13_stamp" --read-only \
  --network "$b13_dry_network" --env-file "$B13_RELEASE/monitor.env" \
  --env DATABASE_URL="$B13_FIXTURE_MONITOR_DATABASE_URL" \
  --env MONITOR_DATABASE_URL="$B13_FIXTURE_MONITOR_DATABASE_URL" \
  --env REDIS_URL=redis://redis:6379 --env API_URL=http://api:8000 \
  --env ADMIN_KEY= --env TELEGRAM_BOT_TOKEN= --env TELEGRAM_ADMIN_CHAT_ID= \
  --env AUTO_RECOVERY_T2=false --env MONITOR_STARTUP_GRACE_SECONDS=0 \
  "ekklesia-monitor:eka-b13-$b13_stamp"
docker exec "b13-monitor-dry-$b13_stamp" python3 -c \
  'import os; assert (os.getuid(), os.getgid()) == (10001, 10001)'
b13_once_status=0
docker exec "b13-monitor-dry-$b13_stamp" python3 monitor.py --once \
  > "$B13_RELEASE/monitor-once.log" 2>&1 || b13_once_status=$?
test "$b13_once_status" -le 1
rg -q 'All checks passed|All alerts were repaired|ALERTS:' "$B13_RELEASE/monitor-once.log"
if rg -q 'Traceback|PermissionError|Read-only file system' "$B13_RELEASE/monitor-once.log"; then
  exit 1
fi
docker diff "b13-monitor-dry-$b13_stamp"
```

No writable mount or tmpfs is supplied. Require a complete cycle, no filesystem
changes, and no permission/dependency exceptions. Exit 1 is acceptable in this
isolated dry run **only** after reviewing every alert as an expected fixture or
blocked-public-egress condition; it is not a healthy-production result. The
empty admin/Telegram credentials suppress recovery POSTs and notifications;
Tier 2 stays off and the live socket proxy is unreachable. No `--user` option
is used, so this tests the default user inherited by host cron.

Only after the monitor dry run passes:

```sh
b13_compose -f "$B13_RELEASE/compose.release.yml" up -d --no-deps --no-build --pull never monitor
docker exec ekklesia-monitor id
docker exec ekklesia-monitor python3 monitor.py --once
```

Verify uid/gid 10001, candidate image ID, daemon remains running, and a complete
production cycle after startup grace. Monitor has no Compose healthcheck:
running state alone is insufficient. Review actual alerts and cron's next
host-side run; that run can perform the normal configured recovery/notification
actions. Keep the proxy isolation and Tier 2 setting unchanged. On failure:

```sh
b13_compose -f "$B13_RELEASE/compose.rollback.yml" up -d --no-deps --no-build --pull never monitor
```

## Ollama: dry run, health, switch, rollback

```sh
docker volume create "eka-b13-ollama-dry-$b13_stamp"
docker run -d --name "b13-ollama-dry-$b13_stamp" \
  --network "$b13_dry_network" --env-file "$B13_RELEASE/ollama.env" \
  --memory 2500m --volume "eka-b13-ollama-dry-$b13_stamp:/root/.ollama" \
  "$b13_ollama_image"
docker exec "b13-ollama-dry-$b13_stamp" ollama --version
docker exec "b13-ollama-dry-$b13_stamp" ollama list
```

Wait for the server to start. Require version 0.21.2, image RepoDigests matching
the pinned digest, and successful `ollama list` (the production health command).
The empty disposable model volume tests startup and ownership, not model
availability; never mount the live model volume in this dry run.

```sh
b13_compose --profile ollama up -d --no-deps --no-build --pull never ollama
docker inspect --format '{{.State.Health.Status}}' ekklesia-ollama
docker exec ekklesia-ollama ollama list
```

Switch Ollama only after its own dry run. Require `healthy`, the same verified
digest/version, and the pre-existing production models still listed. Root and
the production model volume remain unchanged. On failure:

```sh
b13_compose -f "$B13_RELEASE/compose.rollback.yml" --profile ollama \
  up -d --no-deps --no-build --pull never ollama
```

After each service, record old/new image IDs, uid/gid where applicable, UTC
time, dry-run and live-health evidence, and rollback outcome if used. Recheck
health after rollback. Release overrides must be retained in the deployed
Compose chain. Stop/remove only the named disposable containers, fixtures,
network and model volume after review; retain rollback tags and private logs.
Do not run a stack-wide `up`, `down`, volume deletion or image prune.
